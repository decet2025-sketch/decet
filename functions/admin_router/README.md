# Admin Router Function

This function handles all admin operations for the certificate backend system.

## Actions Supported

- `CREATE_COURSE` - Create new course
- `EDIT_COURSE` - Update course details
- `DELETE_COURSE` - Remove course
- `UPLOAD_LEARNERS_CSV` - Bulk enroll learners
- `PREVIEW_CERTIFICATE` - Preview certificate template
- `LIST_COURSES` - List all courses
- `VIEW_LEARNERS` - View learners for a course
- `ADD_ORGANIZATION` - Add new organization
- `EDIT_ORGANIZATION` - Update organization
- `DELETE_ORGANIZATION` - Remove organization
- `RESEND_CERTIFICATE` - Resend certificate to SOP
- `LIST_WEBHOOKS` - View webhook events
- `RETRY_WEBHOOK` - Retry failed webhook

## Authentication

Requires valid Appwrite JWT with admin role.

## Example Usage

```bash
curl -X POST https://your-appwrite-host/v1/functions/admin_router \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "CREATE_COURSE",
    "payload": {
      "course_id": "course-123",
      "name": "Python Basics",
      "certificate_template_html": "<html>...</html>"
    }
  }'
```

## Environment Variables

- `APPWRITE_ENDPOINT` - Appwrite API endpoint
- `APPWRITE_PROJECT` - Appwrite project ID
- `APPWRITE_API_KEY` - Appwrite server API key
- `GRAPHY_API_BASE` - Graphy API base URL
- `GRAPHY_API_KEY` - Graphy API key
- `SENDGRID_API_KEY` - SendGrid API key (optional)
- `SMTP_HOST` - SMTP host (fallback)
- `SMTP_PORT` - SMTP port
- `SMTP_USER` - SMTP username
- `SMTP_PASS` - SMTP password
- `HTML_TO_PDF_API_URL` - External PDF API URL (optional)
- `MAX_CSV_ROWS` - Maximum CSV rows (default: 5000)
- `CERTIFICATE_BUCKET_ID` - Storage bucket for certificates
