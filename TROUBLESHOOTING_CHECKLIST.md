# 🔧 Appwrite Functions Troubleshooting Checklist

## 🚨 When Function Fails - Step-by-Step Debugging

### Step 1: Check Function Status
```bash
curl -X GET "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME" \
  -H "X-Appwrite-Project: 68cf04e30030d4b38d19" \
  -H "X-Appwrite-Key: standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142"
```

**Look for:**
- `"latestDeploymentStatus": "ready"` ✅
- `"latestDeploymentStatus": "building"` ⏳ (wait)
- `"latestDeploymentStatus": "failed"` ❌ (check build logs)

### Step 2: Check Build Command
```bash
# Verify build command is set
curl -X GET "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME" \
  -H "X-Appwrite-Project: 68cf04e30030d4b38d19" \
  -H "X-Appwrite-Key: standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142" | jq '.commands'
```

**Should return:** `"pip install -r requirements.txt"`

**If not set:**
```bash
curl -X PUT "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME" \
  -H "X-Appwrite-Project: 68cf04e30030d4b38d19" \
  -H "X-Appwrite-Key: standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142" \
  -H "Content-Type: application/json" \
  -d '{"commands": "pip install -r requirements.txt"}'
```

### Step 3: Test Function Execution
```bash
curl -X POST "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME/executions" \
  -H "X-Appwrite-Project: 68cf04e30030d4b38d19" \
  -H "X-Appwrite-Key: standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142" \
  -H "Content-Type: application/json" \
  -d '{"data": "{\"action\": \"HEALTH_CHECK\"}"}'
```

### Step 4: Check Execution Logs
```bash
curl -X GET "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME/executions" \
  -H "X-Appwrite-Project: 68cf04e30030d4b38d19" \
  -H "X-Appwrite-Key: standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142" | jq '.[0]'
```

---

## 🔍 Error Analysis Guide

### Error: `ModuleNotFoundError: No module named 'shared'`
**Cause:** Import path not set correctly
**Fix:**
```python
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
```

### Error: `ModuleNotFoundError: No module named 'pydantic'`
**Cause:** Dependencies not installed
**Fix:**
1. Check `requirements.txt` has `pydantic>=2.0.0`
2. Set build command: `pip install -r requirements.txt`
3. Redeploy function

### Error: `'dict' object has no attribute 'to_dict'`
**Cause:** Wrong response handling
**Fix:**
```python
# Instead of
return response.to_dict()

# Use
if hasattr(response, 'to_dict'):
    return context.res.json(response.to_dict())
else:
    return context.res.json(response)
```

### Error: `the JSON object must be str, bytes or bytearray, not Context`
**Cause:** Wrong function signature
**Fix:**
```python
# Change from
def main(request):
# To
def main(context):
```

### Error: `__init__() got an unexpected keyword argument 'sendgrid_api_key'`
**Cause:** Service initialization with wrong parameters
**Fix:**
```python
# Instead of
EmailService(sendgrid_api_key=..., smtp_config=...)

# Use
EmailService(self.db.client)
```

### Error: `handle_request() missing 1 required positional argument: 'headers'`
**Cause:** Method signature mismatch
**Fix:**
```python
# Change from
def handle_request(self, request_data, headers):
# To
def handle_request(self, request_data, headers=None):
```

---

## 🚀 Redeployment Process

When you need to redeploy after fixes:

### 1. Update Code
Make your fixes in the source files.

### 2. Rebuild Package
```bash
./deploy_production_fixed.sh
```

### 3. Redeploy Function
```bash
curl -X POST "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME/deployments" \
  -H "X-Appwrite-Project: 68cf04e30030d4b38d19" \
  -H "X-Appwrite-Key: standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142" \
  -H "Content-Type: multipart/form-data" \
  -F "entrypoint=main.py" \
  -F "code=@deployment_packages/FUNCTION_NAME.tar.gz" \
  -F "activate=true"
```

### 4. Wait and Test
```bash
sleep 20
curl -X POST "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME/executions" \
  -H "X-Appwrite-Project: 68cf04e30030d4b38d19" \
  -H "X-Appwrite-Key: standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142" \
  -H "Content-Type: application/json" \
  -d '{"data": "{\"action\": \"HEALTH_CHECK\"}"}'
```

---

## ✅ Success Verification

### Function is Working When:
- **Status**: `"completed"` (not `"failed"`)
- **Response Code**: `200`
- **Response Body**: Valid JSON
- **Logs**: No error messages

### Expected Responses:
- **Health Check**: `{"ok":true,"status":200,"data":{"message":"Function is healthy"}}`
- **Auth Required**: `{"ok":false,"status":401,"error":{"code":"AUTH_ERROR","message":"Unauthorized"}}`
- **Error**: `{"ok":false,"error":"Error message","message":"Internal server error"}`

---

## 🎯 Quick Fix Commands

### Fix Import Issues
```bash
# Add to main.py
echo 'import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)' > temp_imports.py
```

### Fix Build Command
```bash
curl -X PUT "https://cloud.appwrite.io/v1/functions/FUNCTION_NAME" \
  -H "X-Appwrite-Project: 68cf04e30030d4b38d19" \
  -H "X-Appwrite-Key: standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142" \
  -H "Content-Type: application/json" \
  -d '{"commands": "pip install -r requirements.txt"}'
```

### Test All Functions
```bash
for func in admin_router certificate_worker graphy_webhook sop_router; do
  echo "Testing $func..."
  curl -X POST "https://cloud.appwrite.io/v1/functions/$func/executions" \
    -H "X-Appwrite-Project: 68cf04e30030d4b38d19" \
    -H "X-Appwrite-Key: standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142" \
    -H "Content-Type: application/json" \
    -d '{"data": "{\"action\": \"HEALTH_CHECK\"}"}' | jq '.status'
done
```

---

## 📞 Emergency Contacts

If you're still stuck:
1. Check the main guide: `APPWRITE_FUNCTIONS_GUIDE.md`
2. Use the quick reference: `QUICK_REFERENCE.md`
3. Follow this troubleshooting checklist step by step
4. Remember: Most issues are import paths, build commands, or function signatures
