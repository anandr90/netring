# Netring - Distributed Connectivity Monitor

A distributed network monitoring system that provides real-time connectivity testing between multiple datacenters or network locations using a ring-based architecture.

## 🚀 Quick Start

### Using Docker (Recommended)
```bash
# Start complete test environment
docker-compose -f test-docker-compose.yml up -d

# Access dashboard
open http://localhost:8756
```

### Manual Setup
```bash
# Clone and setup
git clone <repository>
cd netring

# Install dependencies
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Start Redis
brew install redis && brew services start redis

# Start registry (central service)
python3 registry/main.py config/registry.yaml

# Start member (in another terminal)
python3 member/main.py config/member.yaml
```

### Quick Status Check
```bash
curl http://localhost:8756/health    # Registry health
curl http://localhost:8757/health    # Member health  
curl http://localhost:8756/members   # See all registered members
curl http://localhost:8757/metrics   # Prometheus metrics
```

## ✨ Features

### Core Monitoring
- **Real-time connectivity monitoring** between ring members
- **Multiple test types**: TCP, HTTP, bandwidth, traceroute  
- **Interactive web dashboard** with connectivity matrix
- **Automatic member discovery** via central registry
- **Prometheus metrics** integration

### Advanced Features (v1.2.0+)
- **🛡️ Fault-tolerant design** with resilient background tasks
- **📊 Bandwidth testing** (1MB tests every 5 minutes)
- **🛣️ Traceroute analysis** for bottleneck identification
- **🔍 Optional missing members detection** with alerting
- **💫 Interactive member tooltips** with real-time stats
- **🐳 Docker & Kubernetes support**

## 📁 Project Structure

```
netring/
├── member/           # Member node implementation
├── registry/         # Registry server with web dashboard
├── config/           # Configuration files
├── deployment/       # Docker Compose & K8s manifests
├── tests/            # Test suite
├── docs/             # Documentation
└── docker/           # Docker build files
```

## 🧪 Testing

```bash
# Run core unit tests
python3 run_tests.py unit

# Run comprehensive test suite  
python3 run_all_tests.py

# Verify fault tolerance
python3 tests/verify_fault_tolerance.py
```

## 📚 Documentation

- **[Fault Tolerance](docs/FAULT-TOLERANCE.md)** - Resilient background tasks and error handling
- **[Missing Members Detection](docs/MISSING-MEMBERS.md)** - Optional alerting for expected members
- **[Version History](docs/VERSION-HISTORY.md)** - Release notes and upgrade paths
- **[Testing Guide](docs/TESTING.md)** - Comprehensive testing approach
- **[Test Results](docs/TEST-RESULTS.md)** - Latest test verification results

## 🏗️ Architecture

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

- **Registry Service**: Central coordination (Python + Redis + aiohttp)
- **Member Service**: Connectivity testing (Python + aiohttp + Prometheus)
- **Web Dashboard**: Real-time visualization with interactive features
- **Redis Backend**: Member state and metrics storage

## 🔧 Configuration

### Environment Variables (Recommended)
```bash
export NETRING_LOCATION=US1
export NETRING_REGISTRY_URL=http://registry:8756
export NETRING_SERVER_PORT=8757
export NETRING_BANDWIDTH_TEST_INTERVAL=300  # 5 minutes
export NETRING_TRACEROUTE_INTERVAL=300      # 5 minutes
```

### Configuration Files
- `config/registry.yaml` - Registry server settings
- `config/member.yaml` - Member node settings (optional)
- `config/expected-members.yaml` - Expected members for alerting (optional)

## 📊 Dashboard Features

- **Real-time connectivity matrix** with status indicators
- **Performance metrics** (bandwidth, latency, traceroute)
- **Member health monitoring** with last seen timestamps
- **Optional missing members alerts** with location-based tracking
- **Interactive member tooltips** with detailed statistics

## 🛡️ Production Ready

- ✅ **Fault tolerance**: Background tasks resilient to network failures
- ✅ **Health monitoring**: Automatic dead task detection and restart
- ✅ **Graceful degradation**: Continues operation during outages
- ✅ **Zero-downtime deployment**: Backward compatible updates
- ✅ **Comprehensive testing**: Full test coverage verified

## 📊 Prometheus Metrics

### Connectivity Metrics
```promql
# TCP connectivity between locations (1=success, 0=failure)
netring_connectivity_tcp{
  source_location="us1-k8s",
  target_location="eu1-k8s",
  target_ip="10.1.2.3"
} 1

# HTTP endpoint connectivity  
netring_connectivity_http{
  source_location="us1-k8s",
  target_location="eu1-k8s",
  endpoint="/health"
} 1
```

### Performance Metrics
```promql
# Check duration histograms
netring_check_duration_seconds_bucket

# Bandwidth test results (v1.2.0+)
netring_bandwidth_mbps{
  source_location="us1-k8s",
  target_location="eu1-k8s"
} 415.7

# Traceroute analysis (v1.2.0+)
netring_traceroute_hops_total
netring_traceroute_max_hop_latency_ms

# Member tracking
netring_members_total 5
```

## 🚀 Deployment

### Multi-Datacenter Setup

**US1 (Primary with Registry):**
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/redis-deployment.yaml  
kubectl apply -f k8s/registry-deployment.yaml
kubectl apply -f k8s/member-deployment.yaml
```

**EU1/ASIA1 (Members Only):**
```bash
# Update member.location: "eu1-k8s" in config
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/member-deployment.yaml
```

### Docker Deployment
```bash
# Using production images
docker run -d --name netring-member \
  -p 8757:8757 \
  -e NETRING_LOCATION="us1-docker" \
  -e NETRING_REGISTRY_URL="http://registry.company.com:8756" \
  harbor.rajasystems.com/library/netring-member:latest
```

See `deployment/` directory for complete configurations.

## 📈 Monitoring Integration

### Prometheus Configuration
```yaml
scrape_configs:
  - job_name: 'netring'
    static_configs:
      - targets:
        - 'us1-member.company.com:8757'
        - 'eu1-member.company.com:8757'
    metrics_path: '/metrics'
    scrape_interval: 30s
```

### Alerting Rules
```yaml
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
      
  - alert: NetringLowBandwidth
    expr: netring_bandwidth_mbps < 100
    for: 5m
    labels:
      severity: warning
```

Perfect for integration with:
- **Prometheus** - Metrics collection and alerting
- **Grafana** - Advanced dashboards and visualization  
- **AlertManager** - Alert routing and notification
- **PagerDuty/Slack** - Incident response workflows

## 🔍 Troubleshooting

### Common Issues

**Members not discovering each other:**
```bash
# Check registry connectivity
curl http://registry.company.com:8756/health

# Verify member registration
curl http://registry.company.com:8756/members

# Check member logs
docker logs netring-member
```

**Connectivity checks failing:**
```bash
# Test direct connectivity
telnet target-ip 8757
curl http://target-ip:8757/health

# Check firewall rules between locations
```

**Debug Mode:**
```bash
export LOG_LEVEL=DEBUG
python3 registry/main.py config/registry.yaml
```

---

**Latest Release**: v1.1.9 with fault tolerance improvements and optional missing members detection system.