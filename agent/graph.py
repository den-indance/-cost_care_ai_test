import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from agent.nodes import (
    booking_node,
    confirmation_node,
    parse_user_info_node,
    qualification_node,
    rag_qa_node,
    router_node,
    slot_proposal_node,
)
from agent.state import AgentState

logger = logging.getLogger(__name__)


def _check_parse_needed_node(state: AgentState) -> AgentState:
    """
    Decide whether to parse user info or just ask questions.
    This prevents parsing when we just asked a question (AI's last message was a question).
    Also skips parsing when slots have been proposed and user is selecting a slot.
    """
    logger.info("🔍 Check parse needed node")

    # KEY FIX: If ready_to_book, go straight to booking
    if state.get("ready_to_book") and state.get("selected_slot"):
        logger.info("ℹ️  Ready to book, awaiting confirmation → skip parse")
        state["skip_parse"] = True
        return state

    # KEY FIX: If slots were proposed and user is responding, go straight to confirmation
    if state.get("available_slots") and not state.get("selected_slot"):
        # Slots are shown, waiting for user selection
        # CRITICAL FIX: Check only USER messages, not AI messages
        # This prevents triggering on the AI's own slot proposal message
        if state["messages"]:
            from langchain_core.messages import HumanMessage

            user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]
            if user_messages:
                import re

                last_user_message = user_messages[-1].content.lower()
                # Check if user's message contains a number (likely slot selection)
                if re.search(r"\b\d+\b", last_user_message):
                    logger.info("ℹ️  Slots proposed, user likely selecting → skip parse, go to confirmation")
                    state["stage"] = "confirmation"
                    state["skip_parse"] = True
                    return state

    # Check if the last message was from AI
    if state["messages"]:
        last_message = state["messages"][-1]
        from langchain_core.messages import AIMessage

        if isinstance(last_message, AIMessage):
            state["skip_parse"] = True
            logger.info("ℹ️  Last message was AI question → skip parsing")
        else:
            state["skip_parse"] = False
    else:
        state["skip_parse"] = False

    return state


def route_after_router(
    state: AgentState,
) -> Literal["rag_qa", "check_parse_needed", "slot_proposal", "confirmation", "booking"]:
    """
    Route based on intent detection from router_node.
    Also handles continuing flows based on current stage.
    """
    stage = state.get("stage", "")

    if stage == "rag_qa":
        return "rag_qa"
    elif stage == "qualification":
        return "check_parse_needed"
    elif stage == "confirmation":
        return "confirmation"
    elif stage == "slot_proposal":
        return "slot_proposal"
    elif stage == "booking":
        return "booking"
    else:
        # Default to RAG for safety
        return "rag_qa"


def route_after_check_parse(state: AgentState) -> Literal["parse_info", "qualification", "confirmation", "booking"]:
    """
    Decide whether to parse user info or go directly to qualification/confirmation/booking.
    """
    # Check if user confirmed booking (ready_to_book is set)
    if state.get("ready_to_book") and state.get("selected_slot"):
        logger.info("→ Going to booking (user confirmed)")
        return "booking"
    elif state.get("stage") == "confirmation":
        # User is selecting a slot
        logger.info("→ Going to confirmation (user selecting slot)")
        return "confirmation"
    elif state.get("skip_parse", False):
        logger.info("→ Skipping parse, going to qualification")
        return "qualification"
    else:
        logger.info("→ Parsing user info")
        return "parse_info"


def route_after_parse(state: AgentState) -> Literal["slot_proposal", "__end__"]:
    """
    After parsing, decide next step.
    KEY FIX: Return to END when info is missing, allowing main.py to get new user input.
    """
    has_name = bool(state.get("user_name"))
    has_email = bool(state.get("user_email"))
    has_date = bool(state.get("preferred_date"))

    if has_name and has_email and has_date:
        logger.info("✅ All info collected → slot_proposal")
        return "slot_proposal"
    else:
        missing = []
        if not has_name:
            missing.append("name")
        if not has_email:
            missing.append("email")
        if not has_date:
            missing.append("date")

        logger.info(f"ℹ️  Missing: {', '.join(missing)} → END (waiting for user input)")
        # KEY FIX: Return to END instead of looping back to qualification
        return "__end__"


def route_after_qualification(state: AgentState) -> Literal["__end__"]:
    """
    After asking for info, always return to END.
    KEY FIX: This allows main.py to wait for the next user input.
    """
    logger.info("ℹ️  Qualification complete → END (waiting for user)")
    return "__end__"


def route_after_slots(state: AgentState) -> Literal["confirmation", "qualification", "__end__"]:
    """
    After proposing slots, wait for user to choose.
    """
    if state.get("stage") == "confirmation":
        return "confirmation"
    elif state.get("stage") == "qualification":
        return "qualification"
    else:
        # Wait for user to respond
        logger.info("ℹ️  Slots proposed → END (waiting for user selection)")
        return "__end__"


def route_after_confirmation(state: AgentState) -> Literal["booking", "slot_proposal", "confirmation", "__end__"]:
    """
    Check if user confirmed booking or wants to change.
    """
    stage = state.get("stage", "")

    # CRITICAL FIX: Check if the last message is from a human
    # If not, no new user input - return to END to wait for input instead of looping
    if state.get("messages"):
        from langchain_core.messages import HumanMessage

        user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]
        if not user_messages:
            # No user messages at all, wait for input
            logger.info("ℹ️  No user messages → END (waiting for user)")
            return "__end__"
        last_message = state["messages"][-1]
        if not isinstance(last_message, HumanMessage):
            # Last message was from AI, no new user input - wait
            logger.info("ℹ️  Last message was AI → END (waiting for user input)")
            return "__end__"

    if stage == "booking":
        return "booking"
    elif stage == "slot_proposal":
        return "slot_proposal"
    elif stage == "confirmation":
        # Still waiting for confirmation - but only if we got new user input
        # (which we checked above)
        return "confirmation"
    else:
        # Wait for user to respond
        logger.info("ℹ️  Confirmation pending → END (waiting for user)")
        return "__end__"


def route_after_booking(state: AgentState) -> Literal["__end__", "slot_proposal"]:
    """
    Check if booking succeeded or failed.
    """
    if state.get("stage") == "done":
        logger.info("✅ Booking complete → END")
        return "__end__"
    else:
        # Failed, try different slot
        logger.info("❌ Booking failed → slot_proposal")
        return "slot_proposal"


def create_agent_graph():
    """
    Create LangGraph workflow for the booking agent

    NEW DESIGN: Each invoke() processes ONE user message and returns.
    - Router always runs first to determine intent
    - After each response, return to main.py
    - State is preserved between invocations
    - NO internal loops - all multi-turn handling happens at main.py level

    Flow:
    1. User input → Router → (RAG or Booking)
    2. RAG: rag_qa → END
    3. Booking:
       - check_parse_needed → (parse_info or qualification)
       - parse_info → (slot_proposal or END)
       - qualification → END (ask for info)
       - slot_proposal → (confirmation or END)
       - confirmation → (booking or slot_proposal or END)
       - booking → (END or slot_proposal)
    """

    workflow = StateGraph(AgentState)

    # Add all nodes
    workflow.add_node("router", router_node)
    workflow.add_node("rag_qa", rag_qa_node)
    workflow.add_node("check_parse_needed", _check_parse_needed_node)
    workflow.add_node("parse_info", parse_user_info_node)
    workflow.add_node("qualification", qualification_node)
    workflow.add_node("slot_proposal", slot_proposal_node)
    workflow.add_node("confirmation", confirmation_node)
    workflow.add_node("booking", booking_node)

    # Set entry point
    workflow.set_entry_point("router")

    # === Router edges ===
    workflow.add_conditional_edges(
        "router",
        route_after_router,
        {
            "rag_qa": "rag_qa",
            "check_parse_needed": "check_parse_needed",
            "slot_proposal": "slot_proposal",
            "confirmation": "confirmation",
            "booking": "booking",
        },
    )

    # === RAG path ===
    workflow.add_edge("rag_qa", END)

    # === Check parse needed → (parse_info or qualification or confirmation or booking) ===
    workflow.add_conditional_edges(
        "check_parse_needed",
        route_after_check_parse,
        {
            "parse_info": "parse_info",
            "qualification": "qualification",
            "confirmation": "confirmation",
            "booking": "booking",
        },
    )

    # === Parse info → (slot_proposal or END) ===
    workflow.add_conditional_edges("parse_info", route_after_parse, {"slot_proposal": "slot_proposal", "__end__": END})

    # === Qualification → END ===
    workflow.add_edge("qualification", END)

    # === Slot proposal → (confirmation or qualification or END) ===
    workflow.add_conditional_edges(
        "slot_proposal",
        route_after_slots,
        {"confirmation": "confirmation", "qualification": "qualification", "__end__": END},
    )

    # === Confirmation → (booking or slot_proposal or confirmation or END) ===
    workflow.add_conditional_edges(
        "confirmation",
        route_after_confirmation,
        {"booking": "booking", "slot_proposal": "slot_proposal", "confirmation": "confirmation", "__end__": END},
    )

    # === Booking → (END or slot_proposal) ===
    workflow.add_conditional_edges("booking", route_after_booking, {"__end__": END, "slot_proposal": "slot_proposal"})

    # Compile the graph
    app = workflow.compile()

    logger.info("✅ Agent graph compiled successfully")

    return app
