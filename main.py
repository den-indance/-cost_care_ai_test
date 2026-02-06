# main.py

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

from agent.graph import create_agent_graph
from agent.state import create_initial_state
from agent.state_manager import (
    create_backup_state,
    is_recoverable_error,
    log_state_summary,
    restore_from_backup,
    sanitize_state,
    suggest_recovery_strategy,
    validate_state,
)

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Suppress verbose logging from some libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING)


def print_banner():
    """Print welcome banner"""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║        🤖  CostCare AI Booking Agent                      ║
║                                                           ║
║        Powered by Google Gemini + LangGraph              ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

I can help you with:
  📚 Questions about CostCare AI (features, pricing, etc.)
  📅 Booking meetings with our team

Type 'exit', 'quit', or 'bye' to end the conversation.
"""
    print(banner)


def print_separator():
    """Print separator line"""
    print("\n" + "─" * 60 + "\n")


def validate_environment():
    """Check that all required environment variables and files exist"""
    errors = []

    # Check API key
    if not os.getenv("GOOGLE_API_KEY"):
        errors.append("❌ GOOGLE_API_KEY not found in .env file")

    # Check credentials
    if not Path("config/google_creds.json").exists():
        errors.append("❌ config/google_creds.json not found")

    # Check knowledge base
    if not Path("data/knowledge_base").exists():
        errors.append("❌ knowledge_base/ directory not found")
    elif not list(Path("data/knowledge_base").glob("*.md")):
        errors.append("❌ No .md files found in knowledge_base/")

    # Check prompts
    if not Path("prompts").exists():
        errors.append("❌ prompts/ directory not found")
    else:
        required_prompts = ["system_prompt.md", "rag_prompt.md", "booking_prompt.md"]
        for prompt in required_prompts:
            if not Path(f"prompts/{prompt}").exists():
                errors.append(f"❌ prompts/{prompt} not found")

    if errors:
        print("\n⚠️  Environment validation failed:\n")
        for error in errors:
            print(f"  {error}")
        print("\nPlease fix these issues before running the agent.\n")
        return False

    logger.info("✅ Environment validation passed")
    return True


def reset_booking_state(state: dict) -> dict:
    """Reset booking-related fields while preserving conversation context"""
    state["user_name"] = None
    state["user_email"] = None
    state["preferred_date"] = None
    state["selected_slot"] = None
    state["available_slots"] = []
    state["ready_to_book"] = False
    state["skip_parse"] = False
    return state


def main():
    """
    Main CLI loop

    NEW DESIGN: Each user input triggers ONE agent.invoke() call.
    The graph processes the input and returns, allowing main.py to wait for
    the next user input. State is preserved between calls.
    """
    # Validate environment
    if not validate_environment():
        return

    print_banner()

    try:
        # Create agent graph
        logger.info("Creating agent graph...")
        agent = create_agent_graph()
        logger.info("✅ Agent initialized")

    except Exception as e:
        print(f"\n❌ Error initializing agent: {e}")
        logger.error(f"Initialization error: {e}", exc_info=True)
        return

    # Initialize conversation state
    state = create_initial_state()

    print("\nAgent: Hello! I'm your CostCare AI assistant. How can I help you today?\n")

    # Track conversation for proper message display
    last_message_count = 0

    # Main conversation loop
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            # Check for exit commands
            if user_input.lower() in ["exit", "quit", "bye", "goodbye"]:
                print("\nAgent: Thank you for chatting! Have a great day! 👋\n")
                break

            # Skip empty input
            if not user_input:
                continue

            # Add user message to state
            state["messages"].append(HumanMessage(content=user_input))

            logger.info(f"User input: {user_input[:50]}...")

            # Run agent
            try:
                result = agent.invoke(state)
                state = result

                # Get new messages (only print AI messages that were added)
                new_messages = state["messages"][last_message_count:]

                for message in new_messages:
                    if isinstance(message, AIMessage):
                        print(f"\nAgent: {message.content}\n")

                last_message_count = len(state["messages"])

                # Check if booking was completed successfully
                if state.get("stage") == "done" and state.get("ready_to_book"):
                    print_separator()
                    print("💡 You can ask me another question or book another meeting!")
                    print_separator()

                    # Reset booking state for next interaction
                    state = reset_booking_state(state)
                    state["stage"] = "greeting"

            except Exception as e:
                logger.error(f"Error during agent execution: {e}", exc_info=True)
                logger.error(f"\n❌ I encountered an error: {str(e)}")
                logger.error("Let's try again. What would you like to know?\n")

                # Reset to safe state
                state = create_initial_state()
                last_message_count = 0

        except KeyboardInterrupt:
            logger.info("\n\nAgent: Goodbye! 👋\n")
            break

        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            print(f"\n❌ Unexpected error: {str(e)}")
            print("Please try again.\n")

            # Reset state
            state = create_initial_state()
            last_message_count = 0


if __name__ == "__main__":
    main()
