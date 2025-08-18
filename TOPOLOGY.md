# Network Topology Analysis System

The Netring topology system provides real-time network topology visualization and analysis using NetworkX. It analyzes traceroute data from distributed members to build a comprehensive view of network paths, identify bottlenecks, and visualize network structure.

## Overview

The topology system consists of three main components:

1. **Data Collection**: Traceroute data from distributed Netring members
2. **Analysis Engine**: NetworkX-based graph analysis (`network_topology.py`)
3. **Visualization Interface**: Web-based topology dashboard with interactive controls

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Netring       │    │   Topology       │    │   Web           │
│   Members       │───▶│   Analyzer       │───▶│   Interface     │
│                 │    │                  │    │                 │
│ • Traceroutes   │    │ • NetworkX       │    │ • Stats Cards   │
│ • Hop data      │    │ • Graph analysis │    │ • Visualization │
│ • Latencies     │    │ • Bottlenecks    │    │ • Controls      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Core Components

### NetworkTopologyAnalyzer (`registry/network_topology.py`)

The main analysis engine that processes traceroute data and generates topology insights.

**Key Features:**
- **Graph Construction**: Builds NetworkX directed graph from traceroute hop data
- **Path Analysis**: Analyzes network paths between locations
- **Bottleneck Detection**: Identifies high-latency network segments
- **Visualization Generation**: Creates SVG network diagrams using matplotlib
- **Centrality Analysis**: Calculates node importance and connectivity metrics

**Core Methods:**
```python
def add_traceroute_data(traceroute_data, source_location, target_location)
def analyze_topology()
def generate_visualization()
def find_bottlenecks(latency_threshold=100)
def get_topology_summary()
```

### Data Flow

1. **Collection**: Members perform traceroutes to other ring members
2. **Processing**: Traceroute data sent to registry via `/report_metrics` endpoint
3. **Analysis**: `NetworkTopologyAnalyzer` processes hop-by-hop data
4. **Storage**: Results cached in Redis for fast retrieval
5. **Visualization**: Web interface displays real-time topology state

### API Endpoints

#### GET `/topology`
Returns complete topology analysis including graph data, summary statistics, and bottleneck information.

**Response Structure:**
```json
{
  "summary": {
    "total_locations": 5,
    "total_routers": 12,
    "total_edges": 24,
    "routes_analyzed": 20,
    "bottlenecks_found": 2,
    "locations": ["us1-k8s", "eu1-docker", "asia1-k8s"],
    "graph_density": 0.45,
    "strongly_connected": true
  },
  "topology": {
    "nodes": [...],
    "edges": [...]
  },
  "bottlenecks": [
    {
      "route": "192.168.1.1 → 203.0.113.1",
      "latency": 150.5,
      "severity": "medium",
      "description": "High latency detected"
    }
  ],
  "timestamp": 1734567890
}
```

#### GET `/topology/svg`
Returns SVG visualization of the network topology graph.

**Features:**
- Node positioning using spring layout algorithm
- Color-coded nodes by location/type
- Edge thickness representing connection quality
- Interactive hover information

#### GET `/topology/path`
Analyzes specific paths between locations.

**Query Parameters:**
- `source`: Source location identifier
- `target`: Target location identifier

## Web Interface

### Dashboard Components

#### 1. Header Section
- **Title**: "Network Topology Analysis"
- **Controls**: Refresh and Download SVG buttons
- **Styling**: Dark theme with colored action buttons

#### 2. Statistics Cards
Four metric cards displaying:
- **Locations**: Number of unique network locations
- **Routers**: Total intermediate routers discovered
- **Routes**: Number of analyzed network paths
- **Bottlenecks**: Count of detected performance issues

#### 3. Network Insights Panel
Horizontal panel showing:
- Bottleneck alerts and descriptions
- Network health status
- Performance recommendations

#### 4. Visualization Area
- **Interactive SVG Display**: Full-featured network graph with zoom/pan controls
- **Real Router IPs**: Shows actual IP addresses (e.g., `172.18.0.1`) instead of synthetic names
- **Color-coded Connections**: Green (good latency), yellow (medium), red (high latency)  
- **Professional Styling**: Dark theme with smooth animations and hover effects
- **No Data State**: Helpful placeholder when waiting for traceroute data
- **Loading States**: Progress indicators during data collection and analysis

### Interactive Features

#### Zoom and Pan Controls
The topology visualization includes full zoom and pan functionality:
- **Zoom Controls**: Click the green `+` button to zoom in (up to 3x) or red `−` button to zoom out (down to 0.3x)
- **Pan Navigation**: Click and drag anywhere on the topology to pan around the network
- **Cursor Feedback**: Cursor changes to "grab" when hovering, "grabbing" when dragging
- **Smooth Interactions**: All zoom and pan operations are smooth with proper bounds checking

#### Hover Effects and Tooltips
- **Interactive Nodes**: Hover over location nodes (blue circles) or router nodes (gray squares) for detailed information
- **Edge Information**: Hover over connection lines to see latency measurements
- **Smooth Animations**: Nodes scale and glow on hover without jittering
- **Real-time Data**: Tooltips show actual IP addresses and current latency values

#### Control Buttons
```javascript
async function refreshTopology() {
    // Fetches latest topology data
    // Updates statistics cards  
    // Regenerates visualization with current data
}

function downloadTopologySvg() {
    // Exports current topology as high-resolution SVG file
    // Preserves all styling, colors, and layout
    // Useful for documentation and presentations
}

async function clearRedisData() {
    // Clears all Redis data including members, metrics, and topology
    // Shows confirmation dialog for safety
    // Reports number of keys deleted and auto-reloads page
}
```

#### Dynamic Updates
- Statistics update automatically when new traceroute data arrives
- Visualization refreshes to show topology changes
- Bottleneck alerts appear/disappear based on current conditions

## Implementation Details

### Graph Data Structure

**Nodes**: Represent network endpoints (routers, servers, gateways)
```python
{
    "id": "192.168.1.1",
    "location": "us1-k8s", 
    "type": "router",
    "centrality": 0.75
}
```

**Edges**: Represent network connections with performance metrics
```python
{
    "source": "192.168.1.1",
    "target": "203.0.113.1", 
    "latency": 25.5,
    "packet_loss": 0.0,
    "path_count": 3
}
```

### Bottleneck Detection Algorithm

1. **Latency Analysis**: Identifies edges with >100ms latency
2. **Centrality Scoring**: Finds high-traffic bottleneck nodes
3. **Path Impact**: Measures effect on overall connectivity
4. **Severity Classification**: Categorizes issues (low/medium/high)

### Performance Optimizations

- **Caching**: Topology analysis results cached in Redis
- **Incremental Updates**: Only reprocess changed traceroute data
- **Lazy Loading**: SVG generation on-demand
- **Data Compression**: Efficient storage of graph structures

## Configuration

### Topology Analysis Settings

```yaml
topology:
  analysis_interval: 300  # seconds between analysis runs
  bottleneck_threshold: 100  # latency threshold in ms
  max_graph_size: 1000  # maximum nodes to prevent memory issues
  cache_ttl: 600  # topology cache lifetime in seconds
```

### Visualization Settings

```yaml
visualization:
  layout_algorithm: "spring"  # NetworkX layout algorithm
  node_size_range: [100, 500]  # min/max node sizes
  edge_width_range: [1, 5]  # line thickness range
  color_scheme: "location"  # node coloring strategy
```

## Data Requirements

### Minimum Data for Analysis
- **2+ locations** with active members
- **Successful traceroutes** between locations
- **Complete hop data** including IP addresses and latencies

### Optimal Conditions
- **5+ locations** for meaningful topology
- **Regular traceroute updates** (every 60 seconds)
- **Multiple paths** between location pairs
- **Stable network conditions** for accurate analysis

## Troubleshooting

### Common Issues

#### No Topology Data Available
**Causes:**
- Insufficient traceroute data from members
- All traceroutes failing due to network issues
- Members not reporting traceroute results

**Solutions:**
- Verify member connectivity and traceroute functionality
- Check Redis for stored traceroute data
- Review member logs for traceroute errors

#### Incomplete Visualization
**Causes:**
- Missing intermediate router information
- Inconsistent hop data between traceroutes
- NetworkX layout algorithm issues

**Solutions:**
- Increase traceroute frequency for better data quality
- Verify traceroute hop parsing logic
- Try different visualization layout algorithms

#### Performance Issues
**Causes:**
- Large network graphs (>500 nodes)
- Frequent topology recalculation
- Memory constraints during analysis

**Solutions:**
- Implement graph size limits
- Increase analysis intervals
- Optimize data structures and algorithms

## Development

### Adding New Analysis Features

1. **Extend NetworkTopologyAnalyzer**:
   ```python
   def custom_analysis(self):
       # Add new analysis method
       pass
   ```

2. **Update API Response**:
   ```python
   # Include new data in /topology endpoint
   ```

3. **Enhance Web Interface**:
   ```javascript
   // Add new visualization or statistics
   ```

### Testing Topology Analysis

```python
# Example test with sample data
analyzer = NetworkTopologyAnalyzer()
analyzer.add_traceroute_data(sample_traceroute, "us1", "eu1")
result = analyzer.analyze_topology()
assert result['summary']['total_locations'] == 2
```

## Future Enhancements

### Planned Features
- **Historical Analysis**: Track topology changes over time
- **Predictive Modeling**: Forecast potential network issues
- **Advanced Metrics**: Implement additional graph algorithms
- **3D Visualization**: Enhanced network representation
- **Real-time Updates**: WebSocket-based live topology updates

### Integration Opportunities
- **Alerting Systems**: Integrate with monitoring platforms
- **Network Planning**: Export data for capacity planning tools
- **Documentation**: Auto-generate network documentation
- **APIs**: Expose topology data for external systems

## Related Files

- `registry/network_topology.py` - Core analysis engine
- `registry/main.py` - API endpoints and integration
- `registry/static/app.js` - Frontend JavaScript functionality
- `registry/static/index.html` - Web interface structure
- `config/registry.yaml` - Configuration settings

## Dependencies

- **NetworkX**: Graph analysis and algorithms
- **Matplotlib**: SVG visualization generation
- **Redis**: Data caching and storage
- **aiohttp**: Web server and API endpoints
- **NumPy**: Numerical computations for graph analysis