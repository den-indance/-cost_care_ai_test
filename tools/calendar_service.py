from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Protocol

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from tools.models import BookingData, BookingSlot

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class CalendarProvider(Protocol):
    def check_availability(self, data: BookingSlot) -> List[BookingSlot]:
        ...

    def book_meeting(self, data: BookingData):
        ...


class GoogleCalendarService:
    SCOPES = ["https://www.googleapis.com/auth/calendar"]

    def __init__(self, credentials_file: str, token_file: str, headless: bool = False):
        self.credentials_file = Path(credentials_file)
        self.token_file = Path(token_file)
        self.calendar_id = "primary"
        self.headless = headless

        self._authenticate()
        self.service = build("calendar", "v3", credentials=self.creds, cache_discovery=False)

    def _authenticate(self) -> None:
        self.creds = None

        if self.token_file.exists():
            self.creds = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
                self.token_file.write_text(self.creds.to_json())
            else:
                if not self.credentials_file.exists():
                    raise FileNotFoundError(
                        f"Credentials file not found: {self.credentials_file}\n" "Download it from Google Cloud Console"
                    )

                if self.headless:
                    self._headless_auth()
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_file), self.SCOPES)
                    self.creds = flow.run_local_server(port=0)
                    self.token_file.write_text(self.creds.to_json())

    def _headless_auth(self) -> None:
        """OAuth flow для среды без браузера (Docker)"""
        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.credentials_file), scopes=self.SCOPES, redirect_uri="urn:ietf:wg:oauth:2.0:oob"  # Out of band
        )

        # Получить URL для авторизации
        auth_url, _ = flow.authorization_url(prompt="consent")

        logger.info(
            f"""
{'=' * 70}
🔐 GOOGLE CALENDAR AUTHORIZATION REQUIRED
{'=' * 70}

1. Open this URL in your browser:

   {auth_url}

2. Authorize the application
3. Copy the authorization code
{'=' * 70}
"""
        )

        code = input("Enter the authorization code: ").strip()
        flow.fetch_token(code=code)
        self.creds = flow.credentials

        self.token_file.write_text(self.creds.to_json())
        logger.info("\n✅ Authorization successful! Token saved.\n")

    def check_availability(self, data: BookingSlot) -> List[BookingSlot]:
        body = {
            "timeMin": data.startDate.isoformat(),
            "timeMax": data.endDate.isoformat(),
            "timeZone": data.timezone,
            "items": [{"id": self.calendar_id}],
        }

        try:
            result = self.service.freebusy().query(body=body).execute()
            busy_periods = result["calendars"][self.calendar_id].get("busy", [])
            return self._generate_free_slots(data.startDate, data.endDate, busy_periods, data.timezone)
        except Exception as e:
            logger.error(str(e))
            raise RuntimeError(f"Failed to check availability: {e}")

    def _generate_free_slots(
        self, start: datetime, end: datetime, busy_periods: List, timezone: str, slot_duration_min: int = 30
    ) -> List[BookingSlot]:
        free_slots = []
        current = start
        slot_delta = timedelta(minutes=slot_duration_min)

        while current + slot_delta <= end:
            slot_end = current + slot_delta

            is_free = True
            for busy in busy_periods:
                busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00"))
                busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00"))

                if not (slot_end <= busy_start or current >= busy_end):
                    is_free = False
                    break

            if is_free:
                free_slots.append(
                    BookingSlot(
                        startDate=current.replace(tzinfo=None), endDate=slot_end.replace(tzinfo=None), timezone=timezone
                    )
                )

            current += slot_delta

        return free_slots

    def book_meeting(self, data: BookingData):
        event = {
            "summary": f"Meeting with {data.name}",
            "description": "Booked via AI Agent",
            "start": {
                "dateTime": data.slot.startDate.isoformat(),
                "timeZone": data.slot.timezone,
            },
            "end": {
                "dateTime": data.slot.endDate.isoformat(),
                "timeZone": data.slot.timezone,
            },
            "attendees": [
                {"email": data.email},
            ],
        }

        try:
            created_event = (
                self.service.events().insert(calendarId=self.calendar_id, body=event, sendUpdates="all").execute()
            )

            return {"id": created_event["id"], "link": created_event.get("htmlLink"), "status": created_event["status"]}
        except Exception as e:
            logger.error(str(e))
            raise RuntimeError(f"Failed to book meeting: {e}")
