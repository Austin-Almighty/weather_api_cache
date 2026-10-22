import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from config import Settings, get_settings
from routes.location import router

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[dict[str, httpx.AsyncClient]]:
    settings: Settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.api_timeout_seconds) as client:
        yield {"http_client": client}


app = FastAPI(lifespan=lifespan)

app.include_router(router)
