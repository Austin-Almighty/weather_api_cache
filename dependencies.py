from typing import Annotated, TypedDict

import httpx
import redis.asyncio as redis
from fastapi import Depends, Request


class State(TypedDict):
    http_client: httpx.AsyncClient
    redis_client: redis.Redis


def get_httpx_client(request: Request) -> httpx.AsyncClient:
    return request.state.http_client

def get_redis_client(request: Request) -> redis.Redis:
    return request.state.redis_client

HttpClient = Annotated[httpx.AsyncClient, Depends(get_httpx_client)]
RedisClient = Annotated[redis.Redis, Depends(get_redis_client)]
