# agent/state_manager.py

"""
State Management Utilities for CostCare AI Agent

Provides state backup, restoration, validation, and recovery capabilities
to prevent loss of conversation history during error scenarios.
"""

import copy
import logging
from datetime import datetime
from typing import Any, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from agent.state import AgentState, create_initial_state

logger = logging.getLogger(__name__)


# ============================================================================
# STATE BACKUP & RESTORATION
# ============================================================================


def create_backup_state(state: AgentState) -> dict:
    """
    Create a deep copy of the current agent state for backup purposes.

    This function creates a complete snapshot of the state that can be restored
    later in case of errors. The backup includes all messages, booking data,
    and workflow state.

    Args:
        state: Current AgentState to backup

    Returns:
        dict: Deep copy of state as a dictionary with metadata

    Example:
        >>> state = create_initial_state()
        >>> state["messages"].append(HumanMessage(content="Hello"))
        >>> backup = create_backup_state(state)
        >>> # Later, if error occurs...
        >>> state = restore_from_backup(state, backup)
    """
    logger.info("📦 Creating state backup...")

    try:
        # Create a deep copy to ensure complete isolation
        backup = {
            "timestamp": datetime.now().isoformat(),
            "message_count": len(state.get("messages", [])),
            "stage": state.get("stage"),
            "data": copy.deepcopy(dict(state)),  # Convert TypedDict to dict for deep copy
        }

        # Ensure messages are properly copied (they contain message objects)
        if "messages" in backup["data"]:
            backup["data"]["messages"] = list(backup["data"]["messages"])

        logger.info(
            f"✅ State backup created: {backup['message_count']} messages, "
            f"stage={backup['stage']}, timestamp={backup['timestamp']}"
        )

        return backup

    except Exception as e:
        logger.error(f"❌ Error creating state backup: {e}", exc_info=True)
        # Return minimal backup to avoid total loss
        return {
            "timestamp": datetime.now().isoformat(),
            "message_count": 0,
            "stage": "greeting",
            "data": {},
            "backup_error": str(e),
        }


def restore_from_backup(state: AgentState, backup: dict, strategy: str = "preserve_messages") -> AgentState:
    """
    Restore state from a previously created backup.

    Supports multiple restoration strategies:
    - "preserve_messages": Keep current messages, restore booking data from backup
    - "full_restore": Complete restoration from backup (loses current messages)
    - "merge": Merge current state with backup (current messages take precedence)

    Args:
        state: Current (possibly corrupted) state
        backup: Backup dictionary from create_backup_state()
        strategy: Restoration strategy ("preserve_messages", "full_restore", "merge")

    Returns:
        AgentState: Restored state

    Example:
        >>> state = create_initial_state()  # After error
        >>> state = restore_from_backup(state, backup, strategy="preserve_messages")
    """
    logger.info(f"🔄 Restoring state from backup (strategy={strategy})...")

    try:
        backup_data = backup.get("data", {})
        backup_timestamp = backup.get("timestamp", "unknown")
        backup_message_count = backup.get("message_count", 0)

        if not backup_data:
            logger.warning("⚠️  Backup data is empty, returning current state")
            return state

        if strategy == "full_restore":
            # Complete restoration - replaces current state entirely
            logger.info(f"🔄 Full restore: replacing current state with backup from {backup_timestamp}")
            for key, value in backup_data.items():
                state[key] = copy.deepcopy(value)

        elif strategy == "preserve_messages":
            # Keep current messages if they exist, restore other fields from backup
            current_messages = state.get("messages", [])

            if current_messages:
                logger.info(
                    f"📬 Preserving {len(current_messages)} current messages, " f"restoring booking data from backup"
                )
                # Restore everything except messages
                for key, value in backup_data.items():
                    if key != "messages":
                        state[key] = copy.deepcopy(value)
                # Keep current messages
                state["messages"] = current_messages
            else:
                # No current messages, do full restore
                logger.info("📭 No current messages, performing full restore from backup")
                for key, value in backup_data.items():
                    state[key] = copy.deepcopy(value)

        elif strategy == "merge":
            # Merge strategy: current state takes precedence, fill gaps from backup
            logger.info("🔀 Merging current state with backup")

            # Always restore messages from backup if current is empty
            if not state.get("messages") and backup_data.get("messages"):
                state["messages"] = copy.deepcopy(backup_data["messages"])

            # Fill missing booking fields from backup
            booking_fields = ["user_name", "user_email", "preferred_date", "selected_slot", "available_slots"]
            for field in booking_fields:
                if not state.get(field) and backup_data.get(field):
                    state[field] = copy.deepcopy(backup_data[field])
                    logger.info(f"  ✓ Restored {field} from backup")

        else:
            logger.warning(f"⚠️  Unknown strategy '{strategy}', defaulting to preserve_messages")
            return restore_from_backup(state, backup, strategy="preserve_messages")

        logger.info(f"✅ State restored: {len(state.get('messages', []))} messages, stage={state.get('stage')}")

        return state

    except Exception as e:
        logger.error(f"❌ Error restoring from backup: {e}", exc_info=True)
        # If restore fails, try to preserve at least the messages
        if "messages" in state and state["messages"]:
            logger.warning("⚠️  Restore failed, preserving current messages")
            return state
        # Last resort: return current state as-is
        return state


def reset_booking_fields_only(state: AgentState) -> AgentState:
    """
    Reset only booking-related fields while preserving conversation history.

    This function is designed for post-booking cleanup, allowing the user
    to continue the conversation or book another meeting without losing
    the chat history.

    Preserved:
    - All messages (conversation history)
    - RAG context

    Reset:
    - User booking information (name, email, preferred date)
    - Selected slot and available slots
    - Workflow flags

    Args:
        state: Current AgentState

    Returns:
        AgentState: State with booking fields reset, messages preserved

    Example:
        >>> state = reset_booking_fields_only(state)
        >>> # Messages preserved, booking fields cleared
    """
    logger.info("🔄 Resetting booking fields (preserving conversation history)...")

    fields_to_reset = [
        "user_name",
        "user_email",
        "preferred_date",
        "selected_slot",
        "available_slots",
        "ready_to_book",
        "skip_parse",
        "error_message",
    ]

    for field in fields_to_reset:
        if field in state:
            old_value = state[field]
            state[field] = None if field not in ["available_slots"] else []
            logger.debug(f"  Reset {field}: {old_value} → {state[field]}")

    # Reset stage to greeting for new conversation
    state["stage"] = "greeting"

    message_count = len(state.get("messages", []))
    logger.info(f"✅ Booking fields reset, {message_count} messages preserved")

    return state


# ============================================================================
# STATE VALIDATION
# ============================================================================


def validate_state(state: AgentState) -> tuple[bool, list[str]]:
    """
    Validate state integrity and detect corruption issues.

    Checks for:
    - Valid message objects in messages list
    - Required fields presence
    - Valid stage values
    - No circular references
    - Data type consistency

    Args:
        state: AgentState to validate

    Returns:
        tuple[bool, list[str]]: (is_valid, list_of_errors)

    Example:
        >>> is_valid, errors = validate_state(state)
        >>> if not is_valid:
        ...     for error in errors:
        ...         logger.error(f"Validation error: {error}")
    """
    logger.debug("🔍 Validating state integrity...")

    errors = []

    # Check 1: Messages field exists and is a list
    if "messages" not in state:
        errors.append("Missing 'messages' field")
    elif not isinstance(state["messages"], list):
        errors.append(f"'messages' field is not a list: {type(state['messages'])}")
    else:
        # Check 2: Validate each message object
        for i, msg in enumerate(state["messages"]):
            if not isinstance(msg, BaseMessage):
                errors.append(f"Message {i} is not a BaseMessage: {type(msg)}")
            elif not hasattr(msg, "content"):
                errors.append(f"Message {i} missing 'content' attribute")
            elif not isinstance(msg.content, str):
                errors.append(f"Message {i} content is not a string: {type(msg.content)}")

    # Check 3: Required fields exist
    required_fields = ["stage", "messages", "needs_rag", "ready_to_book"]
    for field in required_fields:
        if field not in state:
            errors.append(f"Missing required field: {field}")

    # Check 4: Valid stage value
    valid_stages = ["greeting", "rag_qa", "qualification", "slot_proposal", "confirmation", "booking", "done"]
    if "stage" in state and state["stage"] not in valid_stages:
        errors.append(f"Invalid stage value: {state.get('stage')}")

    # Check 5: Data type consistency for key fields
    type_checks = [
        ("stage", str),
        ("needs_rag", bool),
        ("ready_to_book", bool),
        ("skip_parse", (bool, type(None))),
        ("rag_context", str),
    ]

    for field, expected_type in type_checks:
        if field in state and state[field] is not None:
            if not isinstance(state[field], expected_type):
                errors.append(f"Field '{field}' has wrong type: " f"expected {expected_type}, got {type(state[field])}")

    # Check 6: Booking data consistency
    if state.get("ready_to_book"):
        # If ready to book, we should have booking data
        if not state.get("user_name"):
            errors.append("ready_to_book=True but user_name is missing")
        if not state.get("user_email"):
            errors.append("ready_to_book=True but user_email is missing")
        if not state.get("selected_slot"):
            errors.append("ready_to_book=True but selected_slot is missing")

    # Check 7: Available slots consistency
    if "available_slots" in state and state["available_slots"]:
        if not isinstance(state["available_slots"], list):
            errors.append(f"available_slots is not a list: {type(state['available_slots'])}")
        else:
            for i, slot in enumerate(state["available_slots"]):
                if not isinstance(slot, dict):
                    errors.append(f"Slot {i} is not a dict: {type(slot)}")
                elif "index" not in slot or "start" not in slot or "end" not in slot:
                    errors.append(f"Slot {i} missing required fields (index, start, end)")

    is_valid = len(errors) == 0

    if is_valid:
        logger.debug("✅ State validation passed")
    else:
        logger.warning(f"⚠️  State validation failed with {len(errors)} errors:")
        for error in errors:
            logger.warning(f"  - {error}")

    return is_valid, errors


def sanitize_state(state: AgentState) -> AgentState:
    """
    Sanitize state by fixing common issues and removing invalid data.

    This function attempts to repair corrupted state by:
    - Removing invalid message objects
    - Fixing type mismatches
    - Setting safe defaults for missing fields
    - Cleaning inconsistent booking data

    Args:
        state: Potentially corrupted AgentState

    Returns:
        AgentState: Sanitized state

    Example:
        >>> state = sanitize_state(corrupted_state)
    """
    logger.info("🧹 Sanitizing state...")

    # Get a clean initial state as fallback for missing fields
    clean_state = create_initial_state()

    # Fix 1: Ensure messages is a valid list
    if "messages" not in state or not isinstance(state.get("messages"), list):
        logger.warning("⚠️  messages field invalid, resetting to empty list")
        state["messages"] = []
    else:
        # Remove invalid message objects
        valid_messages = []
        removed_count = 0
        for msg in state["messages"]:
            if isinstance(msg, BaseMessage) and hasattr(msg, "content") and isinstance(msg.content, str):
                valid_messages.append(msg)
            else:
                removed_count += 1
                logger.warning(f"⚠️  Removed invalid message: {type(msg)}")

        state["messages"] = valid_messages
        if removed_count > 0:
            logger.info(f"🗑️  Removed {removed_count} invalid messages")

    # Fix 2: Ensure all required fields exist
    required_fields = [
        "stage",
        "messages",
        "user_name",
        "user_email",
        "preferred_date",
        "selected_slot",
        "available_slots",
        "rag_context",
        "needs_rag",
        "ready_to_book",
        "skip_parse",
        "error_message",
    ]

    for field in required_fields:
        if field not in state:
            logger.warning(f"⚠️  Missing field '{field}', setting default")
            state[field] = clean_state[field]

    # Fix 3: Validate stage value
    valid_stages = ["greeting", "rag_qa", "qualification", "slot_proposal", "confirmation", "booking", "done"]
    if state.get("stage") not in valid_stages:
        logger.warning(f"⚠️  Invalid stage '{state.get('stage')}', resetting to 'greeting'")
        state["stage"] = "greeting"

    # Fix 4: Sanitize available_slots
    if "available_slots" in state and state["available_slots"]:
        if not isinstance(state["available_slots"], list):
            logger.warning("⚠️  available_slots is not a list, resetting")
            state["available_slots"] = []
        else:
            valid_slots = []
            for slot in state["available_slots"]:
                if isinstance(slot, dict) and "index" in slot and "start" in slot and "end" in slot:
                    valid_slots.append(slot)
                else:
                    logger.warning(f"⚠️  Removed invalid slot: {slot}")
            state["available_slots"] = valid_slots

    # Fix 5: Fix inconsistent booking state
    if state.get("ready_to_book") and not state.get("selected_slot"):
        logger.warning("⚠️  Inconsistent state: ready_to_book but no selected_slot")
        state["ready_to_book"] = False

    logger.info("✅ State sanitization complete")

    return state


# ============================================================================
# STATE SNAPSHOT & DEBUGGING
# ============================================================================


def capture_state_snapshot(state: AgentState, include_messages: bool = True) -> dict:
    """
    Capture a lightweight snapshot of the current state for debugging.

    Unlike create_backup_state(), this creates a summarized view suitable
    for logging and debugging without storing full message content.

    Args:
        state: Current AgentState
        include_messages: Whether to include message summaries (not full content)

    Returns:
        dict: State snapshot for debugging
    """
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "stage": state.get("stage"),
        "message_count": len(state.get("messages", [])),
        "has_user_name": bool(state.get("user_name")),
        "has_user_email": bool(state.get("user_email")),
        "has_preferred_date": bool(state.get("preferred_date")),
        "has_selected_slot": bool(state.get("selected_slot")),
        "available_slots_count": len(state.get("available_slots", [])),
        "ready_to_book": state.get("ready_to_book", False),
        "needs_rag": state.get("needs_rag", False),
    }

    if include_messages and state.get("messages"):
        message_summary = []
        for i, msg in enumerate(state["messages"]):
            msg_type = "Human" if isinstance(msg, HumanMessage) else "AI" if isinstance(msg, AIMessage) else "Other"
            content_preview = msg.content[:50] if hasattr(msg, "content") else "[no content]"
            message_summary.append(
                {
                    "index": i,
                    "type": msg_type,
                    "preview": content_preview,
                }
            )
        snapshot["messages_summary"] = message_summary

    return snapshot


def log_state_summary(state: AgentState, level: str = "info") -> None:
    """
    Log a summary of the current state for debugging purposes.

    Args:
        state: Current AgentState
        level: Log level ("debug", "info", "warning")
    """
    log_func = getattr(logger, level, logger.info)

    log_func("📊 State Summary:")
    log_func(f"  Stage: {state.get('stage')}")
    log_func(f"  Messages: {len(state.get('messages', []))}")
    log_func(f"  User: {state.get('user_name') or '[not set]'}")
    log_func(f"  Email: {state.get('user_email') or '[not set]'}")
    log_func(f"  Preferred Date: {state.get('preferred_date') or '[not set]'}")
    log_func(f"  Selected Slot: {bool(state.get('selected_slot'))}")
    log_func(f"  Available Slots: {len(state.get('available_slots', []))}")
    log_func(f"  Ready to Book: {state.get('ready_to_book', False)}")
    log_func(f"  Needs RAG: {state.get('needs_rag', False)}")


# ============================================================================
# ERROR RECOVERY HELPERS
# ============================================================================


def is_recoverable_error(error: Exception) -> bool:
    """
    Determine if an error is recoverable without full state reset.

    Recoverable errors:
    - Network timeouts
    - API rate limits
    - Temporary service unavailability
    - Transient LLM errors

    Non-recoverable errors:
    - State corruption
    - Invalid data types
    - Memory errors

    Args:
        error: Exception to evaluate

    Returns:
        bool: True if error is recoverable
    """
    recoverable_patterns = [
        "timeout",
        "rate limit",
        "temporary",
        "unavailable",
        "connection",
        "network",
        "5xx",  # Server errors
    ]

    error_str = str(error).lower()

    for pattern in recoverable_patterns:
        if pattern in error_str:
            return True

    return False


def suggest_recovery_strategy(error: Exception, state: AgentState) -> str:
    """
    Suggest an appropriate recovery strategy based on error type and state.

    Args:
        error: Exception that occurred
        state: Current state at time of error

    Returns:
        str: Suggested strategy ("retry", "restore", "sanitize", "reset")
    """
    error_str = str(error).lower()

    # Check if state is corrupted
    is_valid, _ = validate_state(state)

    if not is_valid:
        return "sanitize"

    # Check if it's a transient error
    if is_recoverable_error(error):
        return "retry"

    # Check if we have meaningful conversation history
    if len(state.get("messages", [])) > 2:
        return "restore"

    # Default to reset
    return "reset"
