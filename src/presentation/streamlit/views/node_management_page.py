"""
节点管理页面

使用新架构的服务层
支持节点激活、停止、状态查看
"""

import time
from typing import Optional

import pandas as pd
import streamlit as st

from src.presentation.streamlit.utils.di_utils import container


def render(user_id: Optional[str] = None):
    """渲染节点管理页面"""
    st.header("🖥️ 节点管理")

    client = container.scheduler_client()

    success, result = client.get_all_nodes()
    if success and result:
        nodes_list = result.get("nodes", [])
        if nodes_list:
            st.subheader(f"活跃节点 ({len(nodes_list)})")

            nodes_data = []
            for node_info in nodes_list:
                node_id = node_info.get("node_id", "unknown")
                status = node_info.get("status", "unknown")
                status_emoji = {"在线": "🟢", "离线": "🔴", "忙碌": "🟡"}.get(status, "⚪")

                capacity = node_info.get("capacity", {})
                nodes_data.append(
                    {
                        "节点ID": node_id[:12] + "..." if len(node_id) > 12 else node_id,
                        "状态": f"{status_emoji} {status}",
                        "CPU核心": capacity.get("cpu", "N/A"),
                        "内存(MB)": capacity.get("memory", "N/A"),
                        "当前任务": node_info.get("current_task", "无") or "无",
                        "所有者": node_info.get("owner", "未知"),
                    }
                )

            if nodes_data:
                nodes_df = pd.DataFrame(nodes_data)
                st.dataframe(nodes_df, width="stretch", hide_index=True)
            else:
                st.info("暂无活跃节点")

            st.markdown("---")

            st.subheader("节点详情")
            node_options = {node.get("node_id", "unknown"): node for node in nodes_list}
            selected_node = st.selectbox(
                "选择节点查看详情", list(node_options.keys()), format_func=lambda x: x[:12] + "..."
            )

            if selected_node and selected_node in node_options:
                node_info = node_options[selected_node]

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("节点ID", selected_node[:16] + "...")
                with col2:
                    status = node_info.get("status", "unknown")
                    status_emoji = {"在线": "🟢", "离线": "🔴", "忙碌": "🟡"}.get(status, "⚪")
                    st.metric("状态", f"{status_emoji} {status}")
                with col3:
                    st.metric("所有者", node_info.get("owner", "未知"))

                col1, col2 = st.columns(2)
                capacity = node_info.get("capacity", {})
                with col1:
                    st.metric("CPU核心数", capacity.get("cpu", "N/A"))
                with col2:
                    st.metric("内存(MB)", capacity.get("memory", "N/A"))

                if node_info.get("current_task"):
                    st.info(f"当前任务: {node_info['current_task']}")
        else:
            st.info("暂无活跃节点，请先激活节点")
    else:
        st.info("暂无活跃节点，请先激活节点")

    st.markdown("---")

    st.subheader("🔧 节点操作")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🚀 激活节点")
        st.write("将您的设备注册为计算节点，参与分布式计算")

        node_cpu = st.slider("分配CPU核心数", 0.5, 16.0, 4.0, 0.5, key="node_cpu")
        node_memory = st.slider("分配内存(MB)", 512, 32768, 4096, 512, key="node_memory")

        if st.button("🚀 激活节点", type="primary", width="stretch"):
            with st.spinner("激活中..."):
                success, result = client.activate_local_node(
                    cpu_limit=node_cpu,
                    memory_limit=node_memory,
                    storage_limit=10240,
                    user_id=user_id,
                )

                if success:
                    node_id = result.get("node_id")
                    st.success(f"✅ 节点激活成功！节点ID: `{node_id}`")
                    st.session_state.active_node_id = node_id
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ 激活失败: {result.get('error', '未知错误')}")

    with col2:
        st.markdown("#### 🛑 停止节点")
        st.write("停止当前节点的计算服务")

        if st.session_state.get("active_node_id"):
            st.info(f"当前节点: {st.session_state.active_node_id[:12]}...")

            if st.button("🛑 停止节点", type="secondary", width="stretch"):
                with st.spinner("停止中..."):
                    success, result = client.stop_node(st.session_state.active_node_id)

                    if success:
                        st.success("✅ 节点已停止")
                        st.session_state.active_node_id = None
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ 停止失败: {result.get('error', '未知错误')}")
        else:
            st.info("当前没有活跃的节点")

    st.markdown("---")

    st.subheader("📊 节点统计")

    success, stats = client.get_system_stats()
    if success:
        nodes_info = stats.get("nodes", {})
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总节点数", nodes_info.get("total", 0))
        with col2:
            st.metric("空闲节点", nodes_info.get("idle", 0))
        with col3:
            st.metric("忙碌节点", nodes_info.get("busy", 0))
        with col4:
            st.metric("离线节点", nodes_info.get("offline", 0))


__all__ = ["render"]
