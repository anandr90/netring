#!/usr/bin/env python3
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import redis
import yaml
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NetringRegistry:
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.redis_client = redis.Redis(
            host=self.config['registry']['redis']['host'],
            port=self.config['registry']['redis']['port'],
            db=self.config['registry']['redis']['db'],
            password=self.config['registry']['redis']['password'],
            decode_responses=True
        )
        
        self.member_ttl = self.config['registry']['member_ttl']
        self.cleanup_interval = self.config['registry']['cleanup_interval']
        
    async def register_member(self, request):
        """Register a new ring member"""
        try:
            data = await request.json()
            member_id = data.get('instance_id', str(uuid.uuid4()))
            
            member_info = {
                'instance_id': member_id,
                'location': data['location'],
                'ip': data['ip'],
                'port': data['port'],
                'last_seen': int(time.time()),
                'registered_at': int(time.time())
            }
            
            # Store in Redis with TTL
            key = f"netring:member:{member_id}"
            self.redis_client.hset(key, mapping=member_info)
            self.redis_client.expire(key, self.member_ttl)
            
            # Add to active members set
            self.redis_client.sadd("netring:active_members", member_id)
            
            logger.info(f"Registered member {member_id} from {data['location']}")
            return web.json_response({'instance_id': member_id, 'status': 'registered'})
            
        except Exception as e:
            logger.error(f"Failed to register member: {e}")
            return web.json_response({'error': str(e)}, status=400)
    
    async def heartbeat(self, request):
        """Update member heartbeat"""
        try:
            data = await request.json()
            member_id = data['instance_id']
            
            key = f"netring:member:{member_id}"
            if self.redis_client.exists(key):
                self.redis_client.hset(key, 'last_seen', int(time.time()))
                self.redis_client.expire(key, self.member_ttl)
                return web.json_response({'status': 'ok'})
            else:
                return web.json_response({'error': 'member not found'}, status=404)
                
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
            return web.json_response({'error': str(e)}, status=400)
    
    async def get_members(self, request):
        """Get list of all active members"""
        try:
            members = []
            active_member_ids = self.redis_client.smembers("netring:active_members")
            
            for member_id in active_member_ids:
                key = f"netring:member:{member_id}"
                member_data = self.redis_client.hgetall(key)
                
                if member_data:
                    members.append({
                        'instance_id': member_id,
                        'location': member_data['location'],
                        'ip': member_data['ip'],
                        'port': int(member_data['port']),
                        'last_seen': int(member_data['last_seen']),
                        'registered_at': int(member_data['registered_at'])
                    })
                else:
                    # Remove stale member from active set
                    self.redis_client.srem("netring:active_members", member_id)
            
            return web.json_response({'members': members})
            
        except Exception as e:
            logger.error(f"Failed to get members: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def health_check(self, request):
        """Health check endpoint"""
        try:
            self.redis_client.ping()
            return web.json_response({'status': 'healthy', 'timestamp': time.time()})
        except Exception as e:
            return web.json_response({'status': 'unhealthy', 'error': str(e)}, status=503)
    
    async def cleanup_dead_members(self):
        """Background task to cleanup dead members"""
        while True:
            try:
                current_time = int(time.time())
                active_members = self.redis_client.smembers("netring:active_members")
                
                for member_id in active_members:
                    key = f"netring:member:{member_id}"
                    member_data = self.redis_client.hgetall(key)
                    
                    if not member_data:
                        self.redis_client.srem("netring:active_members", member_id)
                        logger.info(f"Removed stale member {member_id}")
                        continue
                    
                    last_seen = int(member_data.get('last_seen', 0))
                    if current_time - last_seen > self.member_ttl:
                        self.redis_client.delete(key)
                        self.redis_client.srem("netring:active_members", member_id)
                        logger.info(f"Cleaned up dead member {member_id}")
                
                await asyncio.sleep(self.cleanup_interval)
                
            except Exception as e:
                logger.error(f"Cleanup task failed: {e}")
                await asyncio.sleep(self.cleanup_interval)


async def init_app(config_path: str):
    registry = NetringRegistry(config_path)
    
    app = web.Application()
    
    # API routes
    app.router.add_post('/register', registry.register_member)
    app.router.add_post('/heartbeat', registry.heartbeat)
    app.router.add_get('/members', registry.get_members)
    app.router.add_get('/health', registry.health_check)
    
    # Start cleanup task
    asyncio.create_task(registry.cleanup_dead_members())
    
    return app


if __name__ == '__main__':
    import sys
    
    config_path = sys.argv[1] if len(sys.argv) > 1 else '../config/registry.yaml'
    
    app = asyncio.run(init_app(config_path))
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    web.run_app(
        app,
        host=config['registry']['server']['host'],
        port=config['registry']['server']['port']
    )