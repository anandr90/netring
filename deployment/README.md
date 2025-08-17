# Netring Deployment - No Config Files Needed!

This deployment setup eliminates the need for config files by using environment variables and automatic IP detection.

## Quick Start

```bash
# One-command deployment (auto-detects host IP and starts)
./start.sh

# Or manually
./detect-host-ip.sh
docker-compose up -d

# Stop
docker-compose down
```

## What Changed

### ✅ Before (with config.yml):
- Required `config.yml` file with manual IP configuration
- Manual volume mounting
- Manual IP updates for each datacenter

### ✅ Now (environment variables only):
- **No config files needed!**
- All configuration via environment variables in `docker-compose.yml`
- Automatic host IP detection
- Zero manual configuration

## Configuration via Environment Variables

All settings from your `config.yml` are now environment variables in `docker-compose.yml`:

```yaml
environment:
  - NETRING_LOCATION=LNT                                    # was: member.location
  - NETRING_REGISTRY_URL=https://netring-reg.gss.consilio.com  # was: member.registry.url
  - NETRING_POLL_INTERVAL=30                               # was: member.intervals.poll_interval
  - NETRING_CHECK_INTERVAL=60                              # was: member.intervals.check_interval
  - NETRING_HEARTBEAT_INTERVAL=45                          # was: member.intervals.heartbeat_interval
  - NETRING_TCP_TIMEOUT=5                                  # was: member.checks.tcp_timeout
  - NETRING_HTTP_TIMEOUT=10                                # was: member.checks.http_timeout
  - NETRING_HTTP_ENDPOINTS=/health,/metrics                # was: member.checks.http_endpoints
  - NETRING_SERVER_HOST=0.0.0.0                           # was: member.server.host
  - NETRING_SERVER_PORT=8757                               # was: member.server.port
  - HOST_IP=${HOST_IP}                                     # auto-detected!
```

## Files You Can Delete

- ✅ `config.yml` - No longer needed!
- ✅ `member.yml` - No longer needed!

## Benefits

- 🎯 **Zero config files** - Everything in Docker Compose
- 🔄 **Automatic IP detection** - No manual IP configuration
- 📦 **Simpler deployment** - Just `./start.sh`
- 🌐 **Multi-datacenter ready** - Works across all your locations
- 🔧 **Easy customization** - Modify environment variables in `docker-compose.yml`

## How It Works

1. `detect-host-ip.sh` automatically finds your host's LAN IP
2. Creates `.env` file with `HOST_IP=your.detected.ip`
3. Docker Compose picks up the environment variable
4. Container uses environment variables instead of config files
5. Member registers with the correct cross-datacenter IP

Perfect for your production deployment across multiple datacenters!