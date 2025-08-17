# Netring Testing System

This document describes the realistic testing approach used in the Netring project, which focuses on testing actual functionality rather than mocked behavior.

## 🎯 Testing Philosophy

Our testing strategy prioritizes **real functionality over mocked behavior**:

- ✅ **Unit Tests**: Test pure logic functions without external dependencies
- ✅ **Integration Tests**: Test with real services (Redis + HTTP servers)
- ❌ **Mock-Heavy Tests**: Avoid testing implementation details or mocked responses

## 📁 Test Structure

```
tests/
├── conftest_real.py          # Fixtures for real services
├── test_unit_logic.py        # Pure logic tests (no mocking)
├── test_real_integration.py  # End-to-end tests with real services
├── run_real_tests.py         # Realistic test runner
└── (old mock tests)          # Legacy mock-heavy tests (deprecated)
```

## 🚀 Quick Start

### Run Unit Tests (Fast, No Dependencies)
```bash
python3 run_tests.py unit
# or
python3 run_real_tests.py unit
```

### Run Integration Tests (Requires Redis)
```bash
# Install Redis first
brew install redis  # macOS
# or
apt-get install redis-server  # Ubuntu

# Run integration tests
python3 run_real_tests.py integration
```

### Run All Tests
```bash
python3 run_real_tests.py all
```

## 🔧 Test Types

### 1. Unit Tests (`test_unit_logic.py`)

Tests pure logic functions without external dependencies:

- **Bandwidth calculation logic**
- **Traceroute output parsing**
- **IP address validation**
- **Configuration parsing**
- **UUID generation**

**Example:**
```python
def test_bandwidth_calculation_basic(self):
    """Test basic bandwidth calculation."""
    data_size = 1024 * 1024  # 1 MB
    duration = 1.0  # 1 second
    bandwidth_mbps = (data_size * 8) / (duration * 1000000)
    assert abs(bandwidth_mbps - 8.388608) < 0.01  # ~8.39 Mbps
```

**Characteristics:**
- ⚡ **Fast**: Run in ~0.03 seconds
- 🔄 **No Dependencies**: No Redis, no network, no external services
- ✅ **Reliable**: Always produce consistent results
- 🎯 **Focused**: Test specific logic, not integration

### 2. Integration Tests (`test_real_integration.py`)

Tests complete workflows with real services:

- **Real Redis server** (started by test fixtures)
- **Real registry HTTP server** (actual aiohttp server)
- **Real member instances** (actual network communication)
- **End-to-end data flows**

**Example:**
```python
async def test_member_registration_flow(self, registry_server, running_member, redis_client):
    """Test that member can register with real registry and data persists in Redis."""
    
    # Member registers with registry
    success = await running_member.register_with_registry()
    assert success
    
    # Verify registration in registry API
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{registry_server}/members") as resp:
            data = await resp.json()
            assert len(data['members']) == 1
            assert data['members'][0]['location'] == 'test-location'
    
    # Verify data is actually stored in Redis
    member_keys = redis_client.keys('netring:member:*')
    assert len(member_keys) == 1
```

**Characteristics:**
- 🔧 **Real Services**: Tests actual Redis + HTTP communication
- 🌐 **Network Testing**: Tests real TCP/HTTP connectivity
- 📊 **Data Persistence**: Verifies Redis storage and retrieval
- 🔄 **Full Workflows**: Tests complete member registration → discovery → metrics flow

## 🛠️ Test Infrastructure

### Real Service Fixtures (`conftest_real.py`)

Provides fixtures that start actual services for testing:

#### Redis Server Fixture
```python
@pytest.fixture(scope="session")
def redis_server():
    """Start a real Redis server for testing."""
    redis_port = find_free_port()
    redis_proc = subprocess.Popen(['redis-server', '--port', str(redis_port)])
    yield f"redis://localhost:{redis_port}"
    redis_proc.terminate()
```

#### Registry Server Fixture
```python
@pytest.fixture
async def registry_server(redis_server, tmp_path):
    """Start a real registry service for testing."""
    # Creates real config file
    # Starts actual aiohttp server
    # Returns real HTTP URL
```

#### Member Instance Fixture
```python
@pytest.fixture
def member_instance(member_config):
    """Create a real member instance."""
    # Uses environment variables (no config file)
    # Points to real registry server
    # Ready for actual network operations
```

### Test Runners

#### Main Test Runner (`run_tests.py`)
- **Used by `make release`**
- Runs unit tests for fast CI/CD validation
- Updated to use realistic unit tests

#### Realistic Test Runner (`run_real_tests.py`)
- Handles both unit and integration tests
- Checks for Redis availability
- Provides detailed test execution options

## 🔄 CI/CD Integration

### Make Release Integration

The testing system is **fully integrated** into your `make release` process:

```makefile
release: buildx-setup
	@echo "--> Installing test dependencies..."
	python3 -m pip install --break-system-packages -r requirements.txt
	@echo "--> Running tests before release..."
	python3 run_tests.py unit          # ← Tests run here
	@echo "--> Tests passed! Proceeding with release..."
	@echo "--> Creating git tag $(NEW_VERSION)..."
	# ... rest of release process
```

**Release Flow:**
1. Install dependencies
2. **Run unit tests** (fast, no external dependencies)
3. Only proceed if tests pass
4. Create git tag and build/push Docker images

### Why Unit Tests for Release?

- ⚡ **Fast**: Complete in seconds, don't slow down releases
- 🔒 **Reliable**: No external dependencies to fail
- ✅ **Meaningful**: Test actual logic that could break
- 🌍 **Universal**: Work in any CI/CD environment

## 📋 Test Commands Reference

### Basic Commands
```bash
# Fast unit tests (used in make release)
python3 run_tests.py unit

# Integration tests (requires Redis)
python3 run_real_tests.py integration

# All realistic tests
python3 run_real_tests.py all

# Quick smoke test
python3 run_real_tests.py quick
```

### Development Workflow
```bash
# 1. Check basic functionality
python3 run_real_tests.py quick

# 2. Run full unit test suite
python3 run_tests.py unit

# 3. Run integration tests (if Redis available)
python3 run_real_tests.py integration

# 4. Release (runs unit tests automatically)
make release
```

### Direct pytest Commands
```bash
# Run specific test file
python3 -m pytest tests/test_unit_logic.py -v

# Run specific test class
python3 -m pytest tests/test_unit_logic.py::TestBandwidthCalculation -v

# Run integration tests with real fixtures
python3 -m pytest tests/test_real_integration.py --confcutdir=tests -p conftest_real -v
```

## 🔍 Test Coverage

### Unit Tests Cover:
- ✅ Bandwidth calculation math
- ✅ Traceroute output parsing logic
- ✅ IP address validation rules
- ✅ Configuration loading and defaults
- ✅ UUID generation and validation
- ✅ URL construction utilities

### Integration Tests Cover:
- ✅ Member registration with registry
- ✅ Heartbeat and keep-alive functionality
- ✅ Member discovery and polling
- ✅ Bandwidth testing between services
- ✅ Network connectivity checks (TCP/HTTP)
- ✅ Metrics reporting and storage
- ✅ Graceful member deregistration
- ✅ Multi-member scenarios
- ✅ Error handling and recovery

## 🚨 Troubleshooting

### "Redis not available" Error
```bash
# Install Redis
brew install redis         # macOS
apt-get install redis-server  # Ubuntu

# Check Redis is working
redis-server --version
```

### "Prometheus registry conflicts"
- Unit tests automatically clear Prometheus registry between tests
- If you see conflicts, the `clear_prometheus_registry` fixture should handle it

### "Tests timing out"
- Integration tests may take longer due to real service startup
- Unit tests should complete in < 1 second

### "Port conflicts"
- Test fixtures automatically find free ports
- If you see port conflicts, restart the tests

## 🎯 Best Practices

### Writing New Tests

1. **Prefer Unit Tests** for logic validation
2. **Use Integration Tests** for workflow validation
3. **Avoid Mocking** real functionality
4. **Test Behavior**, not implementation details

### Test Naming
- `test_unit_logic.py` - Pure logic, no external services
- `test_real_integration.py` - Real services, end-to-end flows
- Use descriptive test method names

### Test Structure
```python
# Good: Tests actual behavior
def test_bandwidth_calculation_with_real_data(self):
    result = calculate_bandwidth(data_size=1MB, duration=1sec)
    assert result == expected_mbps

# Avoid: Tests mock behavior
def test_bandwidth_calculation_mock(self, mock_http):
    mock_http.return_value = mock_response
    # This tests the mock, not the real function
```

## 📈 Performance

- **Unit Tests**: ~0.03 seconds (13 tests)
- **Integration Tests**: ~2-5 seconds (depends on service startup)
- **Make Release**: ~1-2 seconds for testing step

## 🔮 Future Improvements

- [ ] Add performance benchmarking tests
- [ ] Add Docker-based integration tests
- [ ] Add property-based testing for edge cases
- [ ] Add contract testing for API endpoints
- [ ] Add chaos engineering tests for failure scenarios