"""Langfuse monitoring integration for AI agent observability.

This module provides Langfuse integration for monitoring AI agent performance,
tracking conversations, and analyzing usage patterns.
"""

from __future__ import annotations

import logging
import time
import json
from typing import Optional, Dict, Any, List, Union
from functools import wraps
from contextlib import asynccontextmanager
from datetime import datetime

try:
    from langfuse import Langfuse, observe
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    # Provide mock implementations
    def observe(func):
        """Mock decorator when Langfuse is not available."""
        return func

from ..utils.config import config
from .models import ThreadContext, AIResponse, RequestSession

logger = logging.getLogger(__name__)


class LangfuseMonitor:
    """Langfuse monitoring wrapper for AI agent operations using modern API."""

    def __init__(self):
        """Initialize Langfuse monitor."""
        self._langfuse: Optional[Langfuse] = None
        self._enabled = False
        
        if LANGFUSE_AVAILABLE and self._should_enable():
            try:
                # Set environment variables for Langfuse client
                import os
                if not os.getenv('LANGFUSE_PUBLIC_KEY'):
                    os.environ['LANGFUSE_PUBLIC_KEY'] = config.langfuse_public_key
                if not os.getenv('LANGFUSE_SECRET_KEY'):
                    os.environ['LANGFUSE_SECRET_KEY'] = config.langfuse_secret_key
                if not os.getenv('LANGFUSE_HOST'):
                    os.environ['LANGFUSE_HOST'] = config.langfuse_host
                
                # Initialize Langfuse client
                self._langfuse = Langfuse()
                
                # Test the connection
                auth_result = self._langfuse.auth_check()
                if auth_result:
                    self._enabled = True
                    logger.info("Langfuse monitoring enabled and authenticated successfully")
                else:
                    logger.warning("Langfuse authentication failed")
                    
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse: {e}")
        else:
            logger.info("Langfuse monitoring disabled (missing config or library)")

    def _should_enable(self) -> bool:
        """Check if Langfuse should be enabled based on configuration."""
        return (
            hasattr(config, 'langfuse_public_key') and 
            hasattr(config, 'langfuse_secret_key') and
            config.langfuse_public_key and 
            config.langfuse_secret_key
        )

    @property
    def enabled(self) -> bool:
        """Whether Langfuse monitoring is enabled."""
        return self._enabled

def get_langfuse_observe_decorator():
    """Get the Langfuse observe decorator if available, otherwise return passthrough."""
    if LANGFUSE_AVAILABLE:
        try:
            # Set up environment variables if not already set
            import os
            if not os.getenv('LANGFUSE_PUBLIC_KEY') and config.langfuse_public_key:
                os.environ['LANGFUSE_PUBLIC_KEY'] = config.langfuse_public_key
            if not os.getenv('LANGFUSE_SECRET_KEY') and config.langfuse_secret_key:
                os.environ['LANGFUSE_SECRET_KEY'] = config.langfuse_secret_key
            if not os.getenv('LANGFUSE_HOST') and hasattr(config, 'langfuse_host'):
                os.environ['LANGFUSE_HOST'] = config.langfuse_host
            
            # Check if credentials are actually available
            if not os.getenv('LANGFUSE_PUBLIC_KEY') or not os.getenv('LANGFUSE_SECRET_KEY'):
                logger.debug("Langfuse credentials not available, using passthrough decorator")
                return lambda **kwargs: lambda func: func
            
            from langfuse import observe
            return observe
        except Exception as e:
            logger.warning(f"Failed to get Langfuse observe decorator: {e}")
            return lambda **kwargs: lambda func: func
    else:
        return lambda **kwargs: lambda func: func

    def log_context_analysis(
        self, 
        trace_id: Optional[str],
        thread_context: ThreadContext,
        analysis_time: float
    ) -> None:
        """Log context analysis operation.
        
        Args:
            trace_id: Trace ID from create_trace
            thread_context: Analyzed thread context
            analysis_time: Time taken for analysis in seconds
        """
        if not self._enabled or not self._langfuse or not trace_id:
            return

        try:
            with self._langfuse.start_as_current_span(
                name="context_analysis",
                metadata={
                    "message_count": len(thread_context.messages),
                    "token_count": thread_context.token_count,
                    "analysis_time_seconds": analysis_time,
                    "channel_id": thread_context.channel_id,
                    "thread_ts": thread_context.thread_ts,
                }
            ):
                pass  # Span will be automatically closed
        except Exception as e:
            logger.error(f"Failed to log context analysis: {e}")

    def log_ai_generation(
        self,
        trace_id: Optional[str],
        ai_response: AIResponse,
        user_message: Optional[str],
        system_prompt: Optional[str],
        model_type: str = "azure_openai"
    ) -> None:
        """Log AI response generation.
        
        Args:
            trace_id: Trace ID from create_trace
            ai_response: Generated AI response
            user_message: User's input message
            system_prompt: System prompt used
            model_type: Type of model used (azure_openai, llama_agent)
        """
        if not self._enabled or not self._langfuse or not trace_id:
            return

        try:
            with self._langfuse.start_as_current_generation(
                name="ai_response_generation",
                model=model_type,
                input={
                    "user_message": user_message,
                    "system_prompt": system_prompt,
                },
                metadata={
                    "generation_time_seconds": ai_response.generation_time,
                    "model_type": model_type,
                    "created_at": ai_response.created_at.isoformat(),
                }
            ) as generation:
                generation.update(
                    output=ai_response.content,
                    usage={
                        "promptTokens": ai_response.context_tokens,
                        "completionTokens": ai_response.completion_tokens,
                        "totalTokens": ai_response.tokens_used,
                    }
                )
        except Exception as e:
            logger.error(f"Failed to log AI generation: {e}")

    def log_error(
        self,
        trace_id: Optional[str],
        error: Exception,
        operation: str,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log error in AI operations.
        
        Args:
            trace_id: Trace ID from create_trace
            error: Exception that occurred
            operation: Operation where error occurred
            context: Additional context about the error
        """
        if not self._enabled or not self._langfuse or not trace_id:
            return

        try:
            with self._langfuse.start_as_current_span(
                name=f"error_{operation}",
                level="ERROR",
                metadata={
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "operation": operation,
                    "context": context or {},
                    "timestamp": datetime.now().isoformat(),
                }
            ):
                pass  # Span will be automatically closed
        except Exception as e:
            logger.error(f"Failed to log error: {e}")

    def update_trace(
        self,
        trace_id: Optional[str],
        session: RequestSession,
        final_status: str = "completed"
    ) -> None:
        """Update trace with final session information.
        
        Args:
            trace_id: Trace ID from create_trace
            session: Completed request session
            final_status: Final status of the operation
        """
        if not self._enabled or not self._langfuse or not trace_id:
            return

        try:
            total_time = time.time() - session.started_at.timestamp()
            
            self._langfuse.update_current_trace(
                output={
                    "status": final_status,
                    "total_time_seconds": total_time,
                    "session_status": session.status.value,
                },
                metadata={
                    "completed_at": datetime.now().isoformat(),
                    "total_processing_time": total_time,
                    "final_status": final_status,
                    "error_message": getattr(session, 'error_message', None),
                }
            )
        except Exception as e:
            logger.error(f"Failed to update trace: {e}")

    def create_feedback(
        self,
        trace_id: Optional[str],
        score: float,
        comment: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        """Create feedback for a trace.
        
        Args:
            trace_id: Trace ID to provide feedback for
            score: Feedback score (0.0 to 1.0)
            comment: Optional feedback comment
            user_id: User providing the feedback
        """
        if not self._enabled or not self._langfuse or not trace_id:
            return

        try:
            self._langfuse.create_score(
                name="user_feedback",
                value=score,
                comment=comment,
            )
        except Exception as e:
            logger.error(f"Failed to create feedback: {e}")

    def flush(self) -> None:
        """Flush pending Langfuse data."""
        if self._enabled and self._langfuse:
            try:
                self._langfuse.flush()
            except Exception as e:
                logger.error(f"Failed to flush Langfuse data: {e}")


# Global monitor instance
_monitor = LangfuseMonitor()


def get_langfuse_monitor() -> LangfuseMonitor:
    """Get the global Langfuse monitor instance."""
    return _monitor


def monitor_ai_operation(operation_name: str):
    """Decorator for monitoring AI operations with Langfuse.
    
    Args:
        operation_name: Name of the operation being monitored
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            monitor = get_langfuse_monitor()
            if not monitor.enabled:
                return await func(*args, **kwargs)

            # Extract session if available
            session = None
            for arg in list(args) + list(kwargs.values()):
                if isinstance(arg, RequestSession):
                    session = arg
                    break

            trace_id = None
            if session:
                trace_id = monitor.create_trace(session, operation_name)

            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                
                # Update trace with success
                if session and trace_id:
                    monitor.update_trace(trace_id, session, "completed")
                
                return result
            except Exception as e:
                # Log error
                if trace_id:
                    monitor.log_error(trace_id, e, operation_name)
                
                # Update trace with error
                if session and trace_id:
                    monitor.update_trace(trace_id, session, "error")
                
                raise
            finally:
                monitor.flush()

        return wrapper
    return decorator


@asynccontextmanager
async def langfuse_trace_context(session: RequestSession, operation: str):
    """Async context manager for Langfuse tracing.
    
    Args:
        session: Request session
        operation: Operation name
        
    Yields:
        Trace ID for logging operations
    """
    monitor = get_langfuse_monitor()
    trace_id = None
    
    if monitor.enabled:
        trace_id = monitor.create_trace(session, operation)
    
    try:
        yield trace_id
    finally:
        if monitor.enabled and trace_id and session:
            monitor.update_trace(trace_id, session)
            monitor.flush()