"""Tests for the Netring member component."""

import pytest
import asyncio
import os
import time
import uuid
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from aiohttp import web, ClientTimeout, ClientSession
from aiohttp.test_utils import make_mocked_request
from aioresponses import aioresponses
import json

# Import the member module
import sys
sys.path.append('/Users/ar-admin/Desktop/netring')
from member.main import NetringMember, init_app


class TestNetringMemberConfig:
    """Test NetringMember configuration loading."""
    
    def test_config_from_file(self, temp_config_file):
        """Test loading configuration from YAML file."""
        member = NetringMember(temp_config_file)
        
        assert member.location == 'test-location'
        assert member.instance_id == 'test-instance-123'
        assert member.registry_url == 'http://test-registry:8756'
        assert member.poll_interval == 30
        assert member.check_interval == 60
        assert member.heartbeat_interval == 45
        assert member.tcp_timeout == 5
        assert member.http_timeout == 10
        assert member.http_endpoints == ['/health', '/metrics']
        assert member.server_host == '0.0.0.0'
        assert member.server_port == 8757
        assert member.bandwidth_test_interval == 300
        assert member.traceroute_interval == 300
        assert member.bandwidth_test_size_mb == 1
    
    def test_config_from_env_vars(self, mock_env_vars):
        """Test loading configuration from environment variables."""
        member = NetringMember(None)
        
        assert member.location == 'test-env-location'
        assert member.registry_url == 'http://test-env-registry:8756'
        assert member.poll_interval == 30
        assert member.check_interval == 60
        assert member.heartbeat_interval == 45
        assert member.tcp_timeout == 5
        assert member.http_timeout == 10
        assert member.http_endpoints == ['/health', '/metrics']
        assert member.server_host == '0.0.0.0'
        assert member.server_port == 8757
        assert member.bandwidth_test_interval == 300
        assert member.traceroute_interval == 300
        assert member.bandwidth_test_size_mb == 1
    
    def test_config_defaults(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {}, clear=True):
            member = NetringMember(None)
            
            assert member.location == 'unknown'
            assert member.registry_url == 'http://localhost:8756'
            assert member.poll_interval == 30
            assert member.check_interval == 60
            assert member.heartbeat_interval == 45
    
    def test_instance_id_generation(self):
        """Test automatic instance ID generation."""
        with patch.dict(os.environ, {}, clear=True):
            member = NetringMember(None)
            
            # Should generate a UUID
            assert member.instance_id is not None
            assert len(member.instance_id) == 36  # UUID format
            
            # Should be a valid UUID format
            import uuid
            try:
                uuid.UUID(member.instance_id)
                valid_uuid = True
            except ValueError:
                valid_uuid = False
            assert valid_uuid


class TestNetringMemberNetworkOps:
    """Test network operations of NetringMember."""
    
    @pytest.mark.asyncio
    async def test_register_with_registry_success(self, mock_env_vars, mock_aiohttp_session):
        """Test successful registration with registry."""
        member = NetringMember(None)
        member.session = mock_aiohttp_session
        
        # Mock successful registration response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value='{"status": "registered"}')
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.post.return_value = mock_response
        
        result = await member.register_with_registry()
        
        assert result is True
        mock_aiohttp_session.post.assert_called_once()
        call_args = mock_aiohttp_session.post.call_args
        assert call_args[0][0] == 'http://test-env-registry:8756/register'
    
    @pytest.mark.asyncio
    async def test_register_with_registry_failure(self, mock_env_vars, mock_aiohttp_session):
        """Test failed registration with registry."""
        member = NetringMember(None)
        member.session = mock_aiohttp_session
        
        # Mock failed registration response
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.post.return_value = mock_response
        
        result = await member.register_with_registry()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_poll_members_success(self, mock_env_vars, mock_aiohttp_session, sample_members):
        """Test successful member polling."""
        member = NetringMember(None)
        member.session = mock_aiohttp_session
        
        # Mock successful members response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=json.dumps({'members': list(sample_members.values())}))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.get.return_value = mock_response
        
        await member.poll_members()
        
        assert len(member.members) == 2
        assert 'test-member-1' in member.members
        assert 'test-member-2' in member.members
        assert member.members['test-member-1']['location'] == 'us1-k8s'
    
    @pytest.mark.asyncio
    async def test_test_tcp_connectivity_success(self, mock_env_vars):
        """Test successful TCP connectivity test."""
        member = NetringMember(None)
        
        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_socket.return_value = mock_sock
            mock_sock.connect_ex.return_value = 0  # Success
            
            result = await member.check_tcp_connectivity('10.1.1.1', 8757)
            
            assert result is True
            mock_sock.connect_ex.assert_called_once_with(('10.1.1.1', 8757))
    
    @pytest.mark.asyncio
    async def test_test_tcp_connectivity_failure(self, mock_env_vars):
        """Test failed TCP connectivity test."""
        member = NetringMember(None)
        
        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_socket.return_value = mock_sock
            mock_sock.connect_ex.return_value = 1  # Failure
            
            result = await member.check_tcp_connectivity('10.1.1.1', 8757)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_test_http_connectivity_success(self, mock_env_vars, mock_aiohttp_session):
        """Test successful HTTP connectivity test."""
        member = NetringMember(None)
        member.session = mock_aiohttp_session
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.get.return_value = mock_response
        
        result = await member.check_http_connectivity('10.1.1.1', 8757, '/health')
        
        assert result is True
        mock_aiohttp_session.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_test_http_connectivity_failure(self, mock_env_vars, mock_aiohttp_session):
        """Test failed HTTP connectivity test."""
        member = NetringMember(None)
        member.session = mock_aiohttp_session
        
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_aiohttp_session.get.return_value = mock_response
        
        result = await member.check_http_connectivity('10.1.1.1', 8757, '/health')
        
        assert result is False


class TestNetringMemberBandwidthTesting:
    """Test bandwidth testing functionality."""
    
    @pytest.mark.asyncio
    async def test_bandwidth_test_success(self, mock_env_vars):
        """Test successful bandwidth test."""
        member = NetringMember(None)
        
        # Create a real session for testing
        member.session = ClientSession()
        
        # Mock 1MB response data
        test_data = b'0' * (1024 * 1024)  # 1MB
        
        with aioresponses() as m:
            m.get('http://10.1.1.1:8757/bandwidth_test?size=1', 
                  body=test_data, status=200)
            
            # Mock time to ensure consistent test
            with patch('time.time', side_effect=[0, 1]):  # 1 second duration
                result = await member.test_bandwidth('10.1.1.1', 8757)
        
        await member.session.close()
        
        assert result is not None
        assert 7.5 <= result <= 8.5  # ~8 Mbps (1MB in 1 second), allow for overhead
    
    @pytest.mark.asyncio
    async def test_bandwidth_test_failure(self, mock_env_vars):
        """Test failed bandwidth test."""
        member = NetringMember(None)
        member.session = ClientSession()
        
        with aioresponses() as m:
            m.get('http://10.1.1.1:8757/bandwidth_test?size=1', 
                  status=404)
            
            result = await member.test_bandwidth('10.1.1.1', 8757)
        
        await member.session.close()
        assert result is None
    
    @pytest.mark.asyncio
    async def test_bandwidth_test_no_session(self, mock_env_vars):
        """Test bandwidth test without session."""
        member = NetringMember(None)
        member.session = None
        
        result = await member.test_bandwidth('10.1.1.1', 8757)
        
        assert result is None


class TestNetringMemberTraceroute:
    """Test traceroute functionality."""
    
    @pytest.mark.asyncio
    async def test_traceroute_success(self, mock_env_vars):
        """Test successful traceroute."""
        member = NetringMember(None)
        
        # Mock successful traceroute output
        mock_traceroute_output = """traceroute to 10.1.1.1 (10.1.1.1), 30 hops max, 60 byte packets
 1  gateway (192.168.1.1)  1.234 ms  1.567 ms  1.890 ms
 2  10.1.1.1 (10.1.1.1)  5.432 ms  5.678 ms  5.901 ms"""
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (mock_traceroute_output.encode(), b'')
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await member.run_traceroute('10.1.1.1')
        
        assert result is not None
        assert result['total_hops'] == 2
        assert abs(result['max_hop_latency'] - 5.901) < 0.001  # Should find max latency
    
    @pytest.mark.asyncio
    async def test_traceroute_failure(self, mock_env_vars):
        """Test failed traceroute."""
        member = NetringMember(None)
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b'', b'Network unreachable')
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process
            
            result = await member.run_traceroute('10.1.1.1')
        
        assert result is None


class TestNetringMemberEndpoints:
    """Test web endpoints."""
    
    @pytest.mark.asyncio
    async def test_health_check_endpoint(self, mock_env_vars):
        """Test health check endpoint."""
        member = NetringMember(None)
        member.members = {'test': {}}
        
        request = make_mocked_request('GET', '/health')
        response = await member.health_check(request)
        
        assert response.status == 200
        data = json.loads(response.text)
        assert data['status'] == 'healthy'
        assert data['location'] == 'test-env-location'
        assert data['members_count'] == 1
        assert 'timestamp' in data
    
    @pytest.mark.asyncio
    async def test_bandwidth_test_endpoint(self, mock_env_vars):
        """Test bandwidth test endpoint."""
        member = NetringMember(None)
        
        # Test with default size
        request = make_mocked_request('GET', '/bandwidth_test')
        response = await member.bandwidth_test_endpoint(request)
        
        assert response.status == 200
        assert response.headers['Content-Type'] == 'application/octet-stream'
        assert int(response.headers['Content-Length']) == 1024 * 1024  # 1MB
    
    @pytest.mark.asyncio
    async def test_bandwidth_test_endpoint_custom_size(self, mock_env_vars):
        """Test bandwidth test endpoint with custom size."""
        member = NetringMember(None)
        
        # Mock request with query parameter
        from yarl import URL
        request = make_mocked_request('GET', '/bandwidth_test?size=2')
        request._url = URL('/bandwidth_test?size=2')
        
        response = await member.bandwidth_test_endpoint(request)
        
        assert response.status == 200
        assert int(response.headers['Content-Length']) == 2 * 1024 * 1024  # 2MB
    
    @pytest.mark.asyncio
    async def test_bandwidth_test_endpoint_max_size_limit(self, mock_env_vars):
        """Test bandwidth test endpoint with size limit."""
        member = NetringMember(None)
        
        # Mock request with large size (should be limited to 10MB)
        from yarl import URL
        request = make_mocked_request('GET', '/bandwidth_test?size=20')
        request._url = URL('/bandwidth_test?size=20')
        
        response = await member.bandwidth_test_endpoint(request)
        
        assert response.status == 200
        assert int(response.headers['Content-Length']) == 10 * 1024 * 1024  # Limited to 10MB


class TestNetringMemberMetrics:
    """Test Prometheus metrics functionality."""
    
    def test_metrics_initialization(self, mock_env_vars):
        """Test that Prometheus metrics are properly initialized."""
        member = NetringMember(None)
        
        # Check that metrics are created
        assert hasattr(member, 'connectivity_tcp')
        assert hasattr(member, 'connectivity_http')
        assert hasattr(member, 'ring_members_total')
        assert hasattr(member, 'member_last_seen')
        assert hasattr(member, 'bandwidth_mbps')
        assert hasattr(member, 'traceroute_hops')
        assert hasattr(member, 'traceroute_max_hop_latency')
    
    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, mock_env_vars):
        """Test metrics endpoint returns Prometheus format."""
        member = NetringMember(None)
        
        request = make_mocked_request('GET', '/metrics')
        response = await member.metrics_endpoint(request)
        
        assert response.status == 200
        assert response.content_type == 'text/plain; version=0.0.4; charset=utf-8'


class TestNetringMemberIPDetection:
    """Test IP address detection functionality."""
    
    def test_detect_advertise_ip_env_var(self, mock_env_vars):
        """Test IP detection from environment variable."""
        os.environ['HOST_IP'] = '192.168.1.100'
        
        member = NetringMember(None)
        ip = member._get_advertise_ip()
        
        assert ip == '192.168.1.100'
    
    def test_detect_advertise_ip_socket(self, mock_env_vars):
        """Test IP detection using socket connection."""
        # Remove HOST_IP if set
        if 'HOST_IP' in os.environ:
            del os.environ['HOST_IP']
        
        with patch('socket.socket') as mock_socket:
            mock_sock = Mock()
            mock_socket.return_value.__enter__.return_value = mock_sock
            mock_sock.getsockname.return_value = ('192.168.1.50', 12345)
            
            member = NetringMember(None)
            ip = member._get_advertise_ip()
        
        assert ip == '192.168.1.50'
    
    def test_is_private_ip(self, mock_env_vars):
        """Test private IP detection."""
        member = NetringMember(None)
        
        assert member._is_private_ip('192.168.1.1') is True
        assert member._is_private_ip('10.0.0.1') is True
        assert member._is_private_ip('172.16.0.1') is True
        assert member._is_private_ip('8.8.8.8') is False
        assert member._is_private_ip('1.1.1.1') is False


class TestNetringMemberIntegration:
    """Integration tests for NetringMember."""
    
    @pytest.mark.asyncio
    async def test_init_app_success(self, temp_config_file, mock_redis):
        """Test successful app initialization."""
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            with patch.object(NetringMember, 'register_with_registry', return_value=True):
                result = await init_app(temp_config_file)
        
        assert result is not None
        app, member = result
        assert isinstance(app, web.Application)
        assert isinstance(member, NetringMember)
    
    @pytest.mark.asyncio
    async def test_init_app_registration_failure(self, temp_config_file, mock_redis):
        """Test app initialization with registration failure."""
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            with patch.object(NetringMember, 'register_with_registry', return_value=False):
                result = await init_app(temp_config_file)
        
        assert result is None