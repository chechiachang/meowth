# 🐱 Meowth

Meowth is an intelligent Slack bot with AI-powered responses and comprehensive monitoring.

## 🔍 Monitoring & Observability

Meowth includes optional Langfuse integration for AI observability and monitoring:

### Features
- **Conversation Tracking**: Monitor AI conversations with complete context
- **Performance Metrics**: Track response times, token usage, and model performance
- **Error Analysis**: Detailed error logging and debugging information  
- **Context Analysis**: Monitor how context is processed and analyzed
- **User Feedback**: Track user interactions and satisfaction

### Setup Langfuse (Optional)

1. Sign up at [Langfuse](https://langfuse.com) to get your API keys
2. Add environment variables:
   ```bash
   LANGFUSE_PUBLIC_KEY=pk_your_public_key_here
   LANGFUSE_SECRET_KEY=sk_your_secret_key_here
   LANGFUSE_HOST=https://cloud.langfuse.com  # Optional, defaults to cloud
   ```

3. Restart the bot - monitoring will be automatically enabled

### What Gets Monitored

- **AI Mention Handling**: Complete conversation flow from mention to response
- **Context Analysis**: Time and token usage for context processing
- **AI Generation**: Model performance, prompt/completion tokens, response time
- **Errors**: Comprehensive error tracking with context
- **Session Management**: Thread isolation and concurrent request tracking

### Disabling Monitoring

To disable Langfuse monitoring, simply don't set the environment variables or set them to empty values:

```bash
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

The bot will work normally without monitoring if Langfuse is not configured. 