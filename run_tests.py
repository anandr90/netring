#!/usr/bin/env python3
"""Test runner script for Netring project."""

import sys
import subprocess
import os
from pathlib import Path


def install_test_dependencies():
    """Install test dependencies if needed."""
    print("Installing test dependencies...")
    try:
        subprocess.run([
            sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'
        ], check=True, capture_output=True)
        print("✓ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install dependencies: {e}")
        print(f"stdout: {e.stdout.decode()}")
        print(f"stderr: {e.stderr.decode()}")
        return False


def run_unit_tests():
    """Run unit tests."""
    print("\n" + "="*50)
    print("Running Unit Tests (Pure Logic)")
    print("="*50)
    
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            'tests/test_unit_logic.py',
            '-v', '--tb=short'
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
    """Run integration tests."""
    print("\n" + "="*50)
    print("Running Integration Tests (Real Services)")
    print("="*50)
    
    try:
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


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*50)
    print("Running All Tests")
    print("="*50)
    
    try:
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            'tests/',
            '-v', '--tb=short', '--cov=member', '--cov=registry'
        ], capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print("✓ All tests passed")
            return True
        else:
            print("✗ Some tests failed")
            return False
            
    except Exception as e:
        print(f"✗ Error running all tests: {e}")
        return False


def run_test_summary():
    """Run a test summary with coverage."""
    print("\n" + "="*50)
    print("Test Summary")
    print("="*50)
    
    try:
        # Run tests with coverage
        result = subprocess.run([
            sys.executable, '-m', 'pytest', 
            'tests/',
            '--cov=member',
            '--cov=registry', 
            '--cov-report=term-missing',
            '--tb=line',
            '-q'
        ], capture_output=True, text=True)
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"✗ Error generating test summary: {e}")
        return False


def main():
    """Main test runner."""
    print("Netring Test Runner")
    print("==================")
    
    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        
        if test_type == 'install':
            success = install_test_dependencies()
        elif test_type == 'unit':
            success = run_unit_tests()
        elif test_type == 'integration':
            success = run_integration_tests()
        elif test_type == 'all':
            success = run_all_tests()
        elif test_type == 'summary':
            success = run_test_summary()
        else:
            print(f"Unknown test type: {test_type}")
            print("Usage: python run_tests.py [install|unit|integration|all|summary]")
            sys.exit(1)
    else:
        # Default: run all tests
        print("Running full test suite...")
        success = (
            install_test_dependencies() and
            run_unit_tests() and
            run_integration_tests() and
            run_test_summary()
        )
    
    if success:
        print("\n🎉 All tests completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)


if __name__ == '__main__':
    main()