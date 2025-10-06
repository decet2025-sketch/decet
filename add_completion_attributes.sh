#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
  export $(cat .env | xargs)
fi

APPWRITE_ENDPOINT=${APPWRITE_ENDPOINT:-https://cloud.appwrite.io/v1}
APPWRITE_PROJECT=${APPWRITE_PROJECT:-68cf04e30030d4b38d19} # Replace with your project ID
APPWRITE_API_KEY=${APPWRITE_API_KEY:-standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142} # Replace with your API Key
APPWRITE_DATABASE_ID=${APPWRITE_DATABASE_ID:-main} # Replace with your database ID

COLLECTION_ID="learners"

echo "🚀 Adding completion tracking attributes to ${COLLECTION_ID} collection..."

# Add completion_percentage attribute
echo "📋 Adding completion_percentage attribute..."
ADD_ATTRIBUTE_RESPONSE=$(curl -s -X POST "${APPWRITE_ENDPOINT}/databases/${APPWRITE_DATABASE_ID}/collections/${COLLECTION_ID}/attributes/float" \
  -H "Content-Type: application/json" \
  -H "X-Appwrite-Project: ${APPWRITE_PROJECT}" \
  -H "X-Appwrite-Key: ${APPWRITE_API_KEY}" \
  --data-raw '{
      "key": "completion_percentage",
      "required": false,
      "min": 0,
      "max": 100
  }')
echo "${ADD_ATTRIBUTE_RESPONSE}"
if echo "${ADD_ATTRIBUTE_RESPONSE}" | grep -q "\"key\":\"completion_percentage\""; then
  echo "✅ Attribute completion_percentage added successfully!"
elif echo "${ADD_ATTRIBUTE_RESPONSE}" | grep -q "already exists"; then
  echo "⚠️ Attribute completion_percentage already exists. Skipping."
else
  echo "❌ Failed to add attribute completion_percentage: ${ADD_ATTRIBUTE_RESPONSE}"
fi

# Add completion_data attribute
echo "📋 Adding completion_data attribute..."
ADD_ATTRIBUTE_RESPONSE=$(curl -s -X POST "${APPWRITE_ENDPOINT}/databases/${APPWRITE_DATABASE_ID}/collections/${COLLECTION_ID}/attributes/string" \
  -H "Content-Type: application/json" \
  -H "X-Appwrite-Project: ${APPWRITE_PROJECT}" \
  -H "X-Appwrite-Key: ${APPWRITE_API_KEY}" \
  --data-raw '{
      "key": "completion_data",
      "size": 5000,
      "required": false,
      "array": false
  }')
echo "${ADD_ATTRIBUTE_RESPONSE}"
if echo "${ADD_ATTRIBUTE_RESPONSE}" | grep -q "\"key\":\"completion_data\""; then
  echo "✅ Attribute completion_data added successfully!"
elif echo "${ADD_ATTRIBUTE_RESPONSE}" | grep -q "already exists"; then
  echo "⚠️ Attribute completion_data already exists. Skipping."
else
  echo "❌ Failed to add attribute completion_data: ${ADD_ATTRIBUTE_RESPONSE}"
fi

# Add last_completion_check attribute
echo "📋 Adding last_completion_check attribute..."
ADD_ATTRIBUTE_RESPONSE=$(curl -s -X POST "${APPWRITE_ENDPOINT}/databases/${APPWRITE_DATABASE_ID}/collections/${COLLECTION_ID}/attributes/datetime" \
  -H "Content-Type: application/json" \
  -H "X-Appwrite-Project: ${APPWRITE_PROJECT}" \
  -H "X-Appwrite-Key: ${APPWRITE_API_KEY}" \
  --data-raw '{
      "key": "last_completion_check",
      "required": false,
      "array": false
  }')
echo "${ADD_ATTRIBUTE_RESPONSE}"
if echo "${ADD_ATTRIBUTE_RESPONSE}" | grep -q "\"key\":\"last_completion_check\""; then
  echo "✅ Attribute last_completion_check added successfully!"
elif echo "${ADD_ATTRIBUTE_RESPONSE}" | grep -q "already exists"; then
  echo "⚠️ Attribute last_completion_check already exists. Skipping."
else
  echo "❌ Failed to add attribute last_completion_check: ${ADD_ATTRIBUTE_RESPONSE}"
fi

# Add completion_date attribute
echo "📋 Adding completion_date attribute..."
ADD_ATTRIBUTE_RESPONSE=$(curl -s -X POST "${APPWRITE_ENDPOINT}/databases/${APPWRITE_DATABASE_ID}/collections/${COLLECTION_ID}/attributes/datetime" \
  -H "Content-Type: application/json" \
  -H "X-Appwrite-Project: ${APPWRITE_PROJECT}" \
  -H "X-Appwrite-Key: ${APPWRITE_API_KEY}" \
  --data-raw '{
      "key": "completion_date",
      "required": false,
      "array": false
  }')
echo "${ADD_ATTRIBUTE_RESPONSE}"
if echo "${ADD_ATTRIBUTE_RESPONSE}" | grep -q "\"key\":\"completion_date\""; then
  echo "✅ Attribute completion_date added successfully!"
elif echo "${ADD_ATTRIBUTE_RESPONSE}" | grep -q "already exists"; then
  echo "⚠️ Attribute completion_date already exists. Skipping."
else
  echo "❌ Failed to add attribute completion_date: ${ADD_ATTRIBUTE_RESPONSE}"
fi

# Add enrollment_status attribute
echo "📋 Adding enrollment_status attribute..."
ADD_ATTRIBUTE_RESPONSE=$(curl -s -X POST "${APPWRITE_ENDPOINT}/databases/${APPWRITE_DATABASE_ID}/collections/${COLLECTION_ID}/attributes/string" \
  -H "Content-Type: application/json" \
  -H "X-Appwrite-Project: ${APPWRITE_PROJECT}" \
  -H "X-Appwrite-Key: ${APPWRITE_API_KEY}" \
  --data-raw '{
      "key": "enrollment_status",
      "size": 50,
      "required": false,
      "array": false
  }')
echo "${ADD_ATTRIBUTE_RESPONSE}"
if echo "${ADD_ATTRIBUTE_RESPONSE}" | grep -q "\"key\":\"enrollment_status\""; then
  echo "✅ Attribute enrollment_status added successfully!"
elif echo "${ADD_ATTRIBUTE_RESPONSE}" | grep -q "already exists"; then
  echo "⚠️ Attribute enrollment_status already exists. Skipping."
else
  echo "❌ Failed to add attribute enrollment_status: ${ADD_ATTRIBUTE_RESPONSE}"
fi

echo ""
echo "🎉 Completion tracking attributes setup completed!"
echo ""
echo "📋 Added Attributes:"
echo "   - completion_percentage (float, 0-100)"
echo "   - completion_data (string, 5000 chars)"
echo "   - last_completion_check (datetime)"
echo "   - completion_date (datetime)"
echo "   - enrollment_status (string, 50 chars)"
echo ""
echo "🚀 Ready for completion tracking!"