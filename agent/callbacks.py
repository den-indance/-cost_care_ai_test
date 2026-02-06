# agent/callbacks.py

"""
Custom Callback Handlers for LangChain/LangGraph Logging

Provides detailed logging for LLM calls, chain execution, and tool usage.
Integrates with LangSmith for observability.
"""

import logging
from typing import Any, Dict, Sequence

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

logger = logging.getLogger("langchain.callbacks")


class DetailedLoggingCallback(BaseCallbackHandler):
    """
    Custom callback handler for detailed logging of LangChain operations.

    Logs:
    - LLM calls with prompts and responses
    - Chain execution start/end
    - Tool calls and results
    - Errors with context

    Usage:
        callback = DetailedLoggingCallback(log_level=logging.INFO)
        llm = ChatGoogleGenerativeAI(callbacks=[callback])
    """

    def __init__(self, log_level: int = logging.INFO):
        """Initialize the callback handler with a specified log level."""
        super().__init__()
        self.log_level = log_level
        self.logger = logging.getLogger("langchain.callbacks")

    def on_llm_start(self, serialized: Dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        """Log when LLM starts processing."""
        prompt_preview = prompts[0][:300] if prompts else "empty"
        self.logger.log(self.log_level, f"🤖 LLM Start - Model: {serialized.get('name', 'unknown')}")
        self.logger.debug(f"   Prompt preview: {prompt_preview}...")

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Log when LLM finishes processing."""
        for generations in response.generations:
            for generation in generations:
                response_preview = generation.text[:300] if hasattr(generation, "text") else "no text"
                token_info = ""
                if hasattr(generation, "generation_info") and generation.generation_info:
                    token_info = f" | Tokens: {generation.generation_info.get('token_usage', 'N/A')}"

                self.logger.log(self.log_level, f"✅ LLM End - Response: {response_preview}...{token_info}")

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """Log each new token (for streaming)."""
        self.logger.debug(f"   Token: {token}")

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """Log LLM errors."""
        self.logger.error(f"❌ LLM Error: {type(error).__name__}: {str(error)}")

    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any) -> None:
        """Log when chain starts."""
        chain_name = serialized.get(
            "name", serialized.get("id", ["unknown"])[-1] if isinstance(serialized.get("id"), list) else "unknown"
        )
        self.logger.log(self.log_level, f"🔗 Chain Start: {chain_name}")
        self.logger.debug(f"   Inputs: {str(inputs)[:200]}...")

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Log when chain ends."""
        output_preview = str(outputs)[:200] if outputs else "empty"
        self.logger.log(self.log_level, "✅ Chain End")
        self.logger.debug(f"   Outputs: {output_preview}...")

    def on_chain_error(self, error: Exception, **kwargs: Any) -> None:
        """Log chain errors."""
        self.logger.error(f"❌ Chain Error: {type(error).__name__}: {str(error)}")

    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> None:
        """Log when tool starts."""
        tool_name = serialized.get("name", "unknown")
        input_preview = input_str[:200] if input_str else "empty"
        self.logger.log(self.log_level, f"🔧 Tool Start: {tool_name}")
        self.logger.debug(f"   Input: {input_preview}...")

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Log when tool ends."""
        output_preview = output[:200] if output else "empty"
        self.logger.log(self.log_level, "✅ Tool End")
        self.logger.debug(f"   Output: {output_preview}...")

    def on_tool_error(self, error: Exception, **kwargs: Any) -> None:
        """Log tool errors."""
        self.logger.error(f"❌ Tool Error: {type(error).__name__}: {str(error)}")

    def on_chat_model_start(
        self, serialized: Dict[str, Any], messages: Sequence[Sequence[BaseMessage]], **kwargs: Any
    ) -> None:
        """Log when chat model starts processing."""
        model_name = serialized.get("name", "unknown")
        self.logger.log(self.log_level, f"💬 Chat Model Start: {model_name}")
        for i, msg_sequence in enumerate(messages):
            for msg in msg_sequence:
                self.logger.debug(f"   Message {i}: [{type(msg).__name__}] {msg.content[:150]}...")


class LangSmithCallback(BaseCallbackHandler):
    """
    LangSmith integration callback for production observability.

    Requires LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY set.
    """

    def __init__(self, project_name: str = "cost-care-ai-booking"):
        """Initialize LangSmith callback."""
        super().__init__()
        self.project_name = project_name
        self.logger = logging.getLogger("langchain.langsmith")

    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any) -> None:
        """Log chain start with project context."""
        self.logger.debug(f"[{self.project_name}] Chain started")

    def on_llm_start(self, serialized: Dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        """Log LLM start for LangSmith tracing."""
        self.logger.debug(f"[{self.project_name}] LLM call initiated")


def get_logging_callbacks(log_level: int = logging.INFO, enable_langsmith: bool = True):
    """
    Factory function to get configured callbacks.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        enable_langsmith: Whether to enable LangSmith tracing callback

    Returns:
        list: List of configured callback handlers
    """
    callbacks = []

    # Add detailed logging callback
    callbacks.append(DetailedLoggingCallback(log_level=log_level))

    # Add LangSmith callback if enabled (requires env vars set)
    if enable_langsmith:
        try:
            import os

            if os.getenv("LANGCHAIN_TRACING_V2") == "true":
                callbacks.append(LangSmithCallback())
                logger.info("✅ LangSmith tracing enabled")
        except Exception as e:
            logger.warning(f"⚠️  Could not enable LangSmith: {e}")

    return callbacks
