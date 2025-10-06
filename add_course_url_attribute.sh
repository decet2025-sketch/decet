#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
  export $(cat .env | xargs)
fi

APPWRITE_ENDPOINT=${APPWRITE_ENDPOINT:-https://cloud.appwrite.io/v1}
APPWRITE_PROJECT=${APPWRITE_PROJECT:-68cf04e30030d4b38d19}
APPWRITE_API_KEY=${APPWRITE_API_KEY:-standard_433c1d266b99746da7293cecabc52ca95bb22210e821cfd4292da0a8eadb137d36963b60dd3ecf89f7cf0461a67046c676ceacb273c60dbc1a19da1bc9042cc82e7653cb167498d8504c6abbda8634393289c3335a0cb72eb8d7972249a0b22a10f9195b0d43243116b54f34f7a15ad837a900922e23bcba34c80c5c09635142}
APPWRITE_DATABASE_ID=${APPWRITE_DATABASE_ID:-main}

COLLECTION_ID="courses"
ATTRIBUTE_KEY="course_url"
ATTRIBUTE_TYPE="string"
ATTRIBUTE_SIZE=1000
ATTRIBUTE_REQUIRED=false
ATTRIBUTE_ARRAY=false

echo "🚀 Adding course_url attribute to courses collection..."

# Add the course_url attribute
echo "📋 Adding course_url attribute..."
ADD_ATTRIBUTE_RESPONSE=$(curl -s -X POST "${APPWRITE_ENDPOINT}/databases/${APPWRITE_DATABASE_ID}/collections/${COLLECTION_ID}/attributes/${ATTRIBUTE_TYPE}" \
  -H "Content-Type: application/json" \
  -H "X-Appwrite-Project: ${APPWRITE_PROJECT}" \
  -H "X-Appwrite-Key: ${APPWRITE_API_KEY}" \
  --data-raw "{
      \"key\": \"${ATTRIBUTE_KEY}\",
      \"size\": ${ATTRIBUTE_SIZE},
      \"required\": ${ATTRIBUTE_REQUIRED},
      \"array\": ${ATTRIBUTE_ARRAY}
  }")

echo "${ADD_ATTRIBUTE_RESPONSE}"

if echo "${ADD_ATTRIBUTE_RESPONSE}" | grep -q "\"key\":\"${ATTRIBUTE_KEY}\""; then
  echo "✅ Attribute ${ATTRIBUTE_KEY} added successfully!"
elif echo "${ADD_ATTRIBUTE_RESPONSE}" | grep -q "already exists"; then
  echo "⚠️ Attribute ${ATTRIBUTE_KEY} already exists. Skipping."
else
  echo "❌ Failed to add attribute ${ATTRIBUTE_KEY}: ${ADD_ATTRIBUTE_RESPONSE}"
  exit 1
fi

echo ""
echo "🎉 Course URL attribute setup completed!"
echo ""
echo "📋 Attribute Details:"
echo "   - Collection: ${COLLECTION_ID}"
echo "   - Attribute: ${ATTRIBUTE_KEY}"
echo "   - Type: ${ATTRIBUTE_TYPE}"
echo "   - Size: ${ATTRIBUTE_SIZE}"
echo "   - Required: ${ATTRIBUTE_REQUIRED}"
echo ""
echo "🚀 Ready to use course URLs!"
