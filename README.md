# Course Completion Certificate Backend

A production-ready backend system for managing course enrollments and generating completion certificates. Built with Appwrite serverless functions in Python 3.

## Architecture Overview

This system handles the complete flow from course creation to certificate delivery:

1. **Admin** uploads courses and learner CSVs
2. **Learners** are enrolled on Graphy platform
3. **Graphy** sends completion webhooks
4. **Backend** generates certificates (HTML→PDF) and emails them to organization SOPs

## Project Structure

```
/functions/
  admin_router/          # Admin operations (CRUD courses, upload learners)
  sop_router/           # SOP operations (view learners, download certificates)
  graphy_webhook/       # Webhook receiver from Graphy
  certificate_worker/   # Certificate generation and email sending
/infra/
  appwrite_collections.json  # Database schema definition
/tests/
  test_*.py            # Unit and integration tests
.github/workflows/
  ci.yml              # CI/CD pipeline
```

## Quick Start

### Option 1: Using Appwrite CLI (Recommended)

1. **Install Appwrite CLI**
   ```bash
   npm install -g appwrite-cli
   ```

2. **Clone and setup**
   ```bash
   git clone <repository-url>
   cd certificate-management-system
   make setup-dev
   source venv/bin/activate
   ```

3. **Configure environment**
   ```bash
   cp env.example env.staging
   # Edit env.staging with your configuration
   ```

4. **Deploy to staging**
   ```bash
   make quick-deploy-staging
   ```

### CLI Commands

```bash
# Quick deployment
make quick-deploy-staging
make quick-deploy-production

# Full deployment with tests
make deploy-staging
make deploy-production

# Function management
make list-functions
make logs FUNCTION=admin_router
make update-env FUNCTION=admin_router ENV=staging

# Development
make test
make lint
make format
```

See [CLI_SETUP.md](CLI_SETUP.md) for detailed CLI setup instructions.

### Option 2: Manual Setup

### 1. Prerequisites

- Appwrite Cloud or Self-hosted instance
- Node.js and npm (for Appwrite CLI)
- Python 3.9+ (for local development)
- Graphy API access
- SendGrid account (recommended) or SMTP server

### 2. Setup Appwrite Project

1. **Create Appwrite Project**
   ```bash
   # Install Appwrite CLI
   npm install -g appwrite-cli
   
   # Login to Appwrite
   appwrite login
   
   # Create project
   appwrite projects create --name="Certificate Backend" --teamId="your-team-id"
   ```

2. **Setup Database Collections**
   ```bash
   # Copy environment file
   cp env.example .env
   
   # Edit .env with your Appwrite credentials
   nano .env
   
   # Run setup script
   ./scripts/setup-collections.sh
   ```

3. **Create Storage Bucket**
   ```bash
   # Create certificate storage bucket
   appwrite storage createBucket \
     --bucketId="certificates" \
     --name="Certificates" \
     --permissions="read(\"any\")" \
     --fileSecurity=true \
     --maxFileSize=10485760 \
     --allowedFileExtensions="pdf"
   ```

### 3. Environment Configuration

Create `.env` file with your configuration:

```bash
# Appwrite Configuration
APPWRITE_ENDPOINT=https://your-appwrite-host/v1
APPWRITE_PROJECT=your-project-id
APPWRITE_API_KEY=your-server-key
APPWRITE_JWT_SECRET=your-jwt-secret

# Graphy Integration
GRAPHY_API_BASE=https://api.graphy.com
GRAPHY_API_KEY=your-graphy-api-key
GRAPHY_WEBHOOK_SECRET=your-webhook-secret

# Email Service (SendGrid recommended)
SENDGRID_API_KEY=your-sendgrid-key
FROM_EMAIL=noreply@yourdomain.com

# SMTP Fallback
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-smtp-user
SMTP_PASS=your-smtp-password

# PDF Generation
HTML_TO_PDF_API_URL=https://pdf.example.com/convert

# Configuration
MAX_CSV_ROWS=5000
CERTIFICATE_BUCKET_ID=certificates
MAX_EMAIL_RETRY_ATTEMPTS=3
EMAIL_RETRY_DELAY=60
```

### 4. Deploy Functions

**Option A: Automated Deployment**
```bash
# Deploy to staging
./scripts/deploy.sh staging

# Deploy to production
./scripts/deploy.sh production
```

**Option B: Manual Deployment**
```bash
# Deploy each function
appwrite functions create --functionId=admin_router --name="Admin Router" --runtime=python-3.9
appwrite functions create --functionId=sop_router --name="SOP Router" --runtime=python-3.9
appwrite functions create --functionId=graphy_webhook --name="Graphy Webhook" --runtime=python-3.9
appwrite functions create --functionId=certificate_worker --name="Certificate Worker" --runtime=python-3.9

# Deploy code
appwrite functions deploy --functionId=admin_router --src=functions/admin_router
appwrite functions deploy --functionId=sop_router --src=functions/sop_router
appwrite functions deploy --functionId=graphy_webhook --src=functions/graphy_webhook
appwrite functions deploy --functionId=certificate_worker --src=functions/certificate_worker
```

### 5. Configure Function Environment Variables

Set environment variables for each function in Appwrite Console:

1. Go to Functions → [Function Name] → Settings → Environment Variables
2. Add all variables from your `.env` file
3. Save and redeploy functions

### 6. Test the System

```bash
# Run unit tests
pip install -r requirements-dev.txt
pytest tests/ -v

# Test webhook
./scripts/test-webhook.sh https://your-appwrite-host/v1/functions/graphy_webhook

# Test admin router
curl -X POST https://your-appwrite-host/v1/functions/admin_router \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "CREATE_COURSE",
    "payload": {
      "course_id": "test-123",
      "name": "Test Course",
      "certificate_template_html": "<html><body><h1>Certificate</h1></body></html>"
    }
  }'
```

## API Documentation

### Admin Router Actions

All admin operations use POST with JSON body:

```json
{
  "action": "ACTION_NAME",
  "payload": { ... }
}
```

**Available Actions:**
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

### SOP Router Actions

Similar format for SOP operations:
- `LIST_ORG_LEARNERS` - View learners for organization
- `DOWNLOAD_CERTIFICATE` - Download certificate PDF
- `RESEND_CERTIFICATE` - Request certificate resend

### Graphy Webhook

Receives completion notifications from Graphy:

```json
{
  "course_id": "course-123",
  "email": "learner@example.com",
  "event_id": "unique-event-id",
  "completed_at": "2024-01-15T10:30:00Z"
}
```

## CSV Format

For learner uploads, use this CSV format:

```csv
name,email,organization_website
John Doe,john@example.com,example.com
Jane Smith,jane@example.com,example.com
```

## Certificate Templates

Use Jinja2 templates with these variables:
- `{{learner_name}}` - Learner's name
- `{{course_name}}` - Course name
- `{{completion_date}}` - ISO date string
- `{{organization}}` - Organization name/website
- `{{learner_email}}` - Learner's email

## Development

### Local Development Setup

```bash
# Clone repository
git clone <repository-url>
cd certificate-backend

# Install dependencies
pip install -r requirements-dev.txt

# Copy environment file
cp env.example .env
# Edit .env with your configuration

# Run tests
pytest tests/ -v --cov=functions --cov=shared

# Lint code
black functions/ tests/ shared/
flake8 functions/ tests/ shared/
isort functions/ tests/ shared/
mypy functions/ tests/ shared/
```

### Local Function Testing

```bash
# Install Appwrite CLI
npm install -g appwrite-cli

# Start local Appwrite instance (if using self-hosted)
docker run -it --rm \
  --volume /var/run/docker.sock:/var/run/docker.sock \
  --volume "$(pwd)"/appwrite:/usr/src/code/appwrite:rw \
  --entrypoint="install" \
  appwrite/appwrite:latest

# Run functions locally
appwrite functions create --functionId=admin_router --name="Admin Router" --runtime=python-3.9
appwrite functions deploy --functionId=admin_router --src=functions/admin_router
```

### Mock Services

The test suite includes comprehensive mocks for:
- Appwrite SDK (databases, storage, functions)
- Graphy API (enrollment, webhook verification)
- SendGrid/SMTP email services
- PDF generation services (pyppeteer, external APIs)
- Authentication and authorization
- File operations and CSV parsing

## Performance & Scaling

- Certificate generation is limited to 3 concurrent processes
- CSV uploads are capped at 5000 rows
- PDF files are stored in Appwrite Storage with configurable retention
- Webhook processing is idempotent and retry-safe

## Security

- All admin endpoints require valid Appwrite JWT
- SOP endpoints are scoped to organization
- Webhook signatures are validated (if provided by Graphy)
- Certificate templates are sanitized to prevent XSS
- All operations are idempotent

## Monitoring

- Structured JSON logging with request IDs
- Audit trails for all admin actions
- Email delivery status tracking
- Webhook processing metrics

## Troubleshooting

### Common Issues

1. **Certificate generation fails**: Check pyppeteer installation and fallback PDF API
2. **Email sending fails**: Verify SendGrid API key or SMTP credentials
3. **Graphy enrollment fails**: Check API key and course ID format
4. **CSV upload fails**: Verify organization websites exist in database

### Logs

View function logs in Appwrite Console or export to external monitoring service.

## Production Deployment

### Environment Setup

1. **Staging Environment**
   ```bash
   # Create staging environment file
   cp env.example .env.staging
   # Edit with staging credentials
   
   # Deploy to staging
   ./scripts/deploy.sh staging
   ```

2. **Production Environment**
   ```bash
   # Create production environment file
   cp env.example .env.production
   # Edit with production credentials
   
   # Deploy to production
   ./scripts/deploy.sh production
   ```

### CI/CD Pipeline

The repository includes GitHub Actions workflows:

- **CI Pipeline** (`.github/workflows/ci.yml`):
  - Code linting and formatting
  - Unit tests with coverage
  - Security scanning
  - Function package building
  - Automated deployment to staging/production

- **Security Scanning** (`.github/workflows/security.yml`):
  - Dependency vulnerability scanning
  - Code security analysis
  - Secrets detection

- **Release Management** (`.github/workflows/release.yml`):
  - Automated releases on version tags
  - Function package artifacts
  - Changelog generation

### Monitoring & Observability

1. **Logging**
   - Structured JSON logs with request IDs
   - Function execution metrics
   - Error tracking and alerting

2. **Health Checks**
   ```bash
   # Check function health
   curl -X POST https://your-appwrite-host/v1/functions/admin_router \
     -H "Content-Type: application/json" \
     -d '{"action": "health"}'
   ```

3. **Metrics**
   - Certificate generation success rate
   - Email delivery status
   - Webhook processing latency
   - Database query performance

### Backup & Recovery

1. **Database Backups**
   - Regular Appwrite database exports
   - Collection schema versioning
   - Data migration scripts

2. **File Storage**
   - Certificate PDF backups
   - Storage bucket replication
   - Retention policies

## Support

For issues or questions:

1. **Check Logs**
   - Appwrite Console → Functions → Logs
   - Function execution details
   - Error stack traces

2. **Review Documentation**
   - API documentation in README
   - Function-specific README files
   - Test suite examples

3. **Verify Configuration**
   - Environment variables
   - Database collections
   - Storage buckets
   - Function permissions

4. **Common Issues**
   - JWT token validation errors
   - Graphy API connectivity
   - Email delivery failures
   - PDF generation issues

5. **Getting Help**
   - Check GitHub Issues
   - Review test cases
   - Validate with health checks
   - Contact support team
