# Netring - Distributed Connectivity Monitor

A distributed network monitoring system that provides real-time connectivity testing between multiple datacenters or network locations.

## Quick Start

### 🚀 Basic Setup (Development)

1. **Clone and run locally:**
```bash
git clone <repository>
cd netring

# Start Redis
brew install redis && brew services start redis

# Install dependencies
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Start registry (central service)
python registry/main.py config/registry.yaml

# Start member (in another terminal)
python member/main.py config/member.yaml
```

2. **Check status:**
```bash
curl http://localhost:8756/health    # Registry health
curl http://localhost:8757/health    # Member health  
curl http://localhost:8756/members   # See all registered members
curl http://localhost:8757/metrics   # Prometheus metrics
```

### 🐳 Docker Deployment
```bash
# Using provided images
docker-compose up -d

# Or build your own
docker build -f docker/Dockerfile.registry -t netring/registry .
docker build -f docker/Dockerfile.member -t netring/member .
```

### ☸️ Kubernetes Deployment
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/registry-deployment.yaml
kubectl apply -f k8s/member-deployment.yaml
```

---

## 🆕 Latest Features (v1.3.0+)

### 🚀 **Advanced Network Diagnostics for Datacenter Admins**
**Comprehensive bottleneck identification and network performance analysis:**

```bash
cd deployment
./start.sh    # One command deployment with advanced diagnostics!
```

**🔥 NEW: Enterprise-Grade Monitoring Features:**
- ✅ **Periodic Bandwidth Testing** - 1MB tests every 5 minutes between all locations
- ✅ **Traceroute Analysis** - Hop-by-hop latency identification for bottleneck detection
- ✅ **Interactive Member Tooltips** - Hover stats with real-time performance metrics
- ✅ **Enhanced Admin Dashboard** - Professional UI with dedicated metric view buttons
- ✅ **Real-time Metrics Aggregation** - Push-based metrics collection system
- ✅ **Automatic host IP detection** - No manual IP configuration across datacenters
- ✅ **Environment variable configuration** - No more YAML config files required
- ✅ **Graceful shutdown** - Clean deregistration when containers stop

### 🎯 **Bandwidth Testing & Performance Analysis**
Automatically identifies network performance bottlenecks between datacenters:

```bash
# View bandwidth metrics in Prometheus format:
curl http://member:8757/metrics | grep bandwidth
# netring_bandwidth_mbps{source_location="US1",target_location="EU1"} 145.2

# Each member tests bandwidth to all other members every 5 minutes
# Configurable test size and intervals via environment variables
```

**Configuration:**
```yaml
environment:
  - NETRING_BANDWIDTH_TEST_INTERVAL=300     # 5 minutes (seconds)
  - NETRING_BANDWIDTH_TEST_SIZE_MB=1        # 1MB test size
  - NETRING_TRACEROUTE_INTERVAL=300         # 5 minutes (seconds)
```

### 🛣️ **Traceroute Analysis & Bottleneck Detection**
Identifies exactly where network latency bottlenecks occur:

```bash
# View traceroute metrics:
curl http://member:8757/metrics | grep traceroute
# netring_traceroute_hops_total{...} 8
# netring_traceroute_max_hop_latency_ms{...} 45.2

# Each traceroute provides:
# - Total hop count between locations
# - Maximum hop latency (identifies bottleneck point)
# - Complete hop-by-hop analysis for admin review
```

**Admin Benefits:**
- **Pinpoint Bottlenecks**: Identifies which network hop has highest latency
- **Historical Trends**: Track bandwidth degradation over time
- **Multi-Path Analysis**: Compare routes between different datacenter pairs
- **Proactive Monitoring**: Detect issues before users notice

### 🎨 **Professional Admin Dashboard**
Enhanced UI specifically designed for network administrators:

**Dedicated Metric View Buttons:**
- 🔗 **All** - Complete connectivity overview with all metrics
- 🔌 **TCP** - TCP connectivity tests only
- 🌐 **HTTP** - HTTP endpoint tests only  
- 📊 **Bandwidth** - Network throughput analysis (NEW!)
- 🛣️ **Traceroute** - Routing path analysis (NEW!)

**Interactive Member Tooltips (NEW v1.3.0!):**
- 🖱️ **Hover Stats** - Real-time performance metrics on member hover
- 📈 **Performance Data** - Average latency, success rates, bandwidth, hops
- ⏰ **Next Check Times** - Countdown to next connectivity/bandwidth/traceroute tests
- 🎯 **Smart Positioning** - Tooltips appear beside cards with screen-aware placement
- 💡 **Live Calculation** - Stats computed from current metrics data

**Advanced Filtering System:**
- 📍 **Source/Target Location** - Filter by specific datacenter pairs
- ⏱️ **Latency Thresholds** - Show only connections above/below latency limits  
- ⚠️ **Failure Analysis** - Focus on failed connections for troubleshooting
- 👁️ **Offline Visibility** - Include/exclude offline members from view
- 🔄 **Real-time Updates** - Auto-refresh with 5-second polling

**Enhanced UX:**
- Professional dark theme optimized for NOC environments
- Responsive design works on admin workstations and mobile devices
- Compact, informative hover tooltips on all controls

**Access Dashboard:** `http://registry:8756` (auto-updates with live metrics)

### 🎮 **Quick Demo: Latest Features**
Experience the enhanced functionality in your test environment:

```bash
# Start the enhanced test environment
docker-compose -f test-docker-compose.yml up -d

# Access the dashboard
open http://localhost:8756

# Test the new features:
# 1. Click "Bandwidth" button - See network throughput between Test1 ↔ Test2
# 2. Click "Traceroute" button - View routing paths and hop latencies  
# 3. Hover over member cards - See real-time performance tooltips
# 4. Use filters - Try source/target location filtering
```

**What You'll See:**
- **Member Tooltips**: Hover over Test1/Test2 cards for instant performance stats
- **Bandwidth Data**: Real-time throughput measurements (typically 400+ Mbps)
- **Traceroute Analysis**: Hop count and latency bottleneck identification
- **Live Updates**: Auto-refreshing data every 5 seconds

### Automatic IP Detection
Members automatically detect the correct host IP for cross-datacenter connectivity:

```bash
# The deployment script automatically:
# 1. Detects your host's LAN IP (e.g., 10.0.1.145)
# 2. Passes it to Docker containers via HOST_IP env var
# 3. Registers with the correct reachable IP

# Traditional way (manual):
HOST_IP=10.0.1.145 docker-compose up -d

# New way (automatic):
./start.sh
```

### Environment Variable Configuration
All configuration now possible via environment variables in `docker-compose.yml`:

```yaml
environment:
  - NETRING_LOCATION=US1                    # Datacenter identifier
  - NETRING_REGISTRY_URL=https://registry.company.com
  - NETRING_POLL_INTERVAL=30              # Member discovery frequency
  - NETRING_CHECK_INTERVAL=60             # Connectivity test frequency
  - NETRING_HEARTBEAT_INTERVAL=45         # Heartbeat frequency
  - HOST_IP=${HOST_IP}                     # Auto-detected host IP
```

### Graceful Shutdown & Deregistration
Containers cleanly remove themselves from the monitoring pool when stopped:

```bash
# When you run:
docker-compose down
# or: docker stop netring-member

# The container automatically:
# 1. Sends deregister request to registry
# 2. Removes itself from member pool
# 3. Updates UI status to "Deregistered"
# 4. Prevents false "down" alerts
```

### Enhanced Registry UI
New visual status indicators in the web interface at `http://registry:8756`:

- 🟢 **Online** - Active and responding
- 🟡 **Stale** - Active but not seen recently  
- 🔴 **Offline** - Inactive/timeout
- 🟣 **Deregistered** - Gracefully shut down

**Deregistered members show:**
- Purple status badge
- Deregistration timestamp
- Faded appearance with purple border
- Automatic cleanup after 1 hour

---

## Advanced Configuration

### Architecture Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   US1-K8s   │    │   EU1-K8s   │    │ ASIA1-Docker│
│             │    │             │    │             │
│ ┌─────────┐ │    │ ┌─────────┐ │    │ ┌─────────┐ │
│ │ Member  │ │    │ │ Member  │ │    │ │ Member  │ │
│ │ Service │◄┼────┼─┤ Service │◄┼────┼─┤ Service │ │
│ └─────────┘ │    │ └─────────┘ │    │ └─────────┘ │
│             │    │             │    │             │
│ ┌─────────┐ │    └─────────────┘    └─────────────┘
│ │Registry │ │           │                   │
│ │ Service │◄┼───────────┴───────────────────┘
│ └─────────┘ │    All members register with US1
│             │    and discover each other
└─────────────┘
    Central Registry
```

### Core Components

#### Registry Service (US1 Only)
- **Purpose**: Central coordination point for member discovery
- **Technology**: Python + Redis + aiohttp
- **Port**: 8756
- **Responsibilities**:
  - Member registration and heartbeat management
  - Member discovery API
  - Automatic cleanup of dead members
  - Health monitoring

#### Member Service (All Locations)
- **Purpose**: Connectivity testing and metrics collection
- **Technology**: Python + aiohttp + Prometheus client
- **Port**: 8756 (configurable)
- **Responsibilities**:
  - Register with central registry
  - Discover other ring members
  - Perform TCP/HTTP connectivity tests
  - Expose Prometheus metrics
  - Health endpoint

### Configuration Deep Dive

#### Registry Configuration (`config/registry.yaml`)
```yaml
registry:
  redis:
    host: "redis.us1.company.com"
    port: 6379
    db: 0
    password: null                    # Optional Redis auth
  
  server:
    host: "0.0.0.0"                  # Listen interface
    port: 8756                       # Registry API port
    
  member_ttl: 300                    # Member expiration (seconds)
  cleanup_interval: 60               # Cleanup frequency (seconds)
```

#### Member Configuration (`config/member.yaml`)
```yaml
member:
  # Location identifier - appears in all metrics labels
  location: "us1-k8s"               # Examples: "eu1-k8s", "asia1-docker"
  instance_id: null                 # Auto-generated UUID if null
  
  registry:
    # Central registry connection
    url: "http://registry.us1.company.com:8756"
    redis_host: "redis.us1.company.com"    # Direct Redis (unused)
    redis_port: 6379
    redis_db: 0
    redis_password: null
  
  intervals:
    poll_interval: 30               # Registry polling frequency
    check_interval: 60              # Connectivity test frequency  
    heartbeat_interval: 45          # Heartbeat frequency
  
  server:
    host: "0.0.0.0"                # Local server bind
    port: 8756                     # Health/metrics port
    
  checks:
    tcp_timeout: 5                 # TCP connection timeout
    http_timeout: 10               # HTTP request timeout
    http_endpoints:                # Endpoints to test
      - "/health"
      - "/metrics"
```

### Prometheus Metrics Reference

#### Connectivity Metrics
```promql
# TCP connectivity between locations (1=success, 0=failure)
netring_connectivity_tcp{
  source_location="us1-k8s",
  source_instance="uuid-123",
  target_location="eu1-k8s", 
  target_instance="uuid-456",
  target_ip="10.1.2.3"
} 1

# HTTP endpoint connectivity (1=success, 0=failure)  
netring_connectivity_http{
  source_location="us1-k8s",
  target_location="eu1-k8s",
  endpoint="/health",
  target_ip="10.1.2.3"
} 1
```

#### Performance Metrics
```promql
# Check duration histograms
netring_check_duration_seconds_bucket{
  check_type="tcp",
  target_location="eu1-k8s"
} 

# Bandwidth test results (NEW v1.3.0+)
netring_bandwidth_mbps{
  source_location="us1-k8s",
  target_location="eu1-k8s",
  target_ip="10.1.2.3"
} 415.7

# Traceroute analysis (NEW v1.3.0+)
netring_traceroute_hops_total{
  source_location="us1-k8s",
  target_location="eu1-k8s"
} 8

netring_traceroute_max_hop_latency_ms{
  source_location="us1-k8s", 
  target_location="eu1-k8s"
} 45.2

# Total discovered members
netring_members_total 5

# Member last seen timestamps  
netring_member_last_seen_timestamp{
  location="eu1-k8s",
  instance_id="uuid-456"
} 1629123456
```

### Production Deployment Strategies

#### Multi-Datacenter Setup

1. **US1 (Primary)**:
   ```bash
   # Deploy registry + member
   kubectl apply -f k8s/namespace.yaml
   kubectl apply -f k8s/redis-deployment.yaml  
   kubectl apply -f k8s/registry-deployment.yaml
   kubectl apply -f k8s/member-deployment.yaml
   ```

2. **EU1/ASIA1 (Secondary)**:
   ```bash
   # Deploy member only, update config:
   # - member.location: "eu1-k8s" 
   # - registry.url: "http://registry.us1.company.com:8756"
   kubectl apply -f k8s/namespace.yaml
   kubectl apply -f k8s/member-deployment.yaml
   ```

#### Docker Swarm/Standalone
```bash
# US1 (with registry)
docker run -d --name netring-registry \
  -p 8756:8756 \
  -v ./config:/app/config \
  harbor.rajasystems.com/library/netring-registry:latest

docker run -d --name netring-member \
  -p 8757:8756 \
  -v ./config:/app/config \
  harbor.rajasystems.com/library/netring-member:latest

# Other locations (member only)
docker run -d --name netring-member \
  -p 8756:8756 \
  -e MEMBER_LOCATION="eu1-docker" \
  -e REGISTRY_URL="http://registry.us1.company.com:8756" \
  harbor.rajasystems.com/library/netring-member:latest
```

### Monitoring & Alerting

#### Prometheus Configuration
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'netring'
    static_configs:
      - targets:
        - 'us1-member.company.com:8756'
        - 'eu1-member.company.com:8756' 
        - 'asia1-member.company.com:8756'
    metrics_path: '/metrics'
    scrape_interval: 30s
```

#### Grafana Dashboard Queries
```promql
# Connectivity matrix heatmap
netring_connectivity_tcp

# Failed connections  
netring_connectivity_tcp == 0

# Average latency by location
rate(netring_check_duration_seconds_sum[5m]) / 
rate(netring_check_duration_seconds_count[5m])

# Bandwidth trends (NEW v1.3.0+)
netring_bandwidth_mbps

# Bandwidth by datacenter pair
avg by (source_location, target_location) (netring_bandwidth_mbps)

# Traceroute hop analysis (NEW v1.3.0+) 
netring_traceroute_hops_total

# Network bottleneck identification
netring_traceroute_max_hop_latency_ms

# Member count over time
netring_members_total
```

#### Alerting Rules
```yaml
# alerts.yml
groups:
- name: netring
  rules:
  - alert: NetringConnectivityDown
    expr: netring_connectivity_tcp == 0
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "Connectivity failure between {{ $labels.source_location }} and {{ $labels.target_location }}"
      
  - alert: NetringMemberDown  
    expr: up{job="netring"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Netring member {{ $labels.instance }} is down"
      
  # NEW v1.3.0+ Bandwidth and Traceroute Alerts
  - alert: NetringLowBandwidth
    expr: netring_bandwidth_mbps < 100
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Low bandwidth detected: {{ $value }} Mbps between {{ $labels.source_location }} and {{ $labels.target_location }}"
      
  - alert: NetringHighLatencyHop
    expr: netring_traceroute_max_hop_latency_ms > 100
    for: 5m
    labels:
      severity: warning  
    annotations:
      summary: "High hop latency detected: {{ $value }}ms on route from {{ $labels.source_location }} to {{ $labels.target_location }}"
```

### API Reference

#### Registry Endpoints

**POST /register** - Register new member
```json
{
  "instance_id": "uuid-optional",
  "location": "us1-k8s", 
  "ip": "10.1.2.3",
  "port": 8756
}
```

**POST /heartbeat** - Update heartbeat
```json
{
  "instance_id": "uuid-123"
}
```

**POST /deregister** - Graceful member removal
```json
{
  "instance_id": "uuid-123"
}
```

**GET /members** - List active members
```json
{
  "members": [
    {
      "instance_id": "uuid-123",
      "location": "us1-k8s",
      "ip": "10.1.2.3", 
      "port": 8756,
      "last_seen": 1629123456,
      "registered_at": 1629120000
    }
  ]
}
```

#### Member Endpoints

**GET /health** - Health check
```json
{
  "status": "healthy",
  "instance_id": "uuid-123",
  "location": "us1-k8s",
  "members_count": 3,
  "timestamp": 1629123456.789
}
```

**GET /metrics** - Prometheus metrics (text format)

### Troubleshooting

#### Common Issues

1. **Members not discovering each other**:
   ```bash
   # Check registry connectivity
   curl http://registry.us1.company.com:8756/health
   
   # Verify member registration
   curl http://registry.us1.company.com:8756/members
   
   # Check member logs for heartbeat failures
   kubectl logs -f deployment/netring-member
   ```

2. **Connectivity checks showing failures**:
   ```bash
   # Test direct connectivity
   telnet target-ip 8756
   curl http://target-ip:8756/health
   
   # Check firewall rules between locations
   # Verify network policies in Kubernetes
   ```

3. **Redis connection issues**:
   ```bash
   # Test Redis connectivity from registry pod
   redis-cli -h redis.us1.company.com ping
   
   # Check Redis logs
   kubectl logs -f deployment/redis
   ```

#### Debug Mode
```bash
# Enable debug logging
export PYTHONPATH=/app
export LOG_LEVEL=DEBUG
python registry/main.py config/registry.yaml
```

### Security Considerations

- **Network**: Ensure ports 8756 (and Redis 6379) are accessible between locations
- **Authentication**: Consider adding API keys for registry access in production
- **TLS**: Add HTTPS support for registry communication over public networks
- **Firewall**: Whitelist only necessary IPs between datacenters

### Performance Tuning

- **Check intervals**: Adjust based on network latency requirements
- **Timeouts**: Increase for high-latency connections
- **Redis**: Tune memory and persistence settings for large deployments
- **Member TTL**: Balance between responsiveness and stability