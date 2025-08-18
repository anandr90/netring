class NetringDashboard {
    constructor() {
        this.members = [];
        this.metrics = new Map();
        this.updateInterval = 5000; // 5 seconds
        this.intervalId = null;
        this.currentMetricView = 'all';
        this.currentPage = 1;
        this.itemsPerPage = 10;
        this.currentFilters = {
            showFailuresOnly: false,
            sourceLocation: 'all',
            targetLocation: 'all',
            minLatency: 0,
            maxLatency: 10000, // 10 seconds in ms
            showOfflineTargets: true
        };
        
        // Topology state
        this.topologyVisible = false;
        this.topologyData = null;
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.startDataPolling();
        this.checkRegistryHealth();
    }

    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshData());
        }

        // Metric toggle buttons
        const metricToggles = document.querySelectorAll('.metric-toggle');
        metricToggles.forEach(toggle => {
            toggle.addEventListener('click', (e) => {
                // Check if this is the topology modal button
                if (e.target.id === 'topologyModalBtn') {
                    this.openTopologyModal();
                } else {
                    const metric = e.target.dataset.metric;
                    this.switchMetricView(metric);
                }
            });
        });

        // Modal event listeners
        this.setupModalEventListeners();

        // Filter controls
        this.setupFilterControls();

        // Auto-refresh on window focus
        window.addEventListener('focus', () => {
            this.refreshData();
        });
    }

    async checkRegistryHealth() {
        try {
            const response = await fetch('/health');
            const statusIndicator = document.getElementById('registryStatus');
            const statusDot = statusIndicator.querySelector('.status-dot');
            const statusText = statusIndicator.querySelector('span');

            if (response.ok) {
                statusDot.className = 'status-dot healthy';
                statusText.textContent = 'Registry Online';
            } else {
                statusDot.className = 'status-dot error';
                statusText.textContent = 'Registry Error';
            }
        } catch (error) {
            const statusIndicator = document.getElementById('registryStatus');
            const statusDot = statusIndicator.querySelector('.status-dot');
            const statusText = statusIndicator.querySelector('span');
            
            statusDot.className = 'status-dot error';
            statusText.textContent = 'Registry Offline';
        }
    }

    async fetchMembers() {
        try {
            // Try the enhanced endpoint first
            let response = await fetch('/members_with_analysis');
            let data;
            
            if (response.ok) {
                // Enhanced endpoint available
                data = await response.json();
                this.members = data.members || [];
                this.missingAnalysis = data.missing_analysis || { enabled: false, locations: {}, alerts: [] };
            } else {
                // Fallback to basic endpoint (backward compatibility)
                response = await fetch('/members');
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                data = await response.json();
                this.members = data.members || [];
                this.missingAnalysis = { enabled: false, locations: {}, alerts: [] };
            }
            
            this.updateStats();
            this.renderMembers();
            this.renderMissingMembersAnalysis();
            this.fetchMetricsFromMembers();
            
        } catch (error) {
            console.error('Failed to fetch members:', error);
            this.showError('Failed to fetch member data: ' + error.message);
        }
    }

    async fetchMetricsFromMembers() {
        // Fetch aggregated metrics from registry
        try {
            const response = await fetch('/metrics');
            if (response.ok) {
                const data = await response.json();
                this.metrics.clear();
                
                // Process metrics from each member
                for (const [memberId, memberMetrics] of Object.entries(data.metrics)) {
                    this.metrics.set(memberId, {
                        connectivity_tcp: new Map(),
                        connectivity_http: new Map(),
                        check_durations: new Map(),
                        bandwidth_mbps: new Map(),
                        traceroute_hops: new Map(),
                        traceroute_max_latency: new Map(),
                        general: memberMetrics.general || {},
                        member_info: this.members.find(m => m.instance_id === memberId)
                    });
                    
                    const metricData = this.metrics.get(memberId);
                    
                    // Process TCP connectivity metrics
                    for (const [key, metric] of Object.entries(memberMetrics.connectivity_tcp || {})) {
                        metricData.connectivity_tcp.set(key, metric);
                    }
                    
                    // Process HTTP connectivity metrics
                    for (const [key, metric] of Object.entries(memberMetrics.connectivity_http || {})) {
                        metricData.connectivity_http.set(key, metric);
                    }
                    
                    // Process check duration metrics
                    for (const [key, metric] of Object.entries(memberMetrics.check_durations || {})) {
                        metricData.check_durations.set(key, metric);
                    }
                    
                    // Process bandwidth metrics
                    for (const [key, metric] of Object.entries(memberMetrics.bandwidth_tests || {})) {
                        metricData.bandwidth_mbps.set(key, metric);
                    }
                    
                    // Process traceroute metrics
                    for (const [key, metric] of Object.entries(memberMetrics.traceroute_tests || {})) {
                        metricData.traceroute_hops.set(key, metric);
                        metricData.traceroute_max_latency.set(key, metric);
                    }
                }
                
                this.renderMetrics();
            }
        } catch (error) {
            console.error('Failed to fetch metrics:', error);
        }
    }


    updateStats() {
        const now = Date.now() / 1000;
        const staleThreshold = 300; // 5 minutes
        
        // Total members (active + deregistered)
        document.getElementById('totalMembers').textContent = this.members.length;
        
        // Unique locations
        const locations = new Set(this.members.map(m => m.location));
        document.getElementById('totalLocations').textContent = locations.size;
        
        // Active healthy members (exclude deregistered ones)
        const activeMembers = this.members.filter(m => m.status !== 'deregistered');
        const healthy = activeMembers.filter(m => (now - m.last_seen) < staleThreshold);
        document.getElementById('healthyMembers').textContent = healthy.length;
        
        // Last update time
        const lastUpdate = new Date().toLocaleTimeString();
        document.getElementById('lastUpdate').textContent = lastUpdate;
        
        // Update location filters
        this.updateLocationFilters();
    }

    setupFilterControls() {
        // Show failures only checkbox
        const failuresOnlyToggle = document.getElementById('showFailuresOnly');
        if (failuresOnlyToggle) {
            failuresOnlyToggle.addEventListener('change', (e) => {
                this.currentFilters.showFailuresOnly = e.target.checked;
                this.renderMetrics();
            });
        }

        // Location filters
        const sourceLocationFilter = document.getElementById('sourceLocationFilter');
        const targetLocationFilter = document.getElementById('targetLocationFilter');
        
        if (sourceLocationFilter) {
            sourceLocationFilter.addEventListener('change', (e) => {
                this.currentFilters.sourceLocation = e.target.value;
                this.renderMetrics();
            });
        }
        
        if (targetLocationFilter) {
            targetLocationFilter.addEventListener('change', (e) => {
                this.currentFilters.targetLocation = e.target.value;
                this.renderMetrics();
            });
        }

        // Latency range filters
        const minLatencyInput = document.getElementById('minLatency');
        const maxLatencyInput = document.getElementById('maxLatency');
        
        if (minLatencyInput) {
            minLatencyInput.addEventListener('input', (e) => {
                this.currentFilters.minLatency = parseFloat(e.target.value) || 0;
                this.renderMetrics();
            });
        }
        
        if (maxLatencyInput) {
            maxLatencyInput.addEventListener('input', (e) => {
                this.currentFilters.maxLatency = parseFloat(e.target.value) || 10000;
                this.renderMetrics();
            });
        }

        // Show offline targets toggle
        const showOfflineToggle = document.getElementById('showOfflineTargets');
        if (showOfflineToggle) {
            showOfflineToggle.addEventListener('change', (e) => {
                this.currentFilters.showOfflineTargets = e.target.checked;
                this.renderMetrics();
            });
        }
    }

    updateLocationFilters() {
        const sourceSelect = document.getElementById('sourceLocationFilter');
        const targetSelect = document.getElementById('targetLocationFilter');
        
        if (!sourceSelect || !targetSelect) return;
        
        // Get unique locations from members
        const locations = new Set(this.members.map(m => m.location));
        
        // Update source location filter
        const currentSourceValue = sourceSelect.value;
        sourceSelect.innerHTML = '<option value="all">All Sources</option>';
        locations.forEach(location => {
            const option = document.createElement('option');
            option.value = location;
            option.textContent = location;
            if (location === currentSourceValue) option.selected = true;
            sourceSelect.appendChild(option);
        });
        
        // Update target location filter
        const currentTargetValue = targetSelect.value;
        targetSelect.innerHTML = '<option value="all">All Targets</option>';
        locations.forEach(location => {
            const option = document.createElement('option');
            option.value = location;
            option.textContent = location;
            if (location === currentTargetValue) option.selected = true;
            targetSelect.appendChild(option);
        });
    }

    renderMembers() {
        const container = document.getElementById('membersContainer');
        
        if (this.members.length === 0) {
            container.innerHTML = `
                <div class="error-message">
                    <div class="error-icon">🔍</div>
                    <p>No active members found</p>
                </div>
            `;
            return;
        }

        const now = Date.now() / 1000;
        const staleThreshold = 300; // 5 minutes
        const offlineThreshold = 600; // 10 minutes

        const membersHtml = this.members.map(member => {
            let statusClass, statusText, extraInfo = '';
            
            if (member.status === 'deregistered') {
                statusClass = 'deregistered';
                statusText = 'Deregistered';
                const deregisteredText = this.formatTimestamp(member.deregistered_at);
                extraInfo = `<span>Deregistered: ${deregisteredText}</span>`;
            } else {
                const timeSinceLastSeen = now - member.last_seen;
                
                if (timeSinceLastSeen < staleThreshold) {
                    statusClass = 'healthy';
                    statusText = 'Online';
                } else if (timeSinceLastSeen < offlineThreshold) {
                    statusClass = 'stale';
                    statusText = 'Stale';
                } else {
                    statusClass = 'offline';
                    statusText = 'Offline';
                }
            }

            const lastSeenText = this.formatTimestamp(member.last_seen);
            const registeredText = this.formatTimestamp(member.registered_at);
            
            return `
                <div class="member-card ${member.status === 'deregistered' ? 'deregistered-member' : ''}" 
                     data-member-id="${member.instance_id}">
                    <div class="member-info">
                        <div class="member-header">
                            <div class="member-id">${member.instance_id.substring(0, 8)}</div>
                            <div class="location-badge">${member.location}</div>
                        </div>
                        <div class="member-details">
                            <span>IP: ${member.ip}:${member.port}</span>
                            <span>Last seen: ${lastSeenText}</span>
                            <span>Registered: ${registeredText}</span>
                            ${extraInfo}
                        </div>
                    </div>
                    <div class="member-status">
                        <div class="status-badge ${statusClass}">${statusText}</div>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = membersHtml;
        
        // Setup hover tooltips for member cards
        this.setupMemberTooltips();
    }

    renderMissingMembersAnalysis() {
        // Create or find the missing members section
        let analysisSection = document.getElementById('missingMembersSection');
        
        if (!analysisSection) {
            // Create the section if it doesn't exist
            const mainElement = document.querySelector('.main');
            analysisSection = document.createElement('section');
            analysisSection.id = 'missingMembersSection';
            analysisSection.className = 'missing-members-section';
            
            // Insert before the content grid
            const contentGrid = document.querySelector('.content-grid');
            mainElement.insertBefore(analysisSection, contentGrid);
        }

        if (!this.missingAnalysis || !this.missingAnalysis.enabled) {
            analysisSection.style.display = 'none';
            return;
        }

        analysisSection.style.display = 'block';

        // Create alerts section
        let alertsHtml = '';
        if (this.missingAnalysis.alerts && this.missingAnalysis.alerts.length > 0) {
            const alertsByLevel = {
                error: this.missingAnalysis.alerts.filter(a => a.level === 'error'),
                warning: this.missingAnalysis.alerts.filter(a => a.level === 'warning')
            };

            alertsHtml = '<div class="missing-alerts">';
            
            // Show critical alerts first
            if (alertsByLevel.error.length > 0) {
                alertsHtml += alertsByLevel.error.map(alert => `
                    <div class="alert alert-error">
                        <span class="alert-icon">🚨</span>
                        <span class="alert-message">${alert.message}</span>
                    </div>
                `).join('');
            }
            
            // Then warnings
            if (alertsByLevel.warning.length > 0) {
                alertsHtml += alertsByLevel.warning.map(alert => `
                    <div class="alert alert-warning">
                        <span class="alert-icon">⚠️</span>
                        <span class="alert-message">${alert.message}</span>
                    </div>
                `).join('');
            }
            
            alertsHtml += '</div>';
        }

        // Create locations status grid
        const locations = this.missingAnalysis.locations || {};
        const locationsHtml = Object.entries(locations).map(([location, info]) => {
            let statusClass = 'location-healthy';
            let statusIcon = '✅';
            let statusText = 'Healthy';
            
            if (info.status === 'missing_members') {
                statusClass = info.criticality === 'high' ? 'location-critical' : 'location-warning';
                statusIcon = info.criticality === 'high' ? '🚨' : '⚠️';
                statusText = `Missing ${info.missing_count} member(s)`;
            } else if (info.status === 'extra_members') {
                statusClass = 'location-info';
                statusIcon = 'ℹ️';
                statusText = `${info.actual_count - info.expected_count} extra member(s)`;
            } else if (info.status === 'unexpected_location') {
                statusClass = 'location-info';
                statusIcon = '❓';
                statusText = 'Unexpected location';
            }

            const membersList = info.current_members ? 
                info.current_members.map(m => `<li>${m.instance_id.substr(0, 8)}... (${m.ip})</li>`).join('') : '';

            return `
                <div class="location-card ${statusClass}">
                    <div class="location-header">
                        <div class="location-name">
                            <span class="location-icon">${statusIcon}</span>
                            <h4>${location}</h4>
                            <span class="criticality criticality-${info.criticality}">${info.criticality}</span>
                        </div>
                        <div class="location-count">
                            <span class="count-display">${info.actual_count}/${info.expected_count}</span>
                        </div>
                    </div>
                    <div class="location-details">
                        <p class="location-description">${info.description}</p>
                        <p class="location-status">${statusText}</p>
                        ${membersList ? `<div class="current-members"><h5>Current Members:</h5><ul>${membersList}</ul></div>` : ''}
                    </div>
                </div>
            `;
        }).join('');

        // Summary stats
        const summary = this.missingAnalysis.summary || {};
        const summaryHtml = `
            <div class="missing-summary">
                <div class="summary-stat">
                    <span class="stat-value">${summary.total_missing_members || 0}</span>
                    <span class="stat-label">Missing Members</span>
                </div>
                <div class="summary-stat">
                    <span class="stat-value">${summary.critical_locations_missing || 0}</span>
                    <span class="stat-label">Critical Locations</span>
                </div>
                <div class="summary-stat">
                    <span class="stat-value">${summary.unexpected_locations || 0}</span>
                    <span class="stat-label">Unexpected Locations</span>
                </div>
            </div>
        `;

        analysisSection.innerHTML = `
            <div class="section-header">
                <h2>Expected Members Analysis</h2>
                <div class="analysis-timestamp">
                    Last checked: ${this.formatTimestamp(this.missingAnalysis.timestamp)}
                </div>
            </div>
            ${alertsHtml}
            ${summaryHtml}
            <div class="locations-grid">
                ${locationsHtml}
            </div>
        `;
    }
    
    calculateMemberStats(member) {
        const memberMetrics = this.metrics.get(member.instance_id);
        if (!memberMetrics) {
            return {
                avgLatency: 'N/A',
                totalChecks: 0,
                successRate: 'N/A',
                avgBandwidth: 'N/A',
                avgHops: 'N/A',
                nextCheck: 'N/A',
                nextBandwidthTest: 'N/A',
                nextTraceroute: 'N/A'
            };
        }
        
        // Calculate average latency across all checks
        let totalLatency = 0;
        let latencyCount = 0;
        memberMetrics.check_durations.forEach(duration => {
            if (duration.avg_latency_ms !== null) {
                totalLatency += duration.avg_latency_ms;
                latencyCount++;
            }
        });
        const avgLatency = latencyCount > 0 ? (totalLatency / latencyCount).toFixed(1) + 'ms' : 'N/A';
        
        // Calculate total checks and success rate
        const tcpConnections = Array.from(memberMetrics.connectivity_tcp.values());
        const httpConnections = Array.from(memberMetrics.connectivity_http.values());
        const allConnections = [...tcpConnections, ...httpConnections];
        const totalChecks = allConnections.length;
        const successfulChecks = allConnections.filter(conn => conn.value === 1).length;
        const successRate = totalChecks > 0 ? Math.round((successfulChecks / totalChecks) * 100) + '%' : 'N/A';
        
        // Calculate average bandwidth (use correct property names)
        const bandwidthTests = Array.from(memberMetrics.bandwidth_mbps.values());
        let avgBandwidth = 'N/A';
        if (bandwidthTests.length > 0) {
            const totalBandwidth = bandwidthTests.reduce((sum, test) => sum + (test.bandwidth_mbps || 0), 0);
            const avgBw = totalBandwidth / bandwidthTests.length;
            avgBandwidth = avgBw >= 1000 ? (avgBw / 1000).toFixed(1) + ' Gbps' : Math.round(avgBw) + ' Mbps';
        }
        
        // Calculate average hops (use correct property names)
        const tracerouteTests = Array.from(memberMetrics.traceroute_hops.values());
        let avgHops = 'N/A';
        if (tracerouteTests.length > 0) {
            const totalHops = tracerouteTests.reduce((sum, test) => sum + (test.total_hops || 0), 0);
            avgHops = Math.round(totalHops / tracerouteTests.length) + ' hops';
        }
        
        // Calculate next check times (approximate)
        const now = Date.now() / 1000;
        const timeSinceLastSeen = now - member.last_seen;
        const checkInterval = 60; // 60 seconds from config
        const bandwidthInterval = 300; // 5 minutes from config  
        const tracerouteInterval = 300; // 5 minutes from config
        
        const nextCheck = Math.max(0, checkInterval - timeSinceLastSeen);
        const nextBandwidthTest = Math.max(0, bandwidthInterval - (timeSinceLastSeen % bandwidthInterval));
        const nextTraceroute = Math.max(0, tracerouteInterval - (timeSinceLastSeen % tracerouteInterval));
        
        return {
            avgLatency,
            totalChecks,
            successRate,
            avgBandwidth,
            avgHops,
            nextCheck: nextCheck > 0 ? Math.round(nextCheck) + 's' : 'Due now',
            nextBandwidthTest: nextBandwidthTest > 0 ? Math.round(nextBandwidthTest) + 's' : 'Due now',
            nextTraceroute: nextTraceroute > 0 ? Math.round(nextTraceroute) + 's' : 'Due now'
        };
    }
    
    setupMemberTooltips() {
        // Remove existing tooltips
        const existingTooltip = document.querySelector('.member-tooltip');
        if (existingTooltip) existingTooltip.remove();
        
        const memberCards = document.querySelectorAll('.member-card');
        memberCards.forEach(card => {
            card.addEventListener('mouseenter', (e) => this.showMemberTooltip(e));
            card.addEventListener('mouseleave', () => this.hideMemberTooltip());
        });
    }
    
    showMemberTooltip(event) {
        const card = event.currentTarget;
        const memberId = card.dataset.memberId;
        
        // Find the member data
        const member = this.members.find(m => m.instance_id === memberId);
        if (!member) return;
        
        // Calculate stats dynamically with current metrics
        const statsData = this.calculateMemberStats(member);
        
        const tooltip = document.createElement('div');
        tooltip.className = 'member-tooltip';
        tooltip.innerHTML = `
            <div class="tooltip-header">Member Statistics</div>
            <div class="tooltip-content">
                <div class="stat-row">
                    <span class="stat-label">Average Latency:</span>
                    <span class="stat-value">${statsData.avgLatency}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Success Rate:</span>
                    <span class="stat-value">${statsData.successRate}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Total Checks:</span>
                    <span class="stat-value">${statsData.totalChecks}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Avg Bandwidth:</span>
                    <span class="stat-value">${statsData.avgBandwidth}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Avg Hops:</span>
                    <span class="stat-value">${statsData.avgHops}</span>
                </div>
                <div class="tooltip-divider"></div>
                <div class="stat-row">
                    <span class="stat-label">Next Check:</span>
                    <span class="stat-value next-check">${statsData.nextCheck}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Next Bandwidth:</span>
                    <span class="stat-value next-check">${statsData.nextBandwidthTest}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Next Traceroute:</span>
                    <span class="stat-value next-check">${statsData.nextTraceroute}</span>
                </div>
            </div>
        `;
        
        document.body.appendChild(tooltip);
        this.updateTooltipPosition(event);
    }
    
    hideMemberTooltip() {
        const tooltip = document.querySelector('.member-tooltip');
        if (tooltip) tooltip.remove();
    }
    
    updateTooltipPosition(event) {
        const tooltip = document.querySelector('.member-tooltip');
        if (!tooltip) return;
        
        const mouseX = event.clientX;
        const mouseY = event.clientY;
        
        // Position tooltip to the right of the member card, not following mouse
        const card = event.currentTarget;
        const cardRect = card.getBoundingClientRect();
        
        // Position to the right of the card
        let left = cardRect.right + 15;
        let top = cardRect.top;
        
        // Adjust if tooltip goes off screen
        const tooltipRect = tooltip.getBoundingClientRect();
        const windowWidth = window.innerWidth;
        const windowHeight = window.innerHeight;
        
        if (left + tooltipRect.width > windowWidth) {
            // Position to the left of the card if no room on right
            left = cardRect.left - tooltipRect.width - 15;
        }
        
        if (top + tooltipRect.height > windowHeight) {
            // Adjust vertically if needed
            top = windowHeight - tooltipRect.height - 10;
        }
        
        // Ensure it doesn't go above the viewport
        if (top < 10) {
            top = 10;
        }
        
        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
    }

    renderMetrics() {
        const container = document.getElementById('metricsContainer');
        const connectivityData = this.generateConnectivityMatrix();
        
        if (connectivityData.length === 0) {
            container.innerHTML = `
                <div class="metric-placeholder">
                    <p>Connectivity metrics will appear here when members start reporting data</p>
                </div>
            `;
            return;
        }

        const paginatedData = connectivityData.slice((this.currentPage - 1) * this.itemsPerPage, this.currentPage * this.itemsPerPage);

        const metricsHtml = paginatedData.map(connection => {
            const indicator = connection.success ? 'success' : 'failure';
            const statusText = connection.success ? '✓' : '✗';
            
            // Format latency display
            let latencyText = 'N/A';
            if (connection.latency_ms !== null) {
                if (connection.latency_ms < 1) {
                    latencyText = '<1ms';
                } else if (connection.latency_ms < 1000) {
                    latencyText = `${Math.round(connection.latency_ms)}ms`;
                } else {
                    latencyText = `${(connection.latency_ms / 1000).toFixed(2)}s`;
                }
            }
            
            // Format success rate for HTTP
            let successRateText = '';
            if (connection.type === 'http' && connection.success_rate !== undefined) {
                successRateText = `<div class="success-rate">${Math.round(connection.success_rate)}% success</div>`;
            }
            
            // Handle special display for bandwidth and traceroute views
            let primaryMetricText = '';
            if (connection.type === 'bandwidth' && connection.bandwidth_mbps !== undefined) {
                if (connection.bandwidth_mbps >= 1000) {
                    primaryMetricText = `<div class="primary-metric">${(connection.bandwidth_mbps / 1000).toFixed(1)} Gbps</div>`;
                } else {
                    primaryMetricText = `<div class="primary-metric">${Math.round(connection.bandwidth_mbps)} Mbps</div>`;
                }
                latencyText = ''; // Don't show latency for bandwidth view
            } else if (connection.type === 'traceroute') {
                primaryMetricText = `<div class="primary-metric">${connection.traceroute_hops} hops</div>`;
                latencyText = connection.traceroute_max_latency_ms ? `Max: ${Math.round(connection.traceroute_max_latency_ms)}ms` : 'N/A';
            }
            
            // Check count info
            const checkCountText = connection.check_count > 0 ? 
                `<div class="check-count">${connection.check_count} checks</div>` : '';
            
            // Format bandwidth info
            let bandwidthText = '';
            if (connection.bandwidth_mbps !== undefined && connection.bandwidth_mbps !== null) {
                if (connection.bandwidth_mbps >= 1000) {
                    bandwidthText = `<div class="bandwidth">${(connection.bandwidth_mbps / 1000).toFixed(1)} Gbps</div>`;
                } else {
                    bandwidthText = `<div class="bandwidth">${Math.round(connection.bandwidth_mbps)} Mbps</div>`;
                }
            }
            
            // Format traceroute info
            let tracerouteText = '';
            if (connection.traceroute_hops !== undefined && connection.traceroute_max_latency_ms !== undefined) {
                tracerouteText = `<div class="traceroute">${connection.traceroute_hops} hops, max: ${Math.round(connection.traceroute_max_latency_ms)}ms</div>`;
            }
            
            return `
                <div class="connectivity-row ${connection.success ? '' : 'failure-row'}">
                    <div class="source-info">
                        <div class="location-name">${connection.source_location}</div>
                        <div class="instance-name">${connection.source_instance.substring(0, 8)}</div>
                    </div>
                    <div class="target-info">
                        <div class="location-name">${connection.target_location}</div>
                        <div class="instance-name">${connection.target_instance.substring(0, 8)}</div>
                        <div class="target-ip">${connection.target_ip || 'N/A'}</div>
                    </div>
                    <div class="metric-details">
                        ${primaryMetricText}
                        <div class="latency">${latencyText}</div>
                        ${successRateText}
                        ${checkCountText}
                        ${bandwidthText}
                        ${tracerouteText}
                        <div class="protocol-type">${connection.type.toUpperCase()}</div>
                    </div>
                    <div class="connectivity-status">
                        <div class="connectivity-indicator ${indicator}"></div>
                        <span>${statusText}</span>
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = `<div class="connectivity-grid">${metricsHtml}</div>`;
        this.renderPagination(connectivityData.length);
    }

    renderPagination(totalItems) {
        const paginationContainer = document.getElementById('paginationContainer');
        if (!paginationContainer) {
            const container = document.getElementById('metricsContainer');
            const paginationEl = document.createElement('div');
            paginationEl.id = 'paginationContainer';
            container.insertAdjacentElement('afterend', paginationEl);
        }
        
        const totalPages = Math.ceil(totalItems / this.itemsPerPage);
        if (totalPages <= 1) {
            if (paginationContainer) paginationContainer.innerHTML = '';
            return;
        }

        let paginationHtml = '<div class="pagination">';

        // Previous button
        paginationHtml += `<button class="page-btn prev-btn" ${this.currentPage === 1 ? 'disabled' : ''}>&laquo; Prev</button>`;

        // Page numbers
        for (let i = 1; i <= totalPages; i++) {
            paginationHtml += `<button class="page-btn ${i === this.currentPage ? 'active' : ''}" data-page="${i}">${i}</button>`;
        }

        // Next button
        paginationHtml += `<button class="page-btn next-btn" ${this.currentPage === totalPages ? 'disabled' : ''}>Next &raquo;</button>`;

        paginationHtml += '</div>';

        const a = document.getElementById('paginationContainer');
        a.innerHTML = paginationHtml;

        // Add event listeners
        a.querySelectorAll('.page-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                if (e.target.classList.contains('prev-btn')) {
                    this.currentPage--;
                } else if (e.target.classList.contains('next-btn')) {
                    this.currentPage++;
                } else {
                    this.currentPage = parseInt(e.target.dataset.page);
                }
                this.renderMetrics();
            });
        });
    }

    generateConnectivityMatrix() {
        const connections = [];
        
        this.metrics.forEach((memberMetrics) => {
            // TCP connectivity
            if (this.currentMetricView === 'all' || this.currentMetricView === 'tcp') {
                memberMetrics.connectivity_tcp.forEach((metric) => {
                    // Find corresponding latency data
                    const latencyKey = `tcp:${metric.labels.target_location}:${metric.labels.target_instance}`;
                    const latencyData = memberMetrics.check_durations.get(latencyKey);
                    
                    // Find bandwidth data
                    const bandwidthKey = Object.keys(Object.fromEntries(memberMetrics.bandwidth_mbps)).find(key => {
                        const bwMetric = memberMetrics.bandwidth_mbps.get(key);
                        return bwMetric && bwMetric.labels.target_location === metric.labels.target_location &&
                               bwMetric.labels.target_instance === metric.labels.target_instance;
                    });
                    const bandwidthData = bandwidthKey ? memberMetrics.bandwidth_mbps.get(bandwidthKey) : null;
                    
                    // Find traceroute data
                    const tracerouteKey = Object.keys(Object.fromEntries(memberMetrics.traceroute_hops)).find(key => {
                        const trMetric = memberMetrics.traceroute_hops.get(key);
                        return trMetric && trMetric.labels.target_location === metric.labels.target_location &&
                               trMetric.labels.target_instance === metric.labels.target_instance;
                    });
                    
                    const tracerouteData = tracerouteKey ? memberMetrics.traceroute_hops.get(tracerouteKey) : null;
                    
                    const connection = {
                        source_location: metric.labels.source_location,
                        source_instance: metric.labels.source_instance,
                        target_location: metric.labels.target_location,
                        target_instance: metric.labels.target_instance,
                        target_ip: metric.labels.target_ip,
                        type: 'tcp',
                        success: metric.value === 1,
                        latency_ms: latencyData ? latencyData.avg_latency_ms : null,
                        check_count: latencyData ? latencyData.count : 0,
                        bandwidth_mbps: bandwidthData ? bandwidthData.bandwidth_mbps : null,
                        traceroute_hops: tracerouteData ? tracerouteData.total_hops : null,
                        traceroute_max_latency_ms: tracerouteData ? tracerouteData.max_hop_latency_ms : null
                    };
                    
                    if (this.passesFilters(connection)) {
                        connections.push(connection);
                    }
                });
            }
            
            // HTTP connectivity (aggregate by target, not by endpoint)
            if (this.currentMetricView === 'all' || this.currentMetricView === 'http') {
                const httpTargets = new Map();
                memberMetrics.connectivity_http.forEach((metric) => {
                    const targetKey = `${metric.labels.target_location}:${metric.labels.target_instance}`;
                    if (!httpTargets.has(targetKey)) {
                        httpTargets.set(targetKey, {
                            source_location: metric.labels.source_location,
                            source_instance: metric.labels.source_instance,
                            target_location: metric.labels.target_location,
                            target_instance: metric.labels.target_instance,
                            target_ip: metric.labels.target_ip,
                            successes: 0,
                            total: 0
                        });
                    }
                    const target = httpTargets.get(targetKey);
                    target.total++;
                    if (metric.value === 1) target.successes++;
                });
                
                httpTargets.forEach((target) => {
                    // Find corresponding latency data
                    const latencyKey = `http:${target.target_location}:${target.target_instance}`;
                    const latencyData = memberMetrics.check_durations.get(latencyKey);
                    
                    // Find bandwidth data
                    const bandwidthKey = Object.keys(Object.fromEntries(memberMetrics.bandwidth_mbps)).find(key => {
                        const bwMetric = memberMetrics.bandwidth_mbps.get(key);
                        return bwMetric && bwMetric.labels.target_location === target.target_location &&
                               bwMetric.labels.target_instance === target.target_instance;
                    });
                    const bandwidthData = bandwidthKey ? memberMetrics.bandwidth_mbps.get(bandwidthKey) : null;
                    
                    // Find traceroute data
                    const tracerouteKey = Object.keys(Object.fromEntries(memberMetrics.traceroute_hops)).find(key => {
                        const trMetric = memberMetrics.traceroute_hops.get(key);
                        return trMetric && trMetric.labels.target_location === target.target_location &&
                               trMetric.labels.target_instance === target.target_instance;
                    });
                    
                    const tracerouteData = tracerouteKey ? memberMetrics.traceroute_hops.get(tracerouteKey) : null;
                    
                    const connection = {
                        source_location: target.source_location,
                        source_instance: target.source_instance,
                        target_location: target.target_location,
                        target_instance: target.target_instance,
                        target_ip: target.target_ip,
                        type: 'http',
                        success: target.successes > 0,
                        success_rate: target.total > 0 ? (target.successes / target.total * 100) : 0,
                        latency_ms: latencyData ? latencyData.avg_latency_ms : null,
                        check_count: latencyData ? latencyData.count : 0,
                        bandwidth_mbps: bandwidthData ? bandwidthData.bandwidth_mbps : null,
                        traceroute_hops: tracerouteData ? tracerouteData.total_hops : null,
                        traceroute_max_latency_ms: tracerouteData ? tracerouteData.max_hop_latency_ms : null
                    };
                    
                    if (this.passesFilters(connection)) {
                        connections.push(connection);
                    }
                });
            }
            
            // Bandwidth metrics
            if (this.currentMetricView === 'bandwidth') {
                memberMetrics.bandwidth_mbps.forEach((metric) => {
                    const connection = {
                        source_location: metric.labels.source_location,
                        source_instance: metric.labels.source_instance,
                        target_location: metric.labels.target_location,
                        target_instance: metric.labels.target_instance,
                        target_ip: metric.labels.target_ip,
                        type: 'bandwidth',
                        success: metric.bandwidth_mbps > 0,
                        bandwidth_mbps: metric.bandwidth_mbps,
                        latency_ms: null,
                        check_count: 1
                    };
                    
                    if (this.passesFilters(connection)) {
                        connections.push(connection);
                    }
                });
            }
            
            // Traceroute metrics
            if (this.currentMetricView === 'traceroute') {
                memberMetrics.traceroute_hops.forEach((metric) => {
                    const connection = {
                        source_location: metric.labels.source_location,
                        source_instance: metric.labels.source_instance,
                        target_location: metric.labels.target_location,
                        target_instance: metric.labels.target_instance,
                        target_ip: metric.labels.target_ip,
                        type: 'traceroute',
                        success: metric.total_hops > 0,
                        traceroute_hops: metric.total_hops,
                        traceroute_max_latency_ms: metric.max_hop_latency_ms,
                        latency_ms: null,
                        check_count: 1
                    };
                    
                    if (this.passesFilters(connection)) {
                        connections.push(connection);
                    }
                });
            }
        });
        
        return connections;
    }

    passesFilters(connection) {
        // Filter by success/failure
        if (this.currentFilters.showFailuresOnly && connection.success) {
            return false;
        }
        
        // Filter by source location
        if (this.currentFilters.sourceLocation !== 'all' && 
            connection.source_location !== this.currentFilters.sourceLocation) {
            return false;
        }
        
        // Filter by target location
        if (this.currentFilters.targetLocation !== 'all' && 
            connection.target_location !== this.currentFilters.targetLocation) {
            return false;
        }
        
        // Filter by latency range (only if latency data exists)
        if (connection.latency_ms !== null) {
            if (connection.latency_ms < this.currentFilters.minLatency || 
                connection.latency_ms > this.currentFilters.maxLatency) {
                return false;
            }
        }
        
        // Filter offline targets
        if (!this.currentFilters.showOfflineTargets) {
            const targetMember = this.members.find(m => 
                m.location === connection.target_location && 
                m.instance_id === connection.target_instance
            );
            
            if (!targetMember || targetMember.status === 'deregistered') {
                return false;
            }
            
            const now = Date.now() / 1000;
            const timeSinceLastSeen = now - targetMember.last_seen;
            if (timeSinceLastSeen > 600) { // 10 minutes offline threshold
                return false;
            }
        }
        
        return true;
    }

    switchMetricView(metric) {
        this.currentMetricView = metric;
        
        // If topology is visible, hide it and show metrics
        if (this.topologyVisible) {
            this.topologyVisible = false;
            const container = document.getElementById('topologyContainer');
            const metricsContainer = document.getElementById('metricsContainer');
            container.style.display = 'none';
            metricsContainer.style.display = 'block';
        }
        
        // Update button states
        document.querySelectorAll('.metric-toggle').forEach(btn => {
            if (btn.dataset.metric) {
                btn.classList.toggle('active', btn.dataset.metric === metric);
            } else {
                // This is the topology button - remove active state
                btn.classList.remove('active');
            }
        });
        
        // Re-render metrics
        this.renderMetrics();
    }

    formatTimestamp(timestamp) {
        const date = new Date(timestamp * 1000);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        
        return date.toLocaleDateString();
    }

    showError(message) {
        const container = document.getElementById('membersContainer');
        container.innerHTML = `
            <div class="error-message">
                <div class="error-icon">⚠️</div>
                <p>${message}</p>
            </div>
        `;
    }

    async refreshData() {
        const refreshBtn = document.getElementById('refreshBtn');
        refreshBtn.classList.add('spinning');
        
        try {
            await Promise.all([
                this.checkRegistryHealth(),
                this.fetchMembers()
            ]);
        } finally {
            refreshBtn.classList.remove('spinning');
        }
    }

    startDataPolling() {
        this.refreshData(); // Initial load
        
        this.intervalId = setInterval(() => {
            this.refreshData();
        }, this.updateInterval);
    }

    stopDataPolling() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }

    // Legacy topology methods removed - now using modal only

    async clearRedisData() {
        if (!confirm('Are you sure you want to clear all Redis data? This will remove all members, metrics, and topology data. This cannot be undone.')) {
            return;
        }
        
        try {
            const response = await fetch('/clear_redis', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            alert(`✅ Successfully cleared ${result.keys_deleted} Redis keys. Page will reload to reflect changes.`);
            
            // Reload the page to refresh all data
            window.location.reload();
            
        } catch (error) {
            console.error('Failed to clear Redis data:', error);
            alert(`❌ Failed to clear Redis data: ${error.message}`);
        }
    }

    async downloadTopologySvg() {
        try {
            const response = await fetch('/topology/svg?width=16&height=12');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const svgContent = await response.text();
            
            // Create download link
            const blob = new Blob([svgContent], { type: 'image/svg+xml' });
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `netring-topology-${new Date().toISOString().split('T')[0]}.svg`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
            
        } catch (error) {
            console.error('Failed to download topology SVG:', error);
            alert('Failed to download topology visualization');
        }
    }

    setupModalEventListeners() {
        const modal = document.getElementById('topologyModal');
        const closeBtn = document.getElementById('closeModal');

        // Close modal when clicking the X button
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.closeTopologyModal();
            });
        }

        // Close modal when clicking outside the content
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closeTopologyModal();
                }
            });
        }

        // Close modal with Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.style.display === 'block') {
                this.closeTopologyModal();
            }
        });
    }

    openTopologyModal() {
        const modal = document.getElementById('topologyModal');
        if (modal) {
            modal.style.display = 'block';
            document.body.style.overflow = 'hidden'; // Prevent background scrolling
            
            // Load topology data into modal
            this.loadTopologyIntoModal();
        }
    }

    closeTopologyModal() {
        const modal = document.getElementById('topologyModal');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = 'auto'; // Restore scrolling
        }
    }

    async loadTopologyIntoModal() {
        try {
            // Fetch topology data
            const response = await fetch('/topology');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Update modal stats
            this.updateModalTopologyStats(data.summary);
            
            // Update modal bottlenecks
            this.updateModalBottlenecksList(data.bottlenecks);
            
            // Load SVG visualization
            await this.loadModalTopologySvg();
            
        } catch (error) {
            console.error('Failed to load topology data into modal:', error);
            const modalVisualization = document.getElementById('modalTopologyVisualization');
            if (modalVisualization) {
                modalVisualization.innerHTML = `
                    <div style="text-align: center; color: var(--accent-danger);">
                        <p>⚠️ Failed to load topology data</p>
                        <p style="font-size: 0.9rem; margin-top: 8px;">${error.message}</p>
                    </div>
                `;
            }
        }
    }

    updateModalTopologyStats(summary) {
        const statsCards = document.querySelectorAll('#modalTopologyStats .modal-stat-card');
        
        if (statsCards.length >= 4) {
            statsCards[0].querySelector('.modal-stat-value').textContent = summary.total_locations || 0;
            statsCards[1].querySelector('.modal-stat-value').textContent = summary.total_routers || 0;
            statsCards[2].querySelector('.modal-stat-value').textContent = summary.routes_analyzed || 0;
            statsCards[3].querySelector('.modal-stat-value').textContent = summary.bottlenecks_found || 0;
        }
    }

    updateModalBottlenecksList(bottlenecks) {
        const bottlenecksList = document.getElementById('modalBottlenecksList');
        if (!bottlenecksList) return;

        if (!bottlenecks || bottlenecks.length === 0) {
            bottlenecksList.innerHTML = '<span style="color: var(--accent-primary);">✅ No network bottlenecks detected</span>';
            return;
        }

        const bottleneckItems = bottlenecks.map(bottleneck => {
            let severity = '⚠️';
            let color = 'var(--accent-warning)';
            
            if (bottleneck.severity === 'high') {
                severity = '🔴';
                color = 'var(--accent-danger)';
            } else if (bottleneck.severity === 'critical') {
                severity = '🚨';
                color = 'var(--accent-danger)';
            }
            
            return `
                <div style="color: ${color}; margin: 8px 0; padding: 8px 12px; background: rgba(218, 54, 51, 0.1); border-radius: 6px; border-left: 3px solid ${color};">
                    ${severity} <strong>${bottleneck.source}→${bottleneck.target}</strong> 
                    ${bottleneck.latency}ms latency ${bottleneck.description}
                </div>
            `;
        }).join('');

        bottlenecksList.innerHTML = bottleneckItems;
    }

    async loadModalTopologySvg() {
        try {
            // Use larger dimensions for modal view
            const response = await fetch('/topology/svg?width=20&height=15');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const svgContent = await response.text();
            const modalVisualization = document.getElementById('modalTopologyVisualization');
            
            if (modalVisualization) {
                modalVisualization.innerHTML = svgContent;
                
                // Initialize zoom/pan for modal SVG
                this.initializeModalZoomPan();
            }
            
        } catch (error) {
            console.error('Failed to load topology SVG into modal:', error);
            const modalVisualization = document.getElementById('modalTopologyVisualization');
            if (modalVisualization) {
                modalVisualization.innerHTML = `
                    <div style="text-align: center; color: var(--accent-danger);">
                        <p>⚠️ Failed to load topology visualization</p>
                        <p style="font-size: 0.9rem; margin-top: 8px;">${error.message}</p>
                    </div>
                `;
            }
        }
    }

    initializeModalZoomPan() {
        const svg = document.querySelector('#modalTopologyVisualization svg');
        if (!svg) return;
        
        let currentZoom = 1;
        let isPanning = false;
        let startPoint = {x: 0, y: 0};
        let currentTranslate = {x: 0, y: 0};
        
        // Mouse events for panning
        svg.addEventListener('mousedown', (evt) => {
            isPanning = true;
            const rect = svg.getBoundingClientRect();
            startPoint.x = evt.clientX - rect.left - currentTranslate.x;
            startPoint.y = evt.clientY - rect.top - currentTranslate.y;
            svg.style.cursor = 'grabbing';
        });
        
        svg.addEventListener('mousemove', (evt) => {
            if (!isPanning) return;
            
            const rect = svg.getBoundingClientRect();
            currentTranslate.x = evt.clientX - rect.left - startPoint.x;
            currentTranslate.y = evt.clientY - rect.top - startPoint.y;
            
            svg.style.transform = `translate(${currentTranslate.x}px, ${currentTranslate.y}px) scale(${currentZoom})`;
        });
        
        svg.addEventListener('mouseup', () => {
            isPanning = false;
            svg.style.cursor = 'grab';
        });
        
        svg.addEventListener('mouseleave', () => {
            isPanning = false;
            svg.style.cursor = 'default';
        });
        
        // Wheel event for zooming
        svg.addEventListener('wheel', (evt) => {
            evt.preventDefault();
            
            const delta = evt.deltaY > 0 ? 0.9 : 1.1;
            currentZoom = Math.min(Math.max(0.1, currentZoom * delta), 5);
            
            svg.style.transform = `translate(${currentTranslate.x}px, ${currentTranslate.y}px) scale(${currentZoom})`;
        });
        
        // Set initial cursor
        svg.style.cursor = 'grab';
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new NetringDashboard();
});

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (window.dashboard) {
        window.dashboard.stopDataPolling();
    }
});

// Expose refresh function globally for button onclick
function refreshData() {
    if (window.dashboard) {
        window.dashboard.refreshData();
    }
}

// Legacy toggleTopology function removed - now using modal only

function refreshTopology() {
    if (window.dashboard) {
        window.dashboard.loadTopologyIntoModal();
    }
}

function downloadTopologySvg() {
    if (window.dashboard) {
        window.dashboard.downloadTopologySvg();
    }
}

function clearRedisData() {
    if (window.dashboard) {
        window.dashboard.clearRedisData();
    }
}