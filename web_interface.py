# 文件路径：c:\idle-sense\web_interface.py
# 在任务管理部分添加删除功能

import streamlit as st
import requests
import pandas as pd

def show_task_management():
    st.header("🗂️ 任务管理")
    
    # 获取任务列表
    try:
        response = requests.get("http://localhost:8000/results")
        if response.status_code == 200:
            tasks = response.json().get("tasks", [])
            
            if tasks:
                # 显示任务表格
                st.subheader("📊 任务列表")
                df_data = []
                for task in tasks:
                    df_data.append({
                        "任务ID": task.get("task_id"),
                        "状态": task.get("status", "unknown"),
                        "完成时间": task.get("completed_at"),
                        "执行节点": task.get("assigned_node", "未知"),
                        "用户ID": task.get("user_id", "匿名")
                    })
                
                if df_data:
                    df = pd.DataFrame(df_data)
                    st.dataframe(df, use_container_width=True)
                
                # 添加删除功能
                st.subheader("🗑️ 删除任务")
                
                # 获取可删除的任务（只有pending和assigned状态）
                try:
                    all_tasks_response = requests.get("http://localhost:8000/stats")
                    if all_tasks_response.status_code == 200:
                        stats = all_tasks_response.json()
                        pending_tasks = stats.get("tasks", {}).get("pending", 0)
                        assigned_tasks = stats.get("tasks", {}).get("assigned", 0)
                        
                        st.info(f"可删除任务: {pending_tasks}个待处理 + {assigned_tasks}个已分配")
                    
                    # 获取具体任务ID（这里简化实现，实际应该调用专门的任务列表API）
                    deletable_tasks = []
                    for task_id in range(1, 1000):  # 假设任务ID范围
                        status_response = requests.get(f"http://localhost:8000/status/{task_id}")
                        if status_response.status_code == 200:
                            task_info = status_response.json()
                            if task_info.get("status") in ["pending", "assigned"]:
                                deletable_tasks.append({
                                    "task_id": task_id,
                                    "status": task_info.get("status"),
                                    "created_at": task_info.get("created_at")
                                })
                    
                    if deletable_tasks:
                        # 创建选择框
                        task_options = {f"任务{task['task_id']} (状态: {task['status']})": task['task_id'] 
                                      for task in deletable_tasks}
                        selected_task_label = st.selectbox("选择要删除的任务", list(task_options.keys()))
                        selected_task_id = task_options[selected_task_label]
                        
                        # 删除确认
                        if st.button("🗑️ 删除选中任务", type="secondary"):
                            with st.spinner("删除中..."):
                                delete_response = requests.delete(
                                    f"http://localhost:8000/api/tasks/{selected_task_id}"
                                )
                                
                                if delete_response.status_code == 200:
                                    st.success("✅ 任务删除成功！")
                                    st.rerun()  # 刷新页面
                                else:
                                    st.error(f"❌ 删除失败: {delete_response.json().get('error', '未知错误')}")
                    else:
                        st.info("📭 当前没有可删除的任务")
                        
                except Exception as e:
                    st.error(f"获取任务列表失败: {e}")
                
            else:
                st.info("📭 暂无任务记录")
        else:
            st.error("❌ 获取任务列表失败")
    except Exception as e:
        st.error(f"🔌 连接错误: {e}")

# 在原有的页面布局中调用这个函数
def main():
    st.set_page_config(
        page_title="闲置计算加速器",
        page_icon="⚡",
        layout="wide"
    )
    
    st.title("⚡ 闲置计算加速器")
    
    # 侧边栏导航
    page = st.sidebar.selectbox("导航", ["任务提交", "任务管理", "节点状态", "系统统计"])
    
    if page == "任务提交":
        show_task_submission()
    elif page == "任务管理":
        show_task_management()  # 调用新增的删除功能
    elif page == "节点状态":
        show_node_status()
    elif page == "系统统计":
        show_system_stats()

if __name__ == "__main__":
    main()
