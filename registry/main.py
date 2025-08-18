#!/usr/bin/env python3
import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import redis
import yaml
from aiohttp import web

# Import network topology analyzer
try:
    from .network_topology import NetworkTopologyAnalyzer
    from .version import get_cached_version
except ImportError:
    # Handle case when running as script (not as module)
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    from network_topology import NetworkTopologyAnalyzer
    from version import get_cached_version

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
        
        # Load expected members configuration
        self.expected_members_config = None
        self.missing_detection_enabled = False
        self.missing_check_interval = 60
        
        if 'expected_members' in self.config['registry']:
            expected_config = self.config['registry']['expected_members']
            self.missing_detection_enabled = expected_config.get('enable_missing_detection', False)
            self.missing_check_interval = expected_config.get('missing_check_interval', 60)
            
            if self.missing_detection_enabled:
                config_file = expected_config.get('config_file', 'config/expected-members.yaml')
                try:
                    with open(config_file, 'r') as f:
                        self.expected_members_config = yaml.safe_load(f)
                    logger.info(f"Loaded expected members configuration from {config_file}")
                except Exception as e:
                    logger.error(f"Failed to load expected members config: {e}")
                    self.missing_detection_enabled = False
        
        # Initialize network topology analyzer
        self.topology_analyzer = NetworkTopologyAnalyzer()
        
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
    
    async def deregister_member(self, request):
        """Deregister a member (graceful shutdown)"""
        try:
            data = await request.json()
            member_id = data['instance_id']
            
            key = f"netring:member:{member_id}"
            
            # Get member info for logging and tracking
            member_data = self.redis_client.hgetall(key)
            location = member_data.get('location', 'unknown') if member_data else 'unknown'
            
            if member_data:
                # Create deregistered entry with original info + deregister timestamp
                deregistered_info = member_data.copy()
                deregistered_info['status'] = 'deregistered'
                deregistered_info['deregistered_at'] = str(int(time.time()))
                
                # Store in deregistered members (with TTL for cleanup)
                deregistered_key = f"netring:deregistered:{member_id}"
                self.redis_client.hset(deregistered_key, mapping=deregistered_info)
                self.redis_client.expire(deregistered_key, 3600)  # Keep for 1 hour
                
                # Add to deregistered members set
                self.redis_client.sadd("netring:deregistered_members", member_id)
                self.redis_client.expire("netring:deregistered_members", 3600)
            
            # Remove from active members
            self.redis_client.delete(key)
            self.redis_client.srem("netring:active_members", member_id)
            
            logger.info(f"Deregistered member {member_id} from {location}")
            return web.json_response({'status': 'deregistered'})
            
        except Exception as e:
            logger.error(f"Failed to deregister member: {e}")
            return web.json_response({'error': str(e)}, status=400)
    
    async def get_members(self, request):
        """Get list of all active and recently deregistered members"""
        try:
            members = []
            
            # Get active members
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
                        'registered_at': int(member_data['registered_at']),
                        'status': 'active'
                    })
                else:
                    # Remove stale member from active set
                    self.redis_client.srem("netring:active_members", member_id)
            
            # Get deregistered members (for UI display)
            deregistered_member_ids = self.redis_client.smembers("netring:deregistered_members")
            
            for member_id in deregistered_member_ids:
                key = f"netring:deregistered:{member_id}"
                member_data = self.redis_client.hgetall(key)
                
                if member_data:
                    members.append({
                        'instance_id': member_id,
                        'location': member_data['location'],
                        'ip': member_data['ip'],
                        'port': int(member_data['port']),
                        'last_seen': int(member_data['last_seen']),
                        'registered_at': int(member_data['registered_at']),
                        'deregistered_at': int(member_data['deregistered_at']),
                        'status': 'deregistered'
                    })
                else:
                    # Remove stale deregistered member
                    self.redis_client.srem("netring:deregistered_members", member_id)
            
            return web.json_response({'members': members})
            
        except Exception as e:
            logger.error(f"Failed to get members: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    def get_missing_members_analysis(self):
        """Analyze which expected members are missing"""
        if not self.missing_detection_enabled or not self.expected_members_config:
            return {
                'enabled': False,
                'locations': {},
                'alerts': []
            }
        
        try:
            # Get current active members by location
            active_member_ids = self.redis_client.smembers("netring:active_members")
            current_members_by_location = {}
            
            for member_id in active_member_ids:
                key = f"netring:member:{member_id}"
                member_data = self.redis_client.hgetall(key)
                
                if member_data:
                    location = member_data['location']
                    if location not in current_members_by_location:
                        current_members_by_location[location] = []
                    
                    current_members_by_location[location].append({
                        'instance_id': member_id,
                        'last_seen': int(member_data['last_seen']),
                        'ip': member_data['ip']
                    })
            
            # Analyze each expected location
            expected_locations = self.expected_members_config['expected_members']['locations']
            current_time = int(time.time())
            location_analysis = {}
            alerts = []
            
            for location, expected_config in expected_locations.items():
                expected_count = expected_config['expected_count']
                criticality = expected_config['criticality']
                grace_period = expected_config['grace_period']
                description = expected_config.get('description', location)
                
                # Get current members at this location
                current_members = current_members_by_location.get(location, [])
                actual_count = len(current_members)
                
                # Determine status
                missing_count = max(0, expected_count - actual_count)
                status = 'healthy'
                
                if missing_count > 0:
                    if expected_count > 0:  # Only alert if we expect members
                        status = 'missing_members'
                        
                        # Check if this should trigger an alert based on criticality
                        if criticality == 'high':
                            alerts.append({
                                'level': 'error',
                                'message': f"High criticality location '{location}' missing {missing_count} member(s)",
                                'location': location,
                                'missing_count': missing_count,
                                'criticality': criticality
                            })
                        elif criticality == 'medium' and missing_count >= 2:
                            alerts.append({
                                'level': 'warning', 
                                'message': f"Medium criticality location '{location}' missing {missing_count} member(s)",
                                'location': location,
                                'missing_count': missing_count,
                                'criticality': criticality
                            })
                elif actual_count > expected_count:
                    status = 'extra_members'
                
                location_analysis[location] = {
                    'expected_count': expected_count,
                    'actual_count': actual_count,
                    'missing_count': missing_count,
                    'status': status,
                    'criticality': criticality,
                    'grace_period': grace_period,
                    'description': description,
                    'current_members': current_members
                }
            
            # Check for unexpected locations (members in locations not in config)
            for location in current_members_by_location:
                if location not in expected_locations:
                    members = current_members_by_location[location]
                    location_analysis[location] = {
                        'expected_count': 0,
                        'actual_count': len(members),
                        'missing_count': 0,
                        'status': 'unexpected_location',
                        'criticality': 'unknown',
                        'grace_period': 0,
                        'description': f'Unexpected location: {location}',
                        'current_members': members
                    }
            
            # Global alerts
            total_missing = sum(loc['missing_count'] for loc in location_analysis.values())
            critical_missing = sum(1 for loc in location_analysis.values() 
                                 if loc['criticality'] == 'high' and loc['missing_count'] > 0)
            
            settings = self.expected_members_config['expected_members']['settings']
            alert_settings = settings.get('alerts', {})
            
            if critical_missing >= alert_settings.get('critical_missing_threshold', 1):
                alerts.append({
                    'level': 'error',
                    'message': f"Critical: {critical_missing} high-priority location(s) missing members",
                    'critical_locations': critical_missing,
                    'total_missing': total_missing
                })
            elif total_missing >= alert_settings.get('total_missing_threshold', 3):
                alerts.append({
                    'level': 'warning',
                    'message': f"Warning: {total_missing} total members missing across all locations",
                    'total_missing': total_missing
                })
            
            return {
                'enabled': True,
                'timestamp': current_time,
                'locations': location_analysis,
                'alerts': alerts,
                'summary': {
                    'total_expected_locations': len(expected_locations),
                    'total_missing_members': total_missing,
                    'critical_locations_missing': critical_missing,
                    'unexpected_locations': sum(1 for loc in location_analysis.values() 
                                              if loc['status'] == 'unexpected_location')
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze missing members: {e}")
            return {
                'enabled': True,
                'error': str(e),
                'locations': {},
                'alerts': [{'level': 'error', 'message': f'Missing members analysis failed: {e}'}]
            }
    
    async def get_members_with_analysis(self, request):
        """Get members list with missing members analysis"""
        try:
            # Get members data directly (not as response object)
            members = []
            
            # Get active members
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
                        'registered_at': int(member_data['registered_at']),
                        'status': 'active'
                    })
                else:
                    # Remove stale member from active set
                    self.redis_client.srem("netring:active_members", member_id)
            
            # Get deregistered members (for UI display)
            deregistered_member_ids = self.redis_client.smembers("netring:deregistered_members")
            
            for member_id in deregistered_member_ids:
                key = f"netring:deregistered:{member_id}"
                member_data = self.redis_client.hgetall(key)
                
                if member_data:
                    members.append({
                        'instance_id': member_id,
                        'location': member_data['location'],
                        'ip': member_data['ip'],
                        'port': int(member_data['port']),
                        'last_seen': int(member_data['last_seen']),
                        'registered_at': int(member_data['registered_at']),
                        'deregistered_at': int(member_data['deregistered_at']),
                        'status': 'deregistered'
                    })
                else:
                    # Remove stale deregistered member
                    self.redis_client.srem("netring:deregistered_members", member_id)
            
            # Add missing members analysis
            missing_analysis = self.get_missing_members_analysis()
            
            # Combine the data
            response_data = {
                'members': members,
                'missing_analysis': missing_analysis,
                'timestamp': int(time.time())
            }
            
            return web.json_response(response_data)
            
        except Exception as e:
            logger.error(f"Failed to get members with analysis: {e}", exc_info=True)
            return web.json_response({'error': str(e)}, status=500)
    
    async def health_check(self, request):
        """Health check endpoint"""
        try:
            self.redis_client.ping()
            return web.json_response({
                'status': 'healthy', 
                'version': get_cached_version(),
                'component': 'registry',
                'timestamp': time.time()
            })
        except Exception as e:
            return web.json_response({
                'status': 'unhealthy', 
                'version': get_cached_version(),
                'component': 'registry',
                'error': str(e), 
                'timestamp': time.time()
            }, status=503)
    
    async def clear_redis(self, request):
        """Clear all Redis data - useful for development/testing"""
        try:
            # Get count before clearing
            keys = self.redis_client.keys("netring:*")
            count = len(keys)
            
            # Clear all netring-related keys
            if count > 0:
                self.redis_client.delete(*keys)
            
            # Clear topology analyzer data as well
            self.topology_analyzer.clear_topology()
            
            logger.info(f"Cleared {count} Redis keys and topology data")
            return web.json_response({
                'status': 'cleared', 
                'keys_deleted': count,
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"Failed to clear Redis: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def report_metrics(self, request):
        """Accept metrics from members and store them in Redis"""
        try:
            data = await request.json()
            member_id = data['instance_id']
            metrics_data = data['metrics']
            
            # Store metrics in Redis with TTL
            metrics_key = f"netring:metrics:{member_id}"
            self.redis_client.hset(metrics_key, mapping={
                'metrics_data': json.dumps(metrics_data),
                'reported_at': int(time.time())
            })
            self.redis_client.expire(metrics_key, 300)  # 5 minutes TTL
            
            # Add to metrics reporting set
            self.redis_client.sadd("netring:reporting_members", member_id)
            self.redis_client.expire("netring:reporting_members", 300)
            
            # Update topology analyzer with new metrics data
            await self._update_topology_from_metrics(member_id, metrics_data)
            
            logger.debug(f"Received metrics from member {member_id}")
            return web.json_response({'status': 'ok'})
            
        except Exception as e:
            logger.error(f"Failed to report metrics: {e}")
            return web.json_response({'error': str(e)}, status=400)

    async def _update_topology_from_metrics(self, member_id: str, metrics_data: Dict):
        """Extract topology data from metrics and update topology analyzer"""
        try:
            # Get member information
            member_key = f"netring:member:{member_id}"
            member_info = self.redis_client.hgetall(member_key)
            
            if not member_info:
                logger.debug(f"No member info found for {member_id}")
                return
            
            source_location = member_info.get('location', 'unknown')
            
            # Extract detailed traceroute data (preferred) or fallback to aggregated data
            detailed_traceroute_data = metrics_data.get('detailed_traceroute_data', {})
            traceroute_tests = metrics_data.get('traceroute_tests', {})
            bandwidth_tests = metrics_data.get('bandwidth_tests', {})
            
            # Process detailed traceroute data first (contains real hop IPs)
            for target_key, detailed_data in detailed_traceroute_data.items():
                target_location = detailed_data.get('target_location', 'unknown')
                
                if target_location == 'unknown' or target_location == source_location:
                    continue
                
                # Get bandwidth data for this target
                bandwidth_mbps = None
                if target_key in bandwidth_tests:
                    bandwidth_mbps = bandwidth_tests[target_key].get('bandwidth_mbps')
                
                # Use real hop data from detailed traceroute
                hops = detailed_data.get('hops', [])
                
                # Add to topology analyzer
                self.topology_analyzer.add_traceroute_data(
                    source_location=source_location,
                    target_location=target_location,
                    hops=hops,
                    bandwidth_mbps=bandwidth_mbps
                )
                
                logger.debug(f"Updated topology with detailed data: {source_location} -> {target_location} "
                           f"(hops: {len(hops)}, real hop IPs)")
            
            # Process remaining traceroute tests that don't have detailed data (fallback)
            for target_key, traceroute_data in traceroute_tests.items():
                # Skip if we already processed this with detailed data
                if target_key in detailed_traceroute_data:
                    continue
                    
                target_location = traceroute_data.get('labels', {}).get('target_location', 'unknown')
                
                if target_location == 'unknown' or target_location == source_location:
                    continue
                
                # Get bandwidth data for this target
                bandwidth_mbps = None
                if target_key in bandwidth_tests:
                    bandwidth_mbps = bandwidth_tests[target_key].get('bandwidth_mbps')
                
                # Fallback to synthetic hop data from aggregated metrics
                total_hops = int(traceroute_data.get('total_hops', 0))
                max_hop_latency = float(traceroute_data.get('max_hop_latency_ms', 0))
                
                hops = self._create_synthetic_hops(total_hops, max_hop_latency, target_location)
                
                # Add to topology analyzer
                self.topology_analyzer.add_traceroute_data(
                    source_location=source_location,
                    target_location=target_location,
                    hops=hops,
                    bandwidth_mbps=bandwidth_mbps
                )
                
                logger.debug(f"Updated topology with synthetic data: {source_location} -> {target_location} "
                           f"(hops: {total_hops}, max_latency: {max_hop_latency}ms)")
                
        except Exception as e:
            logger.error(f"Failed to update topology from metrics: {e}")
    
    def _create_synthetic_hops(self, total_hops: int, max_hop_latency: float, target_location: str) -> List[Dict]:
        """Create synthetic hop data from aggregated metrics"""
        if total_hops <= 0:
            return []
        
        hops = []
        # Distribute latency across hops, with max latency somewhere in the middle
        max_hop_position = max(1, total_hops // 2)  # Put max latency in middle
        
        for i in range(total_hops):
            if i == max_hop_position - 1:  # 0-indexed
                latency = max_hop_latency
            else:
                # Distribute remaining latency across other hops
                remaining_latency = max(0, max_hop_latency - 20)  # Reserve 20ms for max hop
                latency = remaining_latency / max(1, total_hops - 1) if total_hops > 1 else 5
                latency = max(1, latency)  # Minimum 1ms per hop
            
            hops.append({
                'hop': i + 1,
                'ip': f"hop_{target_location}_{i+1}",  # Synthetic IP
                'latency_ms': round(latency, 2)
            })
        
        return hops

    async def get_network_topology(self, request):
        """Get network topology analysis and visualization"""
        try:
            # Generate topology summary
            summary = self.topology_analyzer.generate_topology_summary()
            
            # Get interactive topology data
            topology_data = self.topology_analyzer.get_interactive_topology_data()
            
            # Find bottlenecks
            bottlenecks = self.topology_analyzer.find_bottlenecks()
            
            return web.json_response({
                'summary': summary,
                'topology': topology_data,
                'bottlenecks': bottlenecks,
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"Failed to get network topology: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    async def get_topology_svg(self, request):
        """Generate SVG visualization of network topology"""
        try:
            # Get optional size parameters
            width = int(request.query.get('width', 12))
            height = int(request.query.get('height', 8))
            
            # Generate SVG
            svg_content = self.topology_analyzer.generate_topology_svg(width, height)
            
            return web.Response(
                text=svg_content,
                content_type='image/svg+xml',
                headers={'Cache-Control': 'no-cache'}
            )
            
        except Exception as e:
            logger.error(f"Failed to generate topology SVG: {e}")
            return web.Response(text=f"Error generating topology: {str(e)}", status=500)
    
    async def get_path_analysis(self, request):
        """Get detailed path analysis between two locations"""
        try:
            source = request.query.get('source')
            target = request.query.get('target')
            
            if not source or not target:
                return web.json_response({
                    'error': 'Missing required parameters: source and target'
                }, status=400)
            
            analysis = self.topology_analyzer.get_path_analysis(source, target)
            
            return web.json_response({
                'path_analysis': analysis,
                'timestamp': time.time()
            })
            
        except Exception as e:
            logger.error(f"Failed to get path analysis: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def get_member_metrics(self, request):
        """Return aggregated metrics from all reporting members"""
        try:
            metrics = {}
            reporting_member_ids = self.redis_client.smembers("netring:reporting_members")
            
            for member_id in reporting_member_ids:
                metrics_key = f"netring:metrics:{member_id}"
                metric_data = self.redis_client.hgetall(metrics_key)
                
                if metric_data and 'metrics_data' in metric_data:
                    try:
                        parsed_metrics = json.loads(metric_data['metrics_data'])
                        metrics[member_id] = parsed_metrics
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid metrics data from member {member_id}")
                        metrics[member_id] = {}
                else:
                    # Remove stale member from reporting set
                    self.redis_client.srem("netring:reporting_members", member_id)
            
            return web.json_response({'metrics': metrics})
            
        except Exception as e:
            logger.error(f"Failed to get member metrics: {e}")
            return web.json_response({'error': str(e)}, status=500)
    
    
    async def cleanup_dead_members(self):
        """Background task to cleanup dead members and old deregistered entries"""
        while True:
            try:
                current_time = int(time.time())
                
                # Cleanup dead active members
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
                
                # Cleanup old deregistered members (older than 1 hour)
                deregistered_members = self.redis_client.smembers("netring:deregistered_members")
                
                for member_id in deregistered_members:
                    key = f"netring:deregistered:{member_id}"
                    member_data = self.redis_client.hgetall(key)
                    
                    if not member_data:
                        self.redis_client.srem("netring:deregistered_members", member_id)
                        continue
                    
                    deregistered_at = int(member_data.get('deregistered_at', 0))
                    if current_time - deregistered_at > 3600:  # 1 hour
                        self.redis_client.delete(key)
                        self.redis_client.srem("netring:deregistered_members", member_id)
                        logger.debug(f"Cleaned up old deregistered member {member_id}")
                
                # Cleanup stale metrics (older than 5 minutes)
                reporting_members = self.redis_client.smembers("netring:reporting_members")
                
                for member_id in reporting_members:
                    metrics_key = f"netring:metrics:{member_id}"
                    metric_data = self.redis_client.hgetall(metrics_key)
                    
                    if not metric_data:
                        self.redis_client.srem("netring:reporting_members", member_id)
                        continue
                    
                    reported_at = int(metric_data.get('reported_at', 0))
                    if current_time - reported_at > 300:  # 5 minutes
                        self.redis_client.delete(metrics_key)
                        self.redis_client.srem("netring:reporting_members", member_id)
                        logger.debug(f"Cleaned up stale metrics from member {member_id}")
                
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
    app.router.add_post('/deregister', registry.deregister_member)
    app.router.add_post('/report_metrics', registry.report_metrics)
    app.router.add_get('/members', registry.get_members)
    app.router.add_get('/members_with_analysis', registry.get_members_with_analysis)
    app.router.add_get('/health', registry.health_check)
    app.router.add_post('/clear_redis', registry.clear_redis)  # POST for safety
    app.router.add_get('/metrics', registry.get_member_metrics)
    
    # Network topology endpoints
    app.router.add_get('/topology', registry.get_network_topology)
    app.router.add_get('/topology/svg', registry.get_topology_svg)
    app.router.add_get('/topology/path', registry.get_path_analysis)
    
    # Static files for frontend
    import os
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    
    async def serve_index(request):
        return web.FileResponse(os.path.join(static_dir, 'index.html'))
    
    # Serve index.html at root
    app.router.add_get('/', serve_index)
    
    # Custom static file handler with no-cache headers for development
    async def serve_static(request):
        file_path = request.match_info['filename']
        full_path = os.path.join(static_dir, file_path)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            response = web.FileResponse(full_path)
            # Add no-cache headers for development
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
        return web.Response(status=404)
    
    app.router.add_get('/static/{filename}', serve_static)
    
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