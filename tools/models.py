import sys
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

# Handle zoneinfo import for Python < 3.9
if sys.version_info >= (3, 9):
    import zoneinfo
else:
    from backports import zoneinfo


class BookingSlot(BaseModel):
    startDate: datetime
    endDate: datetime
    timezone: str = Field(default="UTC", examples=["Europe/Kyiv", "America/New_York"])

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        if v not in zoneinfo.available_timezones():
            raise ValueError("Invalid timezone name")
        return v

    @model_validator(mode="after")
    def validate_and_localize_dates(self):
        if self.endDate <= self.startDate:
            raise ValueError("endDate must be after startDate")

        tz = zoneinfo.ZoneInfo(self.timezone)
        if self.startDate.tzinfo is None:
            self.startDate = self.startDate.replace(tzinfo=tz)
        if self.endDate.tzinfo is None:
            self.endDate = self.endDate.replace(tzinfo=tz)

        return self

    def __str__(self):
        return f"start date: {self.startDate}, end date: {self.endDate}"


class BookingData(BaseModel):
    slot: BookingSlot
    name: str
    email: EmailStr
