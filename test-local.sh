#!/bin/bash

# Test script for local Netring testing with two members

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Command functions
start_test() {
    log_info "Starting Netring test environment..."
    
    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    # Start services
    log_info "Building images..."
    docker-compose -f test-docker-compose.yml build --no-cache
    log_info "Starting Redis and Registry..."
    docker-compose -f test-docker-compose.yml up -d redis registry
    
    # Wait for registry to be healthy
    log_info "Waiting for registry to be ready..."
    for i in {1..30}; do
        if curl -sf http://localhost:8756/health >/dev/null 2>&1; then
            log_success "Registry is ready!"
            break
        fi
        if [ $i -eq 30 ]; then
            log_error "Registry failed to start within 30 seconds"
            docker-compose -f test-docker-compose.yml logs registry
            exit 1
        fi
        sleep 1
    done
    
    # Start members
    log_info "Starting Test1 and Test2 members..."
    docker-compose -f test-docker-compose.yml up -d member-test1 member-test2
    
    # Wait for members to be ready
    log_info "Waiting for members to be ready..."
    sleep 10
    
    # Check member health
    for port in 8757 8758; do
        if curl -sf http://localhost:$port/health >/dev/null 2>&1; then
            log_success "Member on port $port is ready!"
        else
            log_warning "Member on port $port is not responding yet"
        fi
    done
    
    log_success "Test environment started!"
    show_status
}

stop_test() {
    log_info "Stopping test environment..."
    docker-compose -f test-docker-compose.yml down
    log_success "Test environment stopped!"
}

restart_test() {
    log_info "Restarting test environment..."
    stop_test
    sleep 2
    start_test
}

show_status() {
    echo
    log_info "=== Test Environment Status ==="
    echo
    
    # Check services
    echo "Docker containers:"
    docker-compose -f test-docker-compose.yml ps
    echo
    
    # Check endpoints
    echo "Service endpoints:"
    echo "  Registry UI:    http://localhost:8756"
    echo "  Registry API:   http://localhost:8756/health"
    echo "  Member Test1:   http://localhost:8757/health"
    echo "  Member Test2:   http://localhost:8758/health"
    echo
    
    # Check member registration
    echo "Registered members:"
    if curl -sf http://localhost:8756/members >/dev/null 2>&1; then
        curl -s http://localhost:8756/members | jq -r '.members[] | "  \(.location) (\(.instance_id[0:8])) - \(.ip):\(.port)"' 2>/dev/null || \
        curl -s http://localhost:8756/members | grep -o '"location":"[^"]*"' | sed 's/"location":"/  /g' | sed 's/"//g'
    else
        echo "  Registry not responding"
    fi
    echo
}

show_logs() {
    local service=${1:-""}
    if [ -n "$service" ]; then
        log_info "Showing logs for $service..."
        docker-compose -f test-docker-compose.yml logs -f "$service"
    else
        log_info "Showing logs for all services..."
        docker-compose -f test-docker-compose.yml logs -f
    fi
}

test_connectivity() {
    log_info "Testing connectivity between members..."
    
    # Wait a bit for metrics to be generated
    log_info "Waiting for connectivity checks to run..."
    sleep 90
    
    # Check metrics
    log_info "Checking aggregated metrics..."
    if curl -sf http://localhost:8756/metrics >/dev/null 2>&1; then
        local metrics=$(curl -s http://localhost:8756/metrics)
        local test1_metrics=$(echo "$metrics" | jq '.metrics | keys | length' 2>/dev/null || echo "0")
        log_success "Found metrics from $test1_metrics members"
        
        # Show some sample connectivity data
        echo "$metrics" | jq '.metrics | to_entries[] | {member: .key[0:8], tcp_checks: (.value.connectivity_tcp | length), http_checks: (.value.connectivity_http | length)}' 2>/dev/null || \
        log_info "Metrics data available (install jq for pretty formatting)"
    else
        log_error "Failed to retrieve metrics from registry"
    fi
}

# Main command handling
case "${1:-help}" in
    start)
        start_test
        ;;
    stop)
        stop_test
        ;;
    restart)
        restart_test
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$2"
        ;;
    test)
        test_connectivity
        ;;
    help|*)
        echo "Usage: $0 {start|stop|restart|status|logs [service]|test|help}"
        echo
        echo "Commands:"
        echo "  start    - Start the test environment"
        echo "  stop     - Stop the test environment"
        echo "  restart  - Restart the test environment"
        echo "  status   - Show current status"
        echo "  logs     - Show logs (optionally for specific service)"
        echo "  test     - Test connectivity and show metrics"
        echo "  help     - Show this help"
        echo
        echo "Services: redis, registry, member-test1, member-test2"
        echo
        echo "After starting, visit http://localhost:8756 to see the dashboard"
        ;;
esac