"""
任务结果页面

使用新架构的服务层
支持任务结果搜索、查看、下载
"""

from datetime import datetime
from typing import Optional

import pandas as pd
import streamlit as st

from src.di import container


def render(user_id: Optional[str] = None):
    """渲染任务结果页面"""
    st.header("📋 任务结果")

    client = container.scheduler_client

    st.subheader("🔍 搜索任务")

    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("搜索任务ID或内容", placeholder="输入任务ID或关键词...")
    with col2:
        display_count = st.number_input("显示数量", min_value=5, max_value=100, value=20, step=5)

    success, results = client.get_all_results()
    if success and results.get("results"):
        results_list = results["results"]

        if search_query:
            filtered_results = []
            for result in results_list:
                task_id = str(result.get("task_id", ""))
                result_text = str(result.get("result", ""))

                if search_query.lower() in task_id.lower() or search_query.lower() in result_text.lower():
                    filtered_results.append(result)
            results_list = filtered_results

        results_list = results_list[:display_count]

        if results_list:
            st.subheader(f"任务结果 ({len(results_list)} 条)")

            results_data = []
            for result in results_list:
                completed_at = result.get("completed_at")
                if completed_at:
                    time_str = datetime.fromtimestamp(completed_at).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    time_str = "N/A"

                result_text = result.get("result", "")
                if result_text and len(result_text) > 100:
                    result_preview = result_text[:100] + "..."
                else:
                    result_preview = result_text or "无结果"

                results_data.append({
                    "任务ID": result.get("task_id", "N/A"),
                    "完成时间": time_str,
                    "执行节点": result.get("assigned_node", "未知"),
                    "结果预览": result_preview
                })

            results_df = pd.DataFrame(results_data)
            st.dataframe(results_df, use_container_width=True, hide_index=True)

            st.markdown("---")

            st.subheader("📄 查看完整结果")

            selected_task_id = st.selectbox(
                "选择任务查看完整结果",
                [r.get("task_id", "N/A") for r in results_list]
            )

            if selected_task_id:
                full_result = None
                for result in results_list:
                    if str(result.get("task_id")) == str(selected_task_id):
                        full_result = result
                        break

                if full_result:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("任务ID", selected_task_id)
                    with col2:
                        completed_at = full_result.get("completed_at")
                        if completed_at:
                            st.metric("完成时间", datetime.fromtimestamp(completed_at).strftime("%H:%M:%S"))
                    with col3:
                        st.metric("执行节点", full_result.get("assigned_node", "未知"))

                    st.markdown("---")

                    st.subheader("执行结果")
                    result_text = full_result.get("result", "")
                    if result_text:
                        st.code(result_text, language="text")

                        st.download_button(
                            label="📥 下载结果",
                            data=result_text,
                            file_name=f"task_{selected_task_id}_result.txt",
                            mime="text/plain"
                        )
                    else:
                        st.info("该任务没有结果")

                    if full_result.get("required_resources"):
                        st.markdown("---")
                        st.subheader("资源使用")
                        resources = full_result["required_resources"]
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("CPU核心", resources.get("cpu", "N/A"))
                        with col2:
                            st.metric("内存(MB)", resources.get("memory", "N/A"))
        else:
            st.info("没有找到匹配的任务结果")
    else:
        st.info("暂无任务结果")

    st.markdown("---")

    st.subheader("📊 结果统计")

    if success and results.get("results"):
        all_results = results["results"]

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("总结果数", len(all_results))
        with col2:
            nodes_used = {r.get("assigned_node") for r in all_results if r.get("assigned_node")}
            st.metric("使用节点数", len(nodes_used))
        with col3:
            total_size = sum(len(str(r.get("result", ""))) for r in all_results)
            st.metric("总数据量", f"{total_size / 1024:.2f} KB")


__all__ = ["render"]
