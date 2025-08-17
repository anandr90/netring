# Netring Documentation

This directory contains comprehensive documentation for the Netring distributed connectivity monitoring system.

## 📚 Documentation Index

### **Core System**
- **[README-DETAILED.md](../README-DETAILED.md)** - Complete system overview with advanced configuration
- **[Deployment Guide](../deployment/README.md)** - Docker Compose and Kubernetes deployment instructions
- **[Version History](VERSION-HISTORY.md)** - Release notes and upgrade paths

### **Advanced Features**
- **[Fault Tolerance](FAULT-TOLERANCE.md)** - Resilient background tasks and error handling
- **[Missing Members Detection](MISSING-MEMBERS.md)** - Optional alerting for expected members (disabled by default)

### **Testing & Verification**
- **[Testing Guide](TESTING.md)** - Comprehensive testing approach and realistic test philosophy
- **[Test Results](TEST-RESULTS.md)** - Latest comprehensive test verification results
- **[Testing Integration](TESTING-INTEGRATION.md)** - How testing is integrated into the build process

## 🎯 Quick Navigation

### **Getting Started**
1. Read the main [README.md](../README.md) for quick start
2. Follow [deployment instructions](../deployment/README.md)
3. Review [testing guide](TESTING.md) for verification

### **Production Deployment**
1. Study [fault tolerance documentation](FAULT-TOLERANCE.md)
2. Consider [missing members detection](MISSING-MEMBERS.md) for operational alerting
3. Review [test results](TEST-RESULTS.md) for deployment confidence

### **Development**
1. Set up local environment per main README
2. Run tests using instructions in [testing guide](TESTING.md)
3. Review [detailed system documentation](../README-DETAILED.md) for architecture

## 🔧 Configuration Quick Reference

### **Basic Setup (No Config Files Needed)**
```bash
export NETRING_LOCATION=US1
export NETRING_REGISTRY_URL=http://registry:8756
python3 member/main.py
```

### **Advanced Features**
- **Fault Tolerance**: Enabled by default (background task resilience)
- **Missing Members**: Disabled by default (set `enable_missing_detection: true` to enable)

## 🎉 Latest Features

- ✅ **Fault tolerance system** - Prevents task death during network outages
- ✅ **Missing members detection** - Optional alerting for expected members
- ✅ **Comprehensive testing** - Full test coverage with realistic approach
- ✅ **Zero-risk deployment** - Backward compatible with current functionality

---

**Note**: All new features are designed to be optional and backward compatible, ensuring safe deployment of updates.