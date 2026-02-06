"""
Shared pytest fixtures for unit tests.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import pytest

from tools.models import BookingData, BookingSlot


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Fixture providing a temporary directory for test files."""
    return tmp_path


@pytest.fixture
def valid_credentials_data() -> dict:
    """Fixture providing valid Google credentials data."""
    return {
        "installed": {
            "client_id": "test_client_id.apps.googleusercontent.com",
            "client_secret": "test_client_secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
        }
    }


@pytest.fixture
def valid_token_data() -> dict:
    """Fixture providing valid token data."""
    now = datetime.now()
    return {
        "token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test_client_id.apps.googleusercontent.com",
        "client_secret": "test_client_secret",
        "scopes": ["https://www.googleapis.com/auth/calendar"],
        "expiry": (now + timedelta(hours=1)).isoformat(),
    }


@pytest.fixture
def credentials_file(temp_dir: Path, valid_credentials_data: dict) -> Path:
    """Fixture creating a valid credentials.json file."""
    credentials_path = temp_dir / "credentials.json"
    credentials_path.write_text(json.dumps(valid_credentials_data))
    return credentials_path


@pytest.fixture
def token_file(temp_dir: Path, valid_token_data: dict) -> Path:
    """Fixture creating a valid token.json file."""
    token_path = temp_dir / "token.json"
    token_path.write_text(json.dumps(valid_token_data))
    return token_path


@pytest.fixture
def booking_slot_utc() -> BookingSlot:
    """Fixture providing a BookingSlot in UTC timezone (9:00-17:00)."""
    start = datetime(2024, 1, 15, 9, 0)
    end = datetime(2024, 1, 15, 17, 0)
    return BookingSlot(startDate=start, endDate=end, timezone="UTC")


@pytest.fixture
def booking_slot_kyiv() -> BookingSlot:
    """Fixture providing a BookingSlot in Europe/Kyiv timezone (9:00-17:00)."""
    start = datetime(2024, 1, 15, 9, 0)
    end = datetime(2024, 1, 15, 17, 0)
    return BookingSlot(startDate=start, endDate=end, timezone="Europe/Kyiv")


@pytest.fixture
def booking_data() -> BookingData:
    """Fixture providing a complete BookingData object."""
    slot = BookingSlot(startDate=datetime(2024, 1, 15, 10, 0), endDate=datetime(2024, 1, 15, 10, 30), timezone="UTC")
    return BookingData(slot=slot, name="John Doe", email="john.doe@example.com")


@pytest.fixture
def mock_service_builder() -> MagicMock:
    """Fixture providing a mock Google Calendar service builder."""
    service = MagicMock()

    # Mock freebusy().query() response
    freebusy_mock = MagicMock()
    freebusy_mock.query.return_value.execute.return_value = {"calendars": {"primary": {"busy": []}}}
    service.freebusy.return_value = freebusy_mock

    # Mock events().insert() response
    events_mock = MagicMock()
    events_mock.insert.return_value.execute.return_value = {
        "id": "event_123",
        "htmlLink": "https://calendar.google.com/event?id=event_123",
        "status": "confirmed",
    }
    service.events.return_value = events_mock

    return service


@pytest.fixture
def busy_periods_10_to_11_and_14_to_15() -> list[dict]:
    """Fixture providing busy periods 10:00-11:00 and 14:00-15:00."""
    start1 = datetime(2024, 1, 15, 10, 0, tzinfo=ZoneInfo("UTC"))
    end1 = datetime(2024, 1, 15, 11, 0, tzinfo=ZoneInfo("UTC"))
    start2 = datetime(2024, 1, 15, 14, 0, tzinfo=ZoneInfo("UTC"))
    end2 = datetime(2024, 1, 15, 15, 0, tzinfo=ZoneInfo("UTC"))
    # Google API returns UTC times with 'Z' suffix
    return [
        {"start": start1.isoformat().replace("+00:00", "Z"), "end": end1.isoformat().replace("+00:00", "Z")},
        {"start": start2.isoformat().replace("+00:00", "Z"), "end": end2.isoformat().replace("+00:00", "Z")},
    ]


@pytest.fixture
def busy_periods_full_day() -> list[dict]:
    """Fixture providing busy period covering entire day (9:00-17:00)."""
    start = datetime(2024, 1, 15, 9, 0, tzinfo=ZoneInfo("UTC"))
    end = datetime(2024, 1, 15, 17, 0, tzinfo=ZoneInfo("UTC"))
    # Google API returns UTC times with 'Z' suffix
    return [{"start": start.isoformat().replace("+00:00", "Z"), "end": end.isoformat().replace("+00:00", "Z")}]
