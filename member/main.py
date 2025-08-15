#!/usr/bin/env python3
import asyncio
import json
import logging
import socket
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp
import yaml
from aiohttp import web
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NetringMember:
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.location = self.config['member']['location']
        self.instance_id = self.config['member']['instance_id'] or str(uuid.uuid4())
        
        # Registry configuration
        self.registry_url = self.config['member']['registry']['url']
        
        # Timing intervals
        self.poll_interval = self.config['member']['intervals']['poll_interval']
        self.check_interval = self.config['member']['intervals']['check_interval']
        self.heartbeat_interval = self.config['member']['intervals']['heartbeat_interval']
        
        # Check configuration
        self.tcp_timeout = self.config['member']['checks']['tcp_timeout']
        self.http_timeout = self.config['member']['checks']['http_timeout']
        self.http_endpoints = self.config['member']['checks']['http_endpoints']
        
        # Local server configuration
        self.server_host = self.config['member']['server']['host']
        self.server_port = self.config['member']['server']['port']
        
        # Get local IP
        self.local_ip = self._get_local_ip()
        
        # Registry of other members
        self.members: Dict[str, Dict] = {}
        
        # Prometheus metrics
        self.connectivity_tcp = Gauge(
            'netring_connectivity_tcp',
            'TCP connectivity status between ring members',
            ['source_location', 'source_instance', 'target_location', 'target_instance', 'target_ip']
        )
        
        self.connectivity_http = Gauge(
            'netring_connectivity_http',
            'HTTP connectivity status between ring members',
            ['source_location', 'source_instance', 'target_location', 'target_instance', 'target_ip', 'endpoint']
        )
        
        self.check_duration = Histogram(
            'netring_check_duration_seconds',
            'Duration of connectivity checks',
            ['check_type', 'target_location', 'target_instance']
        )
        
        self.ring_members_total = Gauge(
            'netring_members_total',
            'Total number of ring members discovered'
        )
        
        self.member_last_seen = Gauge(
            'netring_member_last_seen_timestamp',
            'Timestamp when member was last seen',
            ['location', 'instance_id']
        )
        
        # HTTP session for reuse
        self.session = None
        
    def _get_local_ip(self) -> str:
        """Get the local IP address"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
    
    async def _init_session(self):
        """Initialize HTTP session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.http_timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def register_with_registry(self):
        """Register this member with the central registry"""
        await self._init_session()
        
        registration_data = {
            'instance_id': self.instance_id,
            'location': self.location,
            'ip': self.local_ip,
            'port': self.server_port
        }
        
        try:
            async with self.session.post(
                f"{self.registry_url}/register",
                json=registration_data
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.instance_id = result['instance_id']
                    logger.info(f"Successfully registered as {self.instance_id}")
                    return True
                else:
                    logger.error(f"Registration failed: {resp.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return False
    
    async def send_heartbeat(self):
        """Send heartbeat to registry"""
        if not self.session:
            return False
            
        heartbeat_data = {
            'instance_id': self.instance_id
        }
        
        try:
            async with self.session.post(
                f"{self.registry_url}/heartbeat",
                json=heartbeat_data
            ) as resp:
                if resp.status == 200:
                    logger.debug("Heartbeat sent successfully")
                    return True
                else:
                    logger.error(f"Heartbeat failed: {resp.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            return False
    
    async def poll_members(self):
        """Poll registry for current members"""
        if not self.session:
            return False
            
        try:
            async with self.session.get(f"{self.registry_url}/members") as resp:
                if resp.status == 200:
                    result = await resp.json()
                    new_members = {}
                    
                    for member in result['members']:
                        if member['instance_id'] != self.instance_id:
                            new_members[member['instance_id']] = member
                    
                    self.members = new_members
                    self.ring_members_total.set(len(self.members))
                    
                    # Update last seen metrics
                    for member in self.members.values():
                        self.member_last_seen.labels(
                            location=member['location'],
                            instance_id=member['instance_id']
                        ).set(member['last_seen'])
                    
                    logger.debug(f"Discovered {len(self.members)} ring members")
                    return True
                else:
                    logger.error(f"Failed to poll members: {resp.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Member polling error: {e}")
            return False
    
    async def check_tcp_connectivity(self, target_ip: str, target_port: int) -> bool:
        """Check TCP connectivity to a target"""
        try:
            future = asyncio.open_connection(target_ip, target_port)
            reader, writer = await asyncio.wait_for(future, timeout=self.tcp_timeout)
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False
    
    async def check_http_connectivity(self, target_ip: str, target_port: int, endpoint: str) -> bool:
        """Check HTTP connectivity to a target endpoint"""
        if not self.session:
            return False
            
        url = f"http://{target_ip}:{target_port}{endpoint}"
        try:
            async with self.session.get(url) as resp:
                return resp.status < 500
        except Exception:
            return False
    
    async def run_connectivity_checks(self):
        """Run connectivity checks against all known members"""
        for member_id, member in self.members.items():
            target_ip = member['ip']
            target_port = member['port']
            target_location = member['location']
            
            # TCP connectivity check
            start_time = time.time()
            tcp_result = await self.check_tcp_connectivity(target_ip, target_port)
            tcp_duration = time.time() - start_time
            
            self.connectivity_tcp.labels(
                source_location=self.location,
                source_instance=self.instance_id,
                target_location=target_location,
                target_instance=member_id,
                target_ip=target_ip
            ).set(1 if tcp_result else 0)
            
            self.check_duration.labels(
                check_type='tcp',
                target_location=target_location,
                target_instance=member_id
            ).observe(tcp_duration)
            
            # HTTP connectivity checks
            for endpoint in self.http_endpoints:
                start_time = time.time()
                http_result = await self.check_http_connectivity(target_ip, target_port, endpoint)
                http_duration = time.time() - start_time
                
                self.connectivity_http.labels(
                    source_location=self.location,
                    source_instance=self.instance_id,
                    target_location=target_location,
                    target_instance=member_id,
                    target_ip=target_ip,
                    endpoint=endpoint
                ).set(1 if http_result else 0)
                
                self.check_duration.labels(
                    check_type='http',
                    target_location=target_location,
                    target_instance=member_id
                ).observe(http_duration)
        
        logger.debug(f"Completed connectivity checks for {len(self.members)} members")
    
    async def health_check(self, request):
        """Health check endpoint"""
        return web.json_response({
            'status': 'healthy',
            'instance_id': self.instance_id,
            'location': self.location,
            'members_count': len(self.members),
            'timestamp': time.time()
        })
    
    async def metrics_endpoint(self, request):
        """Prometheus metrics endpoint"""
        metrics_data = generate_latest()
        return web.Response(
            body=metrics_data,
            headers={'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'}
        )
    
    async def heartbeat_task(self):
        """Background task for sending heartbeats"""
        while True:
            await self.send_heartbeat()
            await asyncio.sleep(self.heartbeat_interval)
    
    async def member_polling_task(self):
        """Background task for polling member list"""
        while True:
            await self.poll_members()
            await asyncio.sleep(self.poll_interval)
    
    async def connectivity_check_task(self):
        """Background task for running connectivity checks"""
        while True:
            if self.members:
                await self.run_connectivity_checks()
            await asyncio.sleep(self.check_interval)
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()


async def init_app(config_path: str):
    member = NetringMember(config_path)
    
    # Register with registry
    if not await member.register_with_registry():
        logger.error("Failed to register with registry")
        return None
    
    app = web.Application()
    
    # API routes
    app.router.add_get('/health', member.health_check)
    app.router.add_get('/metrics', member.metrics_endpoint)
    
    # Start background tasks
    asyncio.create_task(member.heartbeat_task())
    asyncio.create_task(member.member_polling_task())
    asyncio.create_task(member.connectivity_check_task())
    
    # Cleanup on shutdown
    app.on_cleanup.append(lambda app: member.cleanup())
    
    return app, member


if __name__ == '__main__':
    import sys
    
    config_path = sys.argv[1] if len(sys.argv) > 1 else '../config/member.yaml'
    
    async def main():
        result = await init_app(config_path)
        if result is None:
            sys.exit(1)
        
        app, member = result
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(
            runner,
            host=member.server_host,
            port=member.server_port
        )
        
        logger.info(f"Starting netring member {member.instance_id} at {member.location}")
        logger.info(f"Listening on {member.server_host}:{member.server_port}")
        
        await site.start()
        
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            await runner.cleanup()
    
    asyncio.run(main())