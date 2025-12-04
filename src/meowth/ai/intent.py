"""User intent classification and management.

This module provides intent classification capabilities for automatically
determining user intent and suggesting appropriate tools for execution.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from .models import ThreadContext


class IntentType(str, Enum):
    """Supported user intent types."""

    SUMMARIZATION = "summarization"
    ANALYSIS = "analysis"
    INFORMATION_LOOKUP = "information_lookup"
    GREETING = "greeting"
    HELP = "help"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


@dataclass
class UserIntent:
    """Represents classified user intent with confidence and suggestions.

    Attributes:
        primary_intent: The primary classified intent
        confidence: Confidence score (0.0 to 1.0)
        tool_suggestions: List of recommended tools for this intent
        parameters: Extracted parameters from user message
        fallback_suggestions: Fallback options if primary intent fails
    """

    primary_intent: str
    confidence: float
    tool_suggestions: List[str]
    parameters: Dict[str, Any]
    fallback_suggestions: Optional[List[str]] = None

    def __post_init__(self) -> None:
        """Validate intent data after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )

        if not isinstance(self.tool_suggestions, list):
            raise ValueError("tool_suggestions must be a list")

        if not isinstance(self.parameters, dict):
            raise ValueError("parameters must be a dict")

    def to_dict(self) -> Dict[str, Any]:
        """Convert intent to dictionary representation."""
        return {
            "primary_intent": self.primary_intent,
            "confidence": self.confidence,
            "tool_suggestions": self.tool_suggestions,
            "parameters": self.parameters,
            "fallback_suggestions": self.fallback_suggestions,
        }


class IntentClassifier:
    """Classifies user intent from natural language messages."""

    def __init__(self):
        """Initialize the intent classifier with pattern rules."""
        self._intent_patterns = {
            IntentType.SUMMARIZATION: [
                r"\b(summarize|summary|sum up|recap|overview)\b",
                r"\blast\s+\d+\s+(messages?|posts?)\b",
                r"\bwhat\s+(happened|was discussed)\b",
                r"\bgive me (a|an)\s+(summary|overview|recap)\b",
                r"\bcan you summarize\b",
                r"\bsummarize.*messages?\b",
            ],
            IntentType.ANALYSIS: [
                r"\b(analyze|analysis|topics?|themes?)\b",
                r"\bwhat\s+(are|were)\s+the\s+main\b",
                r"\bkey\s+(points?|topics?|themes?)\b",
                r"\b(sentiment|mood|tone)\b",
                r"\bwho\s+(said|mentioned|talked about)\b",
            ],
            IntentType.INFORMATION_LOOKUP: [
                r"\bwho\s+(participated|joined|was in)\b",
                r"\b(when|what time)\b",
                r"\bhow many\s+(people|participants|messages)\b",
                r"\blist\s+(participants|members|users)\b",
                r"\bshow me\s+\w+",  # More specific - requires something after "show me"
                r"\btell me about\s+(\w+\s+){2,}",  # Requires more specific content after "tell me about"
                r"\bwhat\'?s\s+the\s+(current\s+)?(status|state)\b",  # For status queries
            ],
            IntentType.GREETING: [
                r"\b(hello|hi|hey|good morning|good afternoon)\b",
                r"\bwhat\'?s up\b",
                r"\bhow are you\b",
            ],
            IntentType.HELP: [
                r"\bhelp\b",
                r"\bwhat can you do\b",
                r"\bhow do i\b",
                r"\bcan you help\b",
                r"\binstructions?\b",
                r"\bcan you\s+(help|assist|guide)\b",
            ],
        }

        # Patterns for parameter extraction
        self._parameter_patterns = {
            "message_count": r"\blast\s+(\d+)\s+messages?\b",
            "channel_reference": r"#(\w+)",
            "time_reference": r"\b(today|yesterday|this week|last week)\b",
            "user_reference": r"@(\w+)",
            "style_preference": r"\b(brief|detailed|short|long|quick)\b",
        }

    def classify_intent(self, message: str, context: ThreadContext) -> UserIntent:
        """Classify user intent from message text and context.

        Args:
            message: User's message text
            context: Thread context for additional signals

        Returns:
            UserIntent object with classification results
        """
        message_lower = message.lower().strip()

        # Calculate intent scores
        intent_scores = self._calculate_intent_scores(message_lower)

        # Get primary intent and confidence
        if intent_scores:
            primary_intent = max(intent_scores.keys(), key=lambda k: intent_scores[k])
            confidence = intent_scores[primary_intent]
        else:
            primary_intent = IntentType.UNKNOWN
            confidence = 0.0

        # Handle ambiguous cases - be more permissive for clear intents
        high_scoring_intents = [
            intent for intent, score in intent_scores.items() if score > 0.3
        ]
        if confidence < 0.5 and len(high_scoring_intents) == 1:
            # If we have one clear intent above threshold, use it
            primary_intent = high_scoring_intents[0] 
            confidence = max(intent_scores[primary_intent], 0.5)  # Boost confidence for clear single intent
        elif (
            confidence < 0.3 or len([s for s in intent_scores.values() if s > 0.5]) > 1
        ):
            primary_intent = IntentType.AMBIGUOUS
            confidence = min(confidence, 0.4)

        # Extract parameters
        parameters = self._extract_parameters(message)

        # Get tool suggestions based on intent
        tool_suggestions = self._get_tool_suggestions(primary_intent, parameters)

        # Get fallback suggestions
        fallback_suggestions = self._get_fallback_suggestions(primary_intent)

        return UserIntent(
            primary_intent=primary_intent.value,
            confidence=confidence,
            tool_suggestions=tool_suggestions,
            parameters=parameters,
            fallback_suggestions=fallback_suggestions,
        )

    def _calculate_intent_scores(self, message: str) -> Dict[IntentType, float]:
        """Calculate confidence scores for each intent type.

        Args:
            message: Lowercase message text

        Returns:
            Dictionary mapping intent types to confidence scores
        """
        scores: Dict[IntentType, float] = {}

        for intent_type, patterns in self._intent_patterns.items():
            score = 0.0
            matches = 0

            for pattern in patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    matches += 1
                    # Weight multiple pattern matches with higher base score
                    score += 0.5 + (0.15 * min(matches - 1, 3))

            if score > 0:
                # Boost score based on message length and specificity
                specificity_boost = min(len(message.split()) / 20, 0.3)
                score = min(score + specificity_boost, 1.0)
                scores[intent_type] = score

        return scores

    def _extract_parameters(self, message: str) -> Dict[str, Any]:
        """Extract parameters from user message.

        Args:
            message: User's message text

        Returns:
            Dictionary of extracted parameters
        """
        parameters = {}

        for param_name, pattern in self._parameter_patterns.items():
            matches = re.findall(pattern, message, re.IGNORECASE)

            if matches:
                if param_name == "message_count":
                    # Convert to integer and apply limits
                    try:
                        count = int(matches[0])
                        parameters[param_name] = min(max(count, 1), 100)
                    except ValueError:
                        pass
                elif param_name == "channel_reference":
                    parameters[param_name] = f"#{matches[0]}"
                elif param_name == "user_reference":
                    parameters[param_name] = matches[0]
                elif param_name == "style_preference":
                    style = matches[0].lower()
                    if style in ["brief", "short", "quick"]:
                        parameters["style"] = "brief"
                    elif style in ["detailed", "long"]:
                        parameters["style"] = "detailed"
                else:
                    parameters[param_name] = matches[0]

        return parameters

    def _get_tool_suggestions(
        self, intent: str, parameters: Dict[str, Any]
    ) -> List[str]:
        """Get tool suggestions based on classified intent.

        Args:
            intent: Primary classified intent
            parameters: Extracted parameters

        Returns:
            List of recommended tool names
        """
        tool_mapping = {
            IntentType.SUMMARIZATION: ["fetch_slack_messages", "summarize_messages"],
            IntentType.ANALYSIS: ["fetch_slack_messages", "analyze_conversation"],
            IntentType.INFORMATION_LOOKUP: ["fetch_slack_messages"],
            IntentType.GREETING: [],
            IntentType.HELP: [],
            IntentType.AMBIGUOUS: [],
            IntentType.UNKNOWN: [],
        }

        return tool_mapping.get(intent, [])

    def _get_fallback_suggestions(self, intent: str) -> List[str]:
        """Get fallback suggestions for intent handling failures.

        Args:
            intent: Primary classified intent

        Returns:
            List of fallback option names
        """
        fallback_mapping = {
            IntentType.SUMMARIZATION: ["provide_help", "suggest_alternatives"],
            IntentType.ANALYSIS: ["provide_help", "suggest_alternatives"],
            IntentType.INFORMATION_LOOKUP: ["provide_help"],
            IntentType.GREETING: ["provide_greeting_response"],
            IntentType.HELP: ["provide_help"],
            IntentType.AMBIGUOUS: ["ask_clarification", "provide_help"],
            IntentType.UNKNOWN: ["ask_clarification"],
        }

        return fallback_mapping.get(intent, ["provide_help"])


def get_intent_classifier() -> IntentClassifier:
    """Get a global instance of the intent classifier.

    Returns:
        Shared IntentClassifier instance
    """
    if not hasattr(get_intent_classifier, "_instance"):
        get_intent_classifier._instance = IntentClassifier()

    return get_intent_classifier._instance
