from typing import List, Dict, Union, Optional, Literal
from pydantic import BaseModel
import datetime


# /v1/chat/completions 请求模型
class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Dict[str, str]]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[List[str]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None


# # /v1/chat/completions 响应模型 (简化)
# class ChatCompletionResponseChoice(BaseModel):
#     index: int
#     message: Dict[str, str]
#     finish_reason: str


# class ChatCompletionResponse(BaseModel):
#     id: str
#     object: str = "chat.completion"
#     created: int
#     choices: List[ChatCompletionResponseChoice]
#     usage: Optional[Dict[str, int]] = None


class FunctionCall(BaseModel):
    arguments: str
    name: str


class ToolCall(BaseModel):
    id: str
    # "Currently, only function is supported"
    type: Literal["function"] = "function"
    # function: ToolCallFunction
    function: FunctionCall


class LogProbToken(BaseModel):
    token: str
    logprob: float
    bytes: Optional[List[int]]


class MessageContentLogProb(BaseModel):
    token: str
    logprob: float
    bytes: Optional[List[int]]
    top_logprobs: Optional[List[LogProbToken]]


class Message(BaseModel):
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    role: str
    function_call: Optional[FunctionCall] = None  # Deprecated
    reasoning_content: Optional[str] = None  # Used in newer reasoning APIs
    reasoning_content_signature: Optional[str] = None  # NOTE: for Anthropic
    redacted_reasoning_content: Optional[str] = None  # NOTE: for Anthropic


class Choice(BaseModel):
    finish_reason: str
    index: int
    message: Message
    logprobs: Optional[Dict[str, Union[List[MessageContentLogProb], None]]] = None
    seed: Optional[int] = None  # found in TogetherAI


class UsageStatistics(BaseModel):
    completion_tokens: int = 0
    prompt_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: "UsageStatistics") -> "UsageStatistics":
        return UsageStatistics(
            completion_tokens=self.completion_tokens + other.completion_tokens,
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


class ChatCompletionResponse(BaseModel):
    """https://platform.openai.com/docs/api-reference/chat/object"""

    id: str
    choices: List[Choice]
    created: datetime.datetime
    model: Optional[str] = (
        None  # NOTE: this is not consistent with OpenAI API standard, however is necessary to support local LLMs
    )
    # system_fingerprint: str  # docs say this is mandatory, but in reality API returns None
    system_fingerprint: Optional[str] = None
    # object: str = Field(default="chat.completion")
    object: Literal["chat.completion"] = "chat.completion"
    usage: UsageStatistics

    def __str__(self):
        return self.model_dump_json(indent=2)


class FunctionCallDelta(BaseModel):
    # arguments: Optional[str] = None
    name: Optional[str] = None
    arguments: str
    # name: str


class ToolCallDelta(BaseModel):
    index: int
    id: Optional[str] = None
    # "Currently, only function is supported"
    type: Literal["function"] = "function"
    # function: ToolCallFunction
    function: Optional[FunctionCallDelta] = None


class MessageDelta(BaseModel):
    """Partial delta stream of a Message

    Example ChunkResponse:
    {
        'id': 'chatcmpl-9EOCkKdicNo1tiL1956kPvCnL2lLS',
        'object': 'chat.completion.chunk',
        'created': 1713216662,
        'model': 'gpt-4-0613',
        'system_fingerprint': None,
        'choices': [{
            'index': 0,
            'delta': {'content': 'User'},
            'logprobs': None,
            'finish_reason': None
        }]
    }
    """

    content: Optional[str] = None
    reasoning_content: Optional[str] = None
    reasoning_content_signature: Optional[str] = None  # NOTE: for Anthropic
    redacted_reasoning_content: Optional[str] = None  # NOTE: for Anthropic
    tool_calls: Optional[List[ToolCallDelta]] = None
    role: Optional[str] = None
    function_call: Optional[FunctionCallDelta] = None  # Deprecated


class ChunkChoice(BaseModel):
    finish_reason: Optional[str] = None  # NOTE: when streaming will be null
    index: int
    delta: MessageDelta
    logprobs: Optional[Dict[str, Union[List[MessageContentLogProb], None]]] = None


class ChatCompletionChunkResponse(BaseModel):
    """https://platform.openai.com/docs/api-reference/chat/streaming"""

    id: str
    choices: List[ChunkChoice]
    created: Union[datetime.datetime, str]
    model: str
    # system_fingerprint: str  # docs say this is mandatory, but in reality API returns None
    system_fingerprint: Optional[str] = None
    # object: str = Field(default="chat.completion")
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    output_tokens: int = 0


# /v1/models 响应模型 (简化)
class ModelPermission(BaseModel):
    id: str
    object: str = "model_permission"
    created: int
    allow_create_engine: bool
    allow_sampling: bool
    allow_logprobs: bool
    allow_search: bool
    allow_view: bool
    allow_fine_tuning: bool
    organization: str
    group: Optional[str] = None
    is_blocking: bool


class Model(BaseModel):
    id: str
    object: str = "model"
    owned_by: str
    permission: List[ModelPermission]


class ModelsResponse(BaseModel):
    object: str = "list"
    data: List[Model]
