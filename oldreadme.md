A distributed system for monitoring connectivity between datacenters and office locations using a ring-based architecture. Each location runs a monitoring service that tests connectivity to all other locations and reports metrics via Prometheus.

Quick Start
🚀 Basic Setup (Development)
Clone and run locally:
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
Check status:
curl http://localhost:8756/health    # Registry health
curl http://localhost:8757/health    # Member health  
curl http://localhost:8756/members   # See all registered members
curl http://localhost:8757/metrics   # Prometheus metrics
🐳 Docker Deployment
# Using provided images
docker-compose up -d

# Or build your own
docker build -f docker/Dockerfile.registry -t netring/registry .
docker build -f docker/Dockerfile.member -t netring/member .
☸️ Kubernetes Deployment
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/redis-deployment.yaml
kubectl apply -f k8s/registry-deployment.yaml
kubectl apply -f k8s/member-deployment.yaml
Advanced Configuration
Architecture Overview
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
Core Components
Registry Service (US1 Only)
Purpose: Central coordination point for member discovery
Technology: Python + Redis + aiohttp
Port: 8756
Responsibilities:
Member registration and heartbeat management
Member discovery API
Automatic cleanup of dead members
Health monitoring
Member Service (All Locations)
Purpose: Connectivity testing and metrics collection
Technology: Python + aiohttp + Prometheus client
Port: 8756 (configurable)
Responsibilities:
Register with central registry
Discover other ring members
Perform TCP/HTTP connectivity tests
Expose Prometheus metrics
Health endpoint
Configuration Deep Dive
Registry Configuration (config/registry.yaml)
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
Member Configuration (config/member.yaml)
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
Prometheus Metrics Reference
Connectivity Metrics
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
Performance Metrics
# Check duration histograms
netring_check_duration_seconds_bucket{
  check_type="tcp",
  target_location="eu1-k8s"
} 

# Total discovered members
netring_members_total 5

# Member last seen timestamps  
netring_member_last_seen_timestamp{
  location="eu1-k8s",
  instance_id="uuid-456"
} 1629123456
Production Deployment Strategies
Multi-Datacenter Setup
US1 (Primary):

# Deploy registry + member
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/redis-deployment.yaml  
kubectl apply -f k8s/registry-deployment.yaml
kubectl apply -f k8s/member-deployment.yaml
EU1/ASIA1 (Secondary):

# Deploy member only, update config:
# - member.location: "eu1-k8s" 
# - registry.url: "http://registry.us1.company.com:8756"
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/member-deployment.yaml
Docker Swarm/Standalone
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
Monitoring & Alerting
Prometheus Configuration
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
Grafana Dashboard Queries
# Connectivity matrix heatmap
netring_connectivity_tcp

# Failed connections  
netring_connectivity_tcp == 0

# Average latency by location
rate(netring_check_duration_seconds_sum[5m]) / 
rate(netring_check_duration_seconds_count[5m])

# Member count over time
netring_members_total
Alerting Rules
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
API Reference
Registry Endpoints
POST /register - Register new member

{
  "instance_id": "uuid-optional",
  "location": "us1-k8s", 
  "ip": "10.1.2.3",
  "port": 8756
}
POST /heartbeat - Update heartbeat

{
  "instance_id": "uuid-123"
}
GET /members - List active members

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
Member Endpoints
GET /health - Health check

{
  "status": "healthy",
  "instance_id": "uuid-123",
  "location": "us1-k8s",
  "members_count": 3,
  "timestamp": 1629123456.789
}
GET /metrics - Prometheus metrics (text format)

Troubleshooting
Common Issues
Members not discovering each other:

# Check registry connectivity
curl http://registry.us1.company.com:8756/health

# Verify member registration
curl http://registry.us1.company.com:8756/members

# Check member logs for heartbeat failures
kubectl logs -f deployment/netring-member
Connectivity checks showing failures:

# Test direct connectivity
telnet target-ip 8756
curl http://target-ip:8756/health

# Check firewall rules between locations
# Verify network policies in Kubernetes
Redis connection issues:

# Test Redis connectivity from registry pod
redis-cli -h redis.us1.company.com ping

# Check Redis logs
kubectl logs -f deployment/redis
Debug Mode
# Enable debug logging
export PYTHONPATH=/app
export LOG_LEVEL=DEBUG
python registry/main.py config/registry.yaml
Security Considerations
Network: Ensure ports 8756 (and Redis 6379) are accessible between locations
Authentication: Consider adding API keys for registry access in production
TLS: Add HTTPS support for registry communication over public networks
Firewall: Whitelist only necessary IPs between datacenters
Performance Tuning
Check intervals: Adjust based on network latency requirements
Timeouts: Increase for high-latency connections
Redis: Tune memory and persistence settings for large deployments
Member TTL: Balance between responsiveness and stability