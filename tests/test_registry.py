"""Tests for the Netring registry component."""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, AsyncMock, patch
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

# Import the registry module
import sys
sys.path.append('/Users/ar-admin/Desktop/netring')
from registry.main import NetringRegistry, init_app


class TestNetringRegistryConfig:
    """Test NetringRegistry configuration loading."""
    
    def test_config_from_file(self, sample_registry_config):
        """Test loading configuration from YAML file."""
        # Create a temporary registry config file
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
            
            assert registry.member_ttl == 300
            assert registry.cleanup_interval == 60
            
            # Check Redis client configuration by looking at the config
            assert registry.config['registry']['redis']['host'] == 'test-redis'
            assert registry.config['registry']['redis']['port'] == 6379
            assert registry.config['registry']['redis']['db'] == 0
            assert registry.config['registry']['server']['host'] == '0.0.0.0'
            assert registry.config['registry']['server']['port'] == 8756
            
        finally:
            os.unlink(registry_config_path)
    
    def test_config_loading_structure(self, sample_registry_config):
        """Test configuration structure loading."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
            
            # Verify config structure exists
            assert 'registry' in registry.config
            assert 'redis' in registry.config['registry']
            assert 'server' in registry.config['registry']
            assert hasattr(registry, 'redis_client')
            assert hasattr(registry, 'member_ttl')
            assert hasattr(registry, 'cleanup_interval')
            
        finally:
            os.unlink(registry_config_path)


class TestNetringRegistryMemberManagement:
    """Test member registration and management."""
    
    @pytest.mark.asyncio
    async def test_register_member_success(self, mock_redis, sample_registry_config):
        """Test successful member registration."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
            registry.redis_client = mock_redis
        finally:
            os.unlink(registry_config_path)
        
        member_data = {
            'instance_id': 'test-member-1',
            'location': 'us1-k8s',
            'ip': '10.1.1.1',
            'port': 8757
        }
        
        request = make_mocked_request('POST', '/register', json=member_data)
        request.json = AsyncMock(return_value=member_data)
        
        response = await registry.register_member(request)
        
        assert response.status == 200
        data = json.loads(response.text)
        assert data['status'] == 'registered'
        assert data['instance_id'] == 'test-member-1'
        
        # Verify Redis calls
        mock_redis.hset.assert_called()
        mock_redis.expire.assert_called()
    
    @pytest.mark.asyncio
    async def test_register_member_auto_instance_id(self, mock_redis, sample_registry_config):
        """Test member registration with auto-generated instance ID."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
            registry.redis_client = mock_redis
        finally:
            os.unlink(registry_config_path)
        
        member_data = {
            'location': 'us1-k8s',
            'ip': '10.1.1.1',
            'port': 8757
        }
        
        request = make_mocked_request('POST', '/register', json=member_data)
        request.json = AsyncMock(return_value=member_data)
        
        response = await registry.register_member(request)
        
        assert response.status == 200
        data = json.loads(response.text)
        assert data['status'] == 'registered'
        assert 'instance_id' in data
        assert len(data['instance_id']) == 36  # UUID format
    
    @pytest.mark.asyncio
    async def test_register_member_invalid_data(self, mock_redis, sample_registry_config):
        """Test member registration with invalid data."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
            registry.redis_client = mock_redis
        finally:
            os.unlink(registry_config_path)
        
        # Missing required fields
        member_data = {
            'location': 'us1-k8s'
            # Missing ip and port
        }
        
        request = make_mocked_request('POST', '/register', json=member_data)
        request.json = AsyncMock(return_value=member_data)
        
        response = await registry.register_member(request)
        
        assert response.status == 400
        data = json.loads(response.text)
        assert 'error' in data
    
    @pytest.mark.asyncio
    async def test_heartbeat_success(self, mock_redis, sample_registry_config):
        """Test successful heartbeat."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
            registry.redis_client = mock_redis
        finally:
            os.unlink(registry_config_path)
        
        # Mock existing member
        mock_redis.hget.return_value = json.dumps({
            'instance_id': 'test-member-1',
            'location': 'us1-k8s',
            'ip': '10.1.1.1',
            'port': 8757,
            'registered_at': time.time()
        }).encode()
        
        heartbeat_data = {
            'instance_id': 'test-member-1'
        }
        
        request = make_mocked_request('POST', '/heartbeat', json=heartbeat_data)
        request.json = AsyncMock(return_value=heartbeat_data)
        
        response = await registry.heartbeat(request)
        
        assert response.status == 200
        data = json.loads(response.text)
        assert data['status'] == 'ok'
        
        # Verify Redis calls
        mock_redis.hget.assert_called()
        mock_redis.hset.assert_called()
        mock_redis.expire.assert_called()
    
    @pytest.mark.asyncio
    async def test_heartbeat_unknown_member(self, mock_redis, sample_registry_config):
        """Test heartbeat for unknown member."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
            registry.redis_client = mock_redis
        finally:
            os.unlink(registry_config_path)
        
        # Mock member not found
        mock_redis.hget.return_value = None
        
        heartbeat_data = {
            'instance_id': 'unknown-member'
        }
        
        request = make_mocked_request('POST', '/heartbeat', json=heartbeat_data)
        request.json = AsyncMock(return_value=heartbeat_data)
        
        response = await registry.heartbeat(request)
        
        assert response.status == 404
        data = json.loads(response.text)
        assert 'error' in data
    
    @pytest.mark.asyncio
    async def test_deregister_member_success(self, mock_redis, sample_registry_config):
        """Test successful member deregistration."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
            registry.redis_client = mock_redis
        finally:
            os.unlink(registry_config_path)
        
        # Mock existing member
        member_data = {
            'instance_id': 'test-member-1',
            'location': 'us1-k8s',
            'ip': '10.1.1.1',
            'port': 8757,
            'registered_at': time.time()
        }
        mock_redis.hget.return_value = json.dumps(member_data).encode()
        
        deregister_data = {
            'instance_id': 'test-member-1'
        }
        
        request = make_mocked_request('POST', '/deregister', json=deregister_data)
        request.json = AsyncMock(return_value=deregister_data)
        
        response = await registry.deregister_member(request)
        
        assert response.status == 200
        data = json.loads(response.text)
        assert data['status'] == 'deregistered'
        
        # Verify Redis calls
        mock_redis.hget.assert_called()
        mock_redis.hset.assert_called()  # Update with deregistered_at
    
    @pytest.mark.asyncio
    async def test_list_members(self, mock_redis, sample_registry_config):
        """Test listing all members."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
            registry.redis_client = mock_redis
        finally:
            os.unlink(registry_config_path)
        
        # Mock member data
        member1_data = {
            'instance_id': 'test-member-1',
            'location': 'us1-k8s',
            'ip': '10.1.1.1',
            'port': 8757,
            'registered_at': time.time(),
            'last_seen': time.time()
        }
        member2_data = {
            'instance_id': 'test-member-2',
            'location': 'eu1-k8s',
            'ip': '10.1.1.2',
            'port': 8757,
            'registered_at': time.time(),
            'last_seen': time.time()
        }
        
        mock_redis.keys.return_value = [b'member:test-member-1', b'member:test-member-2']
        mock_redis.hgetall.side_effect = [
            {k.encode(): json.dumps(v).encode() if not isinstance(v, (int, float)) else str(v).encode() 
             for k, v in member1_data.items()},
            {k.encode(): json.dumps(v).encode() if not isinstance(v, (int, float)) else str(v).encode() 
             for k, v in member2_data.items()}
        ]
        
        request = make_mocked_request('GET', '/members')
        response = await registry.get_members(request)
        
        assert response.status == 200
        data = json.loads(response.text)
        assert 'members' in data
        assert len(data['members']) == 2
        
        # Check member data
        members = {m['instance_id']: m for m in data['members']}
        assert 'test-member-1' in members
        assert 'test-member-2' in members
        assert members['test-member-1']['location'] == 'us1-k8s'
        assert members['test-member-2']['location'] == 'eu1-k8s'


class TestNetringRegistryMetrics:
    """Test metrics collection and reporting."""
    
    @pytest.mark.asyncio
    async def test_report_metrics_success(self, mock_redis, sample_registry_config):
        """Test successful metrics reporting."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
            registry.redis_client = mock_redis
        finally:
            os.unlink(registry_config_path)
        
        # Mock existing member
        mock_redis.hget.return_value = json.dumps({
            'instance_id': 'test-member-1',
            'location': 'us1-k8s',
            'ip': '10.1.1.1',
            'port': 8757,
            'registered_at': time.time()
        }).encode()
        
        metrics_data = {
            'instance_id': 'test-member-1',
            'metrics': {
                'connectivity_tcp': [
                    {
                        'labels': {'target_location': 'eu1-k8s', 'target_ip': '10.1.1.2'},
                        'value': 1
                    }
                ],
                'bandwidth_mbps': [
                    {
                        'labels': {'target_location': 'eu1-k8s', 'target_ip': '10.1.1.2'},
                        'value': 100.5
                    }
                ]
            }
        }
        
        request = make_mocked_request('POST', '/metrics', json=metrics_data)
        request.json = AsyncMock(return_value=metrics_data)
        
        response = await registry.report_metrics(request)
        
        assert response.status == 200
        data = json.loads(response.text)
        assert data['status'] == 'received'
        
        # Verify Redis storage
        mock_redis.hset.assert_called()
    
    @pytest.mark.asyncio
    async def test_report_metrics_unknown_member(self, mock_redis, sample_registry_config):
        """Test metrics reporting for unknown member."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
            registry.redis_client = mock_redis
        finally:
            os.unlink(registry_config_path)
        
        # Mock member not found
        mock_redis.hget.return_value = None
        
        metrics_data = {
            'instance_id': 'unknown-member',
            'metrics': {}
        }
        
        request = make_mocked_request('POST', '/metrics', json=metrics_data)
        request.json = AsyncMock(return_value=metrics_data)
        
        response = await registry.report_metrics(request)
        
        assert response.status == 404
        data = json.loads(response.text)
        assert 'error' in data
    
    @pytest.mark.asyncio
    async def test_get_aggregated_metrics(self, mock_redis, sample_registry_config):
        """Test getting aggregated metrics."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
            registry.redis_client = mock_redis
        finally:
            os.unlink(registry_config_path)
        
        # Mock metrics data
        member1_metrics = {
            'connectivity_tcp': [
                {
                    'labels': {'source_location': 'us1-k8s', 'target_location': 'eu1-k8s'},
                    'value': 1
                }
            ]
        }
        member2_metrics = {
            'connectivity_tcp': [
                {
                    'labels': {'source_location': 'eu1-k8s', 'target_location': 'us1-k8s'},
                    'value': 0
                }
            ]
        }
        
        mock_redis.keys.return_value = [b'metrics:test-member-1', b'metrics:test-member-2']
        mock_redis.hgetall.side_effect = [
            {k.encode(): json.dumps(v).encode() for k, v in member1_metrics.items()},
            {k.encode(): json.dumps(v).encode() for k, v in member2_metrics.items()}
        ]
        
        request = make_mocked_request('GET', '/metrics')
        response = await registry.get_member_metrics(request)
        
        assert response.status == 200
        data = json.loads(response.text)
        assert 'metrics' in data
        assert 'connectivity_tcp' in data['metrics']


class TestNetringRegistryCleanup:
    """Test member cleanup functionality."""
    
    @pytest.mark.asyncio
    async def test_cleanup_stale_members(self, mock_redis, sample_registry_config):
        """Test cleanup of stale members."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
            registry.redis_client = mock_redis
        finally:
            os.unlink(registry_config_path)
        
        current_time = time.time()
        stale_time = current_time - 400  # Older than TTL (300s)
        
        # Mock stale member
        stale_member = {
            'instance_id': 'stale-member',
            'location': 'us1-k8s',
            'ip': '10.1.1.1',
            'port': 8757,
            'registered_at': stale_time,
            'last_seen': stale_time
        }
        
        mock_redis.keys.return_value = [b'member:stale-member']
        mock_redis.hgetall.return_value = {
            k.encode(): json.dumps(v).encode() if not isinstance(v, (int, float)) else str(v).encode() 
            for k, v in stale_member.items()
        }
        
        with patch('time.time', return_value=current_time):
            await registry.cleanup_dead_members()
        
        # Should mark as offline
        mock_redis.hset.assert_called()
        call_args = mock_redis.hset.call_args[0]
        assert call_args[0] == 'member:stale-member'
        
        # Verify status was updated
        updated_data = json.loads(call_args[2])
        assert updated_data['status'] == 'offline'


class TestNetringRegistryEndpoints:
    """Test web endpoints."""
    
    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, sample_registry_config):
        """Test health check endpoint."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
        finally:
            os.unlink(registry_config_path)
        
        request = make_mocked_request('GET', '/health')
        response = await registry.health_check(request)
        
        assert response.status == 200
        data = json.loads(response.text)
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
    
    @pytest.mark.asyncio
    async def test_index_page(self, sample_registry_config):
        """Test index page endpoint."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
        finally:
            os.unlink(registry_config_path)
        
        request = make_mocked_request('GET', '/')
        
        # Mock file read - serve_index is a standalone function, not a method
        from registry.main import serve_index
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = '<html>Test</html>'
            response = await serve_index(request)
        
        assert response.status == 200
        assert response.content_type == 'text/html'


class TestNetringRegistryIntegration:
    """Integration tests for NetringRegistry."""
    
    @pytest.mark.asyncio
    async def test_init_app_success(self, mock_redis):
        """Test successful app initialization."""
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            result = await init_app(None)
        
        assert result is not None
        app, registry = result
        assert isinstance(app, web.Application)
        assert isinstance(registry, NetringRegistry)
        
        # Check routes are registered
        assert len(app.router.routes()) > 0
    
    @pytest.mark.asyncio
    async def test_member_lifecycle(self, mock_redis, sample_registry_config):
        """Test complete member lifecycle."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
            registry.redis_client = mock_redis
        finally:
            os.unlink(registry_config_path)
        
        # 1. Register member
        member_data = {
            'instance_id': 'lifecycle-test',
            'location': 'test-location',
            'ip': '10.1.1.1',
            'port': 8757
        }
        
        request = make_mocked_request('POST', '/register', json=member_data)
        request.json = AsyncMock(return_value=member_data)
        
        response = await registry.register_member(request)
        assert response.status == 200
        
        # 2. Send heartbeat
        mock_redis.hget.return_value = json.dumps({
            **member_data,
            'registered_at': time.time()
        }).encode()
        
        heartbeat_data = {'instance_id': 'lifecycle-test'}
        request = make_mocked_request('POST', '/heartbeat', json=heartbeat_data)
        request.json = AsyncMock(return_value=heartbeat_data)
        
        response = await registry.heartbeat(request)
        assert response.status == 200
        
        # 3. Deregister member
        request = make_mocked_request('POST', '/deregister', json=heartbeat_data)
        request.json = AsyncMock(return_value=heartbeat_data)
        
        response = await registry.deregister_member(request)
        assert response.status == 200


class TestNetringRegistryErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_redis_connection_error(self, sample_registry_config):
        """Test handling of Redis connection errors."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
        finally:
            os.unlink(registry_config_path)
        
        # Mock Redis connection failure
        mock_redis = AsyncMock()
        mock_redis.hset.side_effect = ConnectionError("Redis unavailable")
        registry.redis = mock_redis
        
        member_data = {
            'instance_id': 'test-member',
            'location': 'us1-k8s',
            'ip': '10.1.1.1',
            'port': 8757
        }
        
        request = make_mocked_request('POST', '/register', json=member_data)
        request.json = AsyncMock(return_value=member_data)
        
        response = await registry.register_member(request)
        
        assert response.status == 500
        data = json.loads(response.text)
        assert 'error' in data
    
    @pytest.mark.asyncio
    async def test_invalid_json_request(self, sample_registry_config):
        """Test handling of invalid JSON requests."""
        import tempfile
        import yaml
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_registry_config, f)
            registry_config_path = f.name
        
        try:
            registry = NetringRegistry(registry_config_path)
        finally:
            os.unlink(registry_config_path)
        
        request = make_mocked_request('POST', '/register')
        request.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
        
        response = await registry.register_member(request)
        
        assert response.status == 400
        data = json.loads(response.text)
        assert 'error' in data