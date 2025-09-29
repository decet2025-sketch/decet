# SOP Router Function

This function handles operations for Single Point of Contact (SOP) users from organizations.

## Features

- Organization-scoped access control
- View learners for organization
- Download certificates
- Request certificate resends
- Organization statistics dashboard

## Actions Supported

- `LIST_ORG_LEARNERS` - View learners for organization
- `DOWNLOAD_CERTIFICATE` - Download certificate PDF
- `RESEND_CERTIFICATE` - Request certificate resend

## Authentication

Requires valid Appwrite JWT with SOP role. SOP users can only access resources for their assigned organization.

## Example Usage

### List Organization Learners

```bash
curl -X POST https://your-appwrite-host/v1/functions/sop_router \
  -H "Authorization: Bearer YOUR_SOP_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "LIST_ORG_LEARNERS",
    "payload": {
      "organization_website": "example.com",
      "limit": 50,
      "offset": 0
    }
  }'
```

### Download Certificate

```bash
curl -X POST https://your-appwrite-host/v1/functions/sop_router \
  -H "Authorization: Bearer YOUR_SOP_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "DOWNLOAD_CERTIFICATE",
    "payload": {
      "learner_email": "learner@example.com",
      "course_id": "course-123"
    }
  }'
```

### Request Certificate Resend

```bash
curl -X POST https://your-appwrite-host/v1/functions/sop_router \
  -H "Authorization: Bearer YOUR_SOP_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "RESEND_CERTIFICATE",
    "payload": {
      "organization_website": "example.com"
    }
  }'
```

### Get Organization Statistics

```bash
curl -X POST https://your-appwrite-host/v1/functions/sop_router \
  -H "Authorization: Bearer YOUR_SOP_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "get_organization_stats",
    "organization_website": "example.com"
  }'
```

## Environment Variables

- `APPWRITE_ENDPOINT` - Appwrite API endpoint
- `APPWRITE_PROJECT` - Appwrite project ID
- `APPWRITE_API_KEY` - Appwrite server API key
- `SENDGRID_API_KEY` - SendGrid API key (optional)
- `SMTP_HOST` - SMTP host (fallback)
- `SMTP_PORT` - SMTP port
- `SMTP_USER` - SMTP username
- `SMTP_PASS` - SMTP password
- `CERTIFICATE_BUCKET_ID` - Storage bucket for certificates

## Security

- SOP users can only access learners from their assigned organization
- Certificate downloads use signed URLs for security
- All operations are logged for audit purposes
- JWT tokens are validated for each request
