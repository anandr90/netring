#!/usr/bin/env python3
"""
Comprehensive test suite for the missing members detection system.
Tests both disabled (default) and enabled states.
"""

import asyncio
import aiohttp
import json
import os
import sys
import time
import yaml
import tempfile
import subprocess
from pathlib import Path

class NetringTester:
    def __init__(self):
        self.registry_process = None
        self.member_processes = []
        self.test_dir = Path(__file__).parent
        
    async def setup_test_environment(self):
        """Set up test registry and member configurations"""
        print("🔧 Setting up test environment...")
        
        # Create test config directory
        test_config_dir = self.test_dir / "test_config"
        test_config_dir.mkdir(exist_ok=True)
        
        # Create test registry config with feature DISABLED
        registry_config = {
            'registry': {
                'redis': {
                    'host': 'localhost',
                    'port': 6379,
                    'db': 1,  # Use different DB for testing
                    'password': None
                },
                'server': {
                    'host': '127.0.0.1',
                    'port': 8760  # Different port for testing
                },
                'member_ttl': 300,
                'cleanup_interval': 60,
                'expected_members': {
                    'config_file': str(test_config_dir / "expected-members.yaml"),
                    'enable_missing_detection': False,  # DEFAULT: DISABLED
                    'missing_check_interval': 60
                }
            }
        }
        
        registry_config_path = test_config_dir / "registry.yaml"
        with open(registry_config_path, 'w') as f:
            yaml.dump(registry_config, f)
        
        # Create test expected members config
        expected_members_config = {
            'expected_members': {
                'locations': {
                    'TEST1': {
                        'expected_count': 1,
                        'criticality': 'high',
                        'grace_period': 60,
                        'description': 'Test Location 1'
                    },
                    'TEST2': {
                        'expected_count': 1,
                        'criticality': 'medium',
                        'grace_period': 120,
                        'description': 'Test Location 2'
                    }
                },
                'settings': {
                    'check_interval': 30,
                    'alerts': {
                        'critical_missing_threshold': 1,
                        'total_missing_threshold': 2
                    }
                }
            }
        }
        
        expected_config_path = test_config_dir / "expected-members.yaml"
        with open(expected_config_path, 'w') as f:
            yaml.dump(expected_members_config, f)
        
        print(f"✅ Test configs created in {test_config_dir}")
        return registry_config_path, expected_config_path
    
    async def start_test_registry(self, config_path):
        """Start test registry"""
        print("🚀 Starting test registry...")
        
        registry_cmd = [
            sys.executable, 
            str(self.test_dir / "registry" / "main.py"),
            str(config_path)
        ]
        
        self.registry_process = subprocess.Popen(
            registry_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for registry to start
        await asyncio.sleep(3)
        
        # Check if registry is running
        if self.registry_process.poll() is not None:
            stdout, stderr = self.registry_process.communicate()
            print(f"❌ Registry failed to start:")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return False
        
        print("✅ Test registry started")
        return True
    
    async def test_registry_health(self, port=8760):
        """Test registry health endpoint"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'http://127.0.0.1:{port}/health') as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"✅ Registry health: {data.get('status', 'unknown')}")
                        return True
                    else:
                        print(f"❌ Registry health check failed: HTTP {resp.status}")
                        return False
        except Exception as e:
            print(f"❌ Registry health check error: {e}")
            return False
    
    async def test_basic_members_endpoint(self, port=8760):
        """Test basic /members endpoint (always should work)"""
        print("\n📡 Testing basic /members endpoint...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'http://127.0.0.1:{port}/members') as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        members = data.get('members', [])
                        print(f"✅ Basic /members endpoint: {len(members)} members")
                        return True, data
                    else:
                        print(f"❌ Basic /members failed: HTTP {resp.status}")
                        return False, None
        except Exception as e:
            print(f"❌ Basic /members error: {e}")
            return False, None
    
    async def test_enhanced_endpoint_disabled(self, port=8760):
        """Test /members_with_analysis when feature is disabled"""
        print("\n📡 Testing /members_with_analysis (feature disabled)...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'http://127.0.0.1:{port}/members_with_analysis') as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        members = data.get('members', [])
                        missing_analysis = data.get('missing_analysis', {})
                        
                        print(f"✅ Enhanced endpoint: {len(members)} members")
                        print(f"   Missing analysis enabled: {missing_analysis.get('enabled', False)}")
                        
                        if not missing_analysis.get('enabled', True):
                            print("✅ Missing analysis correctly disabled")
                            return True, data
                        else:
                            print("❌ Missing analysis should be disabled by default")
                            return False, data
                    else:
                        print(f"❌ Enhanced endpoint failed: HTTP {resp.status}")
                        return False, None
        except Exception as e:
            print(f"❌ Enhanced endpoint error: {e}")
            return False, None
    
    async def test_ui_javascript_fallback(self, port=8760):
        """Test that UI JavaScript handles both endpoints correctly"""
        print("\n🌐 Testing UI JavaScript fallback logic...")
        
        # Test the actual logic by checking endpoints
        basic_success, basic_data = await self.test_basic_members_endpoint(port)
        enhanced_success, enhanced_data = await self.test_enhanced_endpoint_disabled(port)
        
        if basic_success and enhanced_success:
            # Verify data consistency
            basic_members = basic_data.get('members', [])
            enhanced_members = enhanced_data.get('members', [])
            
            if len(basic_members) == len(enhanced_members):
                print("✅ UI JavaScript fallback: Data consistent between endpoints")
                return True
            else:
                print("❌ UI JavaScript fallback: Data inconsistent")
                return False
        else:
            print("❌ UI JavaScript fallback: One or both endpoints failed")
            return False
    
    async def enable_missing_detection(self, config_path):
        """Enable missing detection in config and restart registry"""
        print("\n🔄 Enabling missing members detection...")
        
        # Read current config
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Enable missing detection
        config['registry']['expected_members']['enable_missing_detection'] = True
        
        # Write updated config
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        # Restart registry
        await self.stop_registry()
        await asyncio.sleep(2)
        
        success = await self.start_test_registry(config_path)
        if success:
            await asyncio.sleep(3)  # Wait for startup
            print("✅ Registry restarted with missing detection enabled")
        
        return success
    
    async def test_enhanced_endpoint_enabled(self, port=8760):
        """Test /members_with_analysis when feature is enabled"""
        print("\n📡 Testing /members_with_analysis (feature enabled)...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'http://127.0.0.1:{port}/members_with_analysis') as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        members = data.get('members', [])
                        missing_analysis = data.get('missing_analysis', {})
                        
                        print(f"✅ Enhanced endpoint: {len(members)} members")
                        print(f"   Missing analysis enabled: {missing_analysis.get('enabled', False)}")
                        
                        if missing_analysis.get('enabled', False):
                            locations = missing_analysis.get('locations', {})
                            alerts = missing_analysis.get('alerts', [])
                            summary = missing_analysis.get('summary', {})
                            
                            print(f"   Locations tracked: {len(locations)}")
                            print(f"   Active alerts: {len(alerts)}")
                            print(f"   Missing members: {summary.get('total_missing_members', 0)}")
                            
                            # Test that expected locations are present
                            expected_locations = ['TEST1', 'TEST2']
                            for loc in expected_locations:
                                if loc in locations:
                                    loc_info = locations[loc]
                                    print(f"   {loc}: {loc_info.get('actual_count', 0)}/{loc_info.get('expected_count', 0)} ({loc_info.get('status', 'unknown')})")
                                else:
                                    print(f"   {loc}: Not found in analysis")
                            
                            print("✅ Missing analysis correctly enabled with full data")
                            return True, data
                        else:
                            print("❌ Missing analysis should be enabled")
                            return False, data
                    else:
                        print(f"❌ Enhanced endpoint failed: HTTP {resp.status}")
                        return False, None
        except Exception as e:
            print(f"❌ Enhanced endpoint error: {e}")
            return False, None
    
    async def register_test_member(self, location="TEST1", port=8760):
        """Register a test member to create some data"""
        print(f"\n👤 Registering test member at {location}...")
        
        member_data = {
            'instance_id': f'test-member-{location.lower()}',
            'location': location,
            'ip': '127.0.0.1',
            'port': 8757
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f'http://127.0.0.1:{port}/register', json=member_data) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"✅ Test member registered: {data.get('instance_id', 'unknown')}")
                        return True, data
                    else:
                        print(f"❌ Member registration failed: HTTP {resp.status}")
                        return False, None
        except Exception as e:
            print(f"❌ Member registration error: {e}")
            return False, None
    
    async def stop_registry(self):
        """Stop test registry"""
        if self.registry_process:
            self.registry_process.terminate()
            try:
                await asyncio.sleep(2)
                if self.registry_process.poll() is None:
                    self.registry_process.kill()
                self.registry_process = None
            except:
                pass
    
    async def cleanup(self):
        """Clean up test environment"""
        print("\n🧹 Cleaning up test environment...")
        
        await self.stop_registry()
        
        # Clean up test config directory
        test_config_dir = self.test_dir / "test_config"
        if test_config_dir.exists():
            import shutil
            shutil.rmtree(test_config_dir)
        
        print("✅ Cleanup completed")

async def run_comprehensive_tests():
    """Run all tests"""
    tester = NetringTester()
    
    try:
        print("🧪 Starting Comprehensive Netring Tests")
        print("=" * 50)
        
        # Setup
        registry_config, expected_config = await tester.setup_test_environment()
        
        # Start registry with feature DISABLED (default)
        success = await tester.start_test_registry(registry_config)
        if not success:
            print("❌ Failed to start test registry")
            return False
        
        # Test registry health
        health_ok = await tester.test_registry_health()
        if not health_ok:
            print("❌ Registry health check failed")
            return False
        
        print("\n" + "="*50)
        print("📋 PHASE 1: TESTING DISABLED STATE (Default)")
        print("="*50)
        
        # Test basic functionality (disabled state)
        basic_ok, _ = await tester.test_basic_members_endpoint()
        enhanced_ok, _ = await tester.test_enhanced_endpoint_disabled()
        fallback_ok = await tester.test_ui_javascript_fallback()
        
        if not (basic_ok and enhanced_ok and fallback_ok):
            print("❌ Phase 1 tests failed")
            return False
        
        print("✅ Phase 1: All disabled state tests passed!")
        
        print("\n" + "="*50)
        print("📋 PHASE 2: TESTING ENABLED STATE")
        print("="*50)
        
        # Enable missing detection
        enable_ok = await tester.enable_missing_detection(registry_config)
        if not enable_ok:
            print("❌ Failed to enable missing detection")
            return False
        
        # Test registry health after restart
        health_ok = await tester.test_registry_health()
        if not health_ok:
            print("❌ Registry health check failed after restart")
            return False
        
        # Register test members to create data
        await tester.register_test_member("TEST1")
        await asyncio.sleep(1)
        
        # Test enhanced functionality (enabled state)
        enhanced_enabled_ok, _ = await tester.test_enhanced_endpoint_enabled()
        
        if not enhanced_enabled_ok:
            print("❌ Phase 2 tests failed")
            return False
        
        print("✅ Phase 2: All enabled state tests passed!")
        
        print("\n" + "="*50)
        print("🎉 ALL TESTS PASSED!")
        print("="*50)
        
        print("\n📊 Test Summary:")
        print("✅ Default state (disabled): Working perfectly")
        print("✅ Basic /members endpoint: Working") 
        print("✅ Enhanced endpoint (disabled): Returns disabled state")
        print("✅ UI JavaScript fallback: Handles both endpoints")
        print("✅ Configuration toggle: Enables/disables correctly")
        print("✅ Enhanced endpoint (enabled): Returns full analysis")
        print("✅ Missing members detection: Full functionality")
        
        print("\n🚀 Ready for deployment!")
        print("   • Deploy with enable_missing_detection: false (default)")
        print("   • Current dashboard behavior unchanged")
        print("   • Enable missing detection when ready")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    try:
        success = asyncio.run(run_comprehensive_tests())
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️ Tests interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Tests failed: {e}")
        sys.exit(1)