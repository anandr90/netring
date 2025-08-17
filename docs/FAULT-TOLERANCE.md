# Netring Fault Tolerance & Resilience

This document outlines the fault tolerance mechanisms in Netring and improvements needed for production reliability.

## 🎯 **Design Goals**

Netring is designed to monitor network connectivity between datacenters, which means it must remain operational even when:
- Registry is temporarily unavailable
- Network links between datacenters are degraded
- Individual members go offline
- Redis storage becomes inaccessible
- DNS resolution fails

## 🔍 **Current Fault Tolerance Status**

### ✅ **What Works Well**

#### **1. Individual Operation Failures**
- **TCP/HTTP Tests**: Timeouts prevent hanging (5s/10s)
- **Bandwidth Tests**: Failed tests return `None` gracefully
- **Traceroute Tests**: Process failures handled with `None` return
- **API Endpoints**: All endpoints have try/catch with proper HTTP error responses

#### **2. Registry Communication**
- **Registration Failures**: Members handle failed registration gracefully
- **Heartbeat Failures**: Logged but don't crash the service
- **Member Discovery**: Failed polling logged, service continues
- **Metrics Reporting**: Failed uploads logged as warnings

#### **3. Data Validation**
- **Configuration**: Defaults provided for missing values
- **Network Responses**: JSON parsing errors handled
- **Member Data**: Invalid member data filtered out

### ⚠️ **Critical Vulnerabilities**

#### **1. Background Task Death (HIGH SEVERITY)**
```python
# CURRENT VULNERABLE CODE:
async def heartbeat_task(self):
    while True:
        await self.send_heartbeat()  # ← Unhandled exception kills entire task
        await asyncio.sleep(self.heartbeat_interval)
```

**Impact**: If any background task throws an unhandled exception, that task dies permanently:
- **Heartbeat task dies** → Member appears offline in registry
- **Polling task dies** → Member never discovers new members  
- **Connectivity task dies** → No network monitoring happens
- **Metrics task dies** → No data gets reported

#### **2. No Recovery Mechanisms**
- **No exponential backoff** for failed registry operations
- **No circuit breaker** for persistent registry failures
- **No task health monitoring** to detect dead background tasks
- **No graceful degradation** when registry is offline for extended periods

#### **3. Resource Exhaustion Risks**
- **HTTP Sessions**: Could accumulate if not properly closed
- **DNS Lookups**: No caching or rate limiting
- **Log Spam**: Repeated failures could flood logs

## 🛠️ **Fault Tolerance Improvements**

### **Phase 1: Background Task Resilience (CRITICAL)**

#### **1.1 Exception Handling Wrappers**
Wrap all background tasks to prevent death from unhandled exceptions:

```python
async def resilient_task_wrapper(self, task_name: str, task_func, *args, **kwargs):
    """Wrapper that makes background tasks resilient to exceptions"""
    while True:
        try:
            await task_func(*args, **kwargs)
        except asyncio.CancelledError:
            logger.info(f"Task {task_name} cancelled, shutting down gracefully")
            break
        except Exception as e:
            logger.error(f"Task {task_name} error: {e}", exc_info=True)
            # Continue running instead of dying
            await asyncio.sleep(5)  # Brief pause before retry
```

#### **1.2 Task Health Monitoring**
Monitor background task health and restart dead tasks:

```python
class TaskHealthMonitor:
    def __init__(self):
        self.task_last_heartbeat = {}
        self.monitoring_interval = 60
    
    def record_task_heartbeat(self, task_name: str):
        self.task_last_heartbeat[task_name] = time.time()
    
    async def monitor_task_health(self):
        while True:
            current_time = time.time()
            for task_name, last_heartbeat in self.task_last_heartbeat.items():
                if current_time - last_heartbeat > 300:  # 5 minutes
                    logger.error(f"Task {task_name} appears dead, restarting...")
                    # Restart logic here
            await asyncio.sleep(self.monitoring_interval)
```

### **Phase 2: Network Resilience (HIGH PRIORITY)**

#### **2.1 Exponential Backoff**
Implement exponential backoff for registry operations:

```python
class ExponentialBackoff:
    def __init__(self, base_delay=1, max_delay=300, max_retries=5):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
    
    async def execute_with_backoff(self, operation, *args, **kwargs):
        for attempt in range(self.max_retries):
            try:
                result = await operation(*args, **kwargs)
                return result
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise e
                
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logger.warning(f"Operation failed (attempt {attempt+1}/{self.max_retries}), "
                             f"retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
```

#### **2.2 Circuit Breaker Pattern**
Prevent cascade failures when registry is persistently unavailable:

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=300, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, operation, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await operation(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
    
    def on_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
```

### **Phase 3: Graceful Degradation (MEDIUM PRIORITY)**

#### **3.1 Offline Mode**
When registry is unavailable, continue local operations:

```python
class OfflineMode:
    def __init__(self):
        self.is_offline = False
        self.last_successful_registry_contact = time.time()
        self.offline_threshold = 300  # 5 minutes
    
    def check_offline_status(self):
        if time.time() - self.last_successful_registry_contact > self.offline_threshold:
            if not self.is_offline:
                logger.warning("Entering offline mode - registry unavailable")
                self.is_offline = True
        else:
            if self.is_offline:
                logger.info("Exiting offline mode - registry available")
                self.is_offline = False
    
    def on_registry_success(self):
        self.last_successful_registry_contact = time.time()
```

#### **3.2 Local Member Cache**
Cache member list for offline operation:

```python
class MemberCache:
    def __init__(self, cache_ttl=3600):  # 1 hour
        self.cached_members = {}
        self.cache_timestamp = 0
        self.cache_ttl = cache_ttl
    
    def update_cache(self, members):
        self.cached_members = members
        self.cache_timestamp = time.time()
    
    def get_cached_members(self):
        if time.time() - self.cache_timestamp < self.cache_ttl:
            return self.cached_members
        return {}
    
    def is_cache_valid(self):
        return time.time() - self.cache_timestamp < self.cache_ttl
```

### **Phase 4: Resource Management (LOW PRIORITY)**

#### **4.1 Connection Pooling**
Manage HTTP connections efficiently:

```python
class ConnectionManager:
    def __init__(self, max_connections=10, connection_timeout=30):
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.session = None
    
    async def get_session(self):
        if not self.session or self.session.closed:
            connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                limit_per_host=5,
                keepalive_timeout=self.connection_timeout
            )
            timeout = aiohttp.ClientTimeout(total=self.connection_timeout)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout
            )
        return self.session
```

## 📊 **Failure Scenarios & Responses**

### **Scenario 1: Registry Temporarily Unavailable (5-30 minutes)**
**Current Behavior:**
- ❌ Heartbeat task may die on exception
- ❌ Member polling stops working
- ❌ Metrics reporting fails silently

**Improved Behavior:**
- ✅ Background tasks continue with exponential backoff
- ✅ Circuit breaker prevents resource waste
- ✅ Local operations continue (connectivity tests)
- ✅ Cache provides member list for testing

### **Scenario 2: Network Partition Between Datacenters**
**Current Behavior:**
- ✅ Connectivity tests correctly report failures
- ✅ Individual test timeouts prevent hanging
- ❌ May spam logs with connection failures

**Improved Behavior:**
- ✅ Rate-limited logging prevents log spam
- ✅ Exponential backoff reduces network load
- ✅ Circuit breaker prevents cascade failures

### **Scenario 3: Redis Database Failure**
**Current Behavior:**
- ✅ Registry returns 500 errors gracefully
- ❌ No member persistence during outage

**Improved Behavior:**
- ✅ Registry degrades gracefully to memory-only operation
- ✅ Background Redis reconnection attempts
- ✅ Data recovery when Redis returns

### **Scenario 4: Member Host Network Issues**
**Current Behavior:**
- ❌ Background tasks may die permanently
- ❌ Member becomes "zombie" (running but not functional)

**Improved Behavior:**
- ✅ Task health monitoring detects issues
- ✅ Automatic task restart mechanisms
- ✅ Health endpoint reflects actual operational status

## 🎯 **Implementation Priority**

### **Phase 1 (CRITICAL - COMPLETED ✅)**
1. ✅ Exception handling wrappers for all background tasks - **IMPLEMENTED**
2. ✅ Task health monitoring - **IMPLEMENTED**  
3. ✅ Graceful task restart mechanisms - **IMPLEMENTED**

**Implementation Details:**
- `resilient_task_wrapper()` method prevents task death from unhandled exceptions
- All 6 background tasks now use resilient wrappers instead of bare asyncio.create_task()
- Task health monitoring with configurable timeout (default: 5 minutes)
- Automatic dead task detection and restart capability
- Enhanced `/health` endpoint with task health information
- Graceful shutdown handling for task cancellation
- Comprehensive logging for debugging task issues

### **Phase 2 (HIGH PRIORITY)**
1. Exponential backoff for registry operations
2. Circuit breaker for registry connectivity
3. Offline mode with member caching

### **Phase 3 (MEDIUM PRIORITY)**
1. Connection pooling and resource management
2. Rate-limited logging
3. Enhanced health checks

### **Phase 4 (LOW PRIORITY)**
1. Metrics on fault tolerance effectiveness
2. Alerting on persistent failures
3. Performance optimizations

## 🔧 **Configuration Options**

Future fault tolerance features should be configurable:

```yaml
fault_tolerance:
  exponential_backoff:
    base_delay: 1          # seconds
    max_delay: 300         # seconds  
    max_retries: 5
  
  circuit_breaker:
    failure_threshold: 5   # failures before opening
    timeout: 300           # seconds circuit stays open
    recovery_timeout: 60   # seconds before retry
  
  task_monitoring:
    health_check_interval: 60  # seconds
    task_timeout: 300          # seconds before task considered dead
  
  offline_mode:
    registry_timeout: 300      # seconds before entering offline mode
    member_cache_ttl: 3600     # seconds to cache member list
  
  logging:
    error_rate_limit: 10       # max errors per minute before rate limiting
```

## 📈 **Success Metrics**

We should track these metrics to measure fault tolerance effectiveness:

- **Task Uptime**: Percentage of time each background task is running
- **Registry Availability**: Percentage of successful registry operations
- **Recovery Time**: Time to recover from various failure scenarios
- **Error Rates**: Frequency of different error types
- **Circuit Breaker Stats**: Open/close frequency and duration

## 🚨 **Known Limitations**

1. **Single Point of Failure**: Registry is still a single point of failure
2. **No Data Persistence**: Member-level metrics are not persisted locally
3. **Limited Offline Capability**: Cannot discover new members while offline
4. **No Mesh Networking**: Members cannot communicate directly without registry

These limitations should be addressed in future architectural improvements.