# Netring Test Suite

This directory contains the complete test suite for the Netring distributed connectivity monitoring system.

## 🧪 Test Structure

### **Core Unit Tests**
- **`test_unit_logic.py`** - Pure logic tests (bandwidth calculation, traceroute parsing, etc.)
- **`conftest.py`** - Pytest configuration and shared fixtures

### **Integration Tests**
- **`test_real_integration.py`** - End-to-end tests using real Redis and HTTP servers
- **`conftest_real.py`** - Fixtures for real service testing

### **System Verification Tests**
- **`test_comprehensive.py`** - Complete system test (disabled/enabled states)
- **`test_final_verification.py`** - End-to-end system verification
- **`verify_fault_tolerance.py`** - Fault tolerance feature verification

### **Feature-Specific Tests**
- **`test_missing_members.py`** - Missing members detection API testing
- **`test_health_endpoint.py`** - Enhanced health endpoint testing
- **`test_fault_tolerance.py`** - Interactive fault tolerance demonstration

### **Legacy Tests** (Mock-based, kept for reference)
- **`test_member.py`** - Mock-based member tests
- **`test_registry.py`** - Mock-based registry tests
- **`test_integration.py`** - Mock-based integration tests

## 🚀 Running Tests

### **Quick Tests**
```bash
# Core unit tests only
python3 run_tests.py unit

# All tests including comprehensive system verification
python3 run_all_tests.py
```

### **Individual Test Categories**
```bash
# Unit tests (fast, no dependencies)
python3 -m pytest tests/test_unit_logic.py -v

# Fault tolerance verification
python3 tests/verify_fault_tolerance.py

# Missing members detection
python3 tests/test_missing_members.py

# Comprehensive system test
python3 tests/test_comprehensive.py
```

### **Integration Tests** (Require Redis)
```bash
# Real integration tests
python3 -m pytest tests/test_real_integration.py -v

# Real test runner
python3 run_real_tests.py
```

## 📊 Test Coverage

### **Unit Tests (13 tests)**
- ✅ Bandwidth calculation logic
- ✅ Traceroute output parsing
- ✅ IP validation functions
- ✅ Configuration handling
- ✅ Utility functions

### **System Tests**
- ✅ Default behavior (missing detection disabled)
- ✅ Enhanced behavior (missing detection enabled)
- ✅ API endpoint compatibility
- ✅ UI JavaScript fallback logic
- ✅ Configuration toggle functionality

### **Fault Tolerance Tests**
- ✅ Resilient task wrapper functionality
- ✅ Task health monitoring system
- ✅ Background task restart capability
- ✅ Exception handling robustness

## 🎯 Test Philosophy

Our testing approach emphasizes **realistic functionality** over mock-heavy isolation:

### **Realistic Tests**
- Test actual behavior with real services
- Use actual Redis and HTTP servers
- Verify end-to-end functionality
- Focus on integration points

### **Unit Tests**
- Test pure logic functions
- No mocking of core business logic
- Fast execution for development feedback
- Clear success/failure indicators

### **System Tests**
- Test complete workflows
- Verify backward compatibility
- Test optional feature enablement
- Validate production scenarios

## 🔧 Test Environment Setup

### **Prerequisites**
```bash
# Install test dependencies
pip install -r requirements.txt

# For integration tests, start Redis
redis-server
```

### **Test Configuration**
Tests use isolated configuration in `test_config/` directories to avoid interfering with development setup.

## 📋 Test Results Summary

Latest comprehensive test run results:

```
✅ Unit Tests: 13/13 passed
✅ Fault Tolerance: All features verified
✅ Missing Members (Disabled): Working perfectly
✅ Missing Members (Enabled): Full functionality
✅ System Integration: End-to-end verified
✅ Backward Compatibility: Maintained
```

## 🚨 When Tests Fail

### **Common Issues**
1. **Redis not running**: Start `redis-server` for integration tests
2. **Port conflicts**: Tests use different ports (8760, etc.)
3. **Missing dependencies**: Run `pip install -r requirements.txt`

### **Debugging**
```bash
# Run with verbose output
python3 -m pytest tests/test_unit_logic.py -v -s

# Check specific test
python3 tests/verify_fault_tolerance.py
```

## 🎉 Test Success Indicators

When all tests pass, you'll see:
- ✅ All unit tests passing
- ✅ Fault tolerance features working
- ✅ Missing members detection operational (when enabled)
- ✅ Backward compatibility maintained
- ✅ System ready for production deployment

This comprehensive test suite ensures confidence in deploying updates with zero risk to existing functionality.