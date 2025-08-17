# Missing Members Detection System (Optional Feature)

The Netring registry includes an optional missing members detection system that helps operations teams quickly identify when expected members are offline or missing.

**⚠️ This feature is DISABLED by default** to maintain the current dashboard behavior. Enable it when you're ready to set up expected member monitoring.

## 🚀 **Quick Enable**

To enable missing members detection:

1. **Edit config/registry.yaml:**
   ```yaml
   expected_members:
     enable_missing_detection: true  # Change from false to true
   ```

2. **Configure expected members in config/expected-members.yaml**

3. **Restart registry:**
   ```bash
   python3 registry/main.py config/registry.yaml
   ```

4. **Refresh dashboard** - you'll see the new "Expected Members Analysis" section

## 🎯 **Features**

### **1. Expected Members Configuration**
- Define which members should be online at each location
- Set criticality levels (high/medium/low) for different locations
- Configure grace periods for temporary disconnections
- Handle expected vs. unexpected locations

### **2. Visual UI Alerts**
- **Prominent alert banners** for critical missing members
- **Location status cards** showing expected vs. actual member counts
- **Color-coded indicators** based on criticality levels
- **Real-time dashboard updates** every 5 seconds

### **3. Smart Detection Logic**
- **Grace periods** prevent false alarms for brief disconnections
- **Criticality-based alerting** focuses attention on important locations
- **Historical context** to distinguish expected vs. unexpected locations

## 🔧 **Configuration**

### **Step 1: Configure Expected Members**
Edit `config/expected-members.yaml`:

```yaml
expected_members:
  locations:
    US1:
      expected_count: 1
      criticality: "high"      # high, medium, low
      grace_period: 300        # seconds before marking as missing
      description: "US East Coast Primary"
      
    EU1:
      expected_count: 1
      criticality: "high"
      grace_period: 300
      description: "Europe Primary"
      
    DEV:
      expected_count: 1
      criticality: "low"       # Dev environments are less critical
      grace_period: 900        # 15 minutes grace for dev
      description: "Development Environment"

  settings:
    check_interval: 60
    alerts:
      critical_missing_threshold: 1    # Alert if any high criticality missing
      total_missing_threshold: 3       # Alert if 3+ total missing
```

### **Step 2: Enable in Registry**
Update `config/registry.yaml`:

```yaml
registry:
  # ... existing config ...
  
  expected_members:
    config_file: "config/expected-members.yaml"
    enable_missing_detection: true
    missing_check_interval: 60
```

### **Step 3: Restart Registry**
```bash
python3 registry/main.py config/registry.yaml
```

## 📊 **Dashboard UI**

### **Missing Members Analysis Section**
When enabled, the dashboard shows a new section above the members list with:

1. **Alert Banners**
   - 🚨 **Critical alerts** (red) for high-priority locations missing members
   - ⚠️ **Warning alerts** (yellow) for medium-priority or multiple missing members

2. **Summary Statistics**
   - Total missing members across all locations
   - Number of critical locations with missing members
   - Count of unexpected locations

3. **Location Status Cards**
   - **Expected vs. Actual counts** (e.g., "1/2" means 1 actual, 2 expected)
   - **Criticality badges** showing high/medium/low priority
   - **Status indicators**:
     - ✅ Healthy (all expected members present)
     - 🚨 Missing members (high criticality)
     - ⚠️ Missing members (medium/low criticality)
     - ℹ️ Extra members (more than expected)
     - ❓ Unexpected location (not in config)

4. **Current Member Lists**
   - Shows which specific members are currently online at each location
   - Displays member IDs and IP addresses

## 🔄 **API Endpoints**

### **GET /members_with_analysis**
Enhanced members endpoint that includes missing members analysis:

```json
{
  "members": [
    {
      "instance_id": "abc123...",
      "location": "US1",
      "ip": "10.0.1.100",
      "status": "active",
      "last_seen": 1640995200
    }
  ],
  "missing_analysis": {
    "enabled": true,
    "timestamp": 1640995260,
    "alerts": [
      {
        "level": "error",
        "message": "High criticality location 'EU1' missing 1 member(s)",
        "location": "EU1",
        "missing_count": 1,
        "criticality": "high"
      }
    ],
    "locations": {
      "US1": {
        "expected_count": 1,
        "actual_count": 1,
        "missing_count": 0,
        "status": "healthy",
        "criticality": "high",
        "description": "US East Coast Primary",
        "current_members": [...]
      },
      "EU1": {
        "expected_count": 1,
        "actual_count": 0,
        "missing_count": 1,
        "status": "missing_members",
        "criticality": "high",
        "description": "Europe Primary",
        "current_members": []
      }
    },
    "summary": {
      "total_missing_members": 1,
      "critical_locations_missing": 1,
      "unexpected_locations": 0
    }
  }
}
```

## 🚨 **Alert Scenarios**

### **High Criticality Location Missing**
```
🚨 Critical: High criticality location 'EU1' missing 1 member(s)
```
- **Trigger**: Any high-criticality location missing expected members
- **Action**: Immediate investigation recommended

### **Multiple Members Missing**
```
⚠️ Warning: 3 total members missing across all locations
```
- **Trigger**: Configurable threshold (default: 3+ total missing)
- **Action**: Check for widespread connectivity issues

### **Unexpected Location**
```
❓ Unexpected location 'TEST2' detected with 1 member(s)
```
- **Trigger**: Member registers from location not in expected config
- **Action**: Verify if this is intentional or misconfiguration

## 🎨 **Visual Indicators**

### **Status Colors**
- 🟢 **Green**: All expected members healthy
- 🔴 **Red**: High-criticality locations missing members
- 🟡 **Yellow**: Medium/low-criticality missing or warnings
- 🔵 **Blue**: Informational (extra members, unexpected locations)

### **Criticality Badges**
- **HIGH**: Red badge, immediate attention required
- **MEDIUM**: Yellow badge, monitor closely
- **LOW**: Green badge, less urgent

### **Count Display**
- **"2/2"**: All expected members present (healthy)
- **"1/2"**: Missing 1 expected member
- **"3/2"**: 1 extra member beyond expected

## 🔧 **Troubleshooting**

### **Missing Analysis Not Showing**
1. Check `enable_missing_detection: true` in registry.yaml
2. Verify `config/expected-members.yaml` exists and is valid
3. Restart registry service
4. Check registry logs for configuration errors

### **No Alerts Despite Missing Members**
1. Check grace period settings - members may be within grace period
2. Verify criticality levels match alert thresholds
3. Check alert threshold settings in expected-members.yaml

### **False Alarms**
1. Increase grace period for locations with frequent brief disconnections
2. Lower criticality level for non-essential locations
3. Adjust alert thresholds to reduce noise

## 🚀 **Benefits for Operations Teams**

1. **Immediate Visibility**: Instantly see which locations are missing expected members
2. **Prioritized Alerts**: Focus on high-criticality locations first
3. **Reduced False Alarms**: Grace periods prevent alerts for brief disconnections
4. **Contextual Information**: Know exactly what's missing and where
5. **Trending Data**: Track patterns of member availability over time
6. **Proactive Monitoring**: Catch issues before they impact users

## 📈 **Future Enhancements**

- **Email/Slack notifications** for critical alerts
- **Historical trending** of member availability
- **Maintenance mode** to suppress alerts during planned outages
- **Auto-discovery** of expected member counts based on historical patterns
- **Integration** with external monitoring systems (PagerDuty, etc.)

---

This missing members detection system transforms the Netring dashboard from a passive monitoring tool into an active alerting system that helps operations teams maintain reliable connectivity monitoring across all datacenter locations.