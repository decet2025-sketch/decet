#!/bin/bash

# Production Deployment Script - FIXED VERSION
# This script creates deployment packages with shared modules in the correct location

set -e

echo "🚀 Starting Production Deployment (Fixed Version)..."

# Clean up previous deployments
rm -rf deployment_packages/
mkdir -p deployment_packages

# Function names
FUNCTIONS=("admin_router" "certificate_worker" "graphy_webhook" "sop_router" "completion_checker")

for func in "${FUNCTIONS[@]}"; do
    echo "📦 Packaging $func..."
    
    # Create function-specific deployment directory
    mkdir -p "deployment_packages/$func"
    
    # Copy the main.py file
    cp "functions/$func/src/main.py" "deployment_packages/$func/"
    
    # Copy the requirements.txt file
    cp "functions/$func/requirements.txt" "deployment_packages/$func/"
    
    # Copy the shared directory contents directly to the function directory
    # This ensures shared modules are accessible from main.py
    cp -r "shared" "deployment_packages/$func/"
    
    # Create tar.gz package with the correct structure
    cd "deployment_packages/$func"
    tar -czf "../${func}.tar.gz" main.py requirements.txt shared/
    cd ../..
    
    echo "✅ $func packaged successfully"
done

echo ""
echo "🎯 Deployment packages created:"
ls -la deployment_packages/*.tar.gz

echo ""
echo "📋 Package structure:"
echo "  - main.py (entrypoint)"
echo "  - requirements.txt (dependencies)"
echo "  - shared/ (modules accessible from main.py)"
echo ""
echo "🚀 Ready for production deployment!"
