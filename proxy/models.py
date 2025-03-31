from typing import List, Dict, Union, Optional, Literal, Any
from pydantic import BaseModel, Field, field_validator
import datetime


class SystemMessage(BaseModel):
    content: str
    role: str = "system"
    name: Optional[str] = None


class UserMessage(BaseModel):
    content: Union[str, List[str]]
    role: str = "user"
    name: Optional[str] = None


class ToolCallFunction(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    id: str
    type: Literal["function"] = "function"
    function: ToolCallFunction


class AssistantMessage(BaseModel):
    content: Optional[str] = None
    role: str = "assistant"
    name: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None


class ToolMessage(BaseModel):
    content: str
    role: str = "tool"
    tool_call_id: str


ChatMessage = Union[SystemMessage, UserMessage, AssistantMessage, ToolMessage]


# TODO: this might not be necessary with the validator
def cast_message_to_subtype(m_dict: dict) -> ChatMessage:
    """Cast a dictionary to one of the individual message types"""
    role = m_dict.get("role")
    if role == "system":
        return SystemMessage(**m_dict)
    elif role == "user":
        return UserMessage(**m_dict)
    elif role == "assistant":
        return AssistantMessage(**m_dict)
    elif role == "tool":
        return ToolMessage(**m_dict)
    else:
        raise ValueError("Unknown message role")


class ResponseFormat(BaseModel):
    type: str = Field(default="text", pattern="^(text|json_object)$")


## tool_choice ##
class FunctionCall(BaseModel):
    name: str


class ToolFunctionChoice(BaseModel):
    # The type of the tool. Currently, only function is supported
    type: Literal["function"] = "function"
    # type: str = Field(default="function", const=True)
    function: FunctionCall


class AnthropicToolChoiceTool(BaseModel):
    type: str = "tool"
    name: str
    disable_parallel_tool_use: Optional[bool] = False


class AnthropicToolChoiceAny(BaseModel):
    type: str = "any"
    disable_parallel_tool_use: Optional[bool] = False


class AnthropicToolChoiceAuto(BaseModel):
    type: str = "auto"
    disable_parallel_tool_use: Optional[bool] = False


ToolChoice = Union[
    Literal["none", "auto", "required", "any"],
    ToolFunctionChoice,
    AnthropicToolChoiceTool,
    AnthropicToolChoiceAny,
    AnthropicToolChoiceAuto,
]


## tools ##
class FunctionSchema(BaseModel):
    name: str
    description: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None  # JSON Schema for the parameters
    strict: bool = False


class Tool(BaseModel):
    # The type of the tool. Currently, only function is supported
    type: Literal["function"] = "function"
    # type: str = Field(default="function", const=True)
    function: FunctionSchema


## function_call ##
FunctionCallChoice = Union[Literal["none", "auto"], FunctionCall]


class ChatCompletionRequest(BaseModel):
    """https://platform.openai.com/docs/api-reference/chat/create"""

    model: str
    messages: List[Union[ChatMessage, Dict]]
    frequency_penalty: Optional[float] = 0
    logit_bias: Optional[Dict[str, int]] = None
    logprobs: Optional[bool] = False
    top_logprobs: Optional[int] = None
    max_tokens: Optional[int] = None
    n: Optional[int] = 1
    presence_penalty: Optional[float] = 0
    response_format: Optional[ResponseFormat] = None
    seed: Optional[int] = None
    stop: Optional[Union[str, List[str]]] = None
    stream: Optional[bool] = False
    temperature: Optional[float] = 1
    top_p: Optional[float] = 1
    user: Optional[str] = None  # unique ID of the end-user (for monitoring)

    # function-calling related
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[ToolChoice] = None  # "none" means don't call a tool
    # deprecated scheme
    functions: Optional[List[FunctionSchema]] = None
    function_call: Optional[FunctionCallChoice] = None

    @field_validator("messages", mode="before")
    @classmethod
    def cast_all_messages(cls, v):
        return [cast_message_to_subtype(m) if isinstance(m, dict) else m for m in v]


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
    created: Union[datetime.datetime, str, int]
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
    created: Union[datetime.datetime, str, int]
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
    created: Union[datetime.datetime, str, int]
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
