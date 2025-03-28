import sys, os

sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), ".."))

import streamlit as st
from admin.pages import config_management, async_conversation, log_viewer

# 设置页面标题和图标
st.set_page_config(page_title="Lite Proxy Admin", page_icon="⚙️", layout="wide")

# 使用 st.navigation 进行页面导航
pg = st.navigation(
    [
        "pages/config_management.py",
        "pages/async_conversation.py",
        "pages/log_viewer.py",
    ],
    # default_page="pages/config_management.py"
)

# 运行导航
pg.run()
