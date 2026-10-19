from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Path, status

from config import Settings, get_settings
from validation.date_string import DateSpec

router = APIRouter(tags=["location"])

Location = Annotated[
    str,
    Path(
        min_length=1,
        max_length=200,
        examples=["10001", "Vancouver, BC", "49.2827,-123.1207"],
    ),
]

Date = Annotated[str | None, Path()]

EnvSettings = Annotated[Settings, Depends(get_settings)]


@router.get("/{location}", status_code=status.HTTP_200_OK)
async def get_current_weather_with_location(
    location: Location, env_settings: EnvSettings
):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            env_settings.api_base_url,
            params={
                "location": location,
                "key": env_settings.weather_api_key.get_secret_value(),
            },
        )
    response.raise_for_status()

    return response.json()
    # location="vancouver"
    # token = os.environ.get("weather_api")
    # today = datetime.now(UTC)
    # tomorrow = today + timedelta(days=1)
    # today = today.strftime("%Y-%m-%d")
    # tomorrow = tomorrow.strftime("%Y-%m-%d")

    # request_url = f"{base_url}{location}/{today}/{tomorrow}" if location else base_url

    # response = httpx.get(request_url, params={"key":token, "include":"days"})

    # print(response.status_code)
    # print(response.json())


@router.get("/{location}/{date1}", status_code=status.HTTP_200_OK)
async def get_weather_with_location_and_date(location: Location, date1: DateSpec):
    # async with httpx.AsyncClient() as client:
    #     pass
    pass
