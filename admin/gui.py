import sys, os

sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), ".."))

import streamlit as st
import asyncio

# 设置页面标题
st.set_page_config(page_title="Lite Proxy Admin", page_icon="⚙️")

# 导入各个页面的内容
from admin.pages import config_management, async_conversation

st.sidebar.title("Lite Proxy 管理")

page = st.sidebar.selectbox("选择功能", ["配置管理", "异步对话"])

if page == "配置管理":
    asyncio.run(config_management.main())
elif page == "异步对话":
    asyncio.run(async_conversation.main())
