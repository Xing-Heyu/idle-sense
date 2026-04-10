"""
系统统计页面

使用新架构的服务层
支持任务统计、节点统计、性能图表
"""

from typing import Optional

import pandas as pd
import plotly.express as px
import streamlit as st

from src.presentation.streamlit.utils.di_utils import container


def render(user_id: Optional[str] = None):
    """渲染系统统计页面"""
    st.header("📈 系统统计")

    client = container.scheduler_client

    success, stats = client.get_system_stats()
    if success:
        nodes_info = stats.get("nodes", {})
        tasks_info = stats.get("tasks", {})

        st.subheader("📊 调度器统计")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总任务数", tasks_info.get("total", 0))
        with col2:
            st.metric("待处理", tasks_info.get("total", 0) - tasks_info.get("completed", 0) - tasks_info.get("failed", 0))
        with col3:
            st.metric("运行中", tasks_info.get("running", 0))
        with col4:
            st.metric("已完成", tasks_info.get("completed", 0))

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总节点数", nodes_info.get("total", 0))
        with col2:
            st.metric("空闲节点", nodes_info.get("idle", 0))
        with col3:
            st.metric("忙碌节点", nodes_info.get("busy", 0))
        with col4:
            st.metric("离线节点", nodes_info.get("offline", 0))

        st.markdown("---")

        st.subheader("📊 任务状态分布")

        task_status_data = {
            "状态": ["已完成", "失败", "进行中"],
            "数量": [
                tasks_info.get("completed", 0),
                tasks_info.get("failed", 0),
                max(0, tasks_info.get("total", 0) - tasks_info.get("completed", 0) - tasks_info.get("failed", 0))
            ]
        }

        fig_pie = px.pie(
            task_status_data,
            values="数量",
            names="状态",
            title="任务状态分布",
            hole=0.4
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, width="stretch")

        st.markdown("---")

        st.subheader("📊 节点状态分布")

        node_status_data = {
            "状态": ["空闲", "忙碌", "离线"],
            "数量": [
                nodes_info.get("idle", 0),
                nodes_info.get("busy", 0),
                nodes_info.get("offline", 0)
            ]
        }

        fig_bar = px.bar(
            node_status_data,
            x="状态",
            y="数量",
            title="节点状态分布",
            color="状态",
            color_discrete_map={"空闲": "#2ecc71", "忙碌": "#f1c40f", "离线": "#e74c3c"}
        )
        st.plotly_chart(fig_bar, width="stretch")

    else:
        st.warning(f"获取统计信息失败: {stats.get('error', '未知错误')}")

    st.markdown("---")

    st.subheader("📋 用户任务结果")

    success, response = client.get_all_results()
    if success and response:
        results_list = response.get("results", [])
        user_results = []
        for result in results_list:
            if isinstance(result, dict) and result.get("assigned_node"):
                user_results.append({
                    "任务ID": result.get("task_id", "N/A"),
                    "状态": result.get("status", "未知"),
                    "执行节点": result.get("assigned_node", "未知"),
                    "结果预览": (result.get("result", "") or "")[:50] + "..." if result.get("result") else "无结果"
                })

        if user_results:
            results_df = pd.DataFrame(user_results)
            st.dataframe(results_df, width="stretch", hide_index=True)
        else:
            st.info("暂无用户任务结果")
    else:
        st.info("暂无任务结果")

    st.markdown("---")

    st.subheader("📊 计算时数统计")

    if user_id:
        token_service = container.token_economy_service
        account = token_service.get_or_create_account(user_id)

        if account:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("账户余额", f"{account.balance} CMP")
            with col2:
                st.metric("累计消费", f"{account.total_spent} CMP")
            with col3:
                st.metric("累计收益", f"{account.total_earned} CMP")


__all__ = ["render"]
