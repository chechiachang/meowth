# Quickstart Guide: Slack-Notion Integration

**Last Updated**: 2025-11-06  
**Prerequisites**: Python 3.11+, Slack workspace admin access, Notion workspace access

## 🚀 Quick Setup (5 minutes)

### 1. Clone and Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd meowth

# Install uv package manager (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### 2. Slack App Configuration

1. **Create Slack App**:
   - Go to [Slack API Console](https://api.slack.com/apps)
   - Click "Create New App" → "From scratch"
   - Name: "Notion Integration Bot"
   - Select your development workspace

2. **Configure OAuth & Permissions**:
   - Navigate to "OAuth & Permissions"
   - Add Bot Token Scopes:
     - `app_mentions:read`
     - `channels:history`
     - `channels:read`
     - `chat:write`
     - `commands`
     - `groups:history` (for private channels)
     - `im:history`
     - `users:read`
   - Install app to workspace
   - Copy "Bot User OAuth Token" (starts with `xoxb-`)

3. **Enable Socket Mode**:
   - Navigate to "Socket Mode"
   - Enable Socket Mode
   - Generate App Token with `connections:write` scope
   - Copy "App-Level Token" (starts with `xapp-`)

4. **Create Slash Commands**:
   - Navigate to "Slash Commands"
   - Create commands:
     - `/create-notion` - Description: "Create Notion page from message"
     - `/summarize-thread` - Description: "Summarize current thread"
     - `/summarize-channel` - Description: "Summarize channel activity"

5. **Configure Event Subscriptions**:
   - Navigate to "Event Subscriptions"
   - Enable Events
   - Subscribe to Bot Events:
     - `app_mention`
     - `message.channels`
     - `message.groups`
     - `message.im`

### 3. Notion Integration Setup

1. **Create Notion Integration**:
   - Go to [Notion Developers](https://www.notion.so/my-integrations)
   - Click "New integration"
   - Name: "Slack Messages"
   - Select workspace
   - Copy "Internal Integration Token" (starts with `secret_`)

2. **Setup Notion Database**:
   ```bash
   # Run setup script to create database template
   python -m src.cli.setup notion-database
   ```
   
   Or manually create database with properties:
   - Title (Title)
   - Source (Select: Slack)
   - Channel (Text)
   - Author (Text)
   - Created (Date)
   - Message URL (URL)
   - Keywords (Multi-select)
   - Status (Select: Draft, Published, Archived)

3. **Share Database**:
   - Open your Notion database
   - Click "Share" → "Invite"
   - Add your integration by name
   - Copy database ID from URL (32-character string)

### 4. Environment Configuration

Create `.env` file in project root:

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
SLACK_SIGNING_SECRET=your-signing-secret

# Notion Configuration  
NOTION_TOKEN=secret_your-notion-token
NOTION_DATABASE_ID=your-database-id

# Database Configuration
DATABASE_URL=sqlite:///data/slack_notion.db
# For production: DATABASE_URL=postgresql://user:pass@localhost/slack_notion

# Application Configuration
LOG_LEVEL=INFO
ENVIRONMENT=development
API_HOST=0.0.0.0
API_PORT=8000

# Rate Limiting
SLACK_RATE_LIMIT=50  # requests per minute
NOTION_RATE_LIMIT=3  # requests per second

# Processing Configuration
MAX_RETRY_ATTEMPTS=3
QUEUE_POLL_INTERVAL=5  # seconds
DUPLICATE_SIMILARITY_THRESHOLD=0.8
```

### 5. Initialize Database

```bash
# Create database schema
python -m src.cli.init-db

# Run database migrations
python -m src.cli.migrate
```

### 6. Start the Service

```bash
# Start the application
python -m src.main

# Or use development mode with auto-reload
python -m src.main --dev
```

The service will start and display:
```
🚀 Slack-Notion Integration Service starting...
✅ Database connected
✅ Slack connection established
✅ Notion API validated
🔄 Socket mode listener started
📡 API server running on http://localhost:8000
```

## 🧪 Test Your Setup

### 1. Basic Slack Command Test

In your Slack workspace:
```
/create-notion Hello from Slack! This is a test message.
```

Expected response:
```
✅ Notion page created successfully!
📄 Page: "Hello from Slack! This is a test message."
🔗 View in Notion: [link]
```

### 2. Keyword Monitoring Test

1. **Create keyword rule**:
   ```bash
   curl -X POST http://localhost:8000/keywords \
     -H "Content-Type: application/json" \
     -d '{
       "name": "Bug Reports",
       "keywords": ["bug", "error", "issue"],
       "channels": ["C1234567890"],
       "notion_database_id": "your-database-id"
     }'
   ```

2. **Post message with keyword**:
   Post in monitored channel: "Found a bug in the login system"

3. **Check processing**:
   ```bash
   curl http://localhost:8000/messages?status=processed
   ```

### 3. Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-06T10:30:00Z",
  "services": {
    "slack_api": {"status": "up", "response_time_ms": 150},
    "notion_api": {"status": "up", "response_time_ms": 200},
    "database": {"status": "up", "response_time_ms": 5}
  }
}
```

## 📊 Monitoring and Logs

### View Application Logs

```bash
# Follow real-time logs
tail -f logs/app.log

# View specific log level
grep "ERROR" logs/app.log

# Monitor processing queue
curl http://localhost:8000/queue
```

### Common Log Messages

- `✅ Slack message processed: {message_id}` - Successful processing
- `⚠️ Rate limit approached for Slack API` - Rate limiting warning
- `❌ Failed to create Notion page: {error}` - Creation failure
- `🔄 Retrying failed message: {message_id}` - Retry attempt

## 🛠️ Development Workflow

### Run Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_slack_client.py

# Run integration tests (requires test environment)
uv run pytest tests/integration/ -m integration
```

### Code Quality

```bash
# Format code
uv run black src/ tests/

# Lint code
uv run flake8 src/ tests/

# Type checking
uv run mypy src/

# Run all quality checks
uv run pre-commit run --all-files
```

### Database Migrations

```bash
# Create new migration
python -m src.cli.migration create "add_new_field"

# Apply migrations
python -m src.cli.migration upgrade

# Rollback migration
python -m src.cli.migration downgrade
```

## 🔧 Configuration Options

### Keyword Rules

Create monitoring rules via API:

```bash
curl -X POST http://localhost:8000/keywords \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Feature Requests",
    "keywords": ["feature", "enhancement", "suggestion"],
    "channels": ["C1234567890", "C0987654321"],
    "notion_database_id": "database-uuid",
    "aggregation_schedule": "0 18 * * *",
    "match_mode": "contains",
    "case_sensitive": false
  }'
```

### Aggregation Schedules

Standard cron expressions:
- `0 9 * * *` - Daily at 9 AM
- `0 18 * * 5` - Weekly on Friday at 6 PM  
- `0 0 1 * *` - Monthly on 1st at midnight

### Notion Database Templates

For different use cases:

1. **General Messages**: Basic template above
2. **Bug Reports**: Add Priority, Severity, Assignee fields
3. **Feature Requests**: Add Status, Epic, Effort fields
4. **Meeting Notes**: Add Attendees, Action Items, Decision fields

## 🚨 Troubleshooting

### Common Issues

#### "Slack connection failed"
- Verify bot token starts with `xoxb-`
- Check app is installed in workspace
- Ensure required OAuth scopes are granted

#### "Notion database not found"
- Verify database ID is correct (32 characters)
- Check integration has access to database
- Ensure database has required properties

#### "Rate limit exceeded"
- Reduce `SLACK_RATE_LIMIT` or `NOTION_RATE_LIMIT`
- Check for high message volumes
- Monitor queue processing times

#### "Messages not processing"
- Check application logs for errors
- Verify keyword rules are active
- Test with simple `/create-notion` command

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python -m src.main
```

### Health Monitoring

Set up monitoring endpoints:

```bash
# Service health
curl http://localhost:8000/health

# Processing queue status  
curl http://localhost:8000/queue

# Recent errors
curl http://localhost:8000/messages?status=failed&limit=10
```

## 📈 Production Deployment

### Docker Deployment

```bash
# Build image
docker build -t slack-notion-integration .

# Run container
docker run -d \
  --name slack-notion-bot \
  --env-file .env \
  -p 8000:8000 \
  -v ./data:/app/data \
  slack-notion-integration
```

### Environment Variables

Additional production settings:

```bash
# Production database
DATABASE_URL=postgresql://user:pass@db:5432/slack_notion

# Redis for caching (optional)
REDIS_URL=redis://redis:6379/0

# Monitoring
SENTRY_DSN=https://your-sentry-dsn
PROMETHEUS_PORT=9090

# Security
API_KEY=your-api-key
ENCRYPTION_KEY=your-32-char-key
```

### Scaling Considerations

- Use PostgreSQL for production database
- Add Redis for caching and job queuing
- Configure load balancer for multiple instances
- Monitor rate limits and adjust accordingly
- Set up log aggregation (ELK stack recommended)

## 📚 Next Steps

1. **Customize Notion Templates**: Modify database schemas for your use cases
2. **Add Custom Keywords**: Configure monitoring rules for your channels
3. **Set Up Aggregation**: Schedule daily/weekly summary reports
4. **Configure Monitoring**: Set up alerts for errors and rate limits
5. **Train Your Team**: Share slash commands and best practices

For detailed development information, see:
- [API Documentation](./contracts/api.yaml)
- [Data Model Guide](./data-model.md)
- [Architecture Research](./research.md)