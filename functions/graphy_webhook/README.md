# Graphy Webhook Function

This function receives completion webhooks from the Graphy platform and enqueues certificate generation.

## Features

- Validates webhook signatures (if provided by Graphy)
- Stores webhook events in database
- Prevents duplicate processing
- Enqueues certificate worker for PDF generation
- Idempotent processing

## Webhook Format

Graphy should send POST requests with the following payload:

```json
{
  "course_id": "course-123",
  "email": "learner@example.com",
  "event_id": "unique-event-id",
  "completed_at": "2024-01-15T10:30:00Z",
  "metadata": {
    "completion_percentage": 100,
    "time_spent": 3600
  }
}
```

## Authentication

This is a public endpoint that accepts webhooks from Graphy. Signature verification is optional but recommended.

## Environment Variables

- `APPWRITE_ENDPOINT` - Appwrite API endpoint
- `APPWRITE_PROJECT` - Appwrite project ID
- `APPWRITE_API_KEY` - Appwrite server API key
- `GRAPHY_API_BASE` - Graphy API base URL
- `GRAPHY_API_KEY` - Graphy API key
- `GRAPHY_WEBHOOK_SECRET` - Secret for webhook signature verification
- `CERTIFICATE_WORKER_FUNCTION_ID` - Appwrite function ID for certificate worker
- `CERTIFICATE_WORKER_URL` - HTTP URL for certificate worker (alternative)

## Testing

```bash
curl -X POST https://your-appwrite-host/v1/functions/graphy_webhook \
  -H "Content-Type: application/json" \
  -d '{
    "course_id": "test-course",
    "email": "test@example.com",
    "event_id": "test-event-123"
  }'
```

## Health Check

```bash
curl -X POST https://your-appwrite-host/v1/functions/graphy_webhook \
  -H "Content-Type: application/json" \
  -d '{"action": "health"}'
```
