# Quickstart Guide: Slack Mention Bot

This guide helps you get the Slack mention bot running locally and deployed.

## Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager
- Slack workspace with admin permissions
- Bot tokens (see Slack App Setup below)

## Slack App Setup

### 1. Create Slack App

1. Go to [Slack API](https://api.slack.com/apps) and click "Create New App"
2. Choose "From scratch" and provide app name: "Meowth Bot"
3. Select your workspace

### 2. Configure Bot Settings

**OAuth & Permissions**:
1. Add Bot Token Scopes:
   - `app_mentions:read` - Read mentions of your bot
   - `chat:write` - Send messages as bot
2. Install app to workspace
3. Copy "Bot User OAuth Token" (starts with `xoxb-`)

**Socket Mode**:
1. Enable Socket Mode in your app settings
2. Generate App-Level Token with `connections:write` scope
3. Copy "App-Level Token" (starts with `xapp-`)

**Event Subscriptions**:
1. Enable Socket Mode (no URL needed)
2. Subscribe to bot events: `app_mention`

### 3. Install Bot to Workspace

1. Go to "Install App" section
2. Click "Install to Workspace"
3. Authorize the app
4. Invite bot to channels: `/invite @meowth`

## Local Development

### 1. Clone and Setup

```bash
# Clone repository
git clone <repository-url>
cd meowth

# Checkout feature branch
git checkout 001-slack-mention-bot

# Install dependencies
uv sync
```

### 2. Environment Configuration

Create `.env` file in project root:

```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
LOG_LEVEL=INFO
```

**Security Note**: Never commit `.env` file or real tokens to git.

### 3. Run the Bot

```bash
# Run with uv
uv run python -m src.meowth.main

# Alternative: activate environment first
uv shell
python -m src.meowth.main
```

### 4. Test the Bot

1. Go to a Slack channel where the bot is present
2. Type: `@meowth hello there!`
3. Bot should respond: "Meowth, that's right!"

## Development Workflow

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test categories
uv run pytest tests/unit/          # Unit tests only
uv run pytest tests/integration/   # Integration tests only

# Run with coverage
uv run pytest --cov=src/meowth
```

### Code Quality

```bash
# Format code
uv run black src/ tests/

# Check types
uv run mypy src/

# Lint code
uv run flake8 src/ tests/
```

### Test-Driven Development

Following the constitution requirement:

1. **Red**: Write failing test first
2. **Green**: Write minimal code to pass
3. **Refactor**: Improve code while keeping tests green

Example workflow:
```bash
# 1. Write test
echo "def test_mention_response(): assert False" >> tests/unit/test_mention_handler.py

# 2. Run test (should fail)
uv run pytest tests/unit/test_mention_handler.py::test_mention_response

# 3. Implement feature
# Edit src/meowth/handlers/mention.py

# 4. Run test until it passes
uv run pytest tests/unit/test_mention_handler.py::test_mention_response
```

## Deployment

### Docker Container

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy source code
COPY src/ ./src/

# Environment variables (set via container runtime)
ENV SLACK_BOT_TOKEN=""
ENV SLACK_APP_TOKEN=""
ENV LOG_LEVEL="INFO"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:3000/health')" || exit 1

# Run bot
CMD ["uv", "run", "python", "-m", "src.meowth.main"]
```

### Environment Variables

**Required**:
- `SLACK_BOT_TOKEN` - Bot User OAuth Token from Slack
- `SLACK_APP_TOKEN` - App-Level Token for Socket Mode

**Optional**:
- `LOG_LEVEL` - Logging level (DEBUG, INFO, ERROR) [default: INFO]

### Production Checklist

- [ ] Environment variables configured securely
- [ ] Bot tokens have minimal required permissions
- [ ] Health check endpoint responding
- [ ] Log aggregation configured
- [ ] Resource limits set (memory, CPU)
- [ ] Restart policy configured

## Monitoring

### Logs

The bot outputs structured logs:

```json
{
  "timestamp": "2025-11-16T10:30:00Z",
  "level": "INFO", 
  "event_type": "mention_received",
  "channel_id": "C1234567890",
  "user_id": "U9876543210",
  "message": "Mention received in channel #general"
}
```

### Health Checks

- Bot connection status
- Last successful API call
- Response time metrics
- Error rates

## Troubleshooting

### Common Issues

**Bot not responding**:
1. Check bot is invited to channel: `/invite @meowth`
2. Verify tokens in environment variables
3. Check logs for connection errors

**Permission errors**:
1. Ensure bot has `chat:write` scope
2. Check channel permissions
3. Verify bot is not restricted

**Connection issues**:
1. Check internet connectivity
2. Verify Slack API status
3. Review exponential backoff logs

### Debug Mode

```bash
# Run with debug logging
LOG_LEVEL=DEBUG uv run python -m src.meowth.main

# Enable Slack SDK debug logs
SLACK_SDK_LOG_LEVEL=DEBUG uv run python -m src.meowth.main
```

### Support

- Check logs in `/var/log/meowth/` (production)
- Review Slack app configuration
- Verify token permissions and scopes