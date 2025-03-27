from fastapi import FastAPI
from fastapi.routing import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse
import asyncio

from core.database import connect_db, close_db
from proxy.api_routes import router as proxy_router


async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="Lite Proxy",
    version="0.1.0",
    description="A lightweight proxy for OpenAI-compatible APIs.",
    lifespan=lifespan,
)


# 健康检查接口
@app.get("/health")
async def health_check():
    return {"status": "ok"}


app.include_router(proxy_router, prefix="/v1")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
