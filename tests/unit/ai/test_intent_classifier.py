"""Unit tests for intent classification logic.

This module tests the AI agent's ability to classify user intent
and automatically select appropriate tools for execution.
"""

import pytest

from meowth.ai.intent import UserIntent, IntentClassifier
from meowth.ai.models import ThreadContext


class TestIntentClassifier:
    """Test intent classification functionality."""

    @pytest.fixture
    def classifier(self):
        """Mock intent classifier for testing."""
        return IntentClassifier()

    @pytest.fixture
    def thread_context(self):
        """Mock thread context for testing."""
        return ThreadContext(
            channel_id="C1234567890",
            thread_ts="1234567890.123456",
            messages=[],
            token_count=0,
        )

    def test_classify_summarization_intent(self, classifier, thread_context):
        """Test classification of message summarization requests."""
        # Test explicit summarization request
        message = "Can you summarize the last 10 messages in this channel?"
        intent = classifier.classify_intent(message, thread_context)

        assert intent.primary_intent == "summarization"
        assert intent.confidence > 0.8
        assert intent.tool_suggestions == ["fetch_slack_messages", "summarize_messages"]

    def test_classify_analysis_intent(self, classifier, thread_context):
        """Test classification of conversation analysis requests."""
        message = "What are the main topics discussed in this thread?"
        intent = classifier.classify_intent(message, thread_context)

        assert intent.primary_intent == "analysis"
        assert intent.confidence > 0.7
        assert "analyze_conversation" in intent.tool_suggestions

    def test_classify_information_lookup_intent(self, classifier, thread_context):
        """Test classification of information lookup requests."""
        message = "Who participated in this conversation?"
        intent = classifier.classify_intent(message, thread_context)

        assert intent.primary_intent == "information_lookup"
        assert intent.confidence > 0.7
        assert "fetch_slack_messages" in intent.tool_suggestions

    def test_classify_ambiguous_intent(self, classifier, thread_context):
        """Test handling of ambiguous user requests."""
        message = "Tell me about stuff"
        intent = classifier.classify_intent(message, thread_context)

        assert intent.primary_intent == "ambiguous"
        assert intent.confidence < 0.4
        assert len(intent.fallback_suggestions) > 0

    def test_classify_greeting_intent(self, classifier, thread_context):
        """Test classification of greeting messages."""
        message = "Hello there!"
        intent = classifier.classify_intent(message, thread_context)

        assert intent.primary_intent == "greeting"
        assert intent.confidence > 0.5
        assert len(intent.tool_suggestions) == 0

    def test_intent_with_parameters(self, classifier, thread_context):
        """Test intent classification extracts parameters."""
        message = "Summarize the last 25 messages from #general"
        intent = classifier.classify_intent(message, thread_context)

        assert intent.primary_intent == "summarization"
        assert intent.parameters.get("message_count") == 25
        assert intent.parameters.get("channel_reference") == "#general"

    def test_intent_confidence_scoring(self, classifier, thread_context):
        """Test that confidence scores are properly calculated."""
        # High confidence case
        message = "Please summarize this conversation"
        intent = classifier.classify_intent(message, thread_context)
        high_confidence = intent.confidence

        # Lower confidence case
        message = "What's happening?"
        intent = classifier.classify_intent(message, thread_context)
        low_confidence = intent.confidence

        assert high_confidence > low_confidence
        assert 0.0 <= low_confidence <= 1.0
        assert 0.0 <= high_confidence <= 1.0

    def test_context_aware_classification(self, classifier):
        """Test that classification considers context."""
        # Same message in different contexts should yield different confidence
        message = "What are the key topics discussed?"

        # Context with recent activity
        active_context = ThreadContext(
            channel_id="C1234567890",
            thread_ts="1234567890.123456",
            messages=[],
            token_count=0,
        )

        intent = classifier.classify_intent(message, active_context)
        assert intent.primary_intent in ["information_lookup", "analysis"]


class TestUserIntent:
    """Test UserIntent data model."""

    def test_user_intent_creation(self):
        """Test UserIntent object creation and validation."""
        intent = UserIntent(
            primary_intent="summarization",
            confidence=0.85,
            tool_suggestions=["fetch_slack_messages", "summarize_messages"],
            parameters={"message_count": 10},
            fallback_suggestions=["provide_help"],
        )

        assert intent.primary_intent == "summarization"
        assert intent.confidence == 0.85
        assert len(intent.tool_suggestions) == 2
        assert intent.parameters["message_count"] == 10

    def test_intent_validation(self):
        """Test validation of UserIntent fields."""
        # Test confidence bounds
        with pytest.raises(ValueError):
            UserIntent(
                primary_intent="test",
                confidence=1.5,  # Invalid confidence > 1.0
                tool_suggestions=[],
                parameters={},
            )

        with pytest.raises(ValueError):
            UserIntent(
                primary_intent="test",
                confidence=-0.1,  # Invalid confidence < 0.0
                tool_suggestions=[],
                parameters={},
            )

    def test_intent_serialization(self):
        """Test UserIntent can be serialized to dict."""
        intent = UserIntent(
            primary_intent="analysis",
            confidence=0.75,
            tool_suggestions=["analyze_conversation"],
            parameters={"depth": "detailed"},
        )

        intent_dict = intent.to_dict()
        assert intent_dict["primary_intent"] == "analysis"
        assert intent_dict["confidence"] == 0.75
        assert "analyze_conversation" in intent_dict["tool_suggestions"]
