#!/bin/bash

# Production deployment script for Netring
# Automatically detects host IP and starts the member service

echo "🚀 Starting Netring member with automatic IP detection..."

# Detect IP and start services
./detect-host-ip.sh --start