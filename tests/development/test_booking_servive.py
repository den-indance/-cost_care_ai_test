from tools.calendar_service import BookingSlot, GoogleCalendarService
from tools.models import BookingData

google_calendar_service = GoogleCalendarService(
    credentials_file="config/google_creds.json", token_file="config/user_token.json", headless=True
)

slots = google_calendar_service.check_availability(
    BookingSlot(startDate="2026-02-06", endDate="2026-02-07", timezone="Europe/Kyiv")
)
for slot in slots:
    print(slot)

booking_event = google_calendar_service.book_meeting(
    BookingData(slot=slots[10], name="john", email="fibohef575@aixind.com")
)
print(booking_event)
