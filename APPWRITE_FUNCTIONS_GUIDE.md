# 🚀 Appwrite Functions Deployment Guide

## 📋 Table of Contents
1. [Overview](#overview)
2. [Critical Appwrite Function Requirements](#critical-appwrite-function-requirements)
3. [Project Structure](#project-structure)
4. [Function Development Checklist](#function-development-checklist)
5. [Deployment Process](#deployment-process)
6. [Common Issues & Solutions](#common-issues--solutions)
7. [Testing & Debugging](#testing--debugging)
8. [Complete Examples](#complete-examples)
9. [Troubleshooting Guide](#troubleshooting-guide)

---

## 🎯 Overview

This guide documents the **critical requirements** and **best practices** for deploying Python functions to Appwrite Cloud. Based on extensive testing and iterations, these are the **non-negotiable** requirements that must be followed.

---

## ⚠️ Critical Appwrite Function Requirements

### 1. **Function Signature (CRITICAL)**
```python
# ❌ WRONG - Will fail
def main(request):
    pass

# ✅ CORRECT - Required signature
def main(context):
    pass
```

### 2. **Request Data Access (CRITICAL)**
```python
# ❌ WRONG - Will fail
if hasattr(request, 'json'):
    request_data = request.json()
else:
    request_data = json.loads(request)

# ✅ CORRECT - Use context
data = context.req.body
if data:
    try:
        request_data = json.loads(data)
    except json.JSONDecodeError as e:
        return context.res.json({
            "ok": False,
            "error": f"Invalid JSON: {e}",
            "message": "Failed to parse request"
        }, 400)
else:
    request_data = {"action": "HEALTH_CHECK"}
```

### 3. **Response Formatting (CRITICAL)**
```python
# ❌ WRONG - Will fail
return {
    'ok': True,
    'data': result
}

# ✅ CORRECT - Use context.res.json()
return context.res.json({
    "ok": True,
    "data": result
})

# For error responses
return context.res.json({
    "ok": False,
    "error": str(e),
    "message": "Internal server error"
}, 500)
```

### 4. **Import Path Structure (CRITICAL)**
```python
# ❌ WRONG - Will fail with ModuleNotFoundError
from shared.models import SomeModel

# ✅ CORRECT - Add to sys.path first
import os
import sys

# Add shared modules to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from shared.models import SomeModel
```

### 5. **Build Command Configuration (CRITICAL)**
```bash
# Must be set for each function
commands: "pip install -r requirements.txt"
```

---

## 📁 Project Structure

```
project/
├── functions/
│   ├── function_name/
│   │   ├── src/
│   │   │   └── main.py          # Entry point
│   │   └── requirements.txt     # Dependencies
│   └── ...
├── shared/                      # Shared modules
│   ├── models.py
│   ├── services/
│   │   ├── db.py
│   │   ├── email_service.py
│   │   └── ...
│   └── ...
├── deployment_packages/         # Generated tar.gz files
└── deploy_production_fixed.sh   # Deployment script
```

---

## ✅ Function Development Checklist

### Before Writing Code:
- [ ] Function signature: `def main(context):`
- [ ] Import path setup with `sys.path.insert(0, current_dir)`
- [ ] `requirements.txt` with all dependencies
- [ ] Error handling with `context.res.json()`

### Code Structure:
- [ ] Request parsing: `context.req.body`
- [ ] JSON parsing with try/catch
- [ ] Response formatting: `context.res.json()`
- [ ] Proper error handling
- [ ] Logging with `context.log()` or `logger`

### Dependencies:
- [ ] All packages in `requirements.txt`
- [ ] No hardcoded paths
- [ ] Fallback imports for optional services

---

## 🚀 Deployment Process

### 1. **Create Deployment Script**
```bash
#!/bin/bash
# deploy_production_fixed.sh

set -e

APPWRITE_ENDPOINT="https://cloud.appwrite.io/v1"
APPWRITE_PROJECT_ID="YOUR_PROJECT_ID"
APPWRITE_API_KEY="YOUR_API_KEY"

# Ensure deployment_packages directory exists
mkdir -p deployment_packages

declare -A functions
functions["admin_router"]="functions/admin_router"
functions["certificate_worker"]="functions/certificate_worker"
functions["graphy_webhook"]="functions/graphy_webhook"
functions["sop_router"]="functions/sop_router"

echo "🚀 Starting Production Deployment..."

for func_name in "${!functions[@]}"; do
    func_path="${functions[$func_name]}"
    echo "📦 Packaging ${func_name}..."

    # Create a temporary directory for packaging
    temp_dir="temp_package_${func_name}"
    mkdir -p "$temp_dir"

    # Copy main.py and requirements.txt to the root of the temp directory
    cp "${func_path}/src/main.py" "${temp_dir}/main.py"
    cp "${func_path}/requirements.txt" "${temp_dir}/requirements.txt"

    # Copy the entire shared directory
    cp -R shared "${temp_dir}/shared"

    # Create the tar.gz package
    tar -czf "deployment_packages/${func_name}.tar.gz" -C "$temp_dir" .

    # Clean up the temporary directory
    rm -rf "$temp_dir"

    echo "✅ ${func_name} packaged successfully"
done

echo "🎯 Deployment packages created:"
ls -lh deployment_packages/*.tar.gz
```

### 2. **Set Build Commands**
```bash
# For each function, set the build command
curl -X PUT "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME" \
  -H "X-Appwrite-Project: YOUR_PROJECT_ID" \
  -H "X-Appwrite-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Function Name", "execute": ["users"], "commands": "pip install -r requirements.txt"}'
```

### 3. **Deploy Functions**
```bash
# Deploy each function
curl -X POST "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME/deployments" \
  -H "X-Appwrite-Project: YOUR_PROJECT_ID" \
  -H "X-Appwrite-Key: YOUR_API_KEY" \
  -H "Content-Type: multipart/form-data" \
  -F "entrypoint=main.py" \
  -F "code=@deployment_packages/FUNCTION_NAME.tar.gz" \
  -F "activate=true"
```

---

## 🔧 Common Issues & Solutions

### Issue 1: `ModuleNotFoundError: No module named 'shared'`
**Cause:** Incorrect import path setup
**Solution:**
```python
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
```

### Issue 2: `ModuleNotFoundError: No module named 'pydantic'`
**Cause:** Build command not set or not working
**Solution:**
```bash
# Set build command
curl -X PUT "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME" \
  -H "X-Appwrite-Project: PROJECT_ID" \
  -H "X-Appwrite-Key: API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"commands": "pip install -r requirements.txt"}'

# Redeploy to trigger build
curl -X POST "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME/deployments" \
  -H "X-Appwrite-Project: PROJECT_ID" \
  -H "X-Appwrite-Key: API_KEY" \
  -H "Content-Type: multipart/form-data" \
  -F "entrypoint=main.py" \
  -F "code=@deployment_packages/FUNCTION_NAME.tar.gz" \
  -F "activate=true"
```

### Issue 3: `'dict' object has no attribute 'to_dict'`
**Cause:** Incorrect response handling
**Solution:**
```python
# Handle both dict and object responses
if hasattr(response, 'to_dict'):
    return context.res.json(response.to_dict())
else:
    return context.res.json(response)
```

### Issue 4: `the JSON object must be str, bytes or bytearray, not Context`
**Cause:** Wrong function signature
**Solution:**
```python
# Change from
def main(request):
# To
def main(context):
```

### Issue 5: `__init__() got an unexpected keyword argument 'sendgrid_api_key'`
**Cause:** Service initialization with wrong parameters
**Solution:**
```python
# Use simplified service initialization
self.email = EmailService(self.db.client)
```

---

## 🧪 Testing & Debugging

### Health Check Test
```bash
curl -X POST "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME/executions" \
  -H "X-Appwrite-Project: PROJECT_ID" \
  -H "X-Appwrite-Key: API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"data": "{\"action\": \"HEALTH_CHECK\"}"}'
```

### Check Function Status
```bash
curl -X GET "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME" \
  -H "X-Appwrite-Project: PROJECT_ID" \
  -H "X-Appwrite-Key: API_KEY"
```

### View Function Logs
```bash
curl -X GET "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME/executions" \
  -H "X-Appwrite-Project: PROJECT_ID" \
  -H "X-Appwrite-Key: API_KEY"
```

---

## 📝 Complete Examples

### Example 1: Basic Function Template
```python
import os
import sys
import json
import logging

# Add shared modules to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from shared.models import SomeModel
from shared.services.db import AppwriteClient

logger = logging.getLogger(__name__)

def main(context):
    """Main function entry point for Appwrite function."""
    try:
        # Get request data from context
        data = context.req.body
        
        # Parse JSON if provided
        if data:
            try:
                request_data = json.loads(data)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                return context.res.json({
                    "ok": False,
                    "error": f"Invalid JSON: {e}",
                    "message": "Failed to parse request"
                }, 400)
        else:
            # Default to health check if no data provided
            request_data = {"action": "HEALTH_CHECK"}
            logger.info("No data provided, using default health check")
        
        # Handle health check
        if request_data.get('action') == 'HEALTH_CHECK':
            return context.res.json({
                "ok": True,
                "status": 200,
                "data": {"message": "Function is healthy"}
            })
        
        # Your business logic here
        result = process_request(request_data)
        
        # Return response
        return context.res.json({
            "ok": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        return context.res.json({
            "ok": False,
            "error": str(e),
            "message": "Internal server error"
        }, 500)

def process_request(request_data):
    """Process the request data."""
    # Your business logic here
    return {"processed": True}
```

### Example 2: Requirements.txt
```
appwrite>=4.0.0
pydantic>=2.0.0
requests>=2.31.0
jinja2>=3.1.0
pyppeteer>=1.0.0
beautifulsoup4>=4.12.0
pyjwt>=2.8.0
email-validator>=2.0.0
```

---

## 🔍 Troubleshooting Guide

### Step 1: Check Function Status
```bash
curl -X GET "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME" \
  -H "X-Appwrite-Project: PROJECT_ID" \
  -H "X-Appwrite-Key: API_KEY" | jq '.latestDeploymentStatus'
```

### Step 2: Check Build Logs
```bash
curl -X GET "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME/deployments" \
  -H "X-Appwrite-Project: PROJECT_ID" \
  -H "X-Appwrite-Key: API_KEY" | jq '.[0].buildLogs'
```

### Step 3: Test Function Execution
```bash
curl -X POST "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME/executions" \
  -H "X-Appwrite-Project: PROJECT_ID" \
  -H "X-Appwrite-Key: API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"data": "{\"action\": \"HEALTH_CHECK\"}"}'
```

### Step 4: Check Execution Logs
```bash
curl -X GET "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME/executions" \
  -H "X-Appwrite-Project: PROJECT_ID" \
  -H "X-Appwrite-Key: API_KEY" | jq '.[0].logs'
```

---

## 🎯 Quick Reference Commands

### Create Function
```bash
curl -X POST "https://cloud.appwrite.io/v1/functions" \
  -H "X-Appwrite-Project: PROJECT_ID" \
  -H "X-Appwrite-Key: API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "functionId": "FUNCTION_NAME",
    "name": "Function Display Name",
    "runtime": "python-3.9",
    "execute": ["users"]
  }'
```

### Set Environment Variables
```bash
curl -X POST "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME/vars" \
  -H "X-Appwrite-Project: PROJECT_ID" \
  -H "X-Appwrite-Key: API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "VARIABLE_NAME",
    "value": "VARIABLE_VALUE",
    "secret": true
  }'
```

### Update Function Settings
```bash
curl -X PUT "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME" \
  -H "X-Appwrite-Project: PROJECT_ID" \
  -H "X-Appwrite-Key: API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Name",
    "execute": ["users"],
    "commands": "pip install -r requirements.txt",
    "timeout": 15
  }'
```

---

## 🚨 Critical Success Factors

1. **Function Signature**: Always use `def main(context):`
2. **Request Access**: Always use `context.req.body`
3. **Response Format**: Always use `context.res.json()`
4. **Import Paths**: Always set `sys.path.insert(0, current_dir)`
5. **Build Commands**: Always set `commands: "pip install -r requirements.txt"`
6. **Package Structure**: Always put `main.py` and `shared/` at root of tar.gz
7. **Error Handling**: Always wrap in try/catch with proper error responses
8. **Dependencies**: Always list all packages in `requirements.txt`

---

## 📚 Additional Resources

- [Appwrite Functions Documentation](https://appwrite.io/docs/functions)
- [Appwrite Python SDK](https://github.com/appwrite/sdk-for-python)
- [Appwrite REST API Reference](https://appwrite.io/docs/references)

---

**Remember**: Appwrite functions have very specific requirements. Following this guide will save hours of debugging and iteration. When in doubt, refer to the examples and troubleshooting steps above.

