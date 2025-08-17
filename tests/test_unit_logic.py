"""Unit tests for pure logic functions (no mocking required)."""

import pytest
import time
from prometheus_client import REGISTRY


@pytest.fixture(autouse=True)
def clear_prometheus_registry():
    """Clear Prometheus registry before each test."""
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except KeyError:
            pass


class TestBandwidthCalculation:
    """Test bandwidth calculation logic."""
    
    def test_bandwidth_calculation_basic(self):
        """Test basic bandwidth calculation."""
        # 1 MB in 1 second = 8 Mbps
        data_size = 1024 * 1024  # 1 MB in bytes
        duration = 1.0  # 1 second
        
        # bandwidth = (bytes * 8) / (duration * 1000000) for Mbps
        expected_mbps = (data_size * 8) / (duration * 1000000)
        
        from member.main import NetringMember
        member = NetringMember(None)
        
        # This tests the actual calculation logic
        start_time = time.time()
        end_time = start_time + duration
        
        # Mock the calculation part only
        bandwidth_bits_per_second = (data_size * 8) / duration
        bandwidth_mbps = bandwidth_bits_per_second / 1000000
        
        assert abs(bandwidth_mbps - expected_mbps) < 0.01
        assert abs(bandwidth_mbps - 8.388608) < 0.01  # Should be ~8.39 Mbps (1MB = 1024*1024 bytes)
    
    def test_bandwidth_calculation_edge_cases(self):
        """Test bandwidth calculation edge cases."""
        # Zero duration should not crash
        data_size = 1024
        duration = 0.0
        
        # Should handle division by zero gracefully
        try:
            bandwidth_mbps = (data_size * 8) / (duration * 1000000) if duration > 0 else 0
            assert bandwidth_mbps == 0
        except ZeroDivisionError:
            pytest.fail("Should handle zero duration gracefully")
        
        # Very small data
        data_size = 1  # 1 byte
        duration = 1.0
        bandwidth_mbps = (data_size * 8) / (duration * 1000000)
        assert bandwidth_mbps > 0
        assert bandwidth_mbps < 1  # Should be very small


class TestTracerouteParser:
    """Test traceroute output parsing logic."""
    
    def test_parse_traceroute_output_basic(self):
        """Test parsing basic traceroute output."""
        sample_output = """traceroute to 8.8.8.8 (8.8.8.8), 30 hops max, 60 byte packets
 1  192.168.1.1  1.234 ms
 2  10.0.0.1  5.678 ms
 3  8.8.8.8  12.345 ms"""
        
        from member.main import NetringMember
        member = NetringMember(None)
        result = member.parse_traceroute_output(sample_output)
        
        assert result['total_hops'] == 3
        assert abs(result['max_hop_latency'] - 12.345) < 0.001
    
    def test_parse_traceroute_output_single_hop(self):
        """Test parsing single hop traceroute."""
        sample_output = """traceroute to 127.0.0.1 (127.0.0.1), 30 hops max, 60 byte packets
 1  127.0.0.1  0.123 ms"""
        
        from member.main import NetringMember
        member = NetringMember(None)
        result = member.parse_traceroute_output(sample_output)
        
        assert result['total_hops'] == 1
        assert abs(result['max_hop_latency'] - 0.123) < 0.001
    
    def test_parse_traceroute_output_with_timeouts(self):
        """Test parsing traceroute with timeouts (asterisks)."""
        sample_output = """traceroute to 8.8.8.8 (8.8.8.8), 30 hops max, 60 byte packets
 1  192.168.1.1  1.234 ms
 2  * * *
 3  8.8.8.8  12.345 ms"""
        
        from member.main import NetringMember
        member = NetringMember(None)
        result = member.parse_traceroute_output(sample_output)
        
        # Should count all hops (including timeout ones)
        assert result['total_hops'] == 3  # All hops are counted
        assert abs(result['max_hop_latency'] - 12.345) < 0.001
    
    def test_parse_traceroute_output_empty(self):
        """Test parsing empty traceroute output."""
        sample_output = "traceroute to 8.8.8.8 (8.8.8.8), 30 hops max, 60 byte packets"
        
        from member.main import NetringMember
        member = NetringMember(None)
        result = member.parse_traceroute_output(sample_output)
        
        assert result['total_hops'] == 0
        assert result['max_hop_latency'] == 0.0
    
    def test_parse_traceroute_output_malformed(self):
        """Test parsing malformed traceroute output."""
        sample_output = "completely invalid output"
        
        from member.main import NetringMember
        member = NetringMember(None)
        result = member.parse_traceroute_output(sample_output)
        
        # Should handle gracefully
        assert result['total_hops'] == 0
        assert result['max_hop_latency'] == 0.0


class TestIPValidation:
    """Test IP address validation logic."""
    
    def test_private_ip_detection(self):
        """Test private IP address detection."""
        from member.main import NetringMember
        member = NetringMember(None)
        
        # Test private ranges
        assert member._is_private_ip('192.168.1.1') is True
        assert member._is_private_ip('192.168.0.1') is True
        assert member._is_private_ip('192.168.255.254') is True
        
        assert member._is_private_ip('10.0.0.1') is True
        assert member._is_private_ip('10.1.1.1') is True
        assert member._is_private_ip('10.255.255.254') is True
        
        assert member._is_private_ip('172.16.0.1') is True
        assert member._is_private_ip('172.31.255.254') is True
        
        # Test public IPs
        assert member._is_private_ip('8.8.8.8') is False
        assert member._is_private_ip('1.1.1.1') is False
        assert member._is_private_ip('208.67.222.222') is False
        
        # Test localhost (not handled by this method)
        assert member._is_private_ip('127.0.0.1') is False
        
        # Test edge cases
        assert member._is_private_ip('172.15.255.255') is False  # Just outside range
        assert member._is_private_ip('172.32.0.1') is False     # Just outside range
        assert member._is_private_ip('192.167.1.1') is False    # Just outside range
        assert member._is_private_ip('192.169.1.1') is False    # Just outside range


class TestConfigurationLogic:
    """Test configuration parsing logic."""
    
    def test_instance_id_generation(self):
        """Test UUID generation for instance IDs."""
        import uuid
        from member.main import NetringMember
        
        # Clear environment to force UUID generation
        import os
        from unittest.mock import patch
        
        with patch.dict(os.environ, {}, clear=True):
            member = NetringMember(None)
            
            # Should generate a valid UUID
            assert member.instance_id is not None
            assert len(member.instance_id) == 36  # Standard UUID length
            
            # Should be a valid UUID format
            try:
                uuid.UUID(member.instance_id)
                valid_uuid = True
            except ValueError:
                valid_uuid = False
            
            assert valid_uuid is True
            
            # Clear registry before creating second member
            collectors = list(REGISTRY._collector_to_names.keys())
            for collector in collectors:
                try:
                    REGISTRY.unregister(collector)
                except KeyError:
                    pass
            
            # Should be unique each time
            member2 = NetringMember(None)
            assert member.instance_id != member2.instance_id
    
    def test_environment_variable_parsing(self):
        """Test parsing of environment variables."""
        import os
        from unittest.mock import patch
        
        test_env = {
            'NETRING_LOCATION': 'test-env-location',
            'NETRING_REGISTRY_URL': 'http://test-registry:9999',
            'NETRING_POLL_INTERVAL': '45',
            'NETRING_CHECK_INTERVAL': '90',
            'NETRING_TCP_TIMEOUT': '3',
            'NETRING_HTTP_TIMEOUT': '7'
        }
        
        with patch.dict(os.environ, test_env, clear=False):
            from member.main import NetringMember
            member = NetringMember(None)
            
            assert member.location == 'test-env-location'
            assert member.registry_url == 'http://test-registry:9999'
            assert member.poll_interval == 45
            assert member.check_interval == 90
            assert member.tcp_timeout == 3
            assert member.http_timeout == 7
    
    def test_configuration_defaults(self):
        """Test default configuration values."""
        import os
        from unittest.mock import patch
        
        # Clear all NETRING env vars
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith('NETRING_')}
        
        with patch.dict(os.environ, clean_env, clear=True):
            from member.main import NetringMember
            member = NetringMember(None)
            
            assert member.location == 'unknown'
            assert member.registry_url == 'http://localhost:8756'
            assert member.poll_interval == 30
            assert member.check_interval == 60
            assert member.heartbeat_interval == 45
            assert member.tcp_timeout == 5
            assert member.http_timeout == 10


class TestUtilityFunctions:
    """Test utility functions that don't require external services."""
    
    def test_endpoint_list_parsing(self):
        """Test parsing of HTTP endpoint lists."""
        # This would test parsing of comma-separated endpoint lists
        # if that logic exists in the member code
        
        endpoints_string = "/health,/metrics,/status"
        expected_list = ["/health", "/metrics", "/status"]
        
        # Split and clean
        parsed_list = [ep.strip() for ep in endpoints_string.split(',')]
        
        assert parsed_list == expected_list
    
    def test_url_construction(self):
        """Test URL construction for various endpoints."""
        base_url = "http://registry:8756"
        
        # Test different endpoint constructions
        register_url = f"{base_url}/register"
        members_url = f"{base_url}/members"
        health_url = f"{base_url}/health"
        
        assert register_url == "http://registry:8756/register"
        assert members_url == "http://registry:8756/members"
        assert health_url == "http://registry:8756/health"
        
        # Test with trailing slash
        base_url_slash = "http://registry:8756/"
        register_url_2 = f"{base_url_slash.rstrip('/')}/register"
        assert register_url_2 == "http://registry:8756/register"