#!/bin/bash

# Setup Activity Logs Collection
# This script creates the activity_logs collection in Appwrite

set -e

# Configuration
APPWRITE_ENDPOINT="https://cloud.appwrite.io/v1"
PROJECT_ID="68cf04e30030d4b38d19"
API_KEY="standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142"
DATABASE_ID="main"

echo "🚀 Setting up Activity Logs Collection..."

# Create activity_logs collection
echo "📝 Creating activity_logs collection..."
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "collectionId": "activity_logs",
    "name": "Activity Logs",
    "permissions": [
      "read(\"any\")",
      "create(\"any\")",
      "update(\"any\")",
      "delete(\"any\")"
    ],
    "documentSecurity": false
  }'

echo ""
echo "✅ Collection created successfully!"

# Add attributes
echo "📋 Adding attributes..."

# activity_type
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/attributes/string" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "activity_type",
    "size": 100,
    "required": true,
    "array": false
  }'

# actor
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/attributes/string" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "actor",
    "size": 255,
    "required": true,
    "array": false
  }'

# actor_email
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/attributes/string" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "actor_email",
    "size": 255,
    "required": false,
    "array": false
  }'

# actor_role
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/attributes/string" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "actor_role",
    "size": 50,
    "required": false,
    "array": false
  }'

# target
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/attributes/string" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "target",
    "size": 255,
    "required": false,
    "array": false
  }'

# target_email
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/attributes/string" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "target_email",
    "size": 255,
    "required": false,
    "array": false
  }'

# organization_website
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/attributes/string" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "organization_website",
    "size": 255,
    "required": false,
    "array": false
  }'

# course_id
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/attributes/string" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "course_id",
    "size": 255,
    "required": false,
    "array": false
  }'

# details
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/attributes/string" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "details",
    "size": 2000,
    "required": true,
    "array": false
  }'

# status
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/attributes/string" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "status",
    "size": 50,
    "required": true,
    "array": false
  }'

# error_message
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/attributes/string" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "error_message",
    "size": 1000,
    "required": false,
    "array": false
  }'

# metadata
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/attributes/string" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "metadata",
    "size": 5000,
    "required": false,
    "array": false
  }'

# timestamp
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/attributes/datetime" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "timestamp",
    "required": true,
    "array": false
  }'

echo ""
echo "✅ Attributes added successfully!"

# Wait for attributes to be ready
echo "⏳ Waiting for attributes to be ready..."
sleep 10

# Add indexes
echo "📊 Adding indexes..."

# activity_type_index
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/indexes" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "activity_type_index",
    "type": "key",
    "attributes": ["activity_type"]
  }'

# actor_index
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/indexes" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "actor_index",
    "type": "key",
    "attributes": ["actor"]
  }'

# organization_website_index
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/indexes" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "organization_website_index",
    "type": "key",
    "attributes": ["organization_website"]
  }'

# course_id_index
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/indexes" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "course_id_index",
    "type": "key",
    "attributes": ["course_id"]
  }'

# status_index
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/indexes" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "status_index",
    "type": "key",
    "attributes": ["status"]
  }'

# timestamp_index
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/indexes" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "timestamp_index",
    "type": "key",
    "attributes": ["timestamp"]
  }'

# actor_role_index
curl -X POST "${APPWRITE_ENDPOINT}/databases/${DATABASE_ID}/collections/activity_logs/indexes" \
  -H "X-Appwrite-Project: ${PROJECT_ID}" \
  -H "X-Appwrite-Key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "actor_role_index",
    "type": "key",
    "attributes": ["actor_role"]
  }'

echo ""
echo "✅ Indexes added successfully!"

echo ""
echo "🎉 Activity Logs Collection setup completed!"
echo ""
echo "📋 Collection Details:"
echo "   - Collection ID: activity_logs"
echo "   - Database ID: ${DATABASE_ID}"
echo "   - Attributes: 13 attributes added"
echo "   - Indexes: 7 indexes added"
echo ""
echo "🚀 Ready to log activities!"
