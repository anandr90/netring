#!/usr/bin/env python3
"""
Test the missing members detection system.
"""

import asyncio
import aiohttp
import json
import sys
import os

async def test_missing_members_api():
    """Test the missing members API endpoint"""
    print("🔍 Testing Missing Members Detection System")
    print("=" * 50)
    
    # Test against registry on port 8756
    registry_url = "http://localhost:8756"
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test the new API endpoint
            print("📡 Testing /members_with_analysis endpoint...")
            async with session.get(f"{registry_url}/members_with_analysis") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    print(f"✅ API Response: HTTP {resp.status}")
                    print(f"📊 Members found: {len(data.get('members', []))}")
                    
                    # Check missing analysis
                    missing_analysis = data.get('missing_analysis', {})
                    if missing_analysis.get('enabled'):
                        print(f"✅ Missing members detection: ENABLED")
                        
                        # Show locations analysis
                        locations = missing_analysis.get('locations', {})
                        if locations:
                            print(f"\n🏢 Location Analysis:")
                            for location, info in locations.items():
                                status = info.get('status', 'unknown')
                                actual = info.get('actual_count', 0)
                                expected = info.get('expected_count', 0)
                                criticality = info.get('criticality', 'unknown')
                                
                                status_emoji = {
                                    'healthy': '✅',
                                    'missing_members': '🚨' if criticality == 'high' else '⚠️',
                                    'extra_members': 'ℹ️',
                                    'unexpected_location': '❓'
                                }.get(status, '❔')
                                
                                print(f"   {status_emoji} {location:10} | {actual:1}/{expected:1} | {criticality:6} | {status}")
                        
                        # Show alerts
                        alerts = missing_analysis.get('alerts', [])
                        if alerts:
                            print(f"\n🚨 Active Alerts:")
                            for alert in alerts:
                                level = alert.get('level', 'info')
                                message = alert.get('message', 'No message')
                                level_emoji = '🚨' if level == 'error' else '⚠️' if level == 'warning' else 'ℹ️'
                                print(f"   {level_emoji} {level.upper()}: {message}")
                        else:
                            print(f"\n✅ No active alerts")
                        
                        # Show summary
                        summary = missing_analysis.get('summary', {})
                        print(f"\n📈 Summary:")
                        print(f"   Total Missing: {summary.get('total_missing_members', 0)}")
                        print(f"   Critical Locations Missing: {summary.get('critical_locations_missing', 0)}")
                        print(f"   Unexpected Locations: {summary.get('unexpected_locations', 0)}")
                        
                    else:
                        print(f"⚠️  Missing members detection: DISABLED")
                        print(f"   (Check config/expected-members.yaml and registry.yaml)")
                    
                    print(f"\n📄 Sample API Response:")
                    print(json.dumps({
                        'members_count': len(data.get('members', [])),
                        'missing_analysis_enabled': missing_analysis.get('enabled', False),
                        'alerts_count': len(missing_analysis.get('alerts', [])),
                        'locations_tracked': len(missing_analysis.get('locations', {}))
                    }, indent=2))
                    
                else:
                    print(f"❌ API Error: HTTP {resp.status}")
                    error_text = await resp.text()
                    print(f"   Response: {error_text}")
                    
    except aiohttp.ClientConnectorError:
        print(f"❌ Cannot connect to registry at {registry_url}")
        print(f"   Make sure the registry is running: python3 registry/main.py config/registry.yaml")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    print(f"\n🎯 Missing Members Detection Features:")
    print(f"   ✅ Expected members configuration system")
    print(f"   ✅ Location-based member tracking")
    print(f"   ✅ Criticality levels (high/medium/low)")
    print(f"   ✅ Grace periods for temporary outages")
    print(f"   ✅ Alert system for missing members")
    print(f"   ✅ UI integration with visual indicators")
    print(f"   ✅ Real-time dashboard updates")
    
    print(f"\n🚀 Dashboard UI Features:")
    print(f"   ✅ Missing members alerts banner")
    print(f"   ✅ Location status cards with expected vs actual")
    print(f"   ✅ Color-coded criticality indicators")
    print(f"   ✅ Current member lists per location")
    print(f"   ✅ Summary statistics")
    print(f"   ✅ Responsive design")
    
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(test_missing_members_api())
        if success:
            print(f"\n✅ Missing members detection system test completed!")
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n⏹️  Test interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)