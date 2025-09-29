#!/bin/bash

# Script to add completion tracking attributes to production database
# This adds the new fields needed for the completion checker scheduler

set -e

APPWRITE_ENDPOINT="https://cloud.appwrite.io/v1"
APPWRITE_PROJECT_ID="main"
APPWRITE_API_KEY="standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142"

echo "🔧 Adding completion tracking attributes to production database..."

# Add status attribute
echo "📝 Adding 'status' attribute..."
curl -X POST "$APPWRITE_ENDPOINT/databases/main/collections/learners/attributes/string" \
  -H "X-Appwrite-Project: $APPWRITE_PROJECT_ID" \
  -H "X-Appwrite-Key: $APPWRITE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "status",
    "size": 50,
    "required": true,
    "default": "enrolled"
  }'

echo "✅ Status attribute added"

# Add completion_data attribute
echo "📝 Adding 'completion_data' attribute..."
curl -X POST "$APPWRITE_ENDPOINT/databases/main/collections/learners/attributes/string" \
  -H "X-Appwrite-Project: $APPWRITE_PROJECT_ID" \
  -H "X-Appwrite-Key: $APPWRITE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "completion_data",
    "size": 5000,
    "required": false
  }'

echo "✅ Completion data attribute added"

# Add completed_at attribute
echo "📝 Adding 'completed_at' attribute..."
curl -X POST "$APPWRITE_ENDPOINT/databases/main/collections/learners/attributes/datetime" \
  -H "X-Appwrite-Project: $APPWRITE_PROJECT_ID" \
  -H "X-Appwrite-Key: $APPWRITE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "completed_at",
    "required": false
  }'

echo "✅ Completed at attribute added"

# Add last_completion_check attribute
echo "📝 Adding 'last_completion_check' attribute..."
curl -X POST "$APPWRITE_ENDPOINT/databases/main/collections/learners/attributes/datetime" \
  -H "X-Appwrite-Project: $APPWRITE_PROJECT_ID" \
  -H "X-Appwrite-Key: $APPWRITE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "last_completion_check",
    "required": false
  }'

echo "✅ Last completion check attribute added"

# Add status index
echo "📝 Adding 'status' index..."
curl -X POST "$APPWRITE_ENDPOINT/databases/main/collections/learners/indexes" \
  -H "X-Appwrite-Project: $APPWRITE_PROJECT_ID" \
  -H "X-Appwrite-Key: $APPWRITE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "status_index",
    "type": "key",
    "attributes": ["status"]
  }'

echo "✅ Status index added"

# Add last_completion_check index
echo "📝 Adding 'last_completion_check' index..."
curl -X POST "$APPWRITE_ENDPOINT/databases/main/collections/learners/indexes" \
  -H "X-Appwrite-Project: $APPWRITE_PROJECT_ID" \
  -H "X-Appwrite-Key: $APPWRITE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "last_completion_check_index",
    "type": "key",
    "attributes": ["last_completion_check"]
  }'

echo "✅ Last completion check index added"

echo ""
echo "🎉 All completion tracking attributes added to production database!"
echo ""
echo "📋 Added attributes:"
echo "  - status (string, 50 chars, required, default: 'enrolled')"
echo "  - completion_data (string, 5000 chars, optional)"
echo "  - completed_at (datetime, optional)"
echo "  - last_completion_check (datetime, optional)"
echo ""
echo "📋 Added indexes:"
echo "  - status_index (for querying enrolled learners)"
echo "  - last_completion_check_index (for tracking check history)"
echo ""
echo "🚀 Your completion checker scheduler is now ready to use!"
