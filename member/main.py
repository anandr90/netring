#!/usr/bin/env python3
import asyncio
import json
import logging
import os
import re
import socket
import subprocess
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp
import yaml
from aiohttp import web
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from version import get_cached_version

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NetringMember:
    def __init__(self, config_path: Optional[str] = None):
        # Load configuration from file or environment variables
        if config_path and os.path.exists(config_path):
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
            self.advertise_ip_config = self.config['member']['server'].get('advertise_ip', 'auto')
        else:
            # Load from environment variables
            self.location = os.getenv('NETRING_LOCATION', 'unknown')
            self.instance_id = os.getenv('NETRING_INSTANCE_ID') or str(uuid.uuid4())
            
            # Registry configuration
            self.registry_url = os.getenv('NETRING_REGISTRY_URL', 'http://localhost:8756')
            
            # Timing intervals (with defaults)
            self.poll_interval = int(os.getenv('NETRING_POLL_INTERVAL', '30'))
            self.check_interval = int(os.getenv('NETRING_CHECK_INTERVAL', '60'))
            self.heartbeat_interval = int(os.getenv('NETRING_HEARTBEAT_INTERVAL', '45'))
            
            # Check configuration (with defaults)
            self.tcp_timeout = int(os.getenv('NETRING_TCP_TIMEOUT', '5'))
            self.http_timeout = int(os.getenv('NETRING_HTTP_TIMEOUT', '10'))
            endpoints_str = os.getenv('NETRING_HTTP_ENDPOINTS', '/health,/metrics')
            self.http_endpoints = [ep.strip() for ep in endpoints_str.split(',')]
            
            # Local server configuration (with defaults)
            self.server_host = os.getenv('NETRING_SERVER_HOST', '0.0.0.0')
            self.server_port = int(os.getenv('NETRING_SERVER_PORT', '8757'))
            self.advertise_ip_config = os.getenv('NETRING_ADVERTISE_IP', 'auto')
        
        # Get IP to advertise to other members
        self.local_ip = self._get_advertise_ip()
        
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
        
        # New metrics for bandwidth and traceroute
        self.bandwidth_mbps = Gauge(
            'netring_bandwidth_mbps',
            'Bandwidth test results in Mbps between ring members',
            ['source_location', 'source_instance', 'target_location', 'target_instance', 'target_ip']
        )
        
        self.traceroute_hops = Gauge(
            'netring_traceroute_hops_total',
            'Total number of hops in traceroute to target',
            ['source_location', 'source_instance', 'target_location', 'target_instance', 'target_ip']
        )
        
        self.traceroute_max_hop_latency = Gauge(
            'netring_traceroute_max_hop_latency_ms',
            'Maximum hop latency in traceroute (bottleneck identification)',
            ['source_location', 'source_instance', 'target_location', 'target_instance', 'target_ip']
        )
        
        # Configuration for advanced tests
        if config_path and os.path.exists(config_path):
            self.bandwidth_test_interval = self.config['member']['intervals'].get('bandwidth_test_interval', 300)  # 5 minutes
            self.traceroute_interval = self.config['member']['intervals'].get('traceroute_interval', 300)  # 5 minutes
            self.bandwidth_test_size_mb = self.config['member']['tests'].get('bandwidth_test_size_mb', 1)  # 1MB test
        else:
            self.bandwidth_test_interval = int(os.getenv('NETRING_BANDWIDTH_TEST_INTERVAL', '300'))  # 5 minutes
            self.traceroute_interval = int(os.getenv('NETRING_TRACEROUTE_INTERVAL', '300'))  # 5 minutes
            self.bandwidth_test_size_mb = int(os.getenv('NETRING_BANDWIDTH_TEST_SIZE_MB', '1'))  # 1MB test
        
        # HTTP session for reuse
        self.session = None
        
        # Task health monitoring
        self.task_last_heartbeat = {}
        self.task_health_monitor_interval = 60  # Check every minute
        self.task_timeout = 300  # 5 minutes before task considered dead
        self.running_tasks = {}  # Track running task objects
        
        # Store detailed traceroute hop data for topology analysis
        self.detailed_traceroute_data = {}  # Format: {target_key: {'hops': [...], 'timestamp': ...}}
        
    def _get_advertise_ip(self) -> str:
        """Get the IP address to advertise to other members"""
        config = self.advertise_ip_config
        
        # Handle environment variable reference
        if config.startswith("env:"):
            env_var = config[4:]  # Remove "env:" prefix
            ip = os.getenv(env_var)
            if ip:
                logger.info(f"Using advertise IP from env var {env_var}: {ip}")
                return ip
            else:
                logger.warning(f"Environment variable {env_var} not found, falling back to auto-detection")
                config = "auto"
        
        # Handle explicit IP
        if config != "auto":
            logger.info(f"Using configured advertise IP: {config}")
            return config
        
        # Auto-detect IP
        return self._get_local_ip()
    
    def _get_local_ip(self) -> str:
        """Get the LAN IP address for cross-datacenter connectivity"""
        # Try Kubernetes pod IP first
        pod_ip = os.getenv('POD_IP')
        if pod_ip:
            logger.info(f"Auto-detected Kubernetes POD_IP: {pod_ip}")
            return pod_ip
        
        # Try other common Kubernetes environment variables
        k8s_ip = os.getenv('KUBERNETES_POD_IP') or os.getenv('MY_POD_IP')
        if k8s_ip:
            logger.info(f"Auto-detected Kubernetes IP from env: {k8s_ip}")
            return k8s_ip
        
        # Try environment variables for manual override
        manual_ip = os.getenv('PUBLIC_IP') or os.getenv('EXTERNAL_IP') or os.getenv('HOST_IP')
        if manual_ip:
            logger.info(f"Using IP from environment: {manual_ip}")
            return manual_ip
        
        # Auto-detect IP - prioritize host IP for containers
        detected_ip = self._detect_usable_ip()
        if detected_ip:
            logger.info(f"Auto-detected IP: {detected_ip}")
            return detected_ip
        
        logger.warning("Failed to auto-detect IP, using 127.0.0.1")
        return "127.0.0.1"
    
    def _detect_usable_ip(self) -> Optional[str]:
        """Detect IP that works for cross-datacenter connectivity"""
        # Check if we're in a container
        if self._is_in_container():
            # In container - try to get host IP
            host_ip = self._get_host_ip_from_container()
            if host_ip:
                return host_ip
        
        # Not in container or fallback - use socket detection
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                detected_ip = s.getsockname()[0]
                if detected_ip != "127.0.0.1":
                    return detected_ip
        except Exception:
            pass
        
        return None
    
    def _is_in_container(self) -> bool:
        """Check if running inside a container"""
        try:
            # Check for .dockerenv file
            if os.path.exists('/.dockerenv'):
                return True
            
            # Check cgroup for container runtime
            with open('/proc/1/cgroup', 'r') as f:
                content = f.read()
                return 'docker' in content or 'containerd' in content
        except:
            return False
    
    def _get_host_ip_from_container(self) -> Optional[str]:
        """Get the host's actual LAN IP when running inside a container"""
        
        # Since this is complex and you don't want environment variables,
        # let's use a simple but effective approach:
        # The container will need to be run with --add-host=host.docker.internal:host-gateway
        # Then we connect to an external service and examine what IP we appear to be coming from
        
        # Method 1: Connect to an external service that tells us our IP
        try:
            import urllib.request
            # This should return the host's external-facing IP when the container 
            # uses the host's network stack for external connections
            with urllib.request.urlopen('https://api.ipify.org', timeout=5) as response:
                external_ip = response.read().decode().strip()
                socket.inet_aton(external_ip)  # Validate
                
                # If this is a private IP, it's likely the host's LAN IP
                if self._is_private_ip(external_ip):
                    logger.debug(f"Found host LAN IP via external query: {external_ip}")
                    return external_ip
                else:
                    # It's a public IP, but let's see if we can determine the LAN IP
                    logger.debug(f"Host has public IP {external_ip}, trying to find LAN IP")
        except:
            pass
        
        # Method 2: Try to connect to likely LAN targets and see what source IP we use
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Test connecting to common private network gateways
                # The idea is that if the host is on 10.0.1.x network,
                # connecting to 10.0.1.1 should reveal our 10.0.1.x address
                test_gateways = [
                    '10.0.1.1',     # Your likely gateway based on 10.0.1.145
                    '10.0.0.1',     # Common 10.x gateway
                    '192.168.1.1',  # Common home gateway
                    '192.168.0.1',  # Another common gateway
                ]
                
                for gateway in test_gateways:
                    try:
                        s.connect((gateway, 53))  # DNS port
                        source_ip = s.getsockname()[0]
                        
                        # Skip obvious container IPs
                        if source_ip.startswith(('172.17.', '172.18.', '172.19.')):
                            continue
                        
                        if self._is_private_ip(source_ip):
                            logger.debug(f"Found LAN IP {source_ip} when connecting to {gateway}")
                            return source_ip
                    except:
                        continue
        except:
            pass
        
        return None
    
    def _is_private_ip(self, ip: str) -> bool:
        """Check if IP is a private/LAN IP address"""
        return (ip.startswith(('192.168.', '10.')) or 
                (ip.startswith('172.') and 16 <= int(ip.split('.')[1]) <= 31))
    
    
    async def _init_session(self):
        """Initialize HTTP session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.http_timeout)
            connector = aiohttp.TCPConnector(ssl=False)
            self.session = aiohttp.ClientSession(timeout=timeout, connector=connector)
    
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
    
    async def deregister_from_registry(self):
        """Deregister this member from the registry"""
        if not self.session:
            return False
            
        deregister_data = {
            'instance_id': self.instance_id
        }
        
        try:
            async with self.session.post(
                f"{self.registry_url}/deregister",
                json=deregister_data
            ) as resp:
                if resp.status == 200:
                    logger.info(f"Successfully deregistered from registry")
                    return True
                else:
                    logger.error(f"Deregistration failed: {resp.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Deregistration error: {e}")
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
                        if member['instance_id'] != self.instance_id and member['status'] == 'active':
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
    
    async def run_bandwidth_tests(self):
        """Run bandwidth tests against all known members"""
        for member_id, member in self.members.items():
            target_ip = member['ip']
            target_port = member['port']
            target_location = member['location']
            
            # Run bandwidth test
            start_time = time.time()
            bandwidth_mbps = await self.test_bandwidth(target_ip, target_port)
            test_duration = time.time() - start_time
            
            if bandwidth_mbps is not None:
                self.bandwidth_mbps.labels(
                    source_location=self.location,
                    source_instance=self.instance_id,
                    target_location=target_location,
                    target_instance=member_id,
                    target_ip=target_ip
                ).set(bandwidth_mbps)
                
                logger.info(f"Bandwidth test to {target_location} ({target_ip}): {bandwidth_mbps:.2f} Mbps")
            else:
                logger.warning(f"Bandwidth test to {target_location} ({target_ip}) failed")
        
        logger.debug(f"Completed bandwidth tests for {len(self.members)} members")
    
    async def run_traceroute_tests(self):
        """Run traceroute tests against all known members"""
        for member_id, member in self.members.items():
            target_ip = member['ip']
            target_location = member['location']
            
            # Run traceroute test
            traceroute_result = await self.run_traceroute(target_ip)
            
            if traceroute_result:
                self.traceroute_hops.labels(
                    source_location=self.location,
                    source_instance=self.instance_id,
                    target_location=target_location,
                    target_instance=member_id,
                    target_ip=target_ip
                ).set(traceroute_result['total_hops'])
                
                self.traceroute_max_hop_latency.labels(
                    source_location=self.location,
                    source_instance=self.instance_id,
                    target_location=target_location,
                    target_instance=member_id,
                    target_ip=target_ip
                ).set(traceroute_result['max_hop_latency'])
                
                # Store detailed hop data for topology analysis
                target_key = f"{target_location}:{member_id}"
                self.detailed_traceroute_data[target_key] = {
                    'hops': traceroute_result['hops'],
                    'timestamp': time.time(),
                    'target_location': target_location,
                    'target_ip': target_ip,
                    'labels': {
                        'source_location': self.location,
                        'source_instance': self.instance_id,
                        'target_location': target_location,
                        'target_instance': member_id,
                        'target_ip': target_ip
                    }
                }
                
                logger.info(f"Traceroute to {target_location} ({target_ip}): {traceroute_result['total_hops']} hops, max hop latency: {traceroute_result['max_hop_latency']:.2f}ms")
            else:
                logger.warning(f"Traceroute to {target_location} ({target_ip}) failed")
        
        logger.debug(f"Completed traceroute tests for {len(self.members)} members")
    
    async def test_bandwidth(self, target_ip: str, target_port: int) -> Optional[float]:
        """Test bandwidth to a target by downloading test data"""
        if not self.session:
            return None
            
        # Create test data endpoint URL
        test_url = f"http://{target_ip}:{target_port}/bandwidth_test?size={self.bandwidth_test_size_mb}"
        
        try:
            start_time = time.time()
            async with self.session.get(test_url) as response:
                if response.status == 200:
                    # Read the response data to measure bandwidth
                    data = await response.read()
                    end_time = time.time()
                    
                    # Calculate bandwidth in Mbps
                    bytes_downloaded = len(data)
                    duration_seconds = end_time - start_time
                    
                    if duration_seconds > 0:
                        mbps = (bytes_downloaded * 8) / (duration_seconds * 1_000_000)  # Convert to Mbps
                        return mbps
                    
        except Exception as e:
            logger.debug(f"Bandwidth test to {target_ip}:{target_port} failed: {e}")
        
        return None
    
    async def run_traceroute(self, target_ip: str) -> Optional[Dict]:
        """Run traceroute to target and parse results"""
        try:
            # Run traceroute command
            process = await asyncio.create_subprocess_exec(
                'traceroute', '-n', '-w', '3', '-q', '1', target_ip,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return self.parse_traceroute_output(stdout.decode('utf-8'))
            else:
                logger.debug(f"Traceroute to {target_ip} failed: {stderr.decode('utf-8')}")
                
        except Exception as e:
            logger.debug(f"Traceroute to {target_ip} failed: {e}")
        
        return None
    
    def parse_traceroute_output(self, output: str) -> Dict:
        """Parse traceroute output to extract hop count and latencies"""
        lines = output.strip().split('\n')
        hops = []
        max_latency = 0.0
        
        for line in lines[1:]:  # Skip the first line (header)
            # Parse traceroute line format: " 1  10.0.1.1  1.234 ms"
            parts = line.strip().split()
            if len(parts) >= 3:
                try:
                    hop_num = int(parts[0])
                    if parts[-1] == 'ms' and len(parts) >= 4:
                        latency = float(parts[-2])
                        hops.append({'hop': hop_num, 'ip': parts[1], 'latency_ms': latency})
                        max_latency = max(max_latency, latency)
                    elif '*' in line:
                        # Timeout hop
                        hops.append({'hop': hop_num, 'ip': '*', 'latency_ms': None})
                except (ValueError, IndexError):
                    continue
        
        return {
            'total_hops': len(hops),
            'max_hop_latency': max_latency,
            'hops': hops
        }
    
    async def bandwidth_test_endpoint(self, request):
        """Endpoint to serve test data for bandwidth testing"""
        try:
            size_mb = int(request.query.get('size', '1'))
            # Limit size to prevent abuse
            size_mb = min(size_mb, 10)  # Max 10MB
            
            # Generate test data (random bytes)
            test_data = b'0' * (size_mb * 1024 * 1024)
            
            return web.Response(
                body=test_data,
                headers={
                    'Content-Type': 'application/octet-stream',
                    'Content-Length': str(len(test_data))
                }
            )
        except Exception as e:
            return web.json_response({'error': str(e)}, status=400)
    
    async def health_check(self, request):
        """Health check endpoint"""
        current_time = time.time()
        task_health = {}
        
        # Check health of all tracked tasks
        for task_name, last_heartbeat in self.task_last_heartbeat.items():
            seconds_since_heartbeat = current_time - last_heartbeat
            task_health[task_name] = {
                'last_heartbeat': last_heartbeat,
                'seconds_since_heartbeat': seconds_since_heartbeat,
                'status': 'healthy' if seconds_since_heartbeat < self.task_timeout else 'unhealthy'
            }
        
        # Overall health status
        unhealthy_tasks = [name for name, info in task_health.items() if info['status'] == 'unhealthy']
        overall_status = 'unhealthy' if unhealthy_tasks else 'healthy'
        
        return web.json_response({
            'status': overall_status,
            'version': get_cached_version(),
            'component': 'member',
            'instance_id': self.instance_id,
            'location': self.location,
            'members_count': len(self.members),
            'timestamp': current_time,
            'task_health': task_health,
            'unhealthy_tasks': unhealthy_tasks,
            'fault_tolerance': {
                'task_timeout_seconds': self.task_timeout,
                'health_monitor_interval_seconds': self.task_health_monitor_interval
            }
        })
    
    async def metrics_endpoint(self, request):
        """Prometheus metrics endpoint"""
        metrics_data = generate_latest()
        return web.Response(
            body=metrics_data,
            headers={'Content-Type': 'text/plain; version=0.0.4; charset=utf-8'}
        )
    
    async def _heartbeat_loop(self):
        """Core heartbeat loop logic"""
        while True:
            await self.send_heartbeat()
            await asyncio.sleep(self.heartbeat_interval)
    
    async def _member_polling_loop(self):
        """Core member polling loop logic"""
        while True:
            await self.poll_members()
            await asyncio.sleep(self.poll_interval)
    
    async def _connectivity_check_loop(self):
        """Core connectivity check loop logic"""
        while True:
            if self.members:
                await self.run_connectivity_checks()
            await asyncio.sleep(self.check_interval)
    
    async def _metrics_reporting_loop(self):
        """Core metrics reporting loop logic"""
        # Wait a bit before starting to ensure member is registered
        await asyncio.sleep(30)
        
        while True:
            await self.report_metrics_to_registry()
            await asyncio.sleep(60)  # Report metrics every minute
    
    async def _bandwidth_test_loop(self):
        """Core bandwidth test loop logic"""
        # Wait for member registration and discovery
        await asyncio.sleep(60)
        
        while True:
            if self.members:
                await self.run_bandwidth_tests()
            await asyncio.sleep(self.bandwidth_test_interval)
    
    async def _traceroute_test_loop(self):
        """Core traceroute test loop logic"""
        # Wait for member registration and discovery
        await asyncio.sleep(90)  # Slightly offset from bandwidth tests
        
        while True:
            if self.members:
                await self.run_traceroute_tests()
            await asyncio.sleep(self.traceroute_interval)
    
    async def report_metrics_to_registry(self):
        """Report current metrics to the registry"""
        try:
            # Ensure session is initialized
            await self._init_session()
            
            # Get current metrics in Prometheus format
            metrics_output = generate_latest()
            
            # Parse the metrics into our structured format
            parsed_metrics = self.parse_prometheus_metrics(metrics_output.decode('utf-8'))
            
            # Add detailed traceroute data for topology analysis
            parsed_metrics['detailed_traceroute_data'] = self.detailed_traceroute_data.copy()
            
            # Send to registry
            async with self.session.post(
                f"{self.registry_url}/report_metrics",
                json={
                    'instance_id': self.instance_id,
                    'metrics': parsed_metrics
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    logger.info(f"Successfully reported metrics to registry")
                else:
                    logger.warning(f"Failed to report metrics: HTTP {response.status}")
                    
        except Exception as e:
            logger.warning(f"Failed to report metrics to registry: {e}")
    
    def parse_prometheus_metrics(self, metrics_text):
        """Parse Prometheus metrics into structured format for registry"""
        lines = metrics_text.split('\n')
        parsed = {
            'connectivity_tcp': {},
            'connectivity_http': {},
            'check_durations': {},
            'bandwidth_tests': {},
            'traceroute_tests': {},
            'general': {}
        }
        
        for line in lines:
            if line.startswith('netring_connectivity_tcp{'):
                match = re.match(r'netring_connectivity_tcp{([^}]+)}\s+([0-9.]+)', line)
                if match:
                    labels = self.parse_metric_labels(match.group(1))
                    value = float(match.group(2))
                    key = f"{labels.get('target_location', '')}:{labels.get('target_instance', '')}"
                    parsed['connectivity_tcp'][key] = {
                        'labels': labels,
                        'value': value
                    }
            elif line.startswith('netring_connectivity_http{'):
                match = re.match(r'netring_connectivity_http{([^}]+)}\s+([0-9.]+)', line)
                if match:
                    labels = self.parse_metric_labels(match.group(1))
                    value = float(match.group(2))
                    key = f"{labels.get('target_location', '')}:{labels.get('target_instance', '')}:{labels.get('endpoint', '')}"
                    parsed['connectivity_http'][key] = {
                        'labels': labels,
                        'value': value
                    }
            elif line.startswith('netring_check_duration_seconds_sum{'):
                match = re.match(r'netring_check_duration_seconds_sum{([^}]+)}\s+([0-9.]+)', line)
                if match:
                    labels = self.parse_metric_labels(match.group(1))
                    value = float(match.group(2))
                    key = f"{labels.get('check_type', '')}:{labels.get('target_location', '')}:{labels.get('target_instance', '')}"
                    if key not in parsed['check_durations']:
                        parsed['check_durations'][key] = {'labels': labels}
                    parsed['check_durations'][key]['sum'] = value
            elif line.startswith('netring_check_duration_seconds_count{'):
                match = re.match(r'netring_check_duration_seconds_count{([^}]+)}\s+([0-9.]+)', line)
                if match:
                    labels = self.parse_metric_labels(match.group(1))
                    value = float(match.group(2))
                    key = f"{labels.get('check_type', '')}:{labels.get('target_location', '')}:{labels.get('target_instance', '')}"
                    if key not in parsed['check_durations']:
                        parsed['check_durations'][key] = {'labels': labels}
                    parsed['check_durations'][key]['count'] = value
            elif line.startswith('netring_bandwidth_mbps{'):
                match = re.match(r'netring_bandwidth_mbps{([^}]+)}\s+([0-9.]+)', line)
                if match:
                    labels = self.parse_metric_labels(match.group(1))
                    value = float(match.group(2))
                    key = f"{labels.get('target_location', '')}:{labels.get('target_instance', '')}"
                    parsed['bandwidth_tests'][key] = {
                        'labels': labels,
                        'bandwidth_mbps': value
                    }
            elif line.startswith('netring_traceroute_hops_total{'):
                match = re.match(r'netring_traceroute_hops_total{([^}]+)}\s+([0-9.]+)', line)
                if match:
                    labels = self.parse_metric_labels(match.group(1))
                    value = float(match.group(2))
                    key = f"{labels.get('target_location', '')}:{labels.get('target_instance', '')}"
                    if key not in parsed['traceroute_tests']:
                        parsed['traceroute_tests'][key] = {'labels': labels}
                    parsed['traceroute_tests'][key]['total_hops'] = value
            elif line.startswith('netring_traceroute_max_hop_latency_ms{'):
                match = re.match(r'netring_traceroute_max_hop_latency_ms{([^}]+)}\s+([0-9.]+)', line)
                if match:
                    labels = self.parse_metric_labels(match.group(1))
                    value = float(match.group(2))
                    key = f"{labels.get('target_location', '')}:{labels.get('target_instance', '')}"
                    if key not in parsed['traceroute_tests']:
                        parsed['traceroute_tests'][key] = {'labels': labels}
                    parsed['traceroute_tests'][key]['max_hop_latency_ms'] = value
            elif line.startswith('netring_members_total'):
                match = re.match(r'netring_members_total\s+([0-9.]+)', line)
                if match:
                    parsed['general']['members_total'] = float(match.group(1))
        
        # Calculate average latencies from histogram data
        for key, data in parsed['check_durations'].items():
            if 'sum' in data and 'count' in data and data['count'] > 0:
                data['avg_latency_ms'] = (data['sum'] / data['count']) * 1000  # Convert to ms
            else:
                data['avg_latency_ms'] = 0
        
        return parsed
    
    def parse_metric_labels(self, label_string):
        """Parse Prometheus metric labels"""
        import re
        labels = {}
        pairs = re.findall(r'(\w+)="([^"]+)"', label_string)
        for key, value in pairs:
            labels[key] = value
        return labels
    
    def record_task_heartbeat(self, task_name: str):
        """Record that a task is still alive"""
        self.task_last_heartbeat[task_name] = time.time()

    async def monitor_task_health(self):
        """Monitor health of background tasks and restart dead ones"""
        while True:
            try:
                current_time = time.time()
                for task_name, last_heartbeat in self.task_last_heartbeat.items():
                    if current_time - last_heartbeat > self.task_timeout:
                        logger.error(f"Task {task_name} appears dead (last heartbeat: {current_time - last_heartbeat:.1f}s ago), restarting...")
                        await self.restart_task(task_name)
                
                await asyncio.sleep(self.task_health_monitor_interval)
            except asyncio.CancelledError:
                logger.info("Task health monitor cancelled, shutting down gracefully")
                break
            except Exception as e:
                logger.error(f"Task health monitor error: {e}", exc_info=True)
                await asyncio.sleep(10)  # Brief pause before retry

    async def restart_task(self, task_name: str):
        """Restart a dead background task"""
        try:
            # Cancel the old task if it exists
            if task_name in self.running_tasks:
                old_task = self.running_tasks[task_name]
                if not old_task.done():
                    old_task.cancel()
                    try:
                        await old_task
                    except asyncio.CancelledError:
                        pass
            
            # Start new task based on task name
            task_map = {
                "heartbeat": self._heartbeat_loop,
                "member_polling": self._member_polling_loop,
                "connectivity_check": self._connectivity_check_loop,
                "metrics_reporting": self._metrics_reporting_loop,
                "bandwidth_test": self._bandwidth_test_loop,
                "traceroute_test": self._traceroute_test_loop
            }
            
            if task_name in task_map:
                logger.info(f"Restarting task: {task_name}")
                new_task = asyncio.create_task(self.resilient_task_wrapper(task_name, task_map[task_name]))
                self.running_tasks[task_name] = new_task
                # Reset heartbeat to give the new task time to start
                self.record_task_heartbeat(task_name)
            else:
                logger.error(f"Unknown task name for restart: {task_name}")
                
        except Exception as e:
            logger.error(f"Failed to restart task {task_name}: {e}", exc_info=True)

    async def resilient_task_wrapper(self, task_name: str, task_func, *args, **kwargs):
        """Wrapper that makes background tasks resilient to exceptions"""
        logger.info(f"Starting resilient task: {task_name}")
        
        # Initial heartbeat
        self.record_task_heartbeat(task_name)
        
        while True:
            try:
                # Record heartbeat before executing task logic
                self.record_task_heartbeat(task_name)
                await task_func(*args, **kwargs)
            except asyncio.CancelledError:
                logger.info(f"Task {task_name} cancelled, shutting down gracefully")
                break
            except Exception as e:
                logger.error(f"Task {task_name} error: {e}", exc_info=True)
                # Continue running instead of dying - brief pause before retry
                await asyncio.sleep(5)
        logger.info(f"Task {task_name} completed")

    async def cleanup(self):
        """Cleanup resources and deregister from registry"""
        # First deregister from registry
        await self.deregister_from_registry()
        
        # Then cleanup HTTP session
        if self.session:
            await self.session.close()


async def init_app(config_path: Optional[str] = None):
    member = NetringMember(config_path)
    
    # Register with registry
    if not await member.register_with_registry():
        logger.error("Failed to register with registry")
        return None
    
    app = web.Application()
    
    # API routes
    app.router.add_get('/health', member.health_check)
    app.router.add_get('/metrics', member.metrics_endpoint)
    app.router.add_get('/bandwidth_test', member.bandwidth_test_endpoint)
    
    # Start background tasks with resilient wrappers
    member.running_tasks["heartbeat"] = asyncio.create_task(member.resilient_task_wrapper("heartbeat", member._heartbeat_loop))
    member.running_tasks["member_polling"] = asyncio.create_task(member.resilient_task_wrapper("member_polling", member._member_polling_loop))
    member.running_tasks["connectivity_check"] = asyncio.create_task(member.resilient_task_wrapper("connectivity_check", member._connectivity_check_loop))
    member.running_tasks["metrics_reporting"] = asyncio.create_task(member.resilient_task_wrapper("metrics_reporting", member._metrics_reporting_loop))
    member.running_tasks["bandwidth_test"] = asyncio.create_task(member.resilient_task_wrapper("bandwidth_test", member._bandwidth_test_loop))
    member.running_tasks["traceroute_test"] = asyncio.create_task(member.resilient_task_wrapper("traceroute_test", member._traceroute_test_loop))
    
    # Start task health monitor
    member.running_tasks["task_health_monitor"] = asyncio.create_task(member.resilient_task_wrapper("task_health_monitor", member.monitor_task_health))
    
    # Cleanup on shutdown
    app.on_cleanup.append(lambda app: member.cleanup())
    
    return app, member


if __name__ == '__main__':
    import sys
    
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    
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
        
        # Set up signal handlers for graceful shutdown
        import signal
        shutdown_event = asyncio.Event()
        
        def signal_handler():
            logger.info("Received shutdown signal, deregistering from pool...")
            shutdown_event.set()
        
        # Handle SIGTERM (Docker stop) and SIGINT (Ctrl+C)
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler())
        signal.signal(signal.SIGINT, lambda s, f: signal_handler())
        
        try:
            await shutdown_event.wait()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            logger.info("Performing graceful shutdown...")
            # Deregister from registry first
            await member.cleanup()
            # Then cleanup web server
            await runner.cleanup()
            logger.info("Shutdown complete")
    
    asyncio.run(main())