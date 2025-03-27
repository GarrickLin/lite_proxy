import httpx
from fastapi import HTTPException, Header
from starlette.requests import Request
from typing import Optional
import asyncio
import time
from datetime import datetime, timezone

from core.database import get_database, ProxyConfig, LogEntry


async def get_proxy_config(proxy_model_name: str):
    db = get_database()
    config = await db["configurations"].find_one({"proxy_model_name": proxy_model_name})
    if config:
        return ProxyConfig(**config)
    return None


async def log_request_response(
    request: Request, response: httpx.Response, start_time: float
):
    db = get_database()
    log_entry = LogEntry(
        timestamp=datetime.now(timezone.utc),
        request_method=request.method,
        request_path=request.url.path,
        request_headers=dict(request.headers),
        request_body=(
            await request.json() if request.method in ["POST", "PUT"] else None
        ),
        response_status_code=response.status_code,
        response_headers=dict(response.headers),
        response_body=response.json() if response.content else None,
        processing_time=time.time() - start_time,
    )
    await db["logs"].insert_one(log_entry.model_dump())


async def proxy_request(
    request: Request, proxy_model_name: str, authorization: Optional[str] = Header(None)
):
    config = await get_proxy_config(proxy_model_name)
    if not config:
        raise HTTPException(
            status_code=404, detail=f"Proxy model '{proxy_model_name}' not found."
        )

    backend_url = config.base_url + request.url.path
    headers = {}
    if authorization:
        headers["Authorization"] = authorization
    if config.backend_api_key:
        headers["Authorization"] = (
            f"Bearer {config.backend_api_key}"  # 优先使用配置中的 API Key
        )

    # import pdb

    # pdb.set_trace()

    async with httpx.AsyncClient(verify=not config.ignore_ssl_verify) as client:
        start_time = time.time()
        # if request.method == "POST":
        #     body = await request.json()
        #     pdb.set_trace()
        #     # 将代理模型名称替换为后端模型名称
        #     body["model"] = config.backend_model_name
        #     response = await client.post(
        #         backend_url, headers=headers, json=body, timeout=None
        #     )
        # pdb.set_trace()
        try:
            if request.method == "POST":
                body = await request.json()
                # pdb.set_trace()
                # 将代理模型名称替换为后端模型名称
                body["model"] = config.backend_model_name
                response = await client.post(
                    backend_url, headers=headers, json=body, timeout=None
                )
                # pdb.set_trace()
            elif request.method == "GET":
                response = await client.get(
                    backend_url,
                    headers=headers,
                    params=request.query_params,
                    timeout=None,
                )
            else:
                raise HTTPException(status_code=405, detail="Method not allowed.")

            # print(response.json())
            # import pdb

            # pdb.set_trace()

            await log_request_response(request, response, start_time)

            if response.status_code >= 400:
                raise HTTPException(
                    status_code=response.status_code, detail=response.json()
                )

            return response.json()
        except httpx.ConnectError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Could not connect to backend: {config.base_url}. Error: {e}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"An unexpected error occurred: {e}"
            )


async def proxy_models_request(
    request: Request, authorization: Optional[str] = Header(None)
):
    db = get_database()
    distinct_base_urls = await db["configurations"].distinct("base_url")
    all_models = []
    headers = {}
    if authorization:
        headers["Authorization"] = authorization

    async with httpx.AsyncClient() as client:  # 注意这里暂时没有使用 backend_api_key 和 ignore_ssl_verify
        for base_url in distinct_base_urls:
            backend_url = base_url + request.url.path
            start_time = time.time()
            try:
                response = await client.get(backend_url, headers=headers, timeout=None)
                await log_request_response(request, response, start_time)
                if response.status_code == 200:
                    models_data = response.json().get(
                        "data",
                    )
                    all_models.extend(models_data)
                elif response.status_code >= 400:
                    print(
                        f"Error fetching models from {base_url}: {response.status_code} - {response.json()}"
                    )
            except httpx.ConnectError as e:
                print(f"Could not connect to backend {base_url} for models: {e}")
            except Exception as e:
                print(
                    f"An unexpected error occurred while fetching models from {base_url}: {e}"
                )

    return {"object": "list", "data": all_models}
