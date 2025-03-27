import httpx
from fastapi import HTTPException, Header, Response, BackgroundTasks
from starlette.requests import Request
from starlette.responses import StreamingResponse
from typing import Optional, AsyncGenerator, Dict, Any
import asyncio
import time
from datetime import datetime, timezone
from json import JSONDecodeError

from core.database import get_database, ProxyConfig, LogEntry


async def get_proxy_config(proxy_model_name: str):
    db = get_database()
    config = await db["configurations"].find_one({"proxy_model_name": proxy_model_name})
    if config:
        return ProxyConfig(**config)
    return None


async def log_request_response(
    request: Request,
    response: httpx.Response,
    start_time: float,
    is_stream: bool = False,
):
    db = get_database()

    # For streaming responses, we can't capture the full response body
    response_body = None
    if not is_stream and response.content:
        try:
            response_body = response.json()
        except JSONDecodeError:
            # If it's not JSON, store it as None
            response_body = None

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
        response_body=response_body,
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

    print(
        f"Proxy request for model: {proxy_model_name}, backend model: {config.backend_model_name}"
    )
    print(f"Backend URL: {backend_url}")
    print(f"Headers: {headers}")

    async with httpx.AsyncClient(verify=not config.ignore_ssl_verify) as client:
        start_time = time.time()
        # try:
        #     if request.method == "POST":
        #         body = await request.json()
        #         # 将代理模型名称替换为后端模型名称
        #         body["model"] = config.backend_model_name

        #         # Check if this is a streaming request
        #         is_stream = body.get("stream", False)
        #         print(f"Request body: {body}")
        #         print(f"Is streaming request: {is_stream}")

        #         if is_stream:
        #             print("Handling streaming request...")
        #             # For streaming responses, we need to use client.stream and return a StreamingResponse
        #             return await handle_streaming_request(client, backend_url, headers, body, request, start_time, config)
        #         else:
        #             print("Handling regular request...")
        #             # Regular non-streaming request
        #             response = await client.post(
        #                 backend_url, headers=headers, json=body, timeout=None
        #             )
        #     elif request.method == "GET":
        #         print("Handling GET request...")
        #         response = await client.get(
        #             backend_url,
        #             headers=headers,
        #             params=request.query_params,
        #             timeout=None,
        #         )
        #     else:
        #         raise HTTPException(status_code=405, detail="Method not allowed.")

        #     # Log the non-streaming response
        #     await log_request_response(request, response, start_time, is_stream=False)

        #     if response.status_code >= 400:
        #         raise HTTPException(
        #             status_code=response.status_code, detail=response.json()
        #         )

        #     return response.json()
        # except httpx.ConnectError as e:
        #     raise HTTPException(
        #         status_code=503,
        #         detail=f"Could not connect to backend: {config.base_url}. Error: {e}",
        #     )
        # except Exception as e:
        #     raise HTTPException(
        #         status_code=500, detail=f"An unexpected error occurred: {e}"
        #     )

        if request.method == "POST":
            body = await request.json()
            # 将代理模型名称替换为后端模型名称
            body["model"] = config.backend_model_name

            # Check if this is a streaming request
            is_stream = body.get("stream", False)
            print(f"Request body: {body}")
            print(f"Is streaming request: {is_stream}")

            if is_stream:
                print("Handling streaming request...")
                # For streaming responses, we need to use client.stream and return a StreamingResponse
                return await handle_streaming_request(
                    client, backend_url, headers, body, request, start_time, config
                )
            else:
                print("Handling regular request...")
                # Regular non-streaming request
                response = await client.post(
                    backend_url, headers=headers, json=body, timeout=None
                )
        elif request.method == "GET":
            print("Handling GET request...")
            response = await client.get(
                backend_url,
                headers=headers,
                params=request.query_params,
                timeout=None,
            )
        else:
            raise HTTPException(status_code=405, detail="Method not allowed.")

        # Log the non-streaming response
        await log_request_response(request, response, start_time, is_stream=False)
        # if response.status_code >= 400:
        #     raise HTTPException(
        #         status_code=response.status_code, detail=response.json()
        #     )

        response.raise_for_status()

        return response.json()


async def handle_streaming_request(
    client, backend_url, headers, body, request, start_time, config
):
    """Handle streaming requests and return a StreamingResponse"""
    # Create a new client specifically for streaming to avoid closure issues
    stream_client = httpx.AsyncClient(verify=not config.ignore_ssl_verify)

    async def stream_generator():
        try:
            async with stream_client.stream(
                "POST", backend_url, headers=headers, json=body, timeout=None
            ) as response:
                # Log the streaming response (without body content)
                await log_request_response(
                    request, response, start_time, is_stream=True
                )

                if response.status_code >= 400:
                    # For error responses, we need to read the full response and raise an exception
                    error_content = await response.read()
                    try:
                        error_json = response.json()
                        error_detail = error_json
                    except Exception:
                        error_detail = error_content.decode("utf-8")

                    raise HTTPException(
                        status_code=response.status_code, detail=error_detail
                    )

                # Stream the response back to the client
                async for chunk in response.aiter_bytes():
                    yield chunk

        except httpx.ConnectError as e:
            error_msg = f"Could not connect to backend: {config.base_url}. Error: {e}"
            yield f'data: {{"error": "{error_msg}"}}\n\n'.encode("utf-8")
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            yield f'data: {{"error": "{error_msg}"}}\n\n'.encode("utf-8")
        finally:
            # Make sure to close the client when done
            await stream_client.aclose()

    # Return a StreamingResponse with the appropriate content type
    response = StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

    # Add a background task to close the client when the response is complete
    # This ensures the client stays open during streaming but is properly closed after
    return response


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
