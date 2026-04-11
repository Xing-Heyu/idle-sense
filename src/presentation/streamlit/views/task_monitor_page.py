"""
任务监控页面

使用新架构的服务层
支持任务状态查看、删除、历史记录
"""

import time
from datetime import datetime
from typing import Optional

import pandas as pd
import streamlit as st

from src.presentation.streamlit.utils.di_utils import container


def render(user_id: Optional[str] = None):
    """渲染任务监控页面"""
    st.header("📊 任务监控")

    if st.button("🔄 刷新任务列表"):
        st.rerun()

    task_monitor_type = st.radio(
        "监控任务类型", ["所有任务", "单节点任务", "分布式任务"], horizontal=True
    )

    client = container.scheduler_client()
    success, results = client.get_all_results()

    if success and results.get("results"):
        results_list = results["results"]

        if results_list:
            st.subheader("已完成的任务")

            results_data = []
            for result in results_list:
                task_type = "单节点任务"
                task_id = result.get("task_id", "N/A")

                if st.session_state.get("task_history"):
                    for task in st.session_state.task_history:
                        if task.get("task_id") == str(task_id) and task.get("type") == "分布式任务":
                            task_type = "分布式任务"
                            break

                if (
                    task_monitor_type == "所有任务"
                    or (task_monitor_type == "单节点任务" and task_type == "单节点任务")
                    or (task_monitor_type == "分布式任务" and task_type == "分布式任务")
                ):

                    completed_at = result.get("completed_at")
                    if completed_at:
                        time_str = datetime.fromtimestamp(completed_at).strftime("%H:%M:%S")
                    else:
                        time_str = "N/A"

                    result_text = result.get("result", "")
                    if result_text and len(result_text) > 50:
                        result_preview = result_text[:50] + "..."
                    else:
                        result_preview = result_text or "无结果"

                    results_data.append(
                        {
                            "任务ID": task_id,
                            "任务类型": task_type,
                            "完成时间": time_str,
                            "执行节点": result.get("assigned_node", "未知"),
                            "结果预览": result_preview,
                        }
                    )

            if results_data:
                results_df = pd.DataFrame(results_data)
                st.dataframe(results_df, width="stretch", hide_index=True)

                selected_task_id = st.selectbox(
                    "选择任务查看完整结果", [r["任务ID"] for r in results_data],
                    key="task_monitor_select_task"
                )

                if selected_task_id:
                    full_result = None
                    task_type = "单节点任务"

                    for result in results_list:
                        if str(result.get("task_id")) == str(selected_task_id):
                            full_result = result
                            break

                    if st.session_state.get("task_history"):
                        for task in st.session_state.task_history:
                            if task.get("task_id") == str(selected_task_id):
                                task_type = task.get("type", "单节点任务")
                                break

                    if full_result and full_result.get("result"):
                        st.subheader(f"任务 {selected_task_id} 的完整结果")
                        st.code(full_result["result"], language="text")

                        if task_type == "分布式任务":
                            distributed_client = container.distributed_task_client()
                            if distributed_client.is_available:
                                st.subheader("分布式任务详情")

                                status_success, status_info = distributed_client.get_status(
                                    selected_task_id
                                )
                                if status_success:
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("总分片数", status_info.get("total_chunks", 0))
                                    with col2:
                                        st.metric(
                                            "已完成分片", status_info.get("completed_chunks", 0)
                                        )
                                    with col3:
                                        st.metric("失败分片", status_info.get("failed_chunks", 0))

                                    progress = status_info.get("progress", 0)
                                    st.progress(progress)
                                    st.write(f"任务进度: {progress:.1%}")
                                else:
                                    st.warning(
                                        f"无法获取分布式任务状态: {status_info.get('error', '未知错误')}"
                                    )
            else:
                st.info(f"没有找到{task_monitor_type}的已完成任务")
        else:
            st.info("暂无已完成的任务")
    elif not success:
        st.warning(f"获取任务结果失败: {results.get('error', '未知错误')}")

    st.markdown("---")

    if st.session_state.get("task_history"):
        st.subheader("任务历史记录")

        history_df = pd.DataFrame(st.session_state.task_history)

        if task_monitor_type != "所有任务":
            filtered_history = history_df[history_df["type"] == task_monitor_type]
        else:
            filtered_history = history_df

        if not filtered_history.empty:
            st.dataframe(filtered_history, width="stretch", hide_index=True)

            st.subheader("🗑️ 任务删除")

            deletable_tasks = []
            for task_id in history_df["task_id"].tolist():
                success, task_info = client.get_task_status(task_id)
                if success and task_info.get("status") in ["pending", "assigned", "running"]:
                    deletable_tasks.append(
                        {"task_id": task_id, "status": task_info.get("status", "unknown")}
                    )

            if deletable_tasks:
                task_options = {
                    f"任务{task['task_id']} (状态: {task['status']})": task["task_id"]
                    for task in deletable_tasks
                }
                selected_task_label = st.selectbox("选择要删除的任务", list(task_options.keys()), key="task_monitor_delete_task")
                selected_task_id = task_options[selected_task_label]

                if st.button("🗑️ 删除选中任务", type="secondary"):
                    with st.spinner("删除中..."):
                        delete_success, delete_result = client.delete_task(selected_task_id)

                        if delete_success:
                            st.success("✅ 任务删除成功！")
                            st.session_state.task_history = [
                                task
                                for task in st.session_state.task_history
                                if task["task_id"] != selected_task_id
                            ]
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(f"❌ 删除失败: {delete_result.get('error', '未知错误')}")
            else:
                st.info("暂无可以删除的任务")

            st.divider()

            if not history_df.empty:
                selected_task = st.selectbox(
                    "查看任务实时状态", history_df["task_id"].tolist(), key="task_status_select"
                )

                if selected_task:
                    with st.spinner("获取任务状态中..."):
                        success, task_info = client.get_task_status(selected_task)

                        if success:
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                status = task_info.get("status", "unknown")
                                status_color = {
                                    "pending": "🟡",
                                    "running": "🔵",
                                    "completed": "🟢",
                                    "failed": "🔴",
                                    "assigned": "🟠",
                                    "deleted": "🔘",
                                }.get(status, "⚪")
                                st.metric("状态", f"{status_color} {status}")

                            with col2:
                                if task_info.get("created_at"):
                                    created = datetime.fromtimestamp(task_info["created_at"])
                                    st.metric("创建时间", created.strftime("%H:%M:%S"))

                            with col3:
                                if task_info.get("assigned_node"):
                                    st.metric("分配节点", task_info["assigned_node"])

                            with col4:
                                if task_info.get("completed_at"):
                                    duration = task_info["completed_at"] - task_info["created_at"]
                                    st.metric("执行时间", f"{duration:.1f}秒")

                            if task_info.get("result"):
                                with st.expander("执行结果", expanded=False):
                                    st.code(task_info["result"], language="text")

                            if task_info.get("required_resources"):
                                st.info(
                                    f"资源需求: CPU={task_info['required_resources'].get('cpu', 1.0)}核心, "
                                    f"内存={task_info['required_resources'].get('memory', 512)}MB"
                                )
                        else:
                            st.warning(f"无法获取任务详情: {task_info.get('error', '未知错误')}")
    else:
        st.info("暂无任务历史，请先提交任务")


__all__ = ["render"]
