import streamlit as st
import httpx
from core.database import connect_db, close_db, get_database, ProxyConfig
from typing import List, Dict, Any


async def fetch_configs():
    db = get_database()
    configs = await db["configurations"].find().to_list(None)
    return [ProxyConfig(**config) for config in configs]


async def send_message(proxy_model: str, message: str):
    headers = {"Content-Type": "application/json"}
    payload = {"model": proxy_model, "messages": [{"role": "user", "content": message}]}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8000/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        return f"Error: {e}"
    except httpx.ConnectError as e:
        return f"Error: Could not connect to the proxy API: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"


# async def send_message(proxy_model: str, message: str, api_key: str = ""):
#     # headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
#     # payload = {"model": proxy_model, "messages": [{"role": "user", "content": message}]}
#     payload = {
#         "model": proxy_model,
#         "messages": [{"role": "user", "content": message}],
#         "temperature": 1.0,
#         "top_p": 1.0,
#         "n": 1,
#         "stream": False,
#         # "max_tokens": None,
#         "presence_penalty": 0.0,
#         "frequency_penalty": 0.0,
#     }

#     # 打印请求信息以便调试
#     # print(f"Request Headers: {headers}")
#     print(f"Request Payload: {payload}")

#     try:
#         async with httpx.AsyncClient() as client:
#             response = await client.post(
#                 "http://localhost:8000/v1/chat/completions",
#                 # headers=headers,
#                 json=payload,
#                 timeout=30.0,
#             )
#             # 打印响应信息
#             print(f"Response Status: {response.status_code}")
#             print(f"Response Headers: {response.headers}")
#             print(f"Response Body: {response.text}")

#             response.raise_for_status()
#             return response.json()["choices"][0]["message"]["content"]
#     except httpx.HTTPStatusError as e:
#         print(f"Full error response: {e.response.text}")
#         return f"Error: {e}"
#     except Exception as e:
#         return f"An unexpected error occurred: {e}"


async def main():
    st.subheader("异步对话")

    await connect_db()
    configs = await fetch_configs()
    await close_db()

    if not configs:
        st.warning("请先在配置管理页面添加代理配置。")
        return

    # st.write(configs)

    model_names = [config.proxy_model_name for config in configs]
    selected_model = st.selectbox("选择代理模型", model_names)

    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []

    for message in st.session_state.conversation_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("请输入你的消息")
    if prompt:
        st.session_state.conversation_history.append(
            {"role": "user", "content": prompt}
        )
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                response = await send_message(selected_model, prompt)
                st.markdown(response)
                st.session_state.conversation_history.append(
                    {"role": "assistant", "content": response}
                )
