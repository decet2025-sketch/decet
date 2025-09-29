# 🚀 Appwrite Functions - Quick Reference

## ⚡ Critical Commands

### 1. Set Build Command (REQUIRED)
```bash
curl -X PUT "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME" \
  -H "X-Appwrite-Project: PROJECT_ID" \
  -H "X-Appwrite-Key: API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"commands": "pip install -r requirements.txt"}'
```

### 2. Deploy Function
```bash
curl -X POST "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME/deployments" \
  -H "X-Appwrite-Project: PROJECT_ID" \
  -H "X-Appwrite-Key: API_KEY" \
  -H "Content-Type: multipart/form-data" \
  -F "entrypoint=main.py" \
  -F "code=@deployment_packages/FUNCTION_NAME.tar.gz" \
  -F "activate=true"
```

### 3. Test Function
```bash
curl -X POST "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME/executions" \
  -H "X-Appwrite-Project: PROJECT_ID" \
  -H "X-Appwrite-Key: API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"data": "{\"action\": \"HEALTH_CHECK\"}"}'
```

## 🔧 Function Template (COPY-PASTE READY)

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

## 📦 Deployment Script (COPY-PASTE READY)

```bash
#!/bin/bash
set -e

APPWRITE_ENDPOINT="https://cloud.appwrite.io/v1"
APPWRITE_PROJECT_ID="YOUR_PROJECT_ID"
APPWRITE_API_KEY="YOUR_API_KEY"

mkdir -p deployment_packages

declare -A functions
functions["function1"]="functions/function1"
functions["function2"]="functions/function2"

for func_name in "${!functions[@]}"; do
    func_path="${functions[$func_name]}"
    echo "📦 Packaging ${func_name}..."

    temp_dir="temp_package_${func_name}"
    mkdir -p "$temp_dir"

    cp "${func_path}/src/main.py" "${temp_dir}/main.py"
    cp "${func_path}/requirements.txt" "${temp_dir}/requirements.txt"
    cp -R shared "${temp_dir}/shared"

    tar -czf "deployment_packages/${func_name}.tar.gz" -C "$temp_dir" .
    rm -rf "$temp_dir"

    echo "✅ ${func_name} packaged successfully"
done
```

## 🚨 Common Errors & Quick Fixes

| Error | Quick Fix |
|-------|-----------|
| `ModuleNotFoundError: No module named 'shared'` | Add `sys.path.insert(0, current_dir)` |
| `ModuleNotFoundError: No module named 'pydantic'` | Set build command: `pip install -r requirements.txt` |
| `'dict' object has no attribute 'to_dict'` | Use `context.res.json(response)` |
| `the JSON object must be str, bytes or bytearray, not Context` | Change `def main(request):` to `def main(context):` |
| `__init__() got an unexpected keyword argument` | Simplify service initialization |

## ✅ Success Indicators

- **Status**: `completed` (not `failed`)
- **Response Code**: `200`
- **Response Body**: Valid JSON
- **Logs**: No error messages

## 🎯 Your Project Values

Replace these in the commands above:
- `PROJECT_ID`: `68cf04e30030d4b38d19`
- `API_KEY`: `standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142`

