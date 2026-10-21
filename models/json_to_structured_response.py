import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class Current(BaseModel):
    temperature: float | None
    feels_like: float | None
    uv_index: Annotated[float, Field(ge=0)] | None
    conditions: str | None
    humidity: float | None


class ForecastDay(BaseModel):
    date: datetime.date
    high: float | None
    low: float | None
    conditions: str | None
    chance_of_rain: float | None


class ResponseShape(BaseModel):
    location: str
    units: Literal["metric"]
    current: Current
    forecasts: Annotated[list[ForecastDay], Field(min_length=3, max_length=3)]


def json_to_structured_response(json_response: dict[str, Any]) -> ResponseShape:
    location: str | None = json_response.get("resolvedAddress")
    days: list[dict[str, Any]] = json_response.get("days") or []
    current_conditions: dict[str, Any] = json_response.get("currentConditions") or {}
    current_forecast = Current(
        temperature=current_conditions.get("temp"),
        feels_like=current_conditions.get("feelslike"),
        uv_index=current_conditions.get("uvindex"),
        conditions=current_conditions.get("conditions"),
        humidity=current_conditions.get("humidity"),
    )

    forecasts: list[ForecastDay] = [
        ForecastDay.model_validate(
            {
                "date": day.get("datetime"),
                "high": day.get("tempmax"),
                "low": day.get("tempmin"),
                "conditions": day.get("conditions"),
                "chance_of_rain": day.get("precipprob"),
            }
        )
        for day in days[:3]
    ]

    output = ResponseShape.model_validate(
        {
            "location": location,
            "units": "metric",
            "current": current_forecast,
            "forecasts": forecasts,
        }
    )
    return output
