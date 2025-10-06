#!/bin/bash

# Production Deployment Script for Certificate Management Functions
# This script creates proper deployment packages with shared modules

set -e

echo "🚀 Starting Production Deployment..."

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
    
    # Copy the shared directory
    cp -r "shared" "deployment_packages/$func/"
    
    # Create tar.gz package
    cd "deployment_packages/$func"
    tar -czf "../${func}.tar.gz" main.py requirements.txt shared/
    cd ../..
    
    echo "✅ $func packaged successfully"
done

echo ""
echo "🎯 Deployment packages created:"
ls -la deployment_packages/*.tar.gz

echo ""
echo "📋 Next steps:"
echo "1. Deploy each function using the tar.gz packages"
echo "2. Set build command to: pip install -r requirements.txt"
echo "3. Set entrypoint to: main.py"
echo ""
echo "🚀 Ready for production deployment!"
