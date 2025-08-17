#!/bin/bash

# Detect host LAN IP for Docker Compose
# This script finds the host's LAN IP and exports it for Docker Compose

detect_lan_ip() {
    local detected_ip=""
    
    # Method 1: Use the same socket technique that works on the host
    detected_ip=$(python3 -c "
import socket
try:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(('8.8.8.8', 80))
        print(s.getsockname()[0])
except:
    print('')
" 2>/dev/null)
    
    # Validate it's a private IP (LAN)
    if [[ $detected_ip =~ ^10\. ]] || [[ $detected_ip =~ ^192\.168\. ]] || [[ $detected_ip =~ ^172\.(1[6-9]|2[0-9]|3[01])\. ]]; then
        echo "$detected_ip"
        return 0
    fi
    
    # Method 2: Try ip route (Linux)
    if command -v ip >/dev/null 2>&1; then
        detected_ip=$(ip route get 8.8.8.8 2>/dev/null | grep -oP 'src \K[0-9.]+' | head -1)
        if [[ $detected_ip =~ ^10\. ]] || [[ $detected_ip =~ ^192\.168\. ]] || [[ $detected_ip =~ ^172\.(1[6-9]|2[0-9]|3[01])\. ]]; then
            echo "$detected_ip"
            return 0
        fi
    fi
    
    # Method 3: Try ifconfig/ipconfig fallback
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        detected_ip=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | grep -E "(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)" | head -1 | awk '{print $2}')
    else
        # Linux
        detected_ip=$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E "^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)" | head -1)
    fi
    
    if [[ -n "$detected_ip" ]]; then
        echo "$detected_ip"
        return 0
    fi
    
    echo ""
    return 1
}

main() {
    echo "🔍 Detecting host LAN IP..."
    
    HOST_IP=$(detect_lan_ip)
    
    if [[ -z "$HOST_IP" ]]; then
        echo "❌ Failed to detect LAN IP automatically"
        echo "Please run manually with: HOST_IP=your.lan.ip docker-compose up"
        exit 1
    fi
    
    echo "✅ Detected LAN IP: $HOST_IP"
    
    # Export for Docker Compose
    export HOST_IP
    
    # Save to .env file for Docker Compose
    echo "HOST_IP=$HOST_IP" > .env
    echo "📝 Saved to .env file"
    
    # Run Docker Compose with the detected IP
    if [[ "$1" == "--start" ]]; then
        echo "🚀 Starting Docker Compose with HOST_IP=$HOST_IP"
        docker-compose up -d
    else
        echo "💡 Run 'docker-compose up -d' or './detect-host-ip.sh --start' to start services"
        echo "💡 HOST_IP is set to: $HOST_IP"
    fi
}

main "$@"