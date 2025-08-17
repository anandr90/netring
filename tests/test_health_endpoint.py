#!/usr/bin/env python3
"""
Test the enhanced health endpoint with fault tolerance information.
"""

import asyncio
import aiohttp
import json
import time
import sys
import os

async def test_health_endpoint():
    """Test the enhanced health endpoint"""
    print("🏥 Testing Enhanced Health Endpoint")
    print("=" * 40)
    
    # Set environment for testing
    os.environ['NETRING_LOCATION'] = 'HEALTH_TEST'
    os.environ['NETRING_REGISTRY_URL'] = 'http://localhost:8756'  # Won't connect
    os.environ['NETRING_SERVER_PORT'] = '8760'  # Test port
    
    # Import and create app
    from member.main import init_app
    from aiohttp import web
    
    # Create test app (will fail registry registration, but that's ok for health test)
    print("⚙️  Creating test member...")
    
    try:
        result = await init_app()
        if result is None:
            # Expected to fail registry connection, let's create a member directly
            from member.main import NetringMember
            member = NetringMember()
            
            # Start just a few tasks for testing
            member.running_tasks = {}
            member.running_tasks["test_task"] = asyncio.create_task(
                member.resilient_task_wrapper("test_task", member._heartbeat_loop)
            )
            
            # Create simple app with health endpoint
            app = web.Application()
            app.router.add_get('/health', member.health_check)
            
            # Start server
            runner = web.AppRunner(app)
            await runner.setup()
            
            site = web.TCPSite(runner, '127.0.0.1', 8760)
            await site.start()
            
            print("✅ Test member started on port 8760")
            
            # Wait a moment for tasks to record heartbeats
            await asyncio.sleep(3)
            
            # Test health endpoint
            print("\n🔍 Testing health endpoint...")
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get('http://127.0.0.1:8760/health') as resp:
                        if resp.status == 200:
                            health_data = await resp.json()
                            
                            print(f"✅ Health endpoint responded: HTTP {resp.status}")
                            print(f"📊 Health Data:")
                            print(f"   Status: {health_data.get('status', 'unknown')}")
                            print(f"   Instance ID: {health_data.get('instance_id', 'unknown')}")
                            print(f"   Location: {health_data.get('location', 'unknown')}")
                            
                            # Check fault tolerance info
                            if 'fault_tolerance' in health_data:
                                ft = health_data['fault_tolerance']
                                print(f"   Task Timeout: {ft.get('task_timeout_seconds', 'unknown')}s")
                                print(f"   Monitor Interval: {ft.get('health_monitor_interval_seconds', 'unknown')}s")
                            
                            # Check task health
                            if 'task_health' in health_data:
                                print(f"\n🔋 Task Health:")
                                for task_name, task_info in health_data['task_health'].items():
                                    status = task_info.get('status', 'unknown')
                                    seconds_ago = task_info.get('seconds_since_heartbeat', 0)
                                    print(f"   {task_name:15} | {status:9} | {seconds_ago:.1f}s ago")
                            
                            # Check unhealthy tasks
                            unhealthy = health_data.get('unhealthy_tasks', [])
                            if unhealthy:
                                print(f"\n⚠️  Unhealthy tasks: {', '.join(unhealthy)}")
                            else:
                                print(f"\n✅ All tasks are healthy!")
                                
                            print(f"\n📄 Full Health Response:")
                            print(json.dumps(health_data, indent=2))
                            
                        else:
                            print(f"❌ Health endpoint failed: HTTP {resp.status}")
                            
                except Exception as e:
                    print(f"❌ Failed to connect to health endpoint: {e}")
            
            # Cleanup
            print(f"\n🧹 Cleaning up...")
            for task in member.running_tasks.values():
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            await runner.cleanup()
            print("✅ Health endpoint test completed!")
            
    except Exception as e:
        print(f"❌ Test setup failed: {e}")
        return

if __name__ == "__main__":
    try:
        asyncio.run(test_health_endpoint())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)