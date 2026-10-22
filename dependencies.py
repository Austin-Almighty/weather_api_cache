from typing import Annotated

import httpx
from fastapi import Depends, Request


def get_httpx_client(request: Request) -> httpx.AsyncClient:
    return request.state.http_client


HttpClient = Annotated[httpx.AsyncClient, Depends(get_httpx_client)]
