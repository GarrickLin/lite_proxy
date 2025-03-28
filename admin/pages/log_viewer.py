import streamlit as st
import asyncio
import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from core.database import connect_db, close_db, get_database, LogEntry
from typing import List, Dict, Any, Optional
import pandas as pd
import time


async def fetch_logs(
    limit: int = 100, 
    skip: int = 0, 
    query: Dict[str, Any] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status_code: Optional[int] = None,
    request_path: Optional[str] = None,
    request_method: Optional[str] = None
):
    """获取日志记录，支持分页和过滤"""
    db = get_database()
    
    # 构建查询条件
    filter_query = query or {}
    
    # 添加日期范围过滤
    if start_date or end_date:
        date_query = {}
        if start_date:
            date_query["$gte"] = start_date
        if end_date:
            date_query["$lte"] = end_date
        if date_query:
            filter_query["timestamp"] = date_query
    
    # 添加状态码过滤
    if status_code:
        filter_query["response_status_code"] = status_code
    
    # 添加请求路径过滤
    if request_path:
        filter_query["request_path"] = {"$regex": request_path, "$options": "i"}
    
    # 添加请求方法过滤
    if request_method:
        filter_query["request_method"] = request_method
    
    # 执行查询
    cursor = db["logs"].find(filter_query).sort("timestamp", -1).skip(skip).limit(limit)
    logs = await cursor.to_list(length=limit)
    
    # 获取总数
    total_count = await db["logs"].count_documents(filter_query)
    
    return logs, total_count


def process_stream_data(data):
    """处理流式响应数据，尝试将每个数据块解析为JSON，并连接content部分"""
    if not isinstance(data, str):
        return data
        
    # 检查是否是流式响应格式
    if not data.startswith('data:') and '{"' not in data:
        return data
        
    # 尝试提取所有的JSON块
    combined_content = ""
    json_objects = []
    
    # 处理SSE格式的数据（data: {...}\n\n）
    if 'data:' in data:
        # 分割数据块
        chunks = re.split(r'\n\n', data)
        for chunk in chunks:
            if not chunk.strip():
                continue
                
            # 处理每个数据块
            if chunk.startswith('data:'):
                json_str = chunk[5:].strip()
                try:
                    json_obj = json.loads(json_str)
                    json_objects.append(json_obj)
                    
                    # 提取content字段
                    if 'choices' in json_obj and len(json_obj['choices']) > 0:
                        if 'delta' in json_obj['choices'][0] and 'content' in json_obj['choices'][0]['delta']:
                            combined_content += json_obj['choices'][0]['delta']['content']
                        elif 'text' in json_obj['choices'][0]:
                            combined_content += json_obj['choices'][0]['text']
                except json.JSONDecodeError:
                    pass  # 忽略无法解析的块
    
    # 如果没有有效的JSON对象，返回原始数据
    if not json_objects:
        return data
        
    # 创建结果对象
    result = {
        "original_chunks": json_objects,
        "combined_content": combined_content
    }
    
    return result


def format_json(data):
    """格式化JSON数据以便于显示"""
    if data is None:
        return {}
        
    # 如果是字典类型，直接返回
    if isinstance(data, dict):
        return data
        
    # 如果是字符串，尝试先处理流式数据
    if isinstance(data, str):
        # 先尝试处理流式数据
        if 'data:' in data or '\n\n' in data:
            stream_result = process_stream_data(data)
            if isinstance(stream_result, dict) and 'combined_content' in stream_result:
                return stream_result
                
        # 如果不是流式数据，尝试解析为JSON
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            # 如果无法解析为JSON，返回原始字符串
            return data
    
    # 其他类型，转换为字符串
    return str(data)


def format_timestamp(timestamp):
    """格式化时间戳为易读格式，并转换为当前时区"""
    if isinstance(timestamp, datetime):
        # 确保时间戳有时区信息（MongoDB通常存储UTC时间）
        if timestamp.tzinfo is None:
            # 如果时间没有时区信息，假设它是UTC时间
            timestamp = timestamp.replace(tzinfo=ZoneInfo("UTC"))
        
        try:
            # 获取当前系统时区
            # 尝试使用系统时区
            local_timezone = ZoneInfo(time.tzname[0])
        except:
            # 如果无法获取系统时区，使用东八区作为默认值
            local_timezone = ZoneInfo("Asia/Shanghai")
        
        # 转换为当前时区
        local_time = timestamp.astimezone(local_timezone)
        
        # 格式化为易读格式
        return local_time.strftime("%Y-%m-%d %H:%M:%S")
    return str(timestamp)


def display_log_details(log):
    """显示日志详情"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("请求信息")
        st.write(f"**方法:** {log.get('request_method')}")
        st.write(f"**路径:** {log.get('request_path')}")
        st.write(f"**时间:** {format_timestamp(log.get('timestamp'))}")
        
        with st.expander("请求头"):
            st.json(log.get('request_headers', {}))
        
        with st.expander("请求体"):
            request_body = log.get('request_body')
            if request_body is None:
                st.write("*无请求体数据*")
            else:
                formatted_data = format_json(request_body)
                # 判断格式化后的数据类型
                if isinstance(formatted_data, dict):
                    # 如果是字典，使用JSON格式显示
                    st.json(formatted_data)
                elif isinstance(formatted_data, str):
                    # 判断字符串是否过长
                    if len(formatted_data) > 5000:
                        st.warning("请求体内容过长")
                        # 显示前5000个字符
                        st.code(formatted_data[:5000] + "...")
                    else:
                        st.code(formatted_data)
                else:
                    # 其他类型
                    st.write(formatted_data)
    
    with col2:
        st.subheader("响应信息")
        status_code = log.get('response_status_code')
        status_color = "green" if status_code < 400 else "red"
        st.write(f"**状态码:** :{status_color}[{status_code}]")
        st.write(f"**处理时间:** {log.get('processing_time', 0):.4f} 秒")
        
        with st.expander("响应头"):
            st.json(log.get('response_headers', {}))
        
        # 响应体处理
        response_body = log.get('response_body')
        if response_body is None:
            with st.expander("响应体"):
                st.write("*无响应体数据*")
        else:
            formatted_data = format_json(response_body)
            
            # 处理流式响应的特殊情况
            if isinstance(formatted_data, dict) and 'combined_content' in formatted_data:
                # 分开显示响应体和原始数据块
                with st.expander("响应体 (流式响应) - 合并后的内容"):
                    st.write(formatted_data['combined_content'])
                
                with st.expander("原始数据块"):
                    st.json(formatted_data['original_chunks'])
            
            # 处理普通字典
            elif isinstance(formatted_data, dict):
                with st.expander("响应体"):
                    # 如果是字典，使用JSON格式显示
                    st.json(formatted_data)
            
            # 处理字符串
            elif isinstance(formatted_data, str):
                with st.expander("响应体"):
                    # 判断字符串是否过长
                    if len(formatted_data) > 5000:
                        st.warning("响应体内容过长，可能是流式响应或二进制数据")
                        # 显示前5000个字符
                        st.code(formatted_data[:5000] + "...")
                    else:
                        st.code(formatted_data)
            else:
                # 其他类型
                with st.expander("响应体"):
                    st.write(formatted_data)


def create_log_dataframe(logs):
    """将日志转换为DataFrame以便于显示"""
    data = []
    for log in logs:
        data.append({
            "时间": format_timestamp(log.get("timestamp")),
            "方法": log.get("request_method"),
            "路径": log.get("request_path"),
            "状态码": log.get("response_status_code"),
            "处理时间(秒)": round(log.get("processing_time", 0), 4),
            "原始数据": log
        })
    return pd.DataFrame(data)


def main():
    st.title("日志查询")
    
    # 连接数据库
    asyncio.run(connect_db())
    
    # 创建过滤器
    with st.expander("过滤选项", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            # 日期范围选择
            today = datetime.now()
            yesterday = today - timedelta(days=1)
            start_date = st.date_input("开始日期", value=yesterday, key="log_viewer_start_date")
            end_date = st.date_input("结束日期", value=today, key="log_viewer_end_date")
            
            # 将日期转换为datetime对象
            start_datetime = datetime.combine(start_date, datetime.min.time()) if start_date else None
            end_datetime = datetime.combine(end_date, datetime.max.time()) if end_date else None
            
            # 请求方法选择
            request_method = st.selectbox(
                "请求方法", 
                options=["全部", "GET", "POST", "PUT", "DELETE"],
                index=0,
                key="log_viewer_request_method"
            )
            if request_method == "全部":
                request_method = None
        
        with col2:
            # 状态码选择
            status_options = ["全部", "成功 (2xx)", "重定向 (3xx)", "客户端错误 (4xx)", "服务器错误 (5xx)"]
            status_selection = st.selectbox("状态码", options=status_options, index=0, key="log_viewer_status_code")
            
            status_code_filter = None
            if status_selection == "成功 (2xx)":
                status_code_filter = {"$gte": 200, "$lt": 300}
            elif status_selection == "重定向 (3xx)":
                status_code_filter = {"$gte": 300, "$lt": 400}
            elif status_selection == "客户端错误 (4xx)":
                status_code_filter = {"$gte": 400, "$lt": 500}
            elif status_selection == "服务器错误 (5xx)":
                status_code_filter = {"$gte": 500, "$lt": 600}
            
            # 路径搜索
            request_path = st.text_input("请求路径包含", key="log_viewer_request_path")
            if not request_path:
                request_path = None
    
    # 分页控制
    page_size = st.selectbox("每页显示", options=[10, 20, 50, 100], index=1, key="log_viewer_page_size")
    
    # 页码管理
    if "log_viewer_page_number" not in st.session_state:
        st.session_state.log_viewer_page_number = 0
    
    # 构建查询条件
    query = {}
    if status_code_filter:
        query["response_status_code"] = status_code_filter
    
    # 获取日志数据
    logs, total_count = asyncio.run(
        fetch_logs(
            limit=page_size,
            skip=st.session_state.log_viewer_page_number * page_size,
            query=query,
            start_date=start_datetime,
            end_date=end_datetime,
            request_path=request_path,
            request_method=request_method
        )
    )
    
    # 显示分页信息
    total_pages = (total_count + page_size - 1) // page_size
    st.write(f"共 {total_count} 条记录，当前第 {st.session_state.log_viewer_page_number + 1}/{max(1, total_pages)} 页")
    
    # 分页控制按钮
    col1, col2, col3, col4 = st.columns([1, 1, 2, 1])
    with col1:
        if st.button("上一页", key="log_viewer_prev_page") and st.session_state.log_viewer_page_number > 0:
            st.session_state.log_viewer_page_number -= 1
            st.rerun()
    
    with col2:
        if st.button("下一页", key="log_viewer_next_page") and st.session_state.log_viewer_page_number < total_pages - 1:
            st.session_state.log_viewer_page_number += 1
            st.rerun()
    
    with col4:
        if st.button("刷新", key="log_viewer_refresh"):
            st.rerun()
    
    # 将日志转换为DataFrame
    if logs:
        df = create_log_dataframe(logs)
        
        # 显示日志表格
        st.dataframe(
            df.drop(columns=["原始数据"]), 
            use_container_width=True,
            hide_index=True
        )
        
        # 选择日志查看详情
        selected_log_index = st.selectbox(
            "选择日志查看详情", 
            range(len(logs)), 
            format_func=lambda i: f"{df.iloc[i]['时间']} - {df.iloc[i]['方法']} {df.iloc[i]['路径']} ({df.iloc[i]['状态码']})",
            key="log_viewer_selected_log"
        )
        
        if selected_log_index is not None:
            st.divider()
            display_log_details(logs[selected_log_index])
    else:
        st.info("没有找到符合条件的日志记录")
    
    # 关闭数据库连接
    asyncio.run(close_db())


if __name__ == "__main__":
    main()
