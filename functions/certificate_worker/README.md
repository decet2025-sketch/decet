# Certificate Worker Function

This function processes webhook events and generates completion certificates with PDF conversion and email delivery.

## Features

- Processes webhook events from Graphy
- Generates certificate PDFs using HTML templates
- Sends certificates via email to organization SOPs
- Handles retry logic for failed operations
- Idempotent processing

## Processing Flow

1. Receives webhook event ID
2. Validates learner and course data
3. Renders certificate HTML template
4. Converts HTML to PDF
5. Uploads PDF to storage
6. Sends email to SOP with attachment
7. Updates learner status and logs

## Environment Variables

- `APPWRITE_ENDPOINT` - Appwrite API endpoint
- `APPWRITE_PROJECT` - Appwrite project ID
- `APPWRITE_API_KEY` - Appwrite server API key
- `SENDGRID_API_KEY` - SendGrid API key (optional)
- `SMTP_HOST` - SMTP host (fallback)
- `SMTP_PORT` - SMTP port
- `SMTP_USER` - SMTP username
- `SMTP_PASS` - SMTP password
- `HTML_TO_PDF_API_URL` - External PDF API URL (optional)
- `CERTIFICATE_BUCKET_ID` - Storage bucket for certificates
- `MAX_EMAIL_RETRY_ATTEMPTS` - Maximum email retry attempts (default: 3)
- `EMAIL_RETRY_DELAY` - Email retry delay in seconds (default: 60)

## Usage

### Process Webhook Event

```bash
curl -X POST https://your-appwrite-host/v1/functions/certificate_worker \
  -H "Content-Type: application/json" \
  -d '{
    "webhook_event_id": "webhook-event-123"
  }'
```

### Retry Failed Certificates

```bash
curl -X POST https://your-appwrite-host/v1/functions/certificate_worker \
  -H "Content-Type: application/json" \
  -d '{
    "action": "retry_failed"
  }'
```

### Health Check

```bash
curl -X POST https://your-appwrite-host/v1/functions/certificate_worker \
  -H "Content-Type: application/json" \
  -d '{
    "action": "health"
  }'
```

## PDF Generation

The function supports two PDF generation methods:

1. **Pyppeteer** (primary) - Uses headless Chromium
2. **External API** (fallback) - Uses configurable PDF service

## Email Delivery

Supports multiple email backends:

1. **SendGrid** (recommended) - Cloud email service
2. **SMTP** (fallback) - Direct SMTP connection

## Error Handling

- Automatic retry for failed email deliveries
- Exponential backoff for retry attempts
- Comprehensive error logging
- Status tracking for all operations
