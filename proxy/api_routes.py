from fastapi import APIRouter, Depends
from starlette.requests import Request
from typing import Optional
from fastapi import Header
from . import proxy_logic
from .models import ChatCompletionRequest, ChatCompletionResponse, ModelsResponse

router = APIRouter()


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    request: Request,
    body: ChatCompletionRequest,
    authorization: Optional[str] = Header(None),
):
    # print("/chat/completions called")
    return await proxy_logic.proxy_request(request, body.model, authorization)


@router.get("/models", response_model=ModelsResponse)
async def get_models(request: Request, authorization: Optional[str] = Header(None)):
    return await proxy_logic.proxy_models_request(request, authorization)
