"""Response formatting for context-aware AI responses.

Formats AI responses appropriately based on channel context, 
audience type, and conversation context.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
import logging

from meowth.ai.execution import ToolExecutionContext
from meowth.ai.context_analyzer import ChannelContext, ContextType


logger = logging.getLogger(__name__)


class FormattingStyle(Enum):
    """Response formatting styles."""
    TECHNICAL = "technical"
    CONVERSATIONAL = "conversational"
    BRIEF = "brief"
    STRUCTURED = "structured"


class AudienceType(Enum):
    """Types of audiences for response formatting."""
    TECHNICAL_TEAM = "technical_team"
    PRODUCT_TEAM = "product_team"
    MIXED_TEAM = "mixed_team"
    EXECUTIVE_TEAM = "executive_team"
    PROJECT_TEAM = "project_team"


@dataclass
class ChannelResponseContext:
    """Context for formatting responses to specific channels."""
    channel_id: str
    audience_type: AudienceType
    expertise_level: str
    preferred_style: FormattingStyle
    context_type: ContextType
    urgency_level: str


@dataclass
class ResponseTemplate:
    """Template for formatting responses."""
    template_type: str
    sections: List[str]
    max_length: Optional[int] = None
    include_technical: bool = False


@dataclass 
class FormattedResponse:
    """A formatted response ready for delivery."""
    formatted_text: str
    style: FormattingStyle
    has_errors: bool = False
    tool_count: int = 0
    metadata: Optional[Dict] = None


class ResponseFormatter:
    """Formats AI tool responses based on context."""
    
    def __init__(self):
        """Initialize response formatter."""
        self.templates = self._initialize_templates()
    
    def format_response(
        self,
        execution_context: ToolExecutionContext,
        channel_context: ChannelResponseContext
    ) -> FormattedResponse:
        """Format response based on execution context and channel context.
        
        Args:
            execution_context: Tool execution context with results
            channel_context: Channel context for formatting
            
        Returns:
            FormattedResponse with appropriately formatted text
        """
        try:
            # Select appropriate template
            template = self._select_template(channel_context)
            
            # Extract results from execution context
            tool_results = list(execution_context.results.values()) if execution_context.results else []
            
            # Format based on style
            if channel_context.preferred_style == FormattingStyle.BRIEF:
                formatted_text = self._format_brief(tool_results, template)
            elif channel_context.preferred_style == FormattingStyle.TECHNICAL:
                formatted_text = self._format_technical(tool_results, template)
            elif channel_context.preferred_style == FormattingStyle.STRUCTURED:
                formatted_text = self._format_structured(tool_results, template)
            else:
                formatted_text = self._format_conversational(tool_results, template)
            
            # Check for errors
            has_errors = any(not result.success for result in tool_results)
            
            return FormattedResponse(
                formatted_text=formatted_text,
                style=channel_context.preferred_style,
                has_errors=has_errors,
                tool_count=len(tool_results),
                metadata={"template": template.template_type}
            )
            
        except Exception as e:
            logger.error(f"Error formatting response: {e}")
            return FormattedResponse(
                formatted_text="Sorry, I encountered an error while formatting the response.",
                style=FormattingStyle.CONVERSATIONAL,
                has_errors=True
            )
    
    def _select_template(self, channel_context: ChannelResponseContext) -> ResponseTemplate:
        """Select appropriate template based on channel context."""
        if channel_context.context_type == ContextType.INCIDENT_RESPONSE:
            return self.templates["incident_response"]
        elif channel_context.context_type == ContextType.TECHNICAL_DISCUSSION:
            return self.templates["technical"]
        elif channel_context.context_type == ContextType.FEATURE_DISCUSSION:
            return self.templates["feature_summary"]
        elif channel_context.context_type == ContextType.PROJECT_COORDINATION:
            return self.templates["project"]
        else:
            return self.templates["general"]
    
    def _format_brief(self, results: List, template: ResponseTemplate) -> str:
        """Format response in brief style."""
        if not results:
            return "No results available."
        
        summary_parts = []
        for result in results[:3]:  # Limit to 3 results for brevity
            if hasattr(result, 'success') and result.success:
                data = result.data if hasattr(result, 'data') else {}
                if isinstance(data, dict) and 'summary' in data:
                    summary_parts.append(data['summary'])
                elif isinstance(data, dict):
                    # Extract key information
                    for key in ['message_count', 'key_decisions', 'status']:
                        if key in data:
                            summary_parts.append(f"{key.replace('_', ' ').title()}: {data[key]}")
        
        return " | ".join(summary_parts) if summary_parts else "Brief summary available."
    
    def _format_technical(self, results: List, template: ResponseTemplate) -> str:
        """Format response in technical style."""
        if not results:
            return "No technical data available."

        formatted_parts = []
        for result in results:
            if hasattr(result, 'success') and result.success:
                data = result.data if hasattr(result, 'data') else {}
                if isinstance(data, dict):
                    # Include technical details
                    formatted_parts.append(f"**{result.tool_name if hasattr(result, 'tool_name') else 'Analysis'}:**")
                    for key, value in data.items():
                        if isinstance(value, list):
                            # Format lists nicely
                            sanitized_value = [self._sanitize_text(str(item)) for item in value]
                            formatted_parts.append(f"  {key}: {sanitized_value}")
                        elif isinstance(value, dict):
                            formatted_parts.append(f"  {key}: {value}")
                        else:
                            formatted_parts.append(f"  {key}: {self._sanitize_text(str(value))}")

        return "\n".join(formatted_parts) if formatted_parts else "Technical analysis complete."

    def _format_conversational(self, results: List, template: ResponseTemplate) -> str:
        """Format response in conversational style."""
        if not results:
            return "I couldn't find any information to share."

        conversational_parts = []
        for result in results:
            if hasattr(result, 'success') and result.success:
                data = result.data if hasattr(result, 'data') else {}
                if isinstance(data, dict) and 'summary' in data:
                    response_text = f"Here's what I found: {data['summary']}"
                    
                    # Include key decisions and action items for better context
                    if 'key_decisions' in data and data['key_decisions']:
                        decisions_text = ", ".join(data['key_decisions'][:2])  # Limit for readability
                        response_text += f". Key decisions include: {decisions_text}"
                    
                    if 'action_items' in data and data['action_items']:
                        actions_text = ", ".join(data['action_items'][:2])  # Limit for readability  
                        response_text += f". Action items: {actions_text}"
                        
                    conversational_parts.append(self._sanitize_text(response_text))
            elif hasattr(result, 'success') and not result.success:
                # Handle failed results
                error_msg = getattr(result, 'error', 'An error occurred')
                if 'rate limit' in error_msg.lower():
                    conversational_parts.append("I hit a rate limit while fetching data. Please try again in a moment.")
                else:
                    conversational_parts.append(f"I ran into an issue: {error_msg}")

        return "\n\n".join(conversational_parts) if conversational_parts else "I've completed the analysis."

    def _format_structured(self, results: List, template: ResponseTemplate) -> str:
        """Format response in structured style."""
        if not results:
            return "## Analysis Results\n\nNo data available."
        
        structured_text = "## Analysis Results\n\n"
        for i, result in enumerate(results, 1):
            if hasattr(result, 'success') and result.success:
                structured_text += f"### {i}. {result.tool_name if hasattr(result, 'tool_name') else 'Analysis'}\n\n"
                data = result.data if hasattr(result, 'data') else {}
                if isinstance(data, dict):
                    for key, value in data.items():
                        structured_text += f"- **{key.replace('_', ' ').title()}:** {value}\n"
                structured_text += "\n"
        
        return structured_text
    
    def _initialize_templates(self) -> Dict[str, ResponseTemplate]:
        """Initialize response templates."""
        return {
            "general": ResponseTemplate(
                template_type="general",
                sections=["overview", "details"]
            ),
            "technical": ResponseTemplate(
                template_type="technical",
                sections=["metrics", "analysis", "recommendations"],
                include_technical=True
            ),
            "incident_response": ResponseTemplate(
                template_type="incident_response",
                sections=["status", "priority", "actions"],
                max_length=500
            ),
            "feature_summary": ResponseTemplate(
                template_type="feature_summary",
                sections=["overview", "decisions", "next_steps"]
            ),
            "project": ResponseTemplate(
                template_type="project",
                sections=["progress", "blockers", "timeline"]
            )
        }

    def _sanitize_text(self, text: str) -> str:
        """Sanitize text to prevent XSS and other security issues."""
        if not isinstance(text, str):
            return str(text)
        
        # Remove dangerous HTML tags
        dangerous_tags = ['<script>', '</script>', '<iframe>', '</iframe>', 
                         '<object>', '</object>', '<embed>', '</embed>']
        
        sanitized = text
        for tag in dangerous_tags:
            sanitized = sanitized.replace(tag, '')
            sanitized = sanitized.replace(tag.upper(), '')
        
        return sanitized