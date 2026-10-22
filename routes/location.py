import logging
from typing import Annotated
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, status
from httpx import Response
from pydantic import ValidationError

from config import Settings, get_settings
from dependencies import HttpClient
from models.json_to_structured_response import (
    ResponseShape,
    json_to_structured_response,
)

router = APIRouter(tags=["location"], prefix="/weather")

logger = logging.getLogger(__name__)

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
    location: Location, env_settings: EnvSettings, client: HttpClient
) -> ResponseShape:
    try:
        response: Response = await client.get(
            f"{env_settings.api_base_url}/{quote(location)}/next2days",
            params={
                "key": env_settings.weather_api_key.get_secret_value(),
                "unitGroup": "metric",
                "include": "days,current",
            },
        )
    except httpx.TimeoutException:
        logger.warning("Visual Crossing timed out for %s", location)
        raise HTTPException(
            status_code=504, detail="Weather provider took too long to respond"
        ) from None
    except httpx.ConnectError:
        logger.warning("Connection to Visual Crossing API failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Connection to API failed",
        ) from None
    try:
        response.raise_for_status()
        logger.info("Fetched weather for %s: status %s", location, response.status_code)
    except httpx.HTTPStatusError as exc:
        if (
            exc.response.status_code == 400
            and "No valid locations" in exc.response.text
        ):
            logger.info(
                "Failed to find the data for %s: status %s",
                location,
                exc.response.status_code,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The system cannot find the location you entered",
            ) from None
        else:
            logger.warning(
                "Visual Crossing returned %s",
                exc.response.status_code,
            )
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY) from None

    data = response.json()
    try:
        res = json_to_structured_response(data)
    except ValidationError:
        logger.exception("Data validation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Weather provider returned incomplete data",
        ) from None
    return res
