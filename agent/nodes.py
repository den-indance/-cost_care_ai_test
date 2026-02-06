# agent/nodes.py

import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from agent.callbacks import get_logging_callbacks
from agent.state import AgentState
from tools.calendar_service import BookingData, BookingSlot, GoogleCalendarService
from tools.rag_service import RAGService

logger = logging.getLogger(__name__)

# ============================================================================
# INITIALIZATION
# ============================================================================

# Initialize LLM (Gemini)
# Enable verbose logging and custom callbacks for observability
llm = ChatGoogleGenerativeAI(
    model="models/gemini-2.0-flash-lite",
    google_api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.3,
    convert_system_message_to_human=True,  # Gemini compatibility
    verbose=True,  # Enable verbose logging for LangChain/LangSmith integration
    callbacks=get_logging_callbacks(log_level=logging.INFO),  # Custom logging callbacks
)

# Initialize services
rag_service = RAGService(google_api_key=os.getenv("GOOGLE_API_KEY"))

calendar_service = GoogleCalendarService(
    credentials_file="config/google_creds.json", token_file="config/user_token.json", headless=True
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def load_prompt(filename: str) -> str:
    """Load prompt from file"""
    prompt_path = Path(f"prompts/{filename}")
    if not prompt_path.exists():
        logger.warning(f"Prompt file not found: {filename}")
        return ""
    return prompt_path.read_text()


def parse_relative_date(date_str: str) -> tuple[datetime, datetime]:
    """
    Parse relative date strings like 'tomorrow afternoon' or 'next week'
    into concrete datetime ranges

    Args:
        date_str: User's date preference (e.g., "tomorrow afternoon", "next week")

    Returns:
        Tuple of (start_datetime, end_datetime)
    """
    now = datetime.now()
    date_str_lower = date_str.lower()

    # Determine target date
    if "today" in date_str_lower:
        target_date = now
    elif "tomorrow" in date_str_lower:
        target_date = now + timedelta(days=1)
    elif "next week" in date_str_lower:
        target_date = now + timedelta(days=7)
    elif "monday" in date_str_lower:
        days_ahead = 0 - now.weekday()  # Monday is 0
        if days_ahead <= 0:
            days_ahead += 7
        target_date = now + timedelta(days=days_ahead)
    elif "tuesday" in date_str_lower:
        days_ahead = 1 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target_date = now + timedelta(days=days_ahead)
    elif "wednesday" in date_str_lower:
        days_ahead = 2 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target_date = now + timedelta(days=days_ahead)
    elif "thursday" in date_str_lower:
        days_ahead = 3 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target_date = now + timedelta(days=days_ahead)
    elif "friday" in date_str_lower:
        days_ahead = 4 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target_date = now + timedelta(days=days_ahead)
    else:
        # Default to tomorrow
        target_date = now + timedelta(days=1)

    # Determine time of day
    if "morning" in date_str_lower:
        start = target_date.replace(hour=9, minute=0, second=0, microsecond=0)
        end = target_date.replace(hour=12, minute=0, second=0, microsecond=0)
    elif "afternoon" in date_str_lower:
        start = target_date.replace(hour=14, minute=0, second=0, microsecond=0)
        end = target_date.replace(hour=17, minute=0, second=0, microsecond=0)
    elif "evening" in date_str_lower:
        start = target_date.replace(hour=17, minute=0, second=0, microsecond=0)
        end = target_date.replace(hour=20, minute=0, second=0, microsecond=0)
    else:
        # Full business day
        start = target_date.replace(hour=9, minute=0, second=0, microsecond=0)
        end = target_date.replace(hour=17, minute=0, second=0, microsecond=0)

    return start, end


# ============================================================================
# AGENT NODES
# ============================================================================


def router_node(state: AgentState) -> AgentState:
    """
    Route to appropriate node based on user input

    Analyzes the last user message and decides whether to:
    - Answer questions using RAG
    - Start/continue booking process
    """
    logger.info("🔀 Router node")

    if not state["messages"]:
        state["stage"] = "greeting"
        return state

    # KEY FIX: Check if we're in the middle of a booking process
    # If we have ANY booking info, continue the booking flow
    has_partial_booking = (
        state.get("user_name") or state.get("user_email") or state.get("preferred_date") or state.get("available_slots")
    )

    if has_partial_booking:
        logger.info("→ Continuing booking flow (partial booking detected)")
        state["stage"] = "qualification"
        return state

    last_message = state["messages"][-1].content.lower()

    # Check for booking intent
    booking_keywords = [
        # English keywords
        "book",
        "schedule",
        "meeting",
        "appointment",
        "call",
        "demo",
        "talk",
        "speak",
        "discuss",
        "reserve",
        "calendar",
        "arrange",
        # Russian keywords (Cyrillic)
        "забронируй",
        "забронировать",
        "бронируй",
        "бронировать",
        "встреча",
        "митинг",
        "созвон",
        "звонок",
        "назначить",
        "планировать",
        "запланировать",
        "договориться",
        "календарь",
        "расписание",
        "слот",
        "тайм",
        "слоты",
        "слота",
    ]

    if any(keyword in last_message for keyword in booking_keywords):
        logger.info("→ Routing to BOOKING flow")
        state["stage"] = "qualification"
        return state

    # Check for questions (default to RAG)
    question_indicators = [
        # English
        "what",
        "how",
        "when",
        "where",
        "who",
        "why",
        "?",
        "tell me",
        "explain",
        # Russian
        "что",
        "как",
        "когда",
        "где",
        "кто",
        "почему",
        "?",
        "расскажи",
        "объясни",
        "покажи",
    ]

    if any(indicator in last_message for indicator in question_indicators):
        logger.info("→ Routing to RAG Q&A")
        state["needs_rag"] = True
        state["stage"] = "rag_qa"
        return state

    # Default: treat as question
    logger.info("→ Routing to RAG Q&A (default)")
    state["stage"] = "rag_qa"
    return state


def rag_qa_node(state: AgentState) -> AgentState:
    """
    Answer user questions using RAG
    """
    logger.info("📚 RAG Q&A node")

    last_message = state["messages"][-1].content

    # Search knowledge base
    context = rag_service.search(last_message, k=3)
    state["rag_context"] = context

    # Load prompts
    system_prompt = load_prompt("system_prompt.md")
    rag_prompt = load_prompt("rag_prompt.md")

    # Construct prompt
    combined_prompt = f"""{system_prompt}

{rag_prompt}

Context from knowledge base:
---
{context}
---

User question: {last_message}

Provide a helpful, accurate answer based on the context above:"""

    try:
        # Get LLM response
        response = llm.invoke([HumanMessage(content=combined_prompt)])

        # Add to messages
        state["messages"].append(AIMessage(content=response.content))

        logger.info(f"✅ RAG response generated ({len(response.content)} chars)")

    except Exception as e:
        logger.error(f"❌ Error in RAG node: {e}")
        error_msg = (
            "I apologize, but I'm having trouble accessing the information right now. "
            "Would you like to book a meeting with our team instead?"
        )
        state["messages"].append(AIMessage(content=error_msg))

    state["stage"] = "done"
    return state


def qualification_node(state: AgentState) -> AgentState:
    """
    Collect user information for booking (name, email, preferred time)
    """
    logger.info("📋 Qualification node")

    # Check what information we already have
    missing_info = []

    if not state.get("user_name"):
        missing_info.append("name")
    if not state.get("user_email"):
        missing_info.append("email")
    if not state.get("preferred_date"):
        missing_info.append("preferred date/time")

    # If we have everything, move to slot proposal
    if not missing_info:
        logger.info("✅ All information collected")
        state["stage"] = "slot_proposal"
        return state

    # Otherwise, ask for missing information
    logger.info(f"ℹ️  Missing: {', '.join(missing_info)}")

    system_prompt = load_prompt("system_prompt.md")
    booking_prompt = load_prompt("booking_prompt.md")

    # Get conversation context (last few messages)
    recent_messages = state["messages"][-3:] if len(state["messages"]) >= 3 else state["messages"]
    conversation_context = "\n".join(
        [f"{'User' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}" for m in recent_messages]
    )

    prompt = f"""{system_prompt}

{booking_prompt}

Current situation:
- Missing information: {', '.join(missing_info)}
- What we have:
  * Name: {state.get('user_name', 'Not provided')}
  * Email: {state.get('user_email', 'Not provided')}
  * Preferred time: {state.get('preferred_date', 'Not provided')}

Recent conversation:
{conversation_context}

Ask the user for the missing information in a friendly, natural way. Be conversational, not robotic:"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        state["messages"].append(AIMessage(content=response.content))

        logger.info("✅ Qualification question sent")

    except Exception as e:
        logger.error(f"❌ Error in qualification node: {e}")
        state["messages"].append(
            AIMessage(
                content="I'd love to help you book a meeting! Could you share your name, email, and preferred time?"
            )
        )

    # Stay in qualification until we have all info
    state["stage"] = "qualification"

    return state


def parse_user_info_node(state: AgentState) -> AgentState:
    """
    Extract booking information from user's message
    Uses LLM to parse name, email, and date preferences

    IMPORTANT: Only processes the last USER message, not AI responses.
    This prevents parsing the AI's own questions/responses.
    """
    logger.info("🔍 Parse user info node")

    # FIX: Get only USER messages, not AI messages
    # This ensures we parse actual user input, not the AI's own responses
    user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]

    if not user_messages:
        logger.warning("⚠️  No user messages found in state")
        return state

    last_user_message = user_messages[-1].content

    # Build context for better extraction
    context_parts = []
    if state.get("preferred_date"):
        context_parts.append(f"Date requested: {state['preferred_date']}")
    if state.get("user_email"):
        context_parts.append(f"Email provided: {state['user_email']}")
    if state.get("user_name"):
        context_parts.append(f"Name already captured: {state['user_name']}")

    context_hint = ""
    if context_parts:
        context_hint = "\n\nBooking context:\n" + "\n".join(context_parts)

    # Determine what we're likely asking for based on what's missing
    missing_hint = ""
    if not state.get("user_name") and state.get("preferred_date") and state.get("user_email"):
        missing_hint = "\nIMPORTANT: The user is likely providing their NAME in response to a question."
    elif not state.get("user_email") and state.get("preferred_date"):
        missing_hint = "\nIMPORTANT: The user is likely providing their EMAIL in response to a question."
    elif not state.get("preferred_date"):
        missing_hint = "\nIMPORTANT: The user is likely providing their PREFERRED DATE/TIME."

    # Use LLM to extract structured data with better context
    extraction_prompt = (
        "You are extracting booking information from a user message. "
        f"We are in the middle of a booking conversation.{missing_hint}{context_hint}\n"
        f'\nUser message: "{last_user_message}"\n\n'
        """Return ONLY a valid JSON object with these exact fields:
{
  "name": "user's name (first name is fine, can be short like 'John', 'Denis', 'Dni', etc.) or null",
  "email": "user's email address (must contain @) or null",
  "preferred_date": "date preference like 'tomorrow afternoon', 'next week', etc. or null"
}

Rules:
- If the message looks like a name (even a short one), extract it as name
- If the message contains @, it's an email
- If the message contains time/day words (tomorrow, next week, etc.), it's a date preference

Return ONLY the JSON, no other text:"""
    )

    try:
        response = llm.invoke([HumanMessage(content=extraction_prompt)])

        # Extract JSON from response
        json_match = re.search(r"\{[^{}]*\}", response.content, re.DOTALL)

        if json_match:
            data = json.loads(json_match.group())

            # Debug logging
            logger.info(f"🔍 LLM extraction response: {data}")

            # Update state with extracted info
            if data.get("name") and not state.get("user_name"):
                state["user_name"] = data["name"]
                logger.info(f"✅ Extracted name: {data['name']}")

            if data.get("email") and not state.get("user_email"):
                state["user_email"] = data["email"]
                logger.info(f"✅ Extracted email: {data['email']}")

            if data.get("preferred_date") and not state.get("preferred_date"):
                state["preferred_date"] = data["preferred_date"]
                logger.info(f"✅ Extracted date: {data['preferred_date']}")
        else:
            logger.warning(f"⚠️  No JSON found in LLM response: {response.content[:200]}")

    except Exception as e:
        logger.warning(f"⚠️  Could not parse user info: {e}")
        logger.warning(f"⚠️  LLM response was: {response.content if 'response' in locals() else 'N/A'}")
        # Continue anyway - qualification node will ask again if needed

    # FALLBACK: If we're clearly asking for a name and LLM didn't extract it,
    # use the message as-is (it's likely just the name)
    if not state.get("user_name") and state.get("preferred_date") and state.get("user_email"):
        # We have date and email, but no name - user must be providing name
        message_stripped = last_user_message.strip()
        # Simple validation: not empty, no @ (not email), reasonable length
        if (
            message_stripped
            and "@" not in message_stripped
            and len(message_stripped) > 1
            and len(message_stripped) < 50
            and not any(
                word in message_stripped.lower()
                for word in ["tomorrow", "today", "next", "week", "morning", "afternoon", "evening"]
            )
        ):
            state["user_name"] = message_stripped
            logger.info(f"✅ Fallback: Using message as name: {message_stripped}")

    return state


def slot_proposal_node(state: AgentState) -> AgentState:
    """
    Check calendar availability and propose time slots
    """
    logger.info("📅 Slot proposal node")

    preferred_date = state.get("preferred_date", "tomorrow")

    try:
        # Parse relative date to concrete datetime
        start_date, end_date = parse_relative_date(preferred_date)

        logger.info(f"🔍 Checking availability: {start_date} to {end_date}")

        # Check calendar availability
        booking_slot = BookingSlot(startDate=start_date, endDate=end_date, timezone="Europe/Kyiv")

        slots = calendar_service.check_availability(booking_slot)

        # Store available slots (limit to first 5)
        state["available_slots"] = [
            {
                "index": i,
                "start": s.startDate.isoformat(),
                "end": s.endDate.isoformat(),
                "start_display": s.startDate.strftime("%I:%M %p"),
                "end_display": s.endDate.strftime("%I:%M %p"),
            }
            for i, s in enumerate(slots[:5])
        ]

        logger.info(f"✅ Found {len(state['available_slots'])} available slots")

    except Exception as e:
        logger.error(f"❌ Error checking availability: {e}")
        state["available_slots"] = []

    # Generate response
    if not state["available_slots"]:
        # No slots available
        prompt = f"""The user requested a meeting for "{preferred_date}" but no time slots are available.

Politely inform them and suggest:
1. Trying different days this week
2. Asking for their flexibility

Be helpful and friendly:"""

        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            state["messages"].append(AIMessage(content=response.content))
        except Exception as e:
            logger.error(f"Error: {e}")
            state["messages"].append(
                AIMessage(
                    content=(
                        f"I don't see any available slots for {preferred_date}. "
                        "Would you like to try a different day?"
                    )
                )
            )

        # Go back to qualification to get new date
        state["stage"] = "qualification"

    else:
        # Present available slots
        slots_text = "\n".join(
            [f"{i + 1}. {s['start_display']} - {s['end_display']}" for i, s in enumerate(state["available_slots"])]
        )

        prompt = f"""The user requested a meeting and here are the available time slots:

{slots_text}

Present these options in a friendly way and ask them to choose by number (1, 2, 3, etc.). Keep it conversational:"""

        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            state["messages"].append(AIMessage(content=response.content))
            logger.info("✅ Slots proposed to user")
        except Exception as e:
            logger.error(f"Error: {e}")
            fallback = (
                f"Great! I found these available times:\n\n{slots_text}\n\n"
                "Which one works best for you? Just tell me the number."
            )
            state["messages"].append(AIMessage(content=fallback))

        # Move to confirmation stage
        state["stage"] = "confirmation"

    return state


def confirmation_node(state: AgentState) -> AgentState:
    """
    Parse user's slot selection and confirm before booking

    IMPORTANT: Only processes the last USER message, not AI responses.
    This prevents parsing the AI's own slot proposal message.
    """
    logger.info("✅ Confirmation node")

    # CRITICAL FIX: Get only USER messages, not AI messages
    # This ensures we parse actual user input (slot selection), not the AI's own slot proposal
    user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)]

    if not user_messages:
        logger.warning("⚠️  No user messages found in state - waiting for user input")
        # No user input yet, stay in confirmation stage
        state["stage"] = "confirmation"
        return state

    last_user_message = user_messages[-1].content.lower()

    # Parse slot selection
    selected_index = None

    # Try to find numbers (but only from user's message)
    numbers = re.findall(r"\b\d+\b", last_user_message)
    if numbers:
        selected_index = int(numbers[0]) - 1  # Convert to 0-indexed
        logger.info(f"📍 User selected slot number: {numbers[0]}")

    # Try text numbers (also only from user's message)
    text_numbers = {
        "first": 0,
        "1st": 0,
        "second": 1,
        "2nd": 1,
        "third": 2,
        "3rd": 2,
        "fourth": 3,
        "4th": 3,
        "fifth": 4,
        "5th": 4,
    }

    for word, idx in text_numbers.items():
        if word in last_user_message:
            selected_index = idx
            logger.info(f"📍 User selected: {word}")
            break

    # Validate selection
    if selected_index is not None and 0 <= selected_index < len(state["available_slots"]):
        # Valid selection
        state["selected_slot"] = state["available_slots"][selected_index]

        # Send confirmation request
        slot = state["selected_slot"]
        confirmation_msg = f"""Perfect! Let me confirm the details:

📅 Date: {slot['start'][:10]}
⏰ Time: {slot['start_display']} - {slot['end_display']}
👤 Name: {state['user_name']}
📧 Email: {state['user_email']}

Should I go ahead and book this meeting? (Yes/No)"""

        state["messages"].append(AIMessage(content=confirmation_msg))
        state["ready_to_book"] = True

        logger.info("✅ Confirmation requested")

        # Stay in confirmation (waiting for yes/no)
        state["stage"] = "confirmation"

    elif state.get("ready_to_book"):
        # User already selected a slot, now checking for yes/no
        # Use last_user_message instead of last_message
        if any(word in last_user_message for word in ["yes", "confirm", "sure", "ok", "book", "go ahead"]):
            logger.info("✅ User confirmed booking")
            state["stage"] = "booking"
        elif any(word in last_user_message for word in ["no", "cancel", "wait", "change"]):
            logger.info("❌ User cancelled booking")
            state["messages"].append(
                AIMessage(content="No problem! Would you like to choose a different time slot or reschedule?")
            )
            state["ready_to_book"] = False
            state["selected_slot"] = None
            state["stage"] = "slot_proposal"
        else:
            # Unclear response
            state["messages"].append(
                AIMessage(
                    content=(
                        "I didn't quite catch that. Should I book this meeting? "
                        "Please say 'yes' to confirm or 'no' to choose a different time."
                    )
                )
            )

    else:
        # Could not parse selection
        logger.warning("⚠️  Could not parse slot selection")
        state["messages"].append(
            AIMessage(
                content="I didn't catch which time slot you'd like. Could you tell me the number? (1, 2, 3, etc.)"
            )
        )

    return state


def booking_node(state: AgentState) -> AgentState:
    """
    Actually book the meeting in Google Calendar
    """
    logger.info("🎯 Booking node")

    selected = state["selected_slot"]

    try:
        # Create booking
        booking_data = BookingData(
            slot=BookingSlot(startDate=selected["start"], endDate=selected["end"], timezone="Europe/Kyiv"),
            name=state["user_name"],
            email=state["user_email"],
        )

        logger.info(f"📤 Booking meeting for {state['user_name']} at {selected['start']}")

        # Book in calendar
        result = calendar_service.book_meeting(booking_data)

        # Success message
        confirmation_message = f"""✅ All set! Your meeting is booked.

**Details:**
- 📅 {selected['start'][:10]}
- ⏰ {selected['start_display']} - {selected['end_display']}
- 👤 {state['user_name']}
- 📧 {state['user_email']}

You'll receive a calendar invitation at {state['user_email']} with:
- Meeting link
- Our team member's contact info

Looking forward to speaking with you!

Is there anything else I can help you with?"""

        state["messages"].append(AIMessage(content=confirmation_message))

        logger.info(f"✅ Meeting booked successfully: {result.get('id')}")

        state["stage"] = "done"

    except Exception as e:
        logger.error(f"❌ Error booking meeting: {e}")

        error_message = f"""❌ I'm sorry, there was an error booking the meeting: {str(e)}

This might be because:
- The slot was just taken by someone else
- There's a calendar sync issue

Would you like to try a different time slot?"""

        state["messages"].append(AIMessage(content=error_message))

        # Go back to slot proposal
        state["selected_slot"] = None
        state["ready_to_book"] = False
        state["stage"] = "slot_proposal"

    return state
