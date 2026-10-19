import re
from datetime import date, datetime
from typing import Annotated

from fastapi import Path
from pydantic import AfterValidator

FIXED_PERIODS = {
    "today",
    "tomorrow",
    "yesterday",
    "yeartodate",
    "monthtodate",
    "lastyear",
    "last24hours",
    "nextweekend",
    "lastweekend",
}

DYNAMIC_PERIOD = re.compile(
    r"(?:next|last)(?:"
    r"\d+days|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r")"
)


def validate_date_spec(value: str) -> str:
    # Unix timestamp
    if value.isdigit():
        return value

    # Dynamic period
    if value in FIXED_PERIODS or DYNAMIC_PERIOD.fullmatch(value):
        return value

    # Calendar date
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            date.fromisoformat(value)
        except ValueError as error:
            raise ValueError("Invalid calendar date") from error
        return value

    # Local date and time
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value):
        try:
            datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        except ValueError as error:
            raise ValueError("Invalid date or time") from error
        return value

    raise ValueError(
        "Expected YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, "
        "a Unix timestamp, or a supported dynamic period"
    )


DateSpec = Annotated[
    str,
    AfterValidator(validate_date_spec),
    Path(description="Visual Crossing date or dynamic period"),
]