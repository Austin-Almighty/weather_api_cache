import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
from fastapi import FastAPI

from config import Settings, get_settings
from dependencies import State
from routes.location import router

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[State]:
    settings: Settings = get_settings()
    async with (
        httpx.AsyncClient(timeout=settings.api_timeout_seconds) as client,
        redis.Redis.from_url(settings.redis_url, decode_responses=True) as cache,
    ):
        yield {"http_client": client, "redis_client": cache}


app = FastAPI(lifespan=lifespan)

app.include_router(router)
