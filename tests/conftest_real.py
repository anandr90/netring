"""Real service fixtures for integration testing."""

import pytest
import asyncio
import subprocess
import time
import tempfile
import yaml
import os
import signal
import socket
from pathlib import Path
import redis
import aiohttp
from aiohttp.test_utils import TestServer


def find_free_port():
    """Find a free port for testing."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


@pytest.fixture(scope="session")
def redis_server():
    """Start a real Redis server for testing."""
    redis_port = find_free_port()
    redis_url = f"redis://localhost:{redis_port}"
    
    # Start Redis server on test port
    redis_proc = subprocess.Popen([
        'redis-server',
        '--port', str(redis_port),
        '--save', '',  # Disable persistence
        '--appendonly', 'no',  # Disable AOF
        '--protected-mode', 'no',  # Allow connections
        '--loglevel', 'warning'  # Reduce noise
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Wait for Redis to start
    for _ in range(30):  # 3 second timeout
        try:
            r = redis.Redis(host='localhost', port=redis_port)
            r.ping()
            break
        except redis.ConnectionError:
            time.sleep(0.1)
    else:
        redis_proc.terminate()
        raise RuntimeError("Redis server failed to start")
    
    yield redis_url
    
    # Cleanup
    redis_proc.terminate()
    redis_proc.wait()


@pytest.fixture
def redis_client(redis_server):
    """Get a Redis client for the test Redis server."""
    port = int(redis_server.split(':')[-1])
    client = redis.Redis(host='localhost', port=port, decode_responses=True)
    
    # Clean up any existing data
    client.flushall()
    
    yield client
    
    # Clean up after test
    client.flushall()
    client.close()


@pytest.fixture
async def registry_server(redis_server, tmp_path):
    """Start a real registry service for testing."""
    redis_port = int(redis_server.split(':')[-1])
    registry_port = find_free_port()
    
    # Create registry config
    config = {
        'registry': {
            'redis': {
                'host': 'localhost',
                'port': redis_port,
                'db': 0,
                'password': None
            },
            'server': {
                'host': '127.0.0.1',
                'port': registry_port
            },
            'member_ttl': 60,
            'cleanup_interval': 10
        }
    }
    
    config_file = tmp_path / "registry_test.yaml"
    with open(config_file, 'w') as f:
        yaml.dump(config, f)
    
    # Import and start registry
    from registry.main import init_app
    app = await init_app(str(config_file))
    
    # Start registry server
    async with TestServer(app, port=registry_port) as server:
        registry_url = f"http://{server.host}:{server.port}"
        # Give it a moment to fully start
        await asyncio.sleep(0.1)
        yield registry_url


@pytest.fixture
def member_config(registry_server, tmp_path):
    """Create member configuration pointing to real registry."""
    registry_url = registry_server
    
    # Use environment variables (no config file for member)
    env_vars = {
        'NETRING_LOCATION': 'test-location',
        'NETRING_REGISTRY_URL': registry_url,
        'NETRING_POLL_INTERVAL': '1',  # Fast polling for tests
        'NETRING_CHECK_INTERVAL': '2',
        'NETRING_HEARTBEAT_INTERVAL': '1',
        'NETRING_TCP_TIMEOUT': '1',
        'NETRING_HTTP_TIMEOUT': '2',
        'NETRING_SERVER_HOST': '127.0.0.1',
        'NETRING_SERVER_PORT': str(find_free_port()),
        'NETRING_BANDWIDTH_TEST_INTERVAL': '5',
        'NETRING_TRACEROUTE_INTERVAL': '10'
    }
    
    return env_vars


@pytest.fixture
def member_instance(member_config):
    """Create a real member instance."""
    import os
    from unittest.mock import patch
    
    with patch.dict(os.environ, member_config, clear=False):
        from member.main import NetringMember
        member = NetringMember(None)  # Use environment variables
        yield member


@pytest.fixture
async def running_member(member_instance):
    """Create a member instance with HTTP session."""
    await member_instance.initialize_session()
    yield member_instance
    await member_instance.close_session()


@pytest.fixture
def sample_test_config():
    """Simple test configuration data."""
    return {
        'test_location': 'test-integration',
        'test_ip': '127.0.0.1',
        'test_timeout': 1.0
    }