"""Test configuration and fixtures for Netring tests."""

import pytest
import asyncio
import os
import tempfile
import yaml
from unittest.mock import Mock, AsyncMock
from aiohttp import web
from aiohttp.test_utils import TestServer, TestClient
import redis.asyncio as redis
from prometheus_client import REGISTRY


@pytest.fixture(autouse=True)
def clear_prometheus_registry():
    """Clear Prometheus registry before each test."""
    # Clear all registered collectors
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except KeyError:
            pass  # Collector was already unregistered


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.set = AsyncMock()
    redis_mock.get = AsyncMock()
    redis_mock.hset = AsyncMock()
    redis_mock.hget = AsyncMock()
    redis_mock.hgetall = AsyncMock()
    redis_mock.hdel = AsyncMock()
    redis_mock.keys = AsyncMock()
    redis_mock.expire = AsyncMock()
    redis_mock.close = AsyncMock()
    return redis_mock


@pytest.fixture
def sample_member_config():
    """Sample member configuration for testing."""
    return {
        'member': {
            'location': 'test-location',
            'instance_id': 'test-instance-123',
            'registry': {
                'url': 'http://test-registry:8756',
                'redis_host': 'test-redis',
                'redis_port': 6379,
                'redis_db': 0,
                'redis_password': None
            },
            'intervals': {
                'poll_interval': 30,
                'check_interval': 60,
                'heartbeat_interval': 45,
                'bandwidth_test_interval': 300,
                'traceroute_interval': 300
            },
            'server': {
                'host': '0.0.0.0',
                'port': 8757,
                'advertise_ip': 'auto'
            },
            'checks': {
                'tcp_timeout': 5,
                'http_timeout': 10,
                'http_endpoints': ['/health', '/metrics']
            },
            'tests': {
                'bandwidth_test_size_mb': 1
            }
        }
    }


@pytest.fixture
def sample_registry_config():
    """Sample registry configuration for testing."""
    return {
        'registry': {
            'redis': {
                'host': 'test-redis',
                'port': 6379,
                'db': 0,
                'password': None
            },
            'server': {
                'host': '0.0.0.0',
                'port': 8756
            },
            'member_ttl': 300,
            'cleanup_interval': 60
        }
    }


@pytest.fixture
def temp_config_file(sample_member_config):
    """Create a temporary configuration file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(sample_member_config, f)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    os.unlink(temp_path)


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp ClientSession."""
    session_mock = AsyncMock()
    
    # Mock response
    response_mock = AsyncMock()
    response_mock.status = 200
    response_mock.text = AsyncMock(return_value='{"status": "ok"}')
    response_mock.read = AsyncMock(return_value=b'0' * 1024 * 1024)  # 1MB test data
    response_mock.__aenter__ = AsyncMock(return_value=response_mock)
    response_mock.__aexit__ = AsyncMock(return_value=None)
    
    session_mock.get = AsyncMock(return_value=response_mock)
    session_mock.post = AsyncMock(return_value=response_mock)
    session_mock.close = AsyncMock()
    
    return session_mock


@pytest.fixture
def sample_members():
    """Sample member data for testing."""
    return {
        'member1': {
            'instance_id': 'test-member-1',
            'location': 'us1-k8s',
            'ip': '10.1.1.1',
            'port': 8757,
            'last_seen': 1629123456,
            'registered_at': 1629120000
        },
        'member2': {
            'instance_id': 'test-member-2',
            'location': 'eu1-k8s',
            'ip': '10.1.1.2',
            'port': 8757,
            'last_seen': 1629123456,
            'registered_at': 1629120000
        }
    }


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        'NETRING_LOCATION': 'test-env-location',
        'NETRING_REGISTRY_URL': 'http://test-env-registry:8756',
        'NETRING_POLL_INTERVAL': '30',
        'NETRING_CHECK_INTERVAL': '60',
        'NETRING_HEARTBEAT_INTERVAL': '45',
        'NETRING_TCP_TIMEOUT': '5',
        'NETRING_HTTP_TIMEOUT': '10',
        'NETRING_HTTP_ENDPOINTS': '/health,/metrics',
        'NETRING_SERVER_HOST': '0.0.0.0',
        'NETRING_SERVER_PORT': '8757',
        'NETRING_BANDWIDTH_TEST_INTERVAL': '300',
        'NETRING_TRACEROUTE_INTERVAL': '300',
        'NETRING_BANDWIDTH_TEST_SIZE_MB': '1'
    }
    
    # Store original values
    original_values = {}
    for key, value in env_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value
    
    yield env_vars
    
    # Restore original values
    for key, value in original_values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value