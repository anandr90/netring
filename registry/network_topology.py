#!/usr/bin/env python3
"""
Network Topology Analyzer for Netring
Analyzes traceroute data to build network topology graphs and identify bottlenecks
"""

import networkx as nx
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for server environments
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.offline as offline
import json
import logging
from typing import Dict, List, Optional, Tuple
import io
import base64

logger = logging.getLogger(__name__)


class NetworkTopologyAnalyzer:
    """Analyzes network topology from traceroute data using NetworkX"""
    
    def __init__(self):
        self.graph = nx.DiGraph()  # Directed graph for routing paths
        self.locations = set()
        self.traceroute_data = {}
        
    def clear_topology(self):
        """Clear existing topology data"""
        self.graph.clear()
        self.locations.clear()
        self.traceroute_data.clear()
        
    def add_traceroute_data(self, source_location: str, target_location: str, 
                           hops: List[Dict], bandwidth_mbps: Optional[float] = None):
        """Add traceroute data for a source-target pair"""
        
        # Store locations
        self.locations.add(source_location)
        self.locations.add(target_location)
        
        # Store raw traceroute data
        route_key = f"{source_location}->{target_location}"
        
        # Remove existing path for this route to avoid accumulation
        self._remove_path_from_graph(source_location, target_location)
        
        self.traceroute_data[route_key] = {
            'hops': hops,
            'bandwidth_mbps': bandwidth_mbps,
            'total_hops': len(hops),
            'max_hop_latency': max((hop.get('latency_ms', 0) for hop in hops), default=0)
        }
        
        # Add location nodes
        self.graph.add_node(source_location, node_type='location', location=source_location)
        self.graph.add_node(target_location, node_type='location', location=target_location)
        
        # Add path through network
        self._add_path_to_graph(source_location, target_location, hops)
    
    def _remove_path_from_graph(self, source: str, target: str):
        """Remove existing path between source and target to avoid accumulating old routes"""
        route_key = f"{source}->{target}"
        
        # Find and remove edges that belong to this specific route
        edges_to_remove = []
        for u, v, data in self.graph.edges(data=True):
            if data.get('route') == route_key:
                edges_to_remove.append((u, v))
        
        # Remove the edges
        for u, v in edges_to_remove:
            self.graph.remove_edge(u, v)
        
        # Remove router nodes that are no longer connected to anything
        nodes_to_remove = []
        for node, data in self.graph.nodes(data=True):
            if data.get('node_type') == 'router' and self.graph.degree(node) == 0:
                nodes_to_remove.append(node)
        
        for node in nodes_to_remove:
            self.graph.remove_node(node)
        
    def _add_path_to_graph(self, source: str, target: str, hops: List[Dict]):
        """Add a routing path to the graph"""
        
        if not hops:
            # Direct connection if no hops
            self.graph.add_edge(source, target, 
                              latency=0, 
                              edge_type='direct',
                              route=f"{source}->{target}")
            return
        
        # Add edges through hops
        prev_node = source
        
        for i, hop in enumerate(hops):
            hop_ip = hop.get('ip', f'unknown_{i}')
            hop_latency = hop.get('latency_ms', 0)
            
            # Skip timeout hops
            if hop_ip == '*' or hop_latency is None:
                continue
                
            # Create hop node ID
            hop_node_id = f"router_{hop_ip}"
            
            # Add router node
            self.graph.add_node(hop_node_id,
                              node_type='router',
                              ip=hop_ip,
                              hop_number=i + 1)
            
            # Add edge from previous node to this hop
            self.graph.add_edge(prev_node, hop_node_id,
                              latency=hop_latency,
                              edge_type='hop',
                              route=f"{source}->{target}",
                              hop_number=i + 1)
            
            prev_node = hop_node_id
        
        # Connect last hop to target
        if prev_node != source:  # Only if we actually have hops
            self.graph.add_edge(prev_node, target,
                              latency=0,  # Final hop to target
                              edge_type='final',
                              route=f"{source}->{target}")
    
    def find_bottlenecks(self, threshold_ms: float = 150.0) -> List[Dict]:
        """Find network bottlenecks above threshold latency"""
        bottlenecks = []
        
        for u, v, data in self.graph.edges(data=True):
            latency = data.get('latency', 0)
            if latency > threshold_ms:
                bottlenecks.append({
                    'from_node': u,
                    'to_node': v,
                    'latency_ms': latency,
                    'route': data.get('route', 'unknown'),
                    'hop_number': data.get('hop_number'),
                    'severity': 'high' if latency > 50 else 'medium'
                })
        
        # Sort by latency (worst first)
        bottlenecks.sort(key=lambda x: x['latency_ms'], reverse=True)
        return bottlenecks
    
    def get_path_analysis(self, source: str, target: str) -> Dict:
        """Get detailed analysis for a specific path"""
        route_key = f"{source}->{target}"
        
        if route_key not in self.traceroute_data:
            return {'error': f'No data for route {route_key}'}
        
        data = self.traceroute_data[route_key]
        
        # Find path in graph
        try:
            path = nx.shortest_path(self.graph, source, target)
            path_edges = []
            
            for i in range(len(path) - 1):
                edge_data = self.graph.get_edge_data(path[i], path[i + 1])
                if edge_data:
                    path_edges.append({
                        'from': path[i],
                        'to': path[i + 1],
                        'latency_ms': edge_data.get('latency', 0),
                        'hop_number': edge_data.get('hop_number')
                    })
        except nx.NetworkXNoPath:
            path = []
            path_edges = []
        
        return {
            'source': source,
            'target': target,
            'total_hops': data['total_hops'],
            'max_hop_latency': data['max_hop_latency'],
            'bandwidth_mbps': data.get('bandwidth_mbps'),
            'path_nodes': path,
            'path_edges': path_edges,
            'bottlenecks': [b for b in self.find_bottlenecks() if b['route'] == route_key]
        }
    
    def generate_topology_svg(self, width: int = 12, height: int = 8) -> str:
        """Generate interactive SVG visualization with hover effects and animations"""
        if self.graph.number_of_nodes() == 0:
            return self._create_empty_topology_svg()
        
        try:
            # Get interactive data for positioning
            data = self.get_interactive_topology_data()
            
            # Create interactive SVG with animations and hover effects
            svg_content = self._create_interactive_svg(data, width * 80, height * 60)
            return svg_content
            
        except Exception as e:
            print(f"Error generating interactive SVG: {e}")
            return self._create_empty_topology_svg()
    
    def _create_empty_topology_svg(self) -> str:
        """Create empty topology SVG with styled message"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="800" height="480" viewBox="0 0 800 480" xmlns="http://www.w3.org/2000/svg">
<rect width="100%" height="100%" fill="#0d1117"/>
<text x="400" y="240" text-anchor="middle" dominant-baseline="central"
      fill="#8b949e" font-family="system-ui" font-size="18">
    No topology data available - waiting for traceroute results...
</text>
<circle cx="400" cy="280" r="3" fill="#58a6ff" opacity="0.8">
    <animate attributeName="opacity" values="0.8;0.3;0.8" dur="2s" repeatCount="indefinite"/>
</circle>
</svg>'''
    
    def _create_interactive_svg(self, data, width: int = 960, height: int = 480) -> str:
        """Generate interactive SVG with hover effects, tooltips, and animations"""
        svg_parts = []
        
        # SVG header with styles and animations
        svg_parts.append(f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
<defs>
    <style>
        <![CDATA[
        .location-node {{
            fill: #58a6ff;
            stroke: #1f6feb;
            stroke-width: 3;
            cursor: pointer;
            transition: fill 0.2s ease, stroke 0.2s ease, stroke-width 0.2s ease, filter 0.2s ease, transform 0.2s ease;
            filter: drop-shadow(0 2px 4px rgba(88, 166, 255, 0.3));
            transform-origin: center;
        }}
        .location-node:hover {{
            fill: #79c0ff;
            stroke: #409dff;
            stroke-width: 4;
            filter: drop-shadow(0 4px 12px rgba(88, 166, 255, 0.6));
            transform: scale(1.1);
        }}
        .router-node {{
            fill: #656d76;
            stroke: #484f58;
            stroke-width: 2;
            cursor: pointer;
            transition: fill 0.2s ease, stroke 0.2s ease, stroke-width 0.2s ease, filter 0.2s ease, transform 0.2s ease;
            filter: drop-shadow(0 1px 3px rgba(101, 109, 118, 0.4));
            transform-origin: center;
        }}
        .router-node:hover {{
            fill: #8b949e;
            stroke: #656d76;
            stroke-width: 3;
            filter: drop-shadow(0 3px 8px rgba(101, 109, 118, 0.6));
            transform: scale(1.15);
        }}
        .edge-good {{
            stroke: #3fb950;
            stroke-width: 2.5;
            opacity: 0.8;
            transition: stroke 0.2s ease, stroke-width 0.2s ease, opacity 0.2s ease;
            cursor: pointer;
        }}
        .edge-good:hover {{
            stroke: #56d364;
            stroke-width: 4;
            opacity: 1;
        }}
        .edge-medium {{
            stroke: #d29922;
            stroke-width: 3;
            opacity: 0.85;
            transition: stroke 0.2s ease, stroke-width 0.2s ease, opacity 0.2s ease;
            cursor: pointer;
        }}
        .edge-medium:hover {{
            stroke: #f2cc60;
            stroke-width: 5;
            opacity: 1;
        }}
        .edge-bad {{
            stroke: #f85149;
            stroke-width: 4;
            opacity: 0.9;
            transition: stroke 0.2s ease, stroke-width 0.2s ease, opacity 0.2s ease;
            cursor: pointer;
            animation: pulse-red 3s infinite;
        }}
        .edge-bad:hover {{
            stroke: #ff7b72;
            stroke-width: 6;
            opacity: 1;
        }}
        .node-label {{
            fill: #f0f6fc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: 13px;
            font-weight: 600;
            text-anchor: middle;
            dominant-baseline: central;
            cursor: default;
            pointer-events: none;
            text-shadow: 0 1px 2px rgba(0,0,0,0.8);
        }}
        .router-label {{
            fill: #e6edf3;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: 10px;
            font-weight: 500;
            text-anchor: middle;
            dominant-baseline: central;
            pointer-events: none;
            text-shadow: 0 1px 2px rgba(0,0,0,0.6);
        }}
        .tooltip-bg {{
            fill: #21262d;
            stroke: #30363d;
            stroke-width: 1;
            rx: 8;
            ry: 8;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
            filter: drop-shadow(0 4px 12px rgba(0,0,0,0.3));
        }}
        .tooltip-text {{
            fill: #f0f6fc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: 12px;
            font-weight: 500;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s ease;
        }}
        .pulse-router {{
            animation: pulse-blue 4s infinite;
        }}
        @keyframes pulse-blue {{
            0% {{ opacity: 0.7; }}
            50% {{ opacity: 0.4; }}
            100% {{ opacity: 0.7; }}
        }}
        @keyframes pulse-red {{
            0% {{ opacity: 0.9; }}
            50% {{ opacity: 0.6; }}
            100% {{ opacity: 0.9; }}
        }}
        .fade-in {{
            animation: fadeIn 1s ease-in;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: scale(0.8); }}
            to {{ opacity: 1; transform: scale(1); }}
        }}
        .direction-arrow {{
            transition: opacity 0.2s ease;
        }}
        .edge-group:hover .direction-arrow {{
            opacity: 1 !important;
        }}
        .latency-label {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            opacity: 0.9;
            transition: opacity 0.2s ease;
        }}
        .edge-group:hover .latency-label {{
            opacity: 1;
            font-weight: 600;
        }}
        ]]>
    </style>
</defs>''')

        # Dark background with subtle gradient
        svg_parts.append(f'''
<defs>
    <radialGradient id="bg-gradient" cx="50%" cy="50%" r="70%">
        <stop offset="0%" style="stop-color:#161b22"/>
        <stop offset="100%" style="stop-color:#0d1117"/>
    </radialGradient>
</defs>
<rect width="100%" height="100%" fill="url(#bg-gradient)"/>''')

        # Calculate center and scale
        center_x, center_y = width // 2, height // 2
        scale = min(width, height) * 0.15
        
        # Draw edges first (behind nodes) - inside scalable content group
        topology_content = []
        topology_content.append('<g id="edges" class="fade-in">')
        for edge in data['edges']:
            source_node = next(n for n in data['nodes'] if n['id'] == edge['source'])
            target_node = next(n for n in data['nodes'] if n['id'] == edge['target'])
            
            x1 = center_x + source_node['x'] * scale
            y1 = center_y + source_node['y'] * scale
            x2 = center_x + target_node['x'] * scale
            y2 = center_y + target_node['y'] * scale
            
            latency = edge['latency']
            css_class = 'edge-bad' if latency > 50 else 'edge-medium' if latency > 20 else 'edge-good'
            
            # Calculate arrow position (75% along the line)
            arrow_x = x1 + 0.75 * (x2 - x1)
            arrow_y = y1 + 0.75 * (y2 - y1)
            
            # Calculate arrow angle
            import math
            angle = math.atan2(y2 - y1, x2 - x1) * 180 / math.pi
            
            # Calculate midpoint for latency label
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            
            # Format latency for display
            latency_text = f"{latency:.1f}ms" if latency > 0 else "<1ms"
            
            topology_content.append(f'''
    <g class="edge-group">
        <line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" 
              class="{css_class}"
              data-latency="{latency:.2f}"
              onmouseover="showTooltip(evt, 'Latency: {latency:.2f}ms')"
              onmouseout="hideTooltip()">
        </line>
        
        <!-- Direction arrow -->
        <g transform="translate({arrow_x:.1f},{arrow_y:.1f}) rotate({angle})">
            <polygon points="-8,-4 8,0 -8,4" 
                     fill="{"#f85149" if latency > 50 else "#d29922" if latency > 20 else "#3fb950"}"
                     opacity="0.8" class="direction-arrow">
            </polygon>
        </g>
        
        <!-- Latency label -->
        <text x="{mid_x:.1f}" y="{mid_y:.1f}" 
              class="latency-label"
              text-anchor="middle" dominant-baseline="central"
              fill="#f0f6fc" font-size="10" font-weight="500"
              style="text-shadow: 0 1px 3px rgba(0,0,0,0.8); pointer-events: none;">
            {latency_text}
        </text>
    </g>''')
        topology_content.append('</g>')
        
        # Draw nodes
        topology_content.append('<g id="nodes" class="fade-in">')
        for node in data['nodes']:
            x = center_x + node['x'] * scale
            y = center_y + node['y'] * scale
            
            if node['type'] == 'location':
                radius = 28
                css_class = 'location-node'
                label_class = 'node-label'
                tooltip_text = f"Location: {node['label']}"
                if node['ip']:
                    tooltip_text += f"\\nIP: {node['ip']}"
            else:
                radius = 16
                css_class = 'router-node pulse-router'
                label_class = 'router-label'
                tooltip_text = f"Router: {node['label']}"
                if node['ip'] and node['ip'] != node['label']:
                    tooltip_text += f"\\nIP: {node['ip']}"
            
            topology_content.append(f'''
    <circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}"
            class="{css_class}"
            onmouseover="showTooltip(evt, '{tooltip_text}')"
            onmouseout="hideTooltip()"
            onclick="selectNode('{node['id']}')">
    </circle>''')
            
            # Add labels - show actual IP for routers
            label = node['label']
            if node['type'] == 'router':
                # Extract IP from router node ID if available
                if node['ip'] and node['ip'] != node['label']:
                    # Show actual IP address for routers
                    label = node['ip']
                # Truncate long IPs for display
                if len(label) > 12:
                    label = label[:12] + '...'
            elif len(label) > 10:
                label = label[:10] + '...'
                
            topology_content.append(f'''
    <text x="{x:.1f}" y="{y:.1f}" class="{label_class}">{label}</text>''')
        
        topology_content.append('</g>')
        
        # Prepare topology content for insertion later
        topology_content_str = ''.join(topology_content)
        
        # Add title
        svg_parts.append(f'''
<text x="{center_x}" y="30" text-anchor="middle" 
      fill="#f0f6fc" font-family="system-ui" font-size="20" font-weight="600"
      class="fade-in">
    Network Topology Analysis
</text>''')
        
        # Add zoom controls and interactive tooltip
        svg_parts.append(f'''
<!-- Zoom and Pan Controls -->
<g id="zoom-controls" style="pointer-events: all;">
    <rect x="{width-120}" y="20" width="100" height="80" rx="8" ry="8" 
          fill="#21262d" stroke="#30363d" stroke-width="1" opacity="0.9"/>
    
    <circle cx="{width-70}" cy="45" r="15" fill="#238636" stroke="#2ea043" stroke-width="1" 
            cursor="pointer" onclick="zoomIn()">
        <title>Zoom In</title>
    </circle>
    <text x="{width-70}" y="50" text-anchor="middle" fill="white" font-size="16" font-weight="bold" 
          pointer-events="none">+</text>
    
    <circle cx="{width-70}" cy="75" r="15" fill="#da3633" stroke="#f85149" stroke-width="1" 
            cursor="pointer" onclick="zoomOut()">
        <title>Zoom Out</title>
    </circle>
    <text x="{width-70}" y="81" text-anchor="middle" fill="white" font-size="18" font-weight="bold" 
          pointer-events="none">−</text>
</g>

<g id="topology-content" transform="translate(0,0) scale(1)">
{topology_content_str}
</g>

<g id="tooltip" style="pointer-events: none;">
    <rect id="tooltip-bg" class="tooltip-bg" x="0" y="0" width="120" height="40"/>
    <text id="tooltip-text" class="tooltip-text" x="10" y="25">Tooltip</text>
</g>

<script>
<![CDATA[
    var currentZoom = 1;
    var isPanning = false;
    var startPoint = {{x: 0, y: 0}};
    var currentTranslate = {{x: 0, y: 0}};
    
    // Initialize pan functionality
    var svg = document.querySelector('svg');
    var topologyContent = document.getElementById('topology-content');
    
    svg.addEventListener('mousedown', startPan);
    svg.addEventListener('mousemove', pan);
    svg.addEventListener('mouseup', endPan);
    svg.addEventListener('mouseleave', endPan);
    
    function startPan(evt) {{
        if (evt.target.closest('#zoom-controls')) return;
        isPanning = true;
        var pt = getSVGPoint(evt);
        startPoint.x = pt.x - currentTranslate.x;
        startPoint.y = pt.y - currentTranslate.y;
        svg.style.cursor = 'grabbing';
    }}
    
    function pan(evt) {{
        if (!isPanning) return;
        var pt = getSVGPoint(evt);
        currentTranslate.x = pt.x - startPoint.x;
        currentTranslate.y = pt.y - startPoint.y;
        updateTransform();
    }}
    
    function endPan() {{
        isPanning = false;
        svg.style.cursor = 'grab';
    }}
    
    function getSVGPoint(evt) {{
        var pt = svg.createSVGPoint();
        pt.x = evt.clientX;
        pt.y = evt.clientY;
        return pt.matrixTransform(svg.getScreenCTM().inverse());
    }}
    
    function zoomIn() {{
        currentZoom = Math.min(currentZoom * 1.2, 3);
        updateTransform();
    }}
    
    function zoomOut() {{
        currentZoom = Math.max(currentZoom / 1.2, 0.3);
        updateTransform();
    }}
    
    function updateTransform() {{
        topologyContent.setAttribute('transform', 
            `translate(${{currentTranslate.x}},${{currentTranslate.y}}) scale(${{currentZoom}})`);
    }}
    
    // Tooltip functions
    function showTooltip(evt, text) {{
        var tooltip = document.getElementById('tooltip');
        var tooltipBg = document.getElementById('tooltip-bg');
        var tooltipText = document.getElementById('tooltip-text');
        
        var pt = getSVGPoint(evt);
        
        tooltipText.textContent = text.replace(/\\\\n/g, ' | ');
        var bbox = tooltipText.getBBox();
        
        var bgWidth = bbox.width + 20;
        var bgHeight = bbox.height + 16;
        var bgX = pt.x - bgWidth/2;
        var bgY = pt.y - bgHeight - 15;
        
        tooltipBg.setAttribute('x', bgX);
        tooltipBg.setAttribute('y', bgY);
        tooltipBg.setAttribute('width', bgWidth);
        tooltipBg.setAttribute('height', bgHeight);
        tooltipText.setAttribute('x', bgX + 10);
        tooltipText.setAttribute('y', bgY + bgHeight/2 + 4);
        
        tooltipBg.style.opacity = '0.95';
        tooltipText.style.opacity = '1';
    }}
    
    function hideTooltip() {{
        document.getElementById('tooltip-bg').style.opacity = '0';
        document.getElementById('tooltip-text').style.opacity = '0';
    }}
    
    function selectNode(nodeId) {{
        console.log('Selected node:', nodeId);
        // Future: highlight connected paths
    }}
    
    // Set initial cursor
    svg.style.cursor = 'grab';
]]>
</script>
</svg>''')

        return ''.join(svg_parts)
    
    def _create_layout(self) -> Dict:
        """Create layout positions for nodes"""
        # Separate location nodes from router nodes
        location_nodes = [n for n, d in self.graph.nodes(data=True) 
                         if d.get('node_type') == 'location']
        router_nodes = [n for n, d in self.graph.nodes(data=True)
                       if d.get('node_type') == 'router']
        
        # Use different layout algorithms for different parts
        if len(location_nodes) <= 1:
            # Simple layout for single location
            pos = nx.spring_layout(self.graph, k=3, iterations=50)
        else:
            # Try to place locations around the edge, routers in middle
            pos = {}
            
            # Place locations in a circle
            import math
            n_locations = len(location_nodes)
            for i, location in enumerate(location_nodes):
                angle = 2 * math.pi * i / n_locations
                pos[location] = (3 * math.cos(angle), 3 * math.sin(angle))
            
            # Place routers using spring layout, but constrained to center
            if router_nodes:
                router_subgraph = self.graph.subgraph(router_nodes + location_nodes)
                router_pos = nx.spring_layout(router_subgraph, pos=pos, 
                                            fixed=location_nodes, k=1, iterations=30)
                pos.update(router_pos)
        
        return pos
    
    def _draw_location_nodes(self, pos: Dict):
        """Draw location nodes (datacenters)"""
        location_nodes = [n for n, d in self.graph.nodes(data=True) 
                         if d.get('node_type') == 'location']
        
        if location_nodes:
            nx.draw_networkx_nodes(self.graph, pos,
                                 nodelist=location_nodes,
                                 node_color='lightblue',
                                 node_size=1500,
                                 node_shape='o',
                                 alpha=0.9)
    
    def _draw_router_nodes(self, pos: Dict):
        """Draw router nodes (intermediate hops)"""
        router_nodes = [n for n, d in self.graph.nodes(data=True)
                       if d.get('node_type') == 'router']
        
        if router_nodes:
            nx.draw_networkx_nodes(self.graph, pos,
                                 nodelist=router_nodes,
                                 node_color='lightgray',
                                 node_size=400,
                                 node_shape='s',
                                 alpha=0.7)
    
    def _draw_edges(self, pos: Dict):
        """Draw edges with latency-based coloring"""
        edges = list(self.graph.edges(data=True))
        
        if not edges:
            return
        
        # Categorize edges by latency
        good_edges = []
        medium_edges = []
        bad_edges = []
        
        for u, v, data in edges:
            latency = data.get('latency', 0)
            edge = (u, v)
            
            if latency > 50:
                bad_edges.append(edge)
            elif latency > 20:
                medium_edges.append(edge)
            else:
                good_edges.append(edge)
        
        # Draw edges with different colors
        if good_edges:
            nx.draw_networkx_edges(self.graph, pos, edgelist=good_edges,
                                 edge_color='green', alpha=0.6, width=1.5)
        if medium_edges:
            nx.draw_networkx_edges(self.graph, pos, edgelist=medium_edges,
                                 edge_color='orange', alpha=0.7, width=2)
        if bad_edges:
            nx.draw_networkx_edges(self.graph, pos, edgelist=bad_edges,
                                 edge_color='red', alpha=0.8, width=2.5)
    
    def _add_labels(self, pos: Dict):
        """Add labels to nodes"""
        # Location labels (larger)
        location_nodes = {n: n for n, d in self.graph.nodes(data=True) 
                         if d.get('node_type') == 'location'}
        
        if location_nodes:
            nx.draw_networkx_labels(self.graph, pos, labels=location_nodes,
                                  font_size=12, font_weight='bold')
        
        # Router labels (smaller, just IP)
        router_labels = {}
        for n, d in self.graph.nodes(data=True):
            if d.get('node_type') == 'router':
                ip = d.get('ip', n)
                # Show only last octet for clarity
                if '.' in ip:
                    router_labels[n] = ip.split('.')[-1]
                else:
                    router_labels[n] = ip[:8]  # Truncate long IPs
        
        if router_labels:
            nx.draw_networkx_labels(self.graph, pos, labels=router_labels,
                                  font_size=8)
    
    def generate_topology_summary(self) -> Dict:
        """Generate summary statistics about the topology"""
        return {
            'total_locations': len(self.locations),
            'total_routers': len([n for n, d in self.graph.nodes(data=True) 
                                if d.get('node_type') == 'router']),
            'total_edges': self.graph.number_of_edges(),
            'routes_analyzed': len(self.traceroute_data),
            'bottlenecks_found': len(self.find_bottlenecks()),
            'locations': list(self.locations),
            'graph_density': nx.density(self.graph),
            'strongly_connected': nx.is_strongly_connected(self.graph) if self.graph.number_of_nodes() > 0 else False
        }
    
    def get_interactive_topology_data(self) -> Dict:
        """Generate data for interactive web visualization"""
        if self.graph.number_of_nodes() == 0:
            return {'nodes': [], 'edges': [], 'summary': self.generate_topology_summary()}
        
        pos = self._create_layout()
        
        # Prepare nodes
        nodes = []
        for node_id, data in self.graph.nodes(data=True):
            x, y = pos.get(node_id, (0, 0))
            nodes.append({
                'id': node_id,
                'x': float(x),
                'y': float(y),
                'type': data.get('node_type', 'unknown'),
                'label': node_id if data.get('node_type') == 'location' else data.get('ip', node_id),
                'ip': data.get('ip'),
                'location': data.get('location')
            })
        
        # Prepare edges
        edges = []
        for u, v, data in self.graph.edges(data=True):
            latency = data.get('latency', 0)
            edges.append({
                'source': u,
                'target': v,
                'latency': float(latency),
                'route': data.get('route', ''),
                'hop_number': data.get('hop_number'),
                'color': 'red' if latency > 50 else 'orange' if latency > 20 else 'green'
            })
        
        return {
            'nodes': nodes,
            'edges': edges,
            'summary': self.generate_topology_summary(),
            'bottlenecks': self.find_bottlenecks()
        }