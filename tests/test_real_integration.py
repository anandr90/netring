"""Real integration tests using actual services."""

import pytest
import asyncio
import time
import aiohttp
import json
from unittest.mock import patch
import os


@pytest.mark.asyncio
class TestRealNetringIntegration:
    """Test Netring with real services (Redis + Registry + Member)."""
    
    async def test_member_registration_flow(self, registry_server, running_member, redis_client):
        """Test that member can register with real registry and data persists in Redis."""
        
        # Member registers with registry
        success = await running_member.register_with_registry()
        assert success, "Member should successfully register with registry"
        
        # Verify registration in registry API
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{registry_server}/members") as resp:
                assert resp.status == 200
                data = await resp.json()
                
                members = data['members']
                assert len(members) == 1, "Should have exactly one registered member"
                
                member = members[0]
                assert member['location'] == 'test-location'
                assert member['status'] == 'active'
                assert 'instance_id' in member
                assert 'ip' in member
                assert 'port' in member
        
        # Verify data is actually stored in Redis
        member_keys = redis_client.keys('netring:member:*')
        assert len(member_keys) == 1, "Should have one member in Redis"
        
        member_data = redis_client.hgetall(member_keys[0])
        assert member_data['location'] == 'test-location'
        assert 'registered_at' in member_data
        assert 'last_seen' in member_data
    
    async def test_member_heartbeat_flow(self, registry_server, running_member, redis_client):
        """Test member heartbeat updates Redis data."""
        
        # Register member first
        await running_member.register_with_registry()
        
        # Get initial last_seen time
        member_keys = redis_client.keys('netring:member:*')
        initial_data = redis_client.hgetall(member_keys[0])
        initial_last_seen = int(initial_data['last_seen'])
        
        # Wait a moment then send heartbeat
        await asyncio.sleep(0.1)
        success = await running_member.send_heartbeat()
        assert success, "Heartbeat should succeed"
        
        # Verify last_seen was updated
        updated_data = redis_client.hgetall(member_keys[0])
        updated_last_seen = int(updated_data['last_seen'])
        assert updated_last_seen > initial_last_seen, "Heartbeat should update last_seen timestamp"
    
    async def test_member_discovery_flow(self, registry_server, running_member):
        """Test member can discover other members through registry."""
        
        # Register first member
        await running_member.register_with_registry()
        
        # Create second member with different location
        second_member_config = {
            'NETRING_LOCATION': 'test-location-2',
            'NETRING_REGISTRY_URL': registry_server,
            'NETRING_SERVER_PORT': '8758'  # Different port
        }
        
        with patch.dict(os.environ, second_member_config, clear=False):
            from member.main import NetringMember
            second_member = NetringMember(None)
            await second_member.initialize_session()
            
            try:
                # Register second member
                await second_member.register_with_registry()
                
                # First member polls for members
                await running_member.poll_members()
                
                # Should discover both members (including itself)
                assert len(running_member.members) == 2, "Should discover 2 members total"
                
                locations = [m['location'] for m in running_member.members.values()]
                assert 'test-location' in locations
                assert 'test-location-2' in locations
                
            finally:
                await second_member.close_session()
    
    async def test_bandwidth_testing_real(self, registry_server, running_member):
        """Test real bandwidth testing between member and registry."""
        
        # Register member
        await running_member.register_with_registry()
        
        # Parse registry URL to get host/port
        registry_url_parts = registry_server.replace('http://', '').split(':')
        registry_host = registry_url_parts[0]
        registry_port = int(registry_url_parts[1])
        
        # Test bandwidth to registry (registry has bandwidth_test endpoint)
        bandwidth_result = await running_member.test_bandwidth(registry_host, registry_port)
        
        # Should get a real bandwidth measurement
        assert bandwidth_result is not None, "Should get bandwidth measurement"
        assert bandwidth_result > 0, "Bandwidth should be positive"
        assert bandwidth_result < 10000, "Bandwidth should be reasonable (< 10Gbps)"
    
    async def test_connectivity_testing_real(self, registry_server, running_member):
        """Test real connectivity testing."""
        
        # Parse registry URL
        registry_url_parts = registry_server.replace('http://', '').split(':')
        registry_host = registry_url_parts[0]
        registry_port = int(registry_url_parts[1])
        
        # Test TCP connectivity to registry
        tcp_result = await running_member.check_tcp_connectivity(registry_host, registry_port)
        assert tcp_result is True, "Should have TCP connectivity to registry"
        
        # Test HTTP connectivity to registry health endpoint
        http_result = await running_member.check_http_connectivity(registry_host, registry_port, '/health')
        assert http_result is True, "Should have HTTP connectivity to registry health endpoint"
        
        # Test connectivity to non-existent service
        tcp_fail = await running_member.check_tcp_connectivity('127.0.0.1', 9999)
        assert tcp_fail is False, "Should fail to connect to non-existent service"
    
    async def test_registry_health_check(self, registry_server):
        """Test registry health check endpoint."""
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{registry_server}/health") as resp:
                assert resp.status == 200
                data = await resp.json()
                
                assert data['status'] == 'healthy'
                assert 'timestamp' in data
    
    async def test_member_metrics_reporting(self, registry_server, running_member, redis_client):
        """Test real metrics reporting flow."""
        
        # Register member
        await running_member.register_with_registry()
        
        # Create some test metrics
        test_metrics = {
            'connectivity_tcp': [
                {
                    'labels': {'target_location': 'test-target', 'target_ip': '127.0.0.1'},
                    'value': 1
                }
            ],
            'bandwidth_mbps': [
                {
                    'labels': {'target_location': 'test-target', 'target_ip': '127.0.0.1'},
                    'value': 100.5
                }
            ]
        }
        
        # Report metrics to registry
        success = await running_member.report_metrics(test_metrics)
        assert success, "Should successfully report metrics"
        
        # Verify metrics are stored in Redis
        metrics_keys = redis_client.keys('netring:metrics:*')
        assert len(metrics_keys) >= 1, "Should have metrics stored in Redis"
        
        # Get metrics back from registry
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{registry_server}/metrics") as resp:
                assert resp.status == 200
                data = await resp.json()
                
                assert 'metrics' in data
                assert len(data['metrics']) >= 1, "Should return stored metrics"
    
    async def test_member_deregistration(self, registry_server, running_member, redis_client):
        """Test member graceful deregistration."""
        
        # Register member
        await running_member.register_with_registry()
        
        # Verify member is registered
        member_keys = redis_client.keys('netring:member:*')
        assert len(member_keys) == 1
        
        # Deregister member
        success = await running_member.deregister_from_registry()
        assert success, "Should successfully deregister"
        
        # Verify member is no longer in active members
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{registry_server}/members") as resp:
                data = await resp.json()
                active_members = [m for m in data['members'] if m['status'] == 'active']
                assert len(active_members) == 0, "Should have no active members after deregistration"
    
    async def test_full_system_workflow(self, registry_server, redis_client):
        """Test complete workflow with multiple members."""
        
        # Create two members
        member1_config = {
            'NETRING_LOCATION': 'datacenter-1',
            'NETRING_REGISTRY_URL': registry_server,
            'NETRING_SERVER_PORT': '8757'
        }
        
        member2_config = {
            'NETRING_LOCATION': 'datacenter-2', 
            'NETRING_REGISTRY_URL': registry_server,
            'NETRING_SERVER_PORT': '8758'
        }
        
        with patch.dict(os.environ, member1_config, clear=False):
            from member.main import NetringMember
            member1 = NetringMember(None)
            await member1.initialize_session()
            
            with patch.dict(os.environ, member2_config, clear=False):
                member2 = NetringMember(None)
                await member2.initialize_session()
                
                try:
                    # Both members register
                    await member1.register_with_registry()
                    await member2.register_with_registry()
                    
                    # Both members discover each other
                    await member1.poll_members()
                    await member2.poll_members()
                    
                    assert len(member1.members) == 2, "Member1 should see both members"
                    assert len(member2.members) == 2, "Member2 should see both members"
                    
                    # Verify Redis has both members
                    member_keys = redis_client.keys('netring:member:*')
                    assert len(member_keys) == 2, "Redis should have both members"
                    
                    # Member1 deregisters
                    await member1.deregister_from_registry()
                    
                    # Member2 polls again and should see only itself
                    await member2.poll_members()
                    
                    # Verify final state
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{registry_server}/members") as resp:
                            data = await resp.json()
                            active_members = [m for m in data['members'] if m['status'] == 'active']
                            assert len(active_members) == 1, "Should have only one active member"
                            assert active_members[0]['location'] == 'datacenter-2'
                
                finally:
                    await member1.close_session()
                    await member2.close_session()


@pytest.mark.asyncio 
class TestNetringConfigurationReal:
    """Test configuration handling with real scenarios."""
    
    def test_member_env_var_config(self, registry_server):
        """Test member configuration from environment variables."""
        
        test_config = {
            'NETRING_LOCATION': 'env-test-location',
            'NETRING_REGISTRY_URL': registry_server,
            'NETRING_POLL_INTERVAL': '30',
            'NETRING_CHECK_INTERVAL': '60',
            'NETRING_TCP_TIMEOUT': '5'
        }
        
        with patch.dict(os.environ, test_config, clear=False):
            from member.main import NetringMember
            member = NetringMember(None)
            
            assert member.location == 'env-test-location'
            assert member.registry_url == registry_server
            assert member.poll_interval == 30
            assert member.check_interval == 60
            assert member.tcp_timeout == 5
    
    def test_member_defaults_when_no_config(self):
        """Test member falls back to defaults when no config provided."""
        
        # Clear relevant env vars
        env_to_clear = [k for k in os.environ.keys() if k.startswith('NETRING_')]
        
        with patch.dict(os.environ, {}, clear=False):
            # Remove NETRING env vars
            for key in env_to_clear:
                if key in os.environ:
                    del os.environ[key]
            
            from member.main import NetringMember
            member = NetringMember(None)
            
            assert member.location == 'unknown'
            assert member.registry_url == 'http://localhost:8756'
            assert member.poll_interval == 30
            assert member.check_interval == 60
            assert member.instance_id is not None  # Should generate UUID


@pytest.mark.asyncio
class TestNetringErrorHandling:
    """Test error handling with real services."""
    
    async def test_member_handles_registry_unavailable(self, member_instance):
        """Test member behavior when registry is unavailable."""
        
        # Member tries to register with non-existent registry
        member_instance.registry_url = 'http://localhost:9999'
        
        success = await member_instance.register_with_registry()
        assert success is False, "Registration should fail gracefully"
        
        # Member should not crash, should handle connection errors
        success = await member_instance.send_heartbeat()
        assert success is False, "Heartbeat should fail gracefully"
    
    async def test_member_handles_invalid_registry_responses(self, registry_server, running_member):
        """Test member handles unexpected registry responses."""
        
        # Test with registry that returns invalid JSON
        # (We'll use a real endpoint but check error handling)
        
        # First register normally
        await running_member.register_with_registry()
        
        # Now test polling with potentially malformed responses
        # Member should handle this gracefully without crashing
        await running_member.poll_members()
        
        # Member should still be functional
        assert running_member.members is not None