from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from core.config import MONGODB_URI, DATABASE_NAME

client: AsyncIOMotorClient = None


async def connect_db():
    global client
    client = AsyncIOMotorClient(MONGODB_URI)


async def close_db():
    global client
    if client:
        client.close()


def get_database():
    return client[DATABASE_NAME]


# 数据模型
class ProxyConfig(BaseModel):
    proxy_model_name: str
    base_url: str
    backend_model_name: str
    backend_api_key: Optional[str] = None
    ignore_ssl_verify: bool = False


class LogEntry(BaseModel):
    timestamp: datetime = datetime.now(timezone.utc)
    request_method: str
    request_path: str
    request_headers: Dict[str, Any]
    request_body: Optional[Dict[str, Any]] = None
    response_status_code: int
    response_headers: Dict[str, Any]
    response_body: Optional[Dict[str, Any]] = None
    processing_time: float
