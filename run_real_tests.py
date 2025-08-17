#!/usr/bin/env python3
"""Test runner for realistic Netring tests."""

import sys
import subprocess
import os
import shutil
from pathlib import Path


def check_redis_available():
    """Check if Redis is available for testing."""
    try:
        result = subprocess.run(['redis-server', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✓ Redis is available")
            return True
        else:
            print("✗ Redis is not available")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("✗ Redis is not available (redis-server not found)")
        return False


def install_dependencies():
    """Install test dependencies."""
    print("Installing test dependencies...")
    try:
        subprocess.run([
            sys.executable, '-m', 'pip', 'install', '--break-system-packages', '-r', 'requirements.txt'
        ], check=True, capture_output=True)
        print("✓ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install dependencies: {e}")
        print(f"stdout: {e.stdout.decode()}")
        print(f"stderr: {e.stderr.decode()}")
        return False


def run_unit_tests():
    """Run pure unit tests (no external services required)."""
    print("\\n" + "="*50)
    print("Running Unit Tests (Pure Logic)")
    print("="*50)
    
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            'tests/test_unit_logic.py',
            '-v', '--tb=short', '-m', 'not slow'
        ], capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print("✓ Unit tests passed")
            return True
        else:
            print("✗ Unit tests failed")
            return False
            
    except Exception as e:
        print(f"✗ Error running unit tests: {e}")
        return False


def run_integration_tests():
    """Run integration tests with real services."""
    print("\\n" + "="*50)
    print("Running Integration Tests (Real Services)")
    print("="*50)
    
    if not check_redis_available():
        print("❌ Redis is required for integration tests")
        print("Install Redis: brew install redis (macOS) or apt-get install redis-server (Ubuntu)")
        return False
    
    try:
        # Use conftest_real.py for fixtures
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            'tests/test_real_integration.py',
            '--confcutdir=tests',
            '-p', 'conftest_real',
            '-v', '--tb=short'
        ], capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print("✓ Integration tests passed")
            return True
        else:
            print("✗ Integration tests failed")
            return False
            
    except Exception as e:
        print(f"✗ Error running integration tests: {e}")
        return False


def run_all_real_tests():
    """Run all realistic tests."""
    print("\\n" + "="*50)
    print("Running All Realistic Tests")
    print("="*50)
    
    unit_success = run_unit_tests()
    
    if check_redis_available():
        integration_success = run_integration_tests()
    else:
        print("⚠️  Skipping integration tests (Redis not available)")
        integration_success = True  # Don't fail the build for missing Redis
    
    return unit_success and integration_success


def run_quick_check():
    """Run a quick smoke test."""
    print("\\n" + "="*50)
    print("Quick Smoke Test")
    print("="*50)
    
    try:
        # Just run a few basic unit tests
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            'tests/test_unit_logic.py::TestBandwidthCalculation::test_bandwidth_calculation_basic',
            'tests/test_unit_logic.py::TestTracerouteParser::test_parse_traceroute_output_basic',
            'tests/test_unit_logic.py::TestIPValidation::test_private_ip_detection',
            '-v'
        ], capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"✗ Error running quick check: {e}")
        return False


def main():
    """Main test runner."""
    print("Netring Realistic Test Runner")
    print("============================")
    
    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        
        if test_type == 'install':
            success = install_dependencies()
        elif test_type == 'unit':
            success = run_unit_tests()
        elif test_type == 'integration':
            success = run_integration_tests()
        elif test_type == 'all':
            success = install_dependencies() and run_all_real_tests()
        elif test_type == 'quick':
            success = run_quick_check()
        else:
            print(f"Unknown test type: {test_type}")
            print("Usage: python run_real_tests.py [install|unit|integration|all|quick]")
            sys.exit(1)
    else:
        # Default: run all tests
        print("Running full realistic test suite...")
        success = (
            install_dependencies() and
            run_all_real_tests()
        )
    
    if success:
        print("\\n🎉 All tests completed successfully!")
        sys.exit(0)
    else:
        print("\\n❌ Some tests failed")
        sys.exit(1)


if __name__ == '__main__':
    main()