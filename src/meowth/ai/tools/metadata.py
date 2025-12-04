"""Tool metadata optimization for enhanced LLM comprehension.

This module provides utilities for optimizing tool descriptions and metadata
to improve LLM understanding and automatic tool selection accuracy.
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from llama_index.core.tools import FunctionTool


@dataclass
class ToolMetadata:
    """Enhanced tool metadata for improved LLM comprehension.

    Attributes:
        name: Tool name (clear and descriptive)
        description: Enhanced description optimized for LLM understanding
        intent_keywords: Keywords that indicate this tool should be used
        parameter_hints: Hints about parameter usage and defaults
        usage_examples: Examples of when to use this tool
        constraints: Limitations and constraints for tool usage
        output_format: Description of expected output format
    """

    name: str
    description: str
    intent_keywords: List[str]
    parameter_hints: Dict[str, str]
    usage_examples: List[str]
    constraints: List[str]
    output_format: str

    def to_llm_description(self) -> str:
        """Convert metadata to LLM-optimized description.

        Returns:
            Formatted description optimized for LLM understanding
        """
        parts = [self.description]

        if self.intent_keywords:
            keywords_str = ", ".join(self.intent_keywords)
            parts.append(f"Use this tool for: {keywords_str}")

        if self.parameter_hints:
            hints_list = [
                f"{param}: {hint}" for param, hint in self.parameter_hints.items()
            ]
            parts.append(f"Parameters: {'; '.join(hints_list)}")

        if self.usage_examples:
            examples_str = " | ".join(self.usage_examples)
            parts.append(f"Examples: {examples_str}")

        if self.constraints:
            constraints_str = " | ".join(self.constraints)
            parts.append(f"Constraints: {constraints_str}")

        if self.output_format:
            parts.append(f"Output: {self.output_format}")

        return " | ".join(parts)


class ToolMetadataOptimizer:
    """Optimizes tool metadata for better LLM comprehension."""

    def __init__(self):
        """Initialize the metadata optimizer."""
        self._common_intent_patterns = {
            "summarize": ["summarize", "summary", "sum up", "recap", "overview"],
            "analyze": ["analyze", "analysis", "examine", "study", "investigate"],
            "fetch": ["get", "retrieve", "fetch", "find", "search", "lookup"],
            "count": ["count", "how many", "number of", "total"],
            "list": ["list", "show", "display", "enumerate"],
            "identify": ["who", "which", "identify", "determine"],
        }

        self._parameter_optimizations = {
            "limit": "Maximum number of items to return (default: 10)",
            "count": "Number of items to process or return",
            "channel_id": "Slack channel identifier (required)",
            "user_id": "Slack user identifier (optional)",
            "start_time": "Start time for data range (ISO format)",
            "end_time": "End time for data range (ISO format)",
            "message_ts": "Slack message timestamp",
            "thread_ts": "Slack thread timestamp",
        }

    def optimize_tool_metadata(self, tool: FunctionTool) -> ToolMetadata:
        """Optimize metadata for a single tool.

        Args:
            tool: LlamaIndex FunctionTool to optimize

        Returns:
            Enhanced tool metadata
        """
        # Extract existing metadata
        name = tool.metadata.name
        original_desc = tool.metadata.description

        # Generate enhanced description
        enhanced_desc = self._enhance_description(original_desc, name)

        # Extract intent keywords
        intent_keywords = self._extract_intent_keywords(name, enhanced_desc)

        # Generate parameter hints
        parameter_hints = self._generate_parameter_hints(tool)

        # Generate usage examples
        usage_examples = self._generate_usage_examples(name, intent_keywords)

        # Identify constraints
        constraints = self._identify_constraints(tool)

        # Describe output format
        output_format = self._describe_output_format(name)

        return ToolMetadata(
            name=name,
            description=enhanced_desc,
            intent_keywords=intent_keywords,
            parameter_hints=parameter_hints,
            usage_examples=usage_examples,
            constraints=constraints,
            output_format=output_format,
        )

    def _enhance_description(self, original_desc: str, tool_name: str) -> str:
        """Enhance tool description for better LLM understanding.

        Args:
            original_desc: Original tool description
            tool_name: Tool name

        Returns:
            Enhanced description
        """
        # Clean up description
        desc = original_desc.strip()

        # Add action-oriented language
        if not desc.lower().startswith(
            ("get", "fetch", "analyze", "summarize", "count", "list")
        ):
            action = self._infer_action_from_name(tool_name)
            if action:
                desc = f"{action} {desc.lower()}"

        # Ensure description is clear and specific
        desc = self._clarify_description(desc)

        return desc

    def _infer_action_from_name(self, tool_name: str) -> Optional[str]:
        """Infer primary action from tool name.

        Args:
            tool_name: Tool name

        Returns:
            Primary action verb or None
        """
        name_lower = tool_name.lower()

        if "fetch" in name_lower or "get" in name_lower:
            return "Retrieve"
        elif "analyze" in name_lower:
            return "Analyze"
        elif "summarize" in name_lower:
            return "Summarize"
        elif "count" in name_lower:
            return "Count"
        elif "list" in name_lower:
            return "List"

        return None

    def _clarify_description(self, desc: str) -> str:
        """Clarify description with specific details.

        Args:
            desc: Description to clarify

        Returns:
            Clarified description
        """
        # Add specifics about Slack context
        if "message" in desc.lower():
            desc = desc.replace("messages", "Slack messages")
            desc = desc.replace("message", "Slack message")

        if "conversation" in desc.lower():
            desc = desc.replace("conversation", "Slack conversation thread")

        if "user" in desc.lower() and "slack" not in desc.lower():
            desc = desc.replace("users", "Slack users")
            desc = desc.replace("user", "Slack user")

        return desc

    def _extract_intent_keywords(self, tool_name: str, description: str) -> List[str]:
        """Extract keywords that indicate when this tool should be used.

        Args:
            tool_name: Tool name
            description: Enhanced description

        Returns:
            List of intent keywords
        """
        keywords: Set[str] = set()

        # Extract from tool name
        name_words = re.findall(r"[a-z]+", tool_name.lower())
        keywords.update(name_words)

        # Extract from description
        desc_words = re.findall(r"\b[a-z]{3,}\b", description.lower())
        keywords.update(desc_words)

        # Add patterns based on common intents
        for intent, patterns in self._common_intent_patterns.items():
            if any(
                pattern in description.lower() or pattern in tool_name.lower()
                for pattern in patterns
            ):
                keywords.update(patterns)

        # Filter to relevant keywords
        relevant_keywords = [kw for kw in keywords if self._is_relevant_keyword(kw)]

        return sorted(relevant_keywords)[:10]  # Limit to top 10

    def _is_relevant_keyword(self, keyword: str) -> bool:
        """Check if keyword is relevant for intent classification.

        Args:
            keyword: Keyword to check

        Returns:
            True if keyword is relevant
        """
        # Skip common words
        skip_words = {"the", "and", "for", "with", "from", "this", "that", "tool"}
        if keyword in skip_words:
            return False

        # Include action words and domain terms
        action_words = {
            "get",
            "fetch",
            "analyze",
            "summarize",
            "count",
            "list",
            "find",
            "search",
        }
        domain_words = {
            "slack",
            "message",
            "conversation",
            "thread",
            "channel",
            "user",
            "participant",
        }

        return keyword in action_words or keyword in domain_words or len(keyword) >= 4

    def _generate_parameter_hints(self, tool: FunctionTool) -> Dict[str, str]:
        """Generate parameter hints for better parameter understanding.

        Args:
            tool: LlamaIndex FunctionTool

        Returns:
            Dictionary of parameter hints
        """
        hints = {}

        # Extract parameter names from function signature if available
        fn = tool.fn
        if hasattr(fn, "__annotations__"):
            for param_name, param_type in fn.__annotations__.items():
                if param_name == "return":
                    continue

                # Use predefined hints or generate from type
                if param_name in self._parameter_optimizations:
                    hints[param_name] = self._parameter_optimizations[param_name]
                else:
                    hints[param_name] = self._generate_type_hint(param_name, param_type)

        return hints

    def _generate_type_hint(self, param_name: str, param_type: Any) -> str:
        """Generate parameter hint from type annotation.

        Args:
            param_name: Parameter name
            param_type: Parameter type annotation

        Returns:
            Parameter hint string
        """
        type_name = str(param_type).replace("<class '", "").replace("'>", "")

        if "str" in type_name:
            return f"String value for {param_name}"
        elif "int" in type_name:
            return f"Integer value for {param_name}"
        elif "bool" in type_name:
            return f"Boolean flag for {param_name}"
        elif "Optional" in type_name:
            return f"Optional parameter for {param_name}"

        return f"Value for {param_name}"

    def _generate_usage_examples(
        self, tool_name: str, intent_keywords: List[str]
    ) -> List[str]:
        """Generate usage examples based on tool name and keywords.

        Args:
            tool_name: Tool name
            intent_keywords: Intent keywords for the tool

        Returns:
            List of usage examples
        """
        examples = []

        # Generate examples based on primary keywords
        if "summarize" in intent_keywords:
            examples.append("User asks: 'Can you summarize the last 10 messages?'")

        if "analyze" in intent_keywords:
            examples.append("User asks: 'What are the main topics discussed?'")

        if "fetch" in intent_keywords or "get" in intent_keywords:
            examples.append("User asks: 'Show me recent messages in this channel'")

        if "count" in intent_keywords:
            examples.append("User asks: 'How many people participated?'")

        if "list" in intent_keywords:
            examples.append("User asks: 'List all participants in this thread'")

        # Fallback examples based on tool name patterns
        if not examples:
            if "message" in tool_name.lower():
                examples.append("When user needs message-related information")
            elif "user" in tool_name.lower():
                examples.append("When user asks about participants or users")
            else:
                examples.append(f"When user needs {tool_name.lower()} functionality")

        return examples[:3]  # Limit to 3 examples

    def _identify_constraints(self, tool: FunctionTool) -> List[str]:
        """Identify tool usage constraints and limitations.

        Args:
            tool: LlamaIndex FunctionTool

        Returns:
            List of constraints
        """
        constraints = []

        # Common constraints based on tool characteristics
        tool_name = tool.metadata.name.lower()

        if "slack" in tool_name:
            constraints.append("Requires valid Slack channel context")

        if "message" in tool_name:
            constraints.append("Limited to available message history")

        if "analyze" in tool_name:
            constraints.append("May require multiple messages for meaningful analysis")

        # Add rate limiting constraint for API-based tools
        if any(keyword in tool_name for keyword in ["fetch", "get", "api"]):
            constraints.append("Subject to API rate limits")

        return constraints

    def _describe_output_format(self, tool_name: str) -> str:
        """Describe the expected output format for the tool.

        Args:
            tool_name: Tool name

        Returns:
            Output format description
        """
        tool_name_lower = tool_name.lower()

        if "summarize" in tool_name_lower:
            return "Structured summary with key points and themes"
        elif "analyze" in tool_name_lower:
            return "Analysis results with insights and patterns"
        elif "count" in tool_name_lower:
            return "Numerical count with breakdown details"
        elif "list" in tool_name_lower:
            return "Formatted list of items with relevant details"
        elif "fetch" in tool_name_lower or "get" in tool_name_lower:
            return "Raw data or formatted information as requested"

        return "Structured data relevant to the request"

    def optimize_tool_collection(
        self, tools: List[FunctionTool]
    ) -> Dict[str, ToolMetadata]:
        """Optimize metadata for a collection of tools.

        Args:
            tools: List of LlamaIndex FunctionTool objects

        Returns:
            Dictionary mapping tool names to optimized metadata
        """
        optimized_metadata = {}

        for tool in tools:
            metadata = self.optimize_tool_metadata(tool)
            optimized_metadata[tool.metadata.name] = metadata

        return optimized_metadata

    def update_tool_descriptions(self, tools: List[FunctionTool]) -> List[FunctionTool]:
        """Update tool descriptions with optimized metadata.

        Args:
            tools: List of LlamaIndex FunctionTool objects

        Returns:
            List of tools with updated descriptions
        """
        updated_tools = []

        for tool in tools:
            metadata = self.optimize_tool_metadata(tool)

            # Create new tool with enhanced description
            enhanced_tool = FunctionTool.from_defaults(
                fn=tool.fn,
                name=tool.metadata.name,
                description=metadata.to_llm_description(),
                return_direct=tool.return_direct,
            )

            updated_tools.append(enhanced_tool)

        return updated_tools


def get_metadata_optimizer() -> ToolMetadataOptimizer:
    """Get a global instance of the metadata optimizer.

    Returns:
        Shared ToolMetadataOptimizer instance
    """
    if not hasattr(get_metadata_optimizer, "_instance"):
        get_metadata_optimizer._instance = ToolMetadataOptimizer()

    return get_metadata_optimizer._instance
