# Data Model: Slack-Notion Integration

**Date**: 2025-11-06  
**Phase**: 1 - Data Model Design

## Core Entities

### SlackMessage

Represents captured Slack content including text, author, timestamp, channel, thread context, and attachments.

**Fields:**
- `id`: str - Unique Slack message ID (ts + channel combination)
- `text`: str - Raw message content 
- `formatted_text`: str - Processed text with Slack markup converted to Notion format
- `author_id`: str - Slack user ID of message author
- `author_name`: str - Display name of message author
- `channel_id`: str - Slack channel ID where message was posted
- `channel_name`: str - Human-readable channel name
- `timestamp`: datetime - When message was posted (converted from Slack ts)
- `thread_ts`: Optional[str] - Parent message timestamp if part of thread
- `thread_replies`: List[str] - List of reply message IDs in thread
- `attachments`: List[Dict] - File attachments, images, links with metadata
- `reactions`: List[Dict] - Emoji reactions with counts and users
- `permalink`: str - Slack permalink URL to original message
- `is_bot`: bool - Whether message was posted by bot user
- `processing_status`: str - Status: pending, processed, failed, duplicate

**Relationships:**
- One-to-many with thread replies (self-referential)
- Many-to-one with NotionPage (multiple messages can create one page)
- Many-to-many with KeywordRule (message can match multiple rules)

**Validation Rules:**
- `id` must be unique across all messages
- `text` must not exceed 4000 characters (Notion block limit)
- `timestamp` must be valid UTC datetime
- `channel_id` must match Slack channel ID pattern (C[A-Z0-9]{8,})
- `author_id` must match Slack user ID pattern (U[A-Z0-9]{8,})

**State Transitions:**
pending → processed (successful Notion page creation)
pending → failed (API error or validation failure)  
pending → duplicate (identified as duplicate content)
failed → pending (retry after error resolution)

### NotionPage

Represents created Notion database entries with standardized properties, content blocks, and metadata.

**Fields:**
- `id`: str - Notion page ID (UUID format)
- `database_id`: str - Target Notion database ID
- `title`: str - Page title (derived from message content or summary)
- `content_blocks`: List[Dict] - Notion block objects (text, headings, etc.)
- `properties`: Dict - Database properties (tags, dates, relations)
- `source_messages`: List[str] - List of SlackMessage IDs that created this page
- `page_url`: str - Public URL to Notion page
- `created_at`: datetime - When page was created in Notion
- `updated_at`: datetime - Last modification timestamp
- `page_type`: str - Type: command_created, aggregated_report, thread_summary, duplicate_consolidated
- `aggregation_period`: Optional[str] - Time period for aggregated reports (daily, weekly, monthly)
- `summary_metadata`: Optional[Dict] - Metadata for AI-generated summaries

**Relationships:**
- One-to-many with SlackMessage (via source_messages)
- Many-to-one with KeywordRule (for aggregated reports)
- One-to-many with DuplicateGroup (consolidated pages)

**Validation Rules:**
- `id` must be valid Notion page UUID
- `database_id` must exist and be accessible
- `title` must not exceed 2000 characters
- `content_blocks` must be valid Notion block format
- `source_messages` must reference existing SlackMessage IDs
- `page_type` must be one of enum values

**State Transitions:**
draft → published (page creation confirmed in Notion)
published → updated (content modifications)
published → archived (page deleted or moved)

### KeywordRule

Defines monitoring criteria including keywords, target channels, and aggregation schedules.

**Fields:**
- `id`: str - Unique rule identifier
- `name`: str - Human-readable rule name
- `keywords`: List[str] - List of keywords/phrases to monitor
- `channels`: List[str] - Slack channel IDs to monitor
- `notion_database_id`: str - Target Notion database for matches
- `aggregation_schedule`: str - Cron expression for scheduled aggregation
- `match_mode`: str - Matching strategy: exact, contains, regex
- `case_sensitive`: bool - Whether keyword matching is case-sensitive
- `is_active`: bool - Whether rule is currently enabled
- `created_by`: str - User who created the rule
- `created_at`: datetime - Rule creation timestamp
- `last_triggered`: Optional[datetime] - When rule last matched a message
- `match_count`: int - Total number of messages matched by this rule

**Relationships:**
- Many-to-many with SlackMessage (via keyword matching)
- One-to-many with NotionPage (aggregated reports)

**Validation Rules:**
- `id` must be unique across all rules
- `keywords` must contain at least one non-empty keyword
- `channels` must contain valid Slack channel IDs
- `notion_database_id` must be accessible Notion database
- `aggregation_schedule` must be valid cron expression
- `match_mode` must be one of: exact, contains, regex

### ProcessingQueue

Manages API requests, rate limiting, and retry logic for both Slack and Notion operations.

**Fields:**
- `id`: str - Unique queue item ID
- `task_type`: str - Type of operation: slack_command, notion_create, notion_update, aggregation_job
- `payload`: Dict - Task-specific data (message content, API parameters)
- `priority`: int - Processing priority (1=highest, 10=lowest)
- `status`: str - Status: queued, processing, completed, failed, retry
- `retry_count`: int - Number of retry attempts made
- `max_retries`: int - Maximum retry attempts allowed
- `scheduled_at`: datetime - When task should be processed
- `started_at`: Optional[datetime] - When processing began
- `completed_at`: Optional[datetime] - When task finished (success or failure)
- `error_message`: Optional[str] - Last error message if failed
- `rate_limit_reset`: Optional[datetime] - When rate limit resets for this API

**Relationships:**
- One-to-one with SlackMessage or NotionPage (depending on task_type)

**Validation Rules:**
- `task_type` must be one of enum values
- `priority` must be between 1 and 10
- `retry_count` must not exceed `max_retries`
- `scheduled_at` must not be in the past for new tasks

**State Transitions:**
queued → processing (task picked up by worker)
processing → completed (successful API operation)
processing → failed (permanent failure after retries)
processing → retry (temporary failure, will retry)
retry → queued (retry attempt scheduled)

### SummaryReport

Aggregated content from multiple messages organized by time period, keyword, or channel.

**Fields:**
- `id`: str - Unique report ID
- `report_type`: str - Type: keyword_aggregation, channel_summary, thread_summary
- `time_period`: str - Period covered: daily, weekly, monthly, custom
- `start_date`: datetime - Beginning of aggregation period
- `end_date`: datetime - End of aggregation period
- `source_channels`: List[str] - Slack channels included in report
- `source_keywords`: List[str] - Keywords that triggered inclusion
- `message_count`: int - Number of messages aggregated
- `summary_text`: str - AI-generated summary content
- `key_topics`: List[str] - Extracted main discussion topics
- `participants`: List[str] - Active participants in discussions
- `action_items`: List[str] - Identified action items or decisions
- `notion_page_id`: str - Associated NotionPage ID
- `generated_at`: datetime - When summary was generated

**Relationships:**
- One-to-one with NotionPage
- Many-to-many with SlackMessage (messages included in summary)
- Many-to-one with KeywordRule (if keyword-triggered)

**Validation Rules:**
- `end_date` must be after `start_date`
- `message_count` must match actual number of source messages
- `summary_text` must not exceed Notion content limits
- `notion_page_id` must reference existing NotionPage

### DuplicateGroup

Collection of similar messages with references to original sources and consolidated Notion page.

**Fields:**
- `id`: str - Unique group ID
- `similarity_threshold`: float - Similarity score used for grouping (0.0-1.0)
- `primary_message_id`: str - SlackMessage ID chosen as primary/canonical version
- `duplicate_message_ids`: List[str] - List of similar SlackMessage IDs
- `consolidated_page_id`: str - NotionPage ID for unified content
- `detection_algorithm`: str - Method used: exact_hash, content_similarity, semantic_similarity
- `confidence_score`: float - Confidence in duplicate detection (0.0-1.0)
- `created_at`: datetime - When group was created
- `last_updated`: datetime - When group was last modified
- `status`: str - Status: active, merged, split, archived

**Relationships:**
- One-to-many with SlackMessage (primary and duplicates)
- One-to-one with NotionPage (consolidated page)

**Validation Rules:**
- `similarity_threshold` must be between 0.0 and 1.0
- `primary_message_id` must exist in SlackMessage table
- `duplicate_message_ids` must contain at least one valid SlackMessage ID
- `confidence_score` must be between 0.0 and 1.0

**State Transitions:**
active → merged (duplicates successfully consolidated)
active → split (false positive, group dissolved)
merged → archived (consolidation completed)

## Schema Relationships

```
SlackMessage 1:N → NotionPage (via source_messages)
SlackMessage N:M → KeywordRule (via keyword matching)
SlackMessage N:M → SummaryReport (via aggregation)
SlackMessage 1:N → DuplicateGroup (primary + duplicates)

NotionPage 1:1 → SummaryReport
NotionPage 1:1 → DuplicateGroup (consolidated)

KeywordRule 1:N → NotionPage (aggregated reports)
KeywordRule 1:N → SummaryReport

ProcessingQueue → SlackMessage | NotionPage (polymorphic)
```

## Database Schema Notes

### Indexing Strategy
- `SlackMessage.timestamp` - for time-based queries
- `SlackMessage.channel_id` - for channel-specific operations  
- `SlackMessage.processing_status` - for queue processing
- `KeywordRule.channels` - for channel monitoring lookups
- `ProcessingQueue.status + scheduled_at` - for task processing
- `DuplicateGroup.primary_message_id` - for duplicate lookups

### Data Retention
- SlackMessage: Configurable retention (default 1 year)
- ProcessingQueue: Completed tasks purged after 30 days
- SummaryReport: Permanent retention for historical analysis
- DuplicateGroup: Archived groups retained for 90 days

### Performance Considerations
- Batch insert for high-volume message processing
- Connection pooling for concurrent API operations
- Read replicas for reporting queries
- Partitioning by date for large message tables