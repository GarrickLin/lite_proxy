import streamlit as st
from core.database import connect_db, close_db, get_database, ProxyConfig
from typing import Optional
import asyncio


async def fetch_configs():
    db = get_database()
    configs = await db["configurations"].find().to_list(None)
    return [ProxyConfig(**config) for config in configs]


async def add_config(
    proxy_model_name: str,
    base_url: str,
    backend_model_name: str,
    backend_api_key: Optional[str],
    ignore_ssl_verify: bool,
):
    db = get_database()
    existing_config = await db["configurations"].find_one(
        {"proxy_model_name": proxy_model_name}
    )
    if existing_config:
        st.error(f"Proxy model name '{proxy_model_name}' already exists.")
        return False
    new_config = {
        "proxy_model_name": proxy_model_name,
        "base_url": base_url,
        "backend_model_name": backend_model_name,
        "backend_api_key": backend_api_key,
        "ignore_ssl_verify": ignore_ssl_verify,
    }
    await db["configurations"].insert_one(new_config)
    st.success("Configuration added successfully!")
    return True


async def update_config(
    proxy_model_name: str,
    new_base_url: str,
    new_backend_model_name: str,
    new_backend_api_key: Optional[str],
    new_ignore_ssl_verify: bool,
):
    db = get_database()
    result = await db["configurations"].update_one(
        {"proxy_model_name": proxy_model_name},
        {
            "$set": {
                "base_url": new_base_url,
                "backend_model_name": new_backend_model_name,
                "backend_api_key": new_backend_api_key,
                "ignore_ssl_verify": new_ignore_ssl_verify,
            }
        },
    )
    if result.modified_count > 0:
        st.success(f"Configuration for '{proxy_model_name}' updated successfully!")
        return True
    else:
        st.warning(
            f"Configuration for '{proxy_model_name}' not found or no changes were made."
        )
        return False


async def delete_config(proxy_model_name: str):
    db = get_database()
    result = await db["configurations"].delete_one(
        {"proxy_model_name": proxy_model_name}
    )
    if result.deleted_count > 0:
        st.success(f"Configuration for '{proxy_model_name}' deleted successfully!")
        return True
    else:
        st.warning(f"Configuration for '{proxy_model_name}' not found.")
        return False


async def amain():
    st.subheader("Current Configurations")
    await connect_db()
    configs = await fetch_configs()
    if configs:
        config_data = [
            {
                "Proxy Model Name": config.proxy_model_name,
                "Base URL": config.base_url,
                "Backend Model Name": config.backend_model_name,
                "Backend API Key": config.backend_api_key,
                "Ignore SSL Verify": config.ignore_ssl_verify,
            }
            for config in configs
        ]
        st.table(config_data)
    else:
        st.info("No configurations found.")

    st.subheader("Add New Configuration")
    with st.form("add_config_form"):
        new_proxy_model_name = st.text_input("Proxy Model Name", key="add_proxy_model")
        new_base_url = st.text_input("Base URL", key="add_base_url")
        new_backend_model_name = st.text_input(
            "Backend Model Name", key="add_backend_model"
        )
        new_backend_api_key = st.text_input(
            "Backend API Key (Optional)", key="add_backend_api_key", value=""
        )
        new_ignore_ssl_verify = st.checkbox(
            "Ignore SSL Verification", key="add_ignore_ssl_verify", value=False
        )
        submitted_add = st.form_submit_button("Add Configuration")
        if submitted_add:
            if await add_config(
                new_proxy_model_name,
                new_base_url,
                new_backend_model_name,
                new_backend_api_key,
                new_ignore_ssl_verify,
            ):
                st.rerun()

    st.subheader("Edit Configuration")
    edit_proxy_model_name = st.selectbox(
        "Select Proxy Model to Edit",
        [config.proxy_model_name for config in configs] if configs else "",
    )
    if edit_proxy_model_name:
        selected_config = next(
            (
                config
                for config in configs
                if config.proxy_model_name == edit_proxy_model_name
            ),
            None,
        )
        if selected_config:
            with st.form("edit_config_form"):
                edit_base_url = st.text_input(
                    "New Base URL", value=selected_config.base_url, key="edit_base_url"
                )
                edit_backend_model_name = st.text_input(
                    "New Backend Model Name",
                    value=selected_config.backend_model_name,
                    key="edit_backend_model",
                )
                edit_backend_api_key = st.text_input(
                    "New Backend API Key (Optional)",
                    value=selected_config.backend_api_key or "",
                    key="edit_backend_api_key",
                )
                edit_ignore_ssl_verify = st.checkbox(
                    "Ignore SSL Verification",
                    value=selected_config.ignore_ssl_verify,
                    key="edit_ignore_ssl_verify",
                )
                submitted_edit = st.form_submit_button("Update Configuration")
                if submitted_edit:
                    if await update_config(
                        edit_proxy_model_name,
                        edit_base_url,
                        edit_backend_model_name,
                        edit_backend_api_key,
                        edit_ignore_ssl_verify,
                    ):
                        st.rerun()

    st.subheader("Delete Configuration")
    delete_proxy_model_name = st.selectbox(
        "Select Proxy Model to Delete",
        [config.proxy_model_name for config in configs] if configs else "",
    )
    if delete_proxy_model_name:
        if st.button(f"Delete Configuration for '{delete_proxy_model_name}'"):
            if await delete_config(delete_proxy_model_name):
                st.rerun()
    await close_db()


def main():
    asyncio.run(amain())
