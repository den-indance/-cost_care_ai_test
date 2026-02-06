# agent/state.py

from typing import Literal, Optional

from langgraph.graph.message import MessagesState


class AgentState(MessagesState):
    """
    State for the AI booking agent

    Extends MessagesState to include conversation history plus custom fields
    for tracking booking workflow
    """

    # Current stage in the conversation flow
    stage: Literal[
        "greeting",  # Initial greeting
        "rag_qa",  # Answering questions using RAG
        "qualification",  # Collecting booking information
        "slot_proposal",  # Proposing available time slots
        "confirmation",  # Confirming slot selection
        "booking",  # Actually booking the meeting
        "done",  # Conversation completed
    ]

    # User information for booking
    user_name: Optional[str]
    user_email: Optional[str]
    preferred_date: Optional[str]  # Can be "tomorrow afternoon", "next week", etc.

    # Selected slot for booking
    selected_slot: Optional[dict]  # {index, start, end}

    # Available slots from calendar
    available_slots: list[dict]  # [{index, start, end}, ...]

    # RAG context
    rag_context: str

    # Workflow flags
    needs_rag: bool
    ready_to_book: bool
    skip_parse: bool  # Skip parsing when AI just asked a question

    # Error handling
    error_message: Optional[str]


# Default initial state
def create_initial_state() -> AgentState:
    """Create initial agent state with defaults"""
    return AgentState(
        messages=[],
        stage="greeting",
        user_name=None,
        user_email=None,
        preferred_date=None,
        selected_slot=None,
        available_slots=[],
        rag_context="",
        needs_rag=False,
        ready_to_book=False,
        skip_parse=False,
        error_message=None,
    )
