# Lite Proxy

一个轻量级的 OpenAI 兼容 API 代理服务，支持多后端配置、请求转发、日志记录和管理界面。

**注：本项目所有代码均由 AI 生成** 

## 功能特点

- **多后端配置**：支持配置多个不同的 API 后端，实现灵活的请求路由
- **请求转发**：将请求无缝转发到配置的后端服务
- **流式响应支持**：完整支持 OpenAI 流式响应格式（SSE）
- **日志记录**：详细记录所有请求和响应信息，便于调试和分析
- **管理界面**：基于 Streamlit 的直观管理界面，包含以下功能：
  - 配置管理：添加、编辑和删除代理配置
  - 日志查看器：查看和筛选请求日志，支持查看详细请求和响应信息
  - 异步对话：直接在界面中测试 API 功能

## 安装说明

### 前置条件

- Python 3.8+
- MongoDB

### 安装步骤

1. 克隆仓库

```bash
git clone https://github.com/garricklin/lite_proxy.git
cd lite_proxy
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 创建配置文件

在项目根目录创建 `.env` 文件，添加以下配置：

```
MONGODB_URI=mongodb://localhost:27017
DATABASE_NAME=lite_proxy
```

## 使用方法

### 方式一：直接启动

#### 启动代理服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

服务将在 `http://localhost:8000` 上运行。

#### 启动管理界面

```bash
streamlit run admin/gui.py
```

管理界面将在 `http://localhost:8501` 上运行。

### 方式二：Docker Compose启动

项目已经配置好了 Docker Compose，可以一键启动所有服务：

```bash
# 构建并启动所有服务
$ docker compose up -d

# 查看运行状态
$ docker compose ps

# 查看日志
$ docker compose logs -f

# 停止服务
$ docker compose down
```

Docker Compose 将启动以下三个服务：

- **proxy-api**：API 代理服务，运行在 http://localhost:8000
- **proxy-admin**：管理界面，运行在 http://localhost:8501
- **proxy-db**：MongoDB 数据库，运行在 localhost:27017

### API 使用示例

配置好代理后，可以像使用 OpenAI API 一样使用：

```python
import requests

url = "http://localhost:8000/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer your-api-key"
}
data = {
    "model": "your-configured-model-name",
    "messages": [
        {"role": "user", "content": "Hello, how are you?"}
    ]
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

## 项目架构

### 目录结构

```
lite_proxy/
├── admin/              # 管理界面
│   ├── gui.py          # 主界面入口
│   └── pages/          # 页面组件
│       ├── async_conversation.py  # 异步对话页面
│       ├── config_management.py   # 配置管理页面
│       └── log_viewer.py          # 日志查看器页面
├── core/               # 核心组件
│   ├── config.py       # 配置管理
│   └── database.py     # 数据库连接和模型
├── proxy/              # 代理服务
│   ├── api_routes.py   # API 路由定义
│   ├── models.py       # 数据模型
│   └── proxy_logic.py  # 代理逻辑实现
├── main.py             # 主程序入口
└── requirements.txt    # 项目依赖
```

### 技术栈

- **FastAPI**：高性能 API 框架
- **Streamlit**：管理界面
- **MongoDB**：数据存储
- **Motor**：异步 MongoDB 驱动
- **HTTPX**：异步 HTTP 客户端

## 特色功能

### 流式响应处理

本项目特别优化了对流式响应（Streaming Response）的处理，能够正确捕获、存储和显示流式响应数据。在日志查看器中，流式响应会被解析并合并显示，同时保留原始数据块以供调试。

### 灵活的代理配置

每个代理配置包含以下信息：
- 代理模型名称：客户端请求使用的模型名称
- 后端 URL：实际的 API 后端 URL
- 后端模型名称：发送给后端的模型名称
- 后端 API 密钥：用于访问后端 API 的密钥

这种设计允许您将多个不同的模型名称映射到不同的后端服务，实现灵活的 API 管理。

## 贡献指南

欢迎提交 Issue 和 Pull Request 来帮助改进项目。

## 许可证

[MIT](LICENSE)
