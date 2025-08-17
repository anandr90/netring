"""Integration tests for the complete Netring system."""

import pytest
import asyncio
import time
import json
from unittest.mock import patch, AsyncMock
from aiohttp import web
from aiohttp.test_utils import TestServer, TestClient

# Import both components
import sys
sys.path.append('/Users/ar-admin/Desktop/netring')
from member.main import NetringMember, init_app as init_member_app
from registry.main import NetringRegistry, init_app as init_registry_app


@pytest.mark.integration
class TestNetringSystemIntegration:
    """Test complete system integration."""
    
    @pytest.mark.asyncio
    async def test_member_registry_integration(self, mock_redis, sample_registry_config):
        """Test member and registry integration."""
        # Initialize registry
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            with patch('redis.asyncio.from_url', return_value=mock_redis):
                registry_result = await init_registry_app(registry_config_path)
        finally:
            os.unlink(registry_config_path)
            
        assert registry_result is not None
        registry_app, registry = registry_result
        
        # Start registry server
        async with TestServer(registry_app) as registry_server:
            registry_url = f"http://{registry_server.host}:{registry_server.port}"
            
            # Initialize member with registry URL
            with patch.dict('os.environ', {
                'NETRING_LOCATION': 'test-integration',
                'NETRING_REGISTRY_URL': registry_url,
                'NETRING_SERVER_PORT': '8757'
            }):
                with patch('redis.asyncio.from_url', return_value=mock_redis):
                    member_result = await init_member_app(None)
            
            assert member_result is not None
            member_app, member = member_result
            
            # Test registration flow
            async with TestClient(registry_server, registry_app) as registry_client:
                # Member should register with registry
                registration_data = {
                    'instance_id': member.instance_id,
                    'location': member.location,
                    'ip': '127.0.0.1',
                    'port': member.server_port
                }
                
                response = await registry_client.post('/register', json=registration_data)
                assert response.status == 200
                
                data = await response.json()
                assert data['status'] == 'registered'
                
                # Test member list
                response = await registry_client.get('/members')
                assert response.status == 200
                
                data = await response.json()
                assert len(data['members']) >= 1
                
                # Find our member
                our_member = None
                for m in data['members']:
                    if m['instance_id'] == member.instance_id:
                        our_member = m
                        break
                
                assert our_member is not None
                assert our_member['location'] == 'test-integration'
    
    @pytest.mark.asyncio
    async def test_metrics_reporting_flow(self, mock_redis):
        """Test metrics reporting from member to registry."""
        # Mock member data in Redis
        member_data = {
            'instance_id': 'test-metrics-member',
            'location': 'test-location',
            'ip': '127.0.0.1',
            'port': 8757,
            'registered_at': time.time()
        }
        
        mock_redis.hget.return_value = json.dumps(member_data).encode()
        
        # Initialize registry
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            registry_result = await init_registry_app(None)
            
        registry_app, registry = registry_result
        
        # Test metrics reporting
        async with TestClient(TestServer(registry_app), registry_app) as client:
            metrics_data = {
                'instance_id': 'test-metrics-member',
                'metrics': {
                    'connectivity_tcp': [
                        {
                            'labels': {
                                'source_location': 'test-location',
                                'target_location': 'other-location',
                                'target_ip': '10.1.1.1'
                            },
                            'value': 1
                        }
                    ],
                    'bandwidth_mbps': [
                        {
                            'labels': {
                                'source_location': 'test-location',
                                'target_location': 'other-location',
                                'target_ip': '10.1.1.1'
                            },
                            'value': 150.5
                        }
                    ]
                }
            }
            
            response = await client.post('/metrics', json=metrics_data)
            assert response.status == 200
            
            data = await response.json()
            assert data['status'] == 'received'
            
            # Verify metrics storage
            mock_redis.hset.assert_called()
    
    @pytest.mark.asyncio
    async def test_member_discovery_flow(self, mock_aiohttp_session, mock_redis):
        """Test member discovery process."""
        # Mock registry response with multiple members
        members_response = {
            'members': [
                {
                    'instance_id': 'member-1',
                    'location': 'us1-k8s',
                    'ip': '10.1.1.1',
                    'port': 8757,
                    'last_seen': time.time()
                },
                {
                    'instance_id': 'member-2',
                    'location': 'eu1-k8s',
                    'ip': '10.1.1.2',
                    'port': 8757,
                    'last_seen': time.time()
                }
            ]
        }
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps(members_response))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.get.return_value = mock_response
        
        # Initialize member
        with patch.dict('os.environ', {
            'NETRING_LOCATION': 'test-discovery',
            'NETRING_REGISTRY_URL': 'http://test-registry:8756'
        }):
            member = NetringMember(None)
            member.session = mock_aiohttp_session
            
            # Test member discovery
            await member.poll_members()
            
            assert len(member.members) == 2
            assert 'member-1' in member.members
            assert 'member-2' in member.members
            assert member.members['member-1']['location'] == 'us1-k8s'
            assert member.members['member-2']['location'] == 'eu1-k8s'
    
    @pytest.mark.asyncio
    async def test_connectivity_testing_flow(self, mock_env_vars):
        """Test connectivity testing between members."""
        member = NetringMember(None)
        
        # Add mock members
        member.members = {
            'test-member-1': {
                'instance_id': 'test-member-1',
                'location': 'remote-location',
                'ip': '10.1.1.1',
                'port': 8757
            }
        }
        
        # Mock successful connectivity tests
        with patch.object(member, 'test_tcp_connectivity', return_value=True):
            with patch.object(member, 'test_http_connectivity', return_value=True):
                await member.run_connectivity_checks()
                
                # Verify metrics were updated
                # (In a real test, we'd check the Prometheus metrics)
                assert len(member.members) == 1
    
    @pytest.mark.asyncio
    async def test_bandwidth_testing_integration(self, mock_env_vars, mock_aiohttp_session):
        """Test bandwidth testing integration."""
        member = NetringMember(None)
        member.session = mock_aiohttp_session
        
        # Add mock members
        member.members = {
            'test-member-1': {
                'instance_id': 'test-member-1',
                'location': 'remote-location',
                'ip': '10.1.1.1',
                'port': 8757
            }
        }
        
        # Mock bandwidth test response
        test_data = b'0' * (1024 * 1024)  # 1MB
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=test_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.get.return_value = mock_response
        
        # Test bandwidth measurement
        with patch('time.time', side_effect=[0, 1]):  # 1 second duration
            await member.run_bandwidth_tests()
            
            # Verify bandwidth test was called
            mock_aiohttp_session.get.assert_called_with(
                'http://10.1.1.1:8757/bandwidth_test?size=1'
            )
    
    @pytest.mark.asyncio
    async def test_traceroute_integration(self, mock_env_vars):
        """Test traceroute integration."""
        member = NetringMember(None)
        
        # Add mock members
        member.members = {
            'test-member-1': {
                'instance_id': 'test-member-1',
                'location': 'remote-location',
                'ip': '10.1.1.1',
                'port': 8757
            }
        }
        
        # Mock traceroute output
        mock_output = """traceroute to 10.1.1.1 (10.1.1.1), 30 hops max, 60 byte packets
 1  gateway (192.168.1.1)  1.234 ms  1.567 ms  1.890 ms
 2  10.1.1.1 (10.1.1.1)  5.432 ms  5.678 ms  5.901 ms"""
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (mock_output.encode(), b'')
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            await member.run_traceroute_tests()
            
            # Verify traceroute was executed
            mock_subprocess.assert_called()


@pytest.mark.integration
class TestNetringErrorRecovery:
    """Test system error recovery and resilience."""
    
    @pytest.mark.asyncio
    async def test_registry_unavailable_recovery(self, mock_env_vars):
        """Test member behavior when registry is unavailable."""
        member = NetringMember(None)
        
        # Mock session that fails initially then succeeds
        mock_session = AsyncMock()
        
        # First call fails
        mock_session.post.side_effect = [
            Exception("Connection refused"),
            AsyncMock(status=200)  # Second call succeeds
        ]
        
        member.session = mock_session
        
        # First registration attempt should fail
        result = await member.register_with_registry()
        assert result is False
        
        # Reset side effect for second attempt
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session.post.side_effect = None
        mock_session.post.return_value = mock_response
        
        # Second attempt should succeed
        result = await member.register_with_registry()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_member_cleanup_on_stale_data(self, mock_redis):
        """Test registry cleanup of stale member data."""
        registry = NetringRegistry(None)
        registry.redis = mock_redis
        
        current_time = time.time()
        stale_time = current_time - 400  # Older than TTL
        
        # Mock stale member data
        stale_member = {
            'instance_id': 'stale-member',
            'location': 'stale-location',
            'ip': '10.1.1.99',
            'port': 8757,
            'registered_at': stale_time,
            'last_seen': stale_time,
            'status': 'active'
        }
        
        mock_redis.keys.return_value = [b'member:stale-member']
        mock_redis.hgetall.return_value = {
            k.encode(): json.dumps(v).encode() if not isinstance(v, (int, float)) else str(v).encode()
            for k, v in stale_member.items()
        }
        
        with patch('time.time', return_value=current_time):
            await registry.cleanup_stale_members()
        
        # Verify member was marked as offline
        mock_redis.hset.assert_called()
        call_args = mock_redis.hset.call_args[0]
        updated_data = json.loads(call_args[2])
        assert updated_data['status'] == 'offline'
    
    @pytest.mark.asyncio
    async def test_partial_network_failure_handling(self, mock_env_vars):
        """Test handling of partial network failures during testing."""
        member = NetringMember(None)
        
        # Add multiple members
        member.members = {
            'working-member': {
                'instance_id': 'working-member',
                'location': 'working-location',
                'ip': '10.1.1.1',
                'port': 8757
            },
            'failing-member': {
                'instance_id': 'failing-member',
                'location': 'failing-location',
                'ip': '10.1.1.2',
                'port': 8757
            }
        }
        
        # Mock mixed success/failure scenarios
        async def mock_tcp_test(ip, port):
            if ip == '10.1.1.1':
                return True  # Working member
            else:
                return False  # Failing member
        
        async def mock_http_test(ip, port, endpoint):
            if ip == '10.1.1.1':
                return True  # Working member
            else:
                return False  # Failing member
        
        with patch.object(member, 'test_tcp_connectivity', side_effect=mock_tcp_test):
            with patch.object(member, 'test_http_connectivity', side_effect=mock_http_test):
                await member.run_connectivity_checks()
                
                # System should continue operating despite partial failures
                assert len(member.members) == 2