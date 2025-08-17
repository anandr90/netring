#!/usr/bin/env python3
"""
Comprehensive test runner for Netring system.
Runs all unit tests, integration tests, and verification tests.
"""

import sys
import subprocess
import asyncio
from pathlib import Path

def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"\n🧪 {description}")
    print("-" * 50)
    
    result = subprocess.run(cmd, shell=True)
    if result.returncode == 0:
        print(f"✅ {description}: PASSED")
        return True
    else:
        print(f"❌ {description}: FAILED")
        return False

def main():
    """Run all tests"""
    project_root = Path(__file__).parent
    
    print("🚀 Netring Comprehensive Test Suite")
    print("=" * 50)
    
    tests_passed = 0
    tests_total = 0
    
    # 1. Unit Tests (Core Logic)
    tests_total += 1
    if run_command(
        f"{sys.executable} -m pytest tests/test_unit_logic.py -v",
        "Unit Tests (Core Logic)"
    ):
        tests_passed += 1
    
    # 2. Fault Tolerance Verification
    tests_total += 1
    if run_command(
        f"{sys.executable} tests/verify_fault_tolerance.py",
        "Fault Tolerance Verification"
    ):
        tests_passed += 1
    
    # 3. Missing Members Detection Tests
    tests_total += 1
    if run_command(
        f"{sys.executable} tests/test_missing_members.py",
        "Missing Members API Test"
    ):
        tests_passed += 1
    
    # 4. Comprehensive System Test
    tests_total += 1
    if run_command(
        f"{sys.executable} tests/test_comprehensive.py",
        "Comprehensive System Test"
    ):
        tests_passed += 1
    
    # 5. Final System Verification
    tests_total += 1
    if run_command(
        f"{sys.executable} tests/test_final_verification.py",
        "Final System Verification"
    ):
        tests_passed += 1
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUITE SUMMARY")
    print("=" * 50)
    print(f"Tests Passed: {tests_passed}/{tests_total}")
    
    if tests_passed == tests_total:
        print("🎉 ALL TESTS PASSED!")
        print("\n✅ System is ready for deployment")
        return True
    else:
        print(f"⚠️ {tests_total - tests_passed} test(s) failed")
        print("\n❌ Please review failures before deployment")
        return False

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️ Tests interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test runner failed: {e}")
        sys.exit(1)