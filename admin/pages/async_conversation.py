import streamlit as st
import asyncio
from openai import AsyncOpenAI, OpenAI
from core.database import connect_db, close_db, get_database, ProxyConfig
from typing import AsyncGenerator
import os


proxy_api_url = os.getenv("PROXY_API_URL", "http://localhost:8000/v1")


async def fetch_configs():
    db = get_database()
    configs = await db["configurations"].find().to_list(None)
    return [ProxyConfig(**config) for config in configs]


async def send_message_stream(
    proxy_model: str, message: str
) -> AsyncGenerator[str, None]:
    """Send a message to the API and stream the response using AsyncOpenAI"""
    try:
        # Create an AsyncOpenAI client pointing to our local proxy
        client = AsyncOpenAI(
            base_url=proxy_api_url,
            api_key="not-needed",  # The proxy doesn't require an API key
        )

        # Create the messages for the chat completion
        messages = [{"role": "user", "content": message}]

        # Make the streaming request
        stream = await client.chat.completions.create(
            model=proxy_model, messages=messages, stream=True
        )

        # Process the streaming response
        async for chunk in stream:
            # Extract content from the chunk if it exists
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                yield content

    except Exception as e:
        yield f"An unexpected error occurred: {e}"


async def send_message(proxy_model: str, message: str, stream: bool = True):
    """Send a message to the API with option for streaming or non-streaming response"""
    if stream:
        # For streaming, we'll return a generator
        return send_message_stream(proxy_model, message)

    # Non-streaming implementation using AsyncOpenAI
    try:
        # Create an AsyncOpenAI client pointing to our local proxy
        client = OpenAI(
            base_url="http://localhost:8000/v1",
            api_key="not-needed",  # The proxy doesn't require an API key
        )

        # Create the messages for the chat completion
        messages = [{"role": "user", "content": message}]

        # Make the non-streaming request
        response = client.chat.completions.create(
            model=proxy_model, messages=messages, stream=False
        )

        # Return the content from the response
        return response.choices[0].message.content
    except Exception as e:
        return f"An unexpected error occurred: {e}"


def main():
    # st.title("异步对话")
    # Run async functions in synchronous context
    asyncio.run(connect_db())
    configs = asyncio.run(fetch_configs())
    asyncio.run(close_db())

    if not configs:
        st.warning("请先在配置管理页面添加代理配置。")
        return

    model_names = [config.proxy_model_name for config in configs]
    selected_model = st.selectbox("选择代理模型", model_names)

    # Add streaming option with default as True
    use_streaming = st.checkbox("使用流式输出", value=True)

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
            if use_streaming:
                # Streaming mode using st.write_stream
                try:
                    # Use Streamlit's write_stream to handle the streaming response
                    full_response = st.write_stream(
                        send_message_stream(selected_model, prompt)
                    )
                except Exception as e:
                    st.error(f"Streaming error: {e}")
                    full_response = f"Error: {e}"
            else:
                # Non-streaming mode
                with st.spinner("思考中..."):
                    try:
                        # Run the async function in a synchronous context
                        full_response = asyncio.run(
                            send_message(selected_model, prompt, stream=False)
                        )
                        st.markdown(full_response)
                    except Exception as e:
                        st.error(f"Error: {e}")
                        full_response = f"Error: {e}"

            # Add to conversation history
            st.session_state.conversation_history.append(
                {"role": "assistant", "content": full_response}
            )


if __name__ == "__main__":
    main()
