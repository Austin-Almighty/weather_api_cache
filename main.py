from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import get_settings
from routes.location import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()
    yield


app = FastAPI(lifespan=lifespan)

app.include_router(router)
