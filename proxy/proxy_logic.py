import httpx
from fastapi import HTTPException, Header, Response
from starlette.requests import Request
from starlette.responses import StreamingResponse
from typing import Optional
import time
from datetime import datetime, timezone
from json import JSONDecodeError
import json

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

    # 处理响应体
    response_body = None
    if not is_stream and response.content:
        try:
            response_body = response.json()
        except JSONDecodeError:
            try:
                # 如果不是JSON，尝试将其作为文本存储
                response_body = response.text
            except Exception:
                # 如果无法解码为文本，则存储为None
                response_body = None

    # 尝试获取请求体
    request_body = None
    if request.method in ["POST", "PUT"]:
        try:
            request_body = await request.json()
        except JSONDecodeError:
            try:
                # 尝试获取原始请求体
                body_bytes = await request.body()
                request_body = body_bytes.decode("utf-8")
            except Exception:
                # 如果无法解码，则存储为None
                request_body = None

    log_entry = LogEntry(
        timestamp=datetime.now(timezone.utc),
        request_method=request.method,
        request_path=request.url.path,
        request_headers=dict(request.headers),
        request_body=request_body,
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
    import pdb

    try:
        async with httpx.AsyncClient(verify=not config.ignore_ssl_verify) as client:
            start_time = time.time()
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

            # 不使用 raise_for_status，而是检查状态码并相应处理
            if response.status_code >= 400:
                # 保留原始状态码，不转换为 500
                error_content = response.text
                try:
                    error_detail = response.json()
                except Exception:
                    error_detail = error_content

                # 返回与原始响应相同的状态码
                return Response(
                    content=json.dumps(error_detail),
                    status_code=response.status_code,
                    media_type="application/json",
                )

            return response.json()

    except httpx.RequestError as e:
        # 网络错误等
        return Response(
            content=json.dumps({"error": f"Connection error: {str(e)}"}),
            status_code=503,
            media_type="application/json",
        )
    except Exception as e:
        # 其他未预期的错误
        print(f"Unexpected error in proxy_request: {e}")
        return Response(
            content=json.dumps({"error": f"Unexpected error: {str(e)}"}),
            status_code=500,
            media_type="application/json",
        )


async def handle_streaming_request(
    client, backend_url, headers, body, request, start_time, config
):
    """Handle streaming requests and return a StreamingResponse"""
    # Create a new client specifically for streaming to avoid closure issues
    stream_client = httpx.AsyncClient(verify=not config.ignore_ssl_verify)

    # 用于收集流式响应的所有数据
    collected_chunks = []

    async def stream_generator():
        try:
            async with stream_client.stream(
                "POST", backend_url, headers=headers, json=body, timeout=None
            ) as response:
                # 先记录初始响应（不包含完整内容）
                await log_request_response(
                    request, response, start_time, is_stream=True
                )

                # 获取数据库连接，用于更新日志
                db = get_database()
                log_id = None

                # 查找刚刚创建的日志记录
                latest_log = await db["logs"].find_one(
                    {"request_path": request.url.path}, sort=[("timestamp", -1)]
                )
                if latest_log:
                    log_id = latest_log["_id"]

                if response.status_code >= 400:
                    # 对于错误响应，我们需要读取完整响应并抛出异常
                    error_content = await response.read()
                    try:
                        error_json = response.json()
                        error_detail = error_json
                    except Exception:
                        error_detail = error_content.decode("utf-8")

                    raise HTTPException(
                        status_code=response.status_code, detail=error_detail
                    )

                # 流式返回响应给客户端，同时收集所有块
                async for chunk in response.aiter_bytes():
                    collected_chunks.append(chunk)
                    yield chunk

                # 在流式传输完成后，更新日志记录以包含完整的响应内容
                if log_id and collected_chunks:
                    try:
                        # 尝试将所有块合并为一个完整的响应
                        full_response = b"".join(collected_chunks).decode("utf-8")

                        # 尝试解析为JSON
                        try:
                            response_json = json.loads(full_response)
                            # 更新日志记录
                            await db["logs"].update_one(
                                {"_id": log_id},
                                {"$set": {"response_body": response_json}},
                            )
                        except JSONDecodeError:
                            # 如果不是JSON，存储为字符串
                            await db["logs"].update_one(
                                {"_id": log_id},
                                {"$set": {"response_body": full_response}},
                            )
                    except Exception as e:
                        print(f"更新流式响应日志时出错: {e}")

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
