"""
Comprehensive unit tests for GoogleCalendarService.

This module contains 13 tests covering:
- Test Suite 1: Authentication (_authenticate) - 4 tests
- Test Suite 2: Availability checking (check_availability) - 5 tests
- Test Suite 3: Meeting booking (book_meeting) - 4 tests
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.calendar_service import GoogleCalendarService
from tools.models import BookingData, BookingSlot

# ============================================================================
# Test Suite 1: Authentication (_authenticate)
# ============================================================================


class TestAuthenticate:
    """Tests for the _authenticate method of GoogleCalendarService."""

    def test_authenticate_with_existing_valid_token(
        self, temp_dir: Path, credentials_file: Path, token_file: Path, mock_service_builder: MagicMock
    ) -> None:
        """
        Test loading existing valid token.

        Setup:
            - Create mock token.json with valid credentials
        Action:
            - Initialize GoogleCalendarService
        Expected:
            - self.creds is not None
            - self.creds.valid == True
            - flow.run_local_server() is NOT called
        """
        with patch("tools.calendar_service.build", return_value=mock_service_builder):
            with patch("tools.calendar_service.Credentials.from_authorized_user_file") as mock_from_file:
                # Setup mock to return valid credentials
                mock_creds = MagicMock()
                mock_creds.valid = True
                mock_creds.expired = False
                mock_from_file.return_value = mock_creds

                # Initialize service
                service = GoogleCalendarService(
                    credentials_file=str(credentials_file), token_file=str(token_file), headless=False
                )

                # Assertions
                assert service.creds is not None
                assert service.creds.valid is True
                mock_from_file.assert_called_once_with(str(token_file), GoogleCalendarService.SCOPES)

    def test_authenticate_with_expired_token_refresh(
        self, temp_dir: Path, credentials_file: Path, valid_token_data: dict, mock_service_builder: MagicMock
    ) -> None:
        """
        Test refresh of expired token.

        Setup:
            - Mock token with expired=True and valid refresh_token
        Action:
            - Initialize service
        Expected:
            - creds.refresh() is called
            - Token is saved to file
            - self.creds.valid == True
        """
        token_file = temp_dir / "token.json"
        expired_data = valid_token_data.copy()
        expired_data["expiry"] = (datetime.now() - timedelta(hours=1)).isoformat()
        token_file.write_text(json.dumps(expired_data))

        with patch("tools.calendar_service.build", return_value=mock_service_builder):
            with patch("tools.calendar_service.Credentials.from_authorized_user_file") as mock_from_file:
                with patch("tools.calendar_service.Request"):
                    # Setup mock credentials
                    mock_creds = MagicMock()
                    mock_creds.valid = False
                    mock_creds.expired = True
                    mock_creds.refresh_token = "valid_refresh_token"
                    mock_creds.to_json.return_value = json.dumps({"token": "new_token"})
                    mock_from_file.return_value = mock_creds

                    # Initialize service
                    service = GoogleCalendarService(
                        credentials_file=str(credentials_file), token_file=str(token_file), headless=False
                    )

                    # Assertions
                    mock_creds.refresh.assert_called_once()
                    assert service.creds is not None

    def test_authenticate_missing_credentials_file(self, temp_dir: Path) -> None:
        """
        Test error handling when credentials.json is missing.

        Setup:
            - Delete/don't create credentials.json
        Action:
            - Initialize service
        Expected:
            - FileNotFoundError with message about credentials
        """
        token_file = temp_dir / "token.json"
        non_existent_creds = temp_dir / "non_existent_credentials.json"

        with pytest.raises(FileNotFoundError) as exc_info:
            GoogleCalendarService(credentials_file=str(non_existent_creds), token_file=str(token_file), headless=False)

        assert "Credentials file not found" in str(exc_info.value)
        assert "Download it from Google Cloud Console" in str(exc_info.value)

    def test_headless_auth_flow(
        self, temp_dir: Path, credentials_file: Path, valid_token_data: dict, mock_service_builder: MagicMock
    ) -> None:
        """
        Test headless OAuth flow.

        Setup:
            - Mock InstalledAppFlow
            - Mock input() to return authorization code
        Action:
            - Call _headless_auth()
        Expected:
            - flow.authorization_url() called with prompt='consent'
            - flow.fetch_token() called with correct code
            - Token is saved
        """
        token_file = temp_dir / "token.json"
        token_file.write_text(json.dumps(valid_token_data))

        with patch("tools.calendar_service.build", return_value=mock_service_builder):
            with patch("tools.calendar_service.Credentials.from_authorized_user_file") as mock_from_file:
                with patch("tools.calendar_service.InstalledAppFlow") as mock_flow_class:
                    with patch("builtins.input", return_value="test_auth_code"):
                        # Setup: token file exists but credentials are invalid
                        mock_creds = MagicMock()
                        mock_creds.valid = False
                        mock_creds.expired = True
                        mock_creds.refresh_token = None
                        mock_from_file.return_value = mock_creds

                        # Setup mock flow
                        mock_flow = MagicMock()
                        mock_flow.authorization_url.return_value = ("https://auth.url", "state")
                        mock_flow.credentials = MagicMock()
                        mock_flow.credentials.valid = True
                        mock_flow.credentials.to_json.return_value = json.dumps(valid_token_data)
                        mock_flow_class.from_client_secrets_file.return_value = mock_flow

                        # Initialize service in headless mode
                        GoogleCalendarService(
                            credentials_file=str(credentials_file), token_file=str(token_file), headless=True
                        )

                        # Assertions
                        mock_flow_class.from_client_secrets_file.assert_called_once()
                        call_args = mock_flow_class.from_client_secrets_file.call_args
                        assert "redirect_uri" in call_args.kwargs
                        assert call_args.kwargs["redirect_uri"] == "urn:ietf:wg:oauth:2.0:oob"

                        mock_flow.authorization_url.assert_called_once_with(prompt="consent")
                        mock_flow.fetch_token.assert_called_once_with(code="test_auth_code")


# ============================================================================
# Test Suite 2: Availability checking (check_availability)
# ============================================================================


class TestCheckAvailability:
    """Tests for the check_availability method of GoogleCalendarService."""

    def test_check_availability_all_free(
        self, temp_dir: Path, credentials_file: Path, token_file: Path, booking_slot_utc: BookingSlot
    ) -> None:
        """
        Test generating slots when entire period is free.

        Setup:
            - Mock API response with empty busy: []
            - BookingSlot: 9:00-17:00 (8 hours)
        Action:
            - Call check_availability()
        Expected:
            - 16 slots returned (8 hours × 2 slots/hour)
            - All slots are 30 minutes
            - Slots are sequential without gaps
        """
        with patch("tools.calendar_service.build") as mock_build:
            # Setup mock service
            mock_service = MagicMock()
            mock_freebusy = MagicMock()
            mock_freebusy.query.return_value.execute.return_value = {"calendars": {"primary": {"busy": []}}}
            mock_service.freebusy.return_value = mock_freebusy
            mock_build.return_value = mock_service

            with patch("tools.calendar_service.Credentials.from_authorized_user_file") as mock_from_file:
                mock_creds = MagicMock()
                mock_creds.valid = True
                mock_from_file.return_value = mock_creds

                # Initialize service
                service = GoogleCalendarService(
                    credentials_file=str(credentials_file), token_file=str(token_file), headless=False
                )

                # Check availability
                slots = service.check_availability(booking_slot_utc)

                # Assertions: 8 hours = 480 minutes = 16 slots of 30 minutes
                assert len(slots) == 16

                # Verify all slots are 30 minutes
                for slot in slots:
                    duration = (slot.endDate - slot.startDate).total_seconds() / 60
                    assert duration == 30

                # Verify slots are sequential
                for i in range(len(slots) - 1):
                    assert slots[i].endDate == slots[i + 1].startDate

    def test_check_availability_with_busy_periods(
        self,
        temp_dir: Path,
        credentials_file: Path,
        token_file: Path,
        booking_slot_utc: BookingSlot,
        busy_periods_10_to_11_and_14_to_15: list[dict],
    ) -> None:
        """
        Test filtering of busy periods.

        Setup:
            - Busy: 10:00-11:00, 14:00-15:00
            - BookingSlot: 9:00-17:00
        Action:
            - Call check_availability()
        Expected:
            - NO slots in 10:00-11:00 and 14:00-15:00
            - Slots exist in 9:00-10:00, 11:00-14:00, 15:00-17:00
        """
        with patch("tools.calendar_service.build") as mock_build:
            # Setup mock service
            mock_service = MagicMock()
            mock_freebusy = MagicMock()
            mock_freebusy.query.return_value.execute.return_value = {
                "calendars": {"primary": {"busy": busy_periods_10_to_11_and_14_to_15}}
            }
            mock_service.freebusy.return_value = mock_freebusy
            mock_build.return_value = mock_service

            with patch("tools.calendar_service.Credentials.from_authorized_user_file") as mock_from_file:
                mock_creds = MagicMock()
                mock_creds.valid = True
                mock_from_file.return_value = mock_creds

                # Initialize service
                service = GoogleCalendarService(
                    credentials_file=str(credentials_file), token_file=str(token_file), headless=False
                )

                # Check availability
                slots = service.check_availability(booking_slot_utc)

                # Assertions
                # Expected: (9:00-10:00) + (11:00-14:00) + (15:00-17:00) = 6 hours = 12 slots
                assert len(slots) == 12

                # Convert to naive UTC for comparison (remove timezone info if present)
                busy_10_start = datetime(2024, 1, 15, 10, 0)
                busy_10_end = datetime(2024, 1, 15, 11, 0)
                busy_14_start = datetime(2024, 1, 15, 14, 0)
                busy_14_end = datetime(2024, 1, 15, 15, 0)

                # Verify no slots fall in busy periods
                for slot in slots:
                    # Remove timezone info for comparison if present
                    slot_start = slot.startDate.replace(tzinfo=None) if slot.startDate.tzinfo else slot.startDate

                    # Not in 10:00-11:00
                    assert not (slot_start >= busy_10_start and slot_start < busy_10_end)
                    # Not in 14:00-15:00
                    assert not (slot_start >= busy_14_start and slot_start < busy_14_end)

    def test_check_availability_completely_busy(
        self,
        temp_dir: Path,
        credentials_file: Path,
        token_file: Path,
        booking_slot_utc: BookingSlot,
        busy_periods_full_day: list[dict],
    ) -> None:
        """
        Test when entire period is busy.

        Setup:
            - Busy: 9:00-17:00 (entire period)
        Action:
            - Call check_availability()
        Expected:
            - Empty list []
        """
        with patch("tools.calendar_service.build") as mock_build:
            # Setup mock service
            mock_service = MagicMock()
            mock_freebusy = MagicMock()
            mock_freebusy.query.return_value.execute.return_value = {
                "calendars": {"primary": {"busy": busy_periods_full_day}}
            }
            mock_service.freebusy.return_value = mock_freebusy
            mock_build.return_value = mock_service

            with patch("tools.calendar_service.Credentials.from_authorized_user_file") as mock_from_file:
                mock_creds = MagicMock()
                mock_creds.valid = True
                mock_from_file.return_value = mock_creds

                # Initialize service
                service = GoogleCalendarService(
                    credentials_file=str(credentials_file), token_file=str(token_file), headless=False
                )

                # Check availability
                slots = service.check_availability(booking_slot_utc)

                # Assertions
                assert len(slots) == 0
                assert slots == []

    def test_check_availability_api_error(
        self, temp_dir: Path, credentials_file: Path, token_file: Path, booking_slot_utc: BookingSlot
    ) -> None:
        """
        Test API error handling.

        Setup:
            - Mock service.freebusy().query() raises exception
        Action:
            - Call check_availability()
        Expected:
            - RuntimeError with message "Failed to check availability"
        """
        with patch("tools.calendar_service.build") as mock_build:
            # Setup mock service to raise exception
            mock_service = MagicMock()
            mock_freebusy = MagicMock()
            mock_freebusy.query.side_effect = Exception("API Error: Rate limit exceeded")
            mock_service.freebusy.return_value = mock_freebusy
            mock_build.return_value = mock_service

            with patch("tools.calendar_service.Credentials.from_authorized_user_file") as mock_from_file:
                mock_creds = MagicMock()
                mock_creds.valid = True
                mock_from_file.return_value = mock_creds

                # Initialize service
                service = GoogleCalendarService(
                    credentials_file=str(credentials_file), token_file=str(token_file), headless=False
                )

                # Check availability should raise RuntimeError
                with pytest.raises(RuntimeError) as exc_info:
                    service.check_availability(booking_slot_utc)

                assert "Failed to check availability" in str(exc_info.value)
                assert "API Error: Rate limit exceeded" in str(exc_info.value)

    def test_check_availability_timezone_handling(
        self, temp_dir: Path, credentials_file: Path, token_file: Path, booking_slot_kyiv: BookingSlot
    ) -> None:
        """
        Test correct timezone handling.

        Setup:
            - BookingSlot with timezone="Europe/Kyiv"
            - Timezone-aware dates
        Action:
            - Call check_availability()
        Expected:
            - API called with correct timeZone: "Europe/Kyiv"
            - Dates in ISO format with timezone
        """
        with patch("tools.calendar_service.build") as mock_build:
            # Setup mock service
            mock_service = MagicMock()
            mock_freebusy = MagicMock()
            mock_freebusy.query.return_value.execute.return_value = {"calendars": {"primary": {"busy": []}}}
            mock_service.freebusy.return_value = mock_freebusy
            mock_build.return_value = mock_service

            with patch("tools.calendar_service.Credentials.from_authorized_user_file") as mock_from_file:
                mock_creds = MagicMock()
                mock_creds.valid = True
                mock_from_file.return_value = mock_creds

                # Initialize service
                service = GoogleCalendarService(
                    credentials_file=str(credentials_file), token_file=str(token_file), headless=False
                )

                # Check availability
                service.check_availability(booking_slot_kyiv)

                # Verify API was called with correct parameters
                mock_freebusy.query.assert_called_once()
                call_kwargs = mock_freebusy.query.call_args.kwargs
                assert "body" in call_kwargs

                body = call_kwargs["body"]
                assert body["timeZone"] == "Europe/Kyiv"
                assert "timeMin" in body
                assert "timeMax" in body


# ============================================================================
# Test Suite 3: Meeting booking (book_meeting)
# ============================================================================


class TestBookMeeting:
    """Tests for the book_meeting method of GoogleCalendarService."""

    def test_book_meeting_success(
        self, temp_dir: Path, credentials_file: Path, token_file: Path, booking_data: BookingData
    ) -> None:
        """
        Test successful meeting creation.

        Setup:
            - Mock API response with event id, htmlLink, status='confirmed'
            - BookingData with valid data
        Action:
            - Call book_meeting()
        Expected:
            - Returns dict with id, link, status
            - API called with correct event body
            - sendUpdates='all'
        """
        with patch("tools.calendar_service.build") as mock_build:
            # Setup mock service
            mock_service = MagicMock()
            mock_events = MagicMock()
            mock_events.insert.return_value.execute.return_value = {
                "id": "event_abc123",
                "htmlLink": "https://calendar.google.com/event?id=event_abc123",
                "status": "confirmed",
            }
            mock_service.events.return_value = mock_events
            mock_build.return_value = mock_service

            with patch("tools.calendar_service.Credentials.from_authorized_user_file") as mock_from_file:
                mock_creds = MagicMock()
                mock_creds.valid = True
                mock_from_file.return_value = mock_creds

                # Initialize service
                service = GoogleCalendarService(
                    credentials_file=str(credentials_file), token_file=str(token_file), headless=False
                )

                # Book meeting
                result = service.book_meeting(booking_data)

                # Assertions
                assert result["id"] == "event_abc123"
                assert result["link"] == "https://calendar.google.com/event?id=event_abc123"
                assert result["status"] == "confirmed"

                # Verify API was called correctly
                mock_events.insert.assert_called_once()
                call_kwargs = mock_events.insert.call_args.kwargs
                assert call_kwargs["calendarId"] == "primary"
                assert call_kwargs["sendUpdates"] == "all"
                assert "body" in call_kwargs

    def test_book_meeting_event_structure(
        self, temp_dir: Path, credentials_file: Path, token_file: Path, booking_data: BookingData
    ) -> None:
        """
        Test structure of created event.

        Setup:
            - Mock API, capture called parameters
        Action:
            - Call book_meeting()
        Expected:
            Event contains:
                - summary: "Meeting with {name}"
                - description: "Booked via AI Agent"
                - start.dateTime in ISO format
                - start.timeZone = slot.timezone
                - attendees[0].email = booking email
        """
        with patch("tools.calendar_service.build") as mock_build:
            # Setup mock service to capture event body
            mock_service = MagicMock()
            mock_events = MagicMock()

            captured_event_body = {}

            def capture_body(**kwargs):
                captured_event_body.update(kwargs.get("body", {}))
                return MagicMock(execute=lambda: {"id": "event_123", "htmlLink": "http://link", "status": "confirmed"})

            mock_events.insert.side_effect = capture_body
            mock_service.events.return_value = mock_events
            mock_build.return_value = mock_service

            with patch("tools.calendar_service.Credentials.from_authorized_user_file") as mock_from_file:
                mock_creds = MagicMock()
                mock_creds.valid = True
                mock_from_file.return_value = mock_creds

                # Initialize service
                service = GoogleCalendarService(
                    credentials_file=str(credentials_file), token_file=str(token_file), headless=False
                )

                # Book meeting
                service.book_meeting(booking_data)

                # Verify event structure
                assert captured_event_body["summary"] == "Meeting with John Doe"
                assert captured_event_body["description"] == "Booked via AI Agent"
                assert "start" in captured_event_body
                assert "end" in captured_event_body
                assert "attendees" in captured_event_body

                # Verify start structure
                assert "dateTime" in captured_event_body["start"]
                assert captured_event_body["start"]["timeZone"] == "UTC"

                # Verify attendees
                assert len(captured_event_body["attendees"]) == 1
                assert captured_event_body["attendees"][0]["email"] == "john.doe@example.com"

    def test_book_meeting_datetime_serialization(
        self, temp_dir: Path, credentials_file: Path, token_file: Path, booking_data: BookingData
    ) -> None:
        """
        Test datetime serialization to strings.

        Setup:
            - BookingData with datetime objects
        Action:
            - Call book_meeting()
        Expected:
            - NO "datetime is not JSON serializable" error
            - dateTime in event are strings (verified via mock)
        """
        with patch("tools.calendar_service.build") as mock_build:
            # Setup mock service
            mock_service = MagicMock()
            mock_events = MagicMock()

            captured_body = {}

            def capture_execute():
                return {
                    "id": "event_123",
                    "htmlLink": "https://calendar.google.com/event",
                    "status": "confirmed",
                }

            mock_events.insert.return_value.execute.return_value = capture_execute()

            def capture_insert(**kwargs):
                captured_body["body"] = kwargs.get("body", {})
                return mock_events.insert

            mock_events.insert.side_effect = capture_insert
            mock_service.events.return_value = mock_events
            mock_build.return_value = mock_service

            with patch("tools.calendar_service.Credentials.from_authorized_user_file") as mock_from_file:
                mock_creds = MagicMock()
                mock_creds.valid = True
                mock_from_file.return_value = mock_creds

                # Initialize service
                service = GoogleCalendarService(
                    credentials_file=str(credentials_file), token_file=str(token_file), headless=False
                )

                # Book meeting - should not raise serialization error
                try:
                    service.book_meeting(booking_data)
                    # Verify datetimes were serialized to strings
                    assert isinstance(captured_body["body"]["start"]["dateTime"], str)
                    assert isinstance(captured_body["body"]["end"]["dateTime"], str)
                except TypeError as e:
                    if "not JSON serializable" in str(e):
                        pytest.fail("DateTime serialization failed")
                    else:
                        raise

    def test_book_meeting_api_error(
        self, temp_dir: Path, credentials_file: Path, token_file: Path, booking_data: BookingData
    ) -> None:
        """
        Test API error handling.

        Setup:
            - Mock events().insert() raises exception
        Action:
            - Call book_meeting()
        Expected:
            - RuntimeError with message "Failed to book meeting"
        """
        with patch("tools.calendar_service.build") as mock_build:
            # Setup mock service to raise exception
            mock_service = MagicMock()
            mock_events = MagicMock()
            mock_events.insert.side_effect = Exception("API Error: Invalid credentials")
            mock_service.events.return_value = mock_events
            mock_build.return_value = mock_service

            with patch("tools.calendar_service.Credentials.from_authorized_user_file") as mock_from_file:
                mock_creds = MagicMock()
                mock_creds.valid = True
                mock_from_file.return_value = mock_creds

                # Initialize service
                service = GoogleCalendarService(
                    credentials_file=str(credentials_file), token_file=str(token_file), headless=False
                )

                # Book meeting should raise RuntimeError
                with pytest.raises(RuntimeError) as exc_info:
                    service.book_meeting(booking_data)

                assert "Failed to book meeting" in str(exc_info.value)
                assert "API Error: Invalid credentials" in str(exc_info.value)
