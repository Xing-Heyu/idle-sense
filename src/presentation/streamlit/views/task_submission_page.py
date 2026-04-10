"""
任务提交页面

使用新架构的服务层
支持单节点任务和分布式任务
"""

import csv
import io
import json
from datetime import datetime
from typing import Any, Optional

import streamlit as st

from src.presentation.streamlit.utils.di_utils import container


def _parse_data_input(data_type: str, data_input: str) -> Any:
    """解析数据输入"""
    if data_type == "数字列表":
        return [int(x.strip()) for x in data_input.split(",") if x.strip()]
    elif data_type == "文本列表":
        return [line.strip() for line in data_input.split("\n") if line.strip()]
    elif data_type == "键值对":
        result = {}
        for line in data_input.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()
        return result
    return None


def _parse_uploaded_file(uploaded_file, file_type: str) -> tuple[bool, Any, str]:
    """
    解析上传的文件

    Returns:
        (是否成功, 数据, 错误消息)
    """
    try:
        content = uploaded_file.read()

        if file_type == "JSON":
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            data = json.loads(content)
            return True, data, ""

        elif file_type == "CSV":
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            reader = csv.reader(io.StringIO(content))
            data = list(reader)
            return True, data, ""

        elif file_type == "TXT (文本列表)":
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            data = [line.strip() for line in content.split("\n") if line.strip()]
            return True, data, ""

        elif file_type == "TXT (数字列表)":
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            data = [float(x.strip()) if "." in x.strip() else int(x.strip())
                   for x in content.replace("\n", ",").split(",") if x.strip()]
            return True, data, ""

        else:
            return False, None, "不支持的文件类型"

    except json.JSONDecodeError as e:
        return False, None, f"JSON 解析错误: {e}"
    except ValueError as e:
        return False, None, f"数据格式错误: {e}"
    except Exception as e:
        return False, None, f"文件解析失败: {e}"


def _render_data_preview(data: Any, max_items: int = 20) -> None:
    """渲染数据预览"""
    if data is None:
        st.warning("暂无数据")
        return

    if isinstance(data, list):
        st.write(f"**数据类型**: 列表 | **数据量**: {len(data)} 项")
        if len(data) > 0:
            preview_data = data[:max_items]
            st.json(preview_data)
            if len(data) > max_items:
                st.info(f"仅显示前 {max_items} 项，共 {len(data)} 项")

    elif isinstance(data, dict):
        st.write(f"**数据类型**: 字典 | **键数量**: {len(data)} 个")
        preview_data = dict(list(data.items())[:max_items])
        st.json(preview_data)
        if len(data) > max_items:
            st.info(f"仅显示前 {max_items} 个键，共 {len(data)} 个")
    else:
        st.write(f"**数据类型**: {type(data).__name__}")
        st.write(data)


def _render_single_node_task(user_id: Optional[str]):
    """渲染单节点任务提交"""
    st.info("💡 单节点任务在一个节点上执行。大型工作负载请使用分布式任务。")

    col1, col2 = st.columns(2)
    with col1:
        timeout = st.number_input("超时时间 (秒)", min_value=10, max_value=7200, value=300, step=10)
        cpu_request = st.slider("CPU需求 (核心)", 0.5, 32.0, 4.0, 0.5)
    with col2:
        memory_request = st.slider("内存需求 (MB)", 512, 65536, 4096, 512)

    priority = st.slider("任务优先级", 0, 10, 0, 1, help="优先级越高，任务调度越快，但消耗更多代币（普通提交免费）")

    if user_id and priority > 0:
        cost_info = container.token_economy_service().estimate_task_cost(
            cpu_request, memory_request, timeout, priority
        )
        st.info(f"💵 预估费用: 基础 {cost_info['base_price']:.2f} CMP | 最终 {cost_info['final_price']:.2f} CMP | 优先级费 {cost_info['priority_fee']:.2f} CMP")
    elif user_id:
        st.info("💵 普通提交: 免费")

    code = st.text_area(
        "Python代码",
        value="",
        height=250,
        placeholder="# 在这里编写你的代码\nprint('你好, IdleSense!')"
    )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("✨ 提交任务", width="stretch", type="primary"):
            if not code.strip():
                st.toast("⚠️ 请输入Python代码", icon="⚠️")
            else:
                with st.spinner("提交任务中..."):
                    client = container.scheduler_client()
                    success, result = client.submit_task(
                        code, timeout, cpu_request, memory_request, user_id
                    )

                    if success:
                        task_id = result.get("task_id")

                        if priority > 0:
                            cost_info = container.token_economy_service().estimate_task_cost(
                                cpu_request, memory_request, timeout, priority
                            )
                            st.toast(f"✅ 任务提交成功！ID: {task_id} | 预估费用: {cost_info['final_price']} CMP", icon="✅")
                        else:
                            st.toast(f"✅ 任务提交成功！ID: {task_id} | 免费", icon="✅")

                        if 'task_history' not in st.session_state:
                            st.session_state.task_history = []

                        st.session_state.task_history.append({
                            "task_id": task_id,
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "status": "submitted",
                            "type": "单节点任务"
                        })
                    else:
                        st.toast(f"❌ 提交失败: {result.get('error', '未知错误')}", icon="❌")

    with col_btn2:
        if st.button("⚡ 加速提交 (高优先级)", width="stretch"):
            if not code.strip():
                st.toast("⚠️ 请输入Python代码", icon="⚠️")
            else:
                with st.spinner("提交加速任务中..."):
                    client = container.scheduler_client()
                    success, result = client.submit_task(
                        code, timeout, cpu_request, memory_request, user_id
                    )

                    if success:
                        task_id = result.get("task_id")

                        high_priority = min(priority + 5, 10)
                        cost_info = container.token_economy_service().estimate_task_cost(
                            cpu_request, memory_request, timeout, high_priority
                        )

                        st.toast(f"✅ 加速任务提交成功！ID: {task_id} | 预估费用: {cost_info['final_price']} CMP", icon="⚡")

                        if 'task_history' not in st.session_state:
                            st.session_state.task_history = []

                        st.session_state.task_history.append({
                            "task_id": task_id,
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "status": "submitted",
                            "type": "单节点任务 (加速)",
                            "priority": high_priority
                        })
                    else:
                        st.toast(f"❌ 提交失败: {result.get('error', '未知错误')}", icon="❌")


def _render_distributed_task(user_id: Optional[str]):
    """渲染分布式任务提交"""
    distributed_client = container.distributed_task_client()

    if not distributed_client.is_available:
        st.error("❌ 分布式任务处理模块不可用，请确保已安装 distributed_task.py")
        return

    st.info("🚀 **分布式任务** 可以利用多个节点的计算资源并行处理大型任务，大幅提升处理效率")

    st.subheader("分布式任务配置")

    col1, col2 = st.columns(2)

    with col1:
        task_name = st.text_input("任务名称", value=f"分布式任务_{int(datetime.now().timestamp())}")
        chunk_size = st.number_input(
            "分片大小（每组数据数量）",
            min_value=1,
            max_value=1000,
            value=10,
            step=1
        )

    with col2:
        task_description = st.text_input("任务描述", value="使用多节点协作处理大型任务")
        max_parallel_chunks = st.number_input(
            "最大并行节点数",
            min_value=1,
            max_value=50,
            value=5,
            step=1
        )

    priority = st.slider("任务优先级", 0, 10, 0, 1, help="优先级越高，任务调度越快，但消耗更多代币（普通提交免费）")

    if user_id and priority > 0:
        cost_info = container.token_economy_service().estimate_task_cost(
            max_parallel_chunks, 4096, 600, priority
        )
        st.info(f"💵 预估费用: 基础 {cost_info['base_price']:.2f} CMP | 最终 {cost_info['final_price']:.2f} CMP | 优先级费 {cost_info['priority_fee']:.2f} CMP")
    elif user_id:
        st.info("💵 普通提交: 免费")

    st.subheader("任务数据")
    data_input_method = st.radio("数据输入方式", ["手动输入", "从文件上传"], horizontal=True)

    task_data = None
    if data_input_method == "手动输入":
        data_type = st.selectbox("数据类型", ["数字列表", "文本列表", "键值对", "JSON 数据"])

        if data_type == "数字列表":
            data_input = st.text_area(
                "输入数字列表，用逗号分隔",
                value="1,2,3,4,5,6,7,8,9,10",
                help="例如: 1,2,3,4,5"
            )
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("✅ 确认数据", type="primary", key="confirm_number_list"):
                    try:
                        st.session_state['manual_task_data'] = _parse_data_input("数字列表", data_input)
                        st.session_state['manual_data_type'] = "数字列表"
                        st.success("✅ 数据已确认！")
                    except ValueError:
                        st.error("输入格式错误，请输入数字并用逗号分隔")

        elif data_type == "文本列表":
            data_input = st.text_area(
                "输入文本列表，每行一项",
                value="苹果\n香蕉\n橙子\n葡萄\n西瓜",
                help="每行输入一个文本项"
            )
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("✅ 确认数据", type="primary", key="confirm_text_list"):
                    st.session_state['manual_task_data'] = _parse_data_input("文本列表", data_input)
                    st.session_state['manual_data_type'] = "文本列表"
                    st.success("✅ 数据已确认！")

        elif data_type == "键值对":
            data_input = st.text_area(
                "输入键值对，每行一个，用冒号分隔",
                value="名称:闲置计算加速器\n版本:2.0\n类型:分布式计算",
                help="格式: 键:值，每行一个"
            )
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("✅ 确认数据", type="primary", key="confirm_key_value"):
                    st.session_state['manual_task_data'] = _parse_data_input("键值对", data_input)
                    st.session_state['manual_data_type'] = "键值对"
                    st.success("✅ 数据已确认！")

        elif data_type == "JSON 数据":
            data_input = st.text_area(
                "输入 JSON 数据",
                value='{"name": "test", "values": [1, 2, 3]}',
                help="输入有效的 JSON 格式数据"
            )
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("✅ 确认数据", type="primary", key="confirm_json_data"):
                    try:
                        st.session_state['manual_task_data'] = json.loads(data_input)
                        st.session_state['manual_data_type'] = "JSON"
                        st.success("✅ 数据已确认！")
                    except json.JSONDecodeError as e:
                        st.error(f"JSON 格式错误: {e}")

        if 'manual_task_data' in st.session_state and st.session_state['manual_task_data']:
            task_data = st.session_state['manual_task_data']
            st.markdown("---")
            st.subheader("📊 数据预览")
            _render_data_preview(task_data)

            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("🗑️ 清除数据", key="clear_manual_data"):
                    st.session_state['manual_task_data'] = None
                    st.session_state['manual_data_type'] = None
                    st.rerun()

    else:
        st.info("📁 支持多种文件格式：JSON、CSV、TXT（文本列表/数字列表）")

        file_type = st.selectbox(
            "选择文件类型",
            ["JSON", "CSV", "TXT (文本列表)", "TXT (数字列表)"],
            help="根据文件内容选择正确的类型",
            key="file_type_selector"
        )

        uploaded_file = st.file_uploader(
            "选择文件",
            type=["json", "csv", "txt"],
            help=f"上传 {file_type} 格式的文件",
            key="file_uploader_widget"
        )

        if uploaded_file:
            st.write(f"📄 **文件名**: {uploaded_file.name}")
            st.write(f"📊 **文件大小**: {uploaded_file.size / 1024:.2f} KB")

            if st.button("✅ 确认上传并解析", type="primary", key="confirm_file_upload"):
                with st.spinner("解析文件中..."):
                    success, data, error_msg = _parse_uploaded_file(uploaded_file, file_type)

                    if success:
                        task_data = data
                        st.success("✅ 文件解析成功！")
                        st.session_state['uploaded_task_data'] = task_data
                    else:
                        st.error(f"❌ {error_msg}")

        if 'uploaded_task_data' in st.session_state and st.session_state['uploaded_task_data']:
            task_data = st.session_state['uploaded_task_data']
            _render_data_preview(task_data)

            if st.button("🗑️ 清除已上传数据", key="clear_uploaded_data"):
                st.session_state['uploaded_task_data'] = None
                st.rerun()

    st.markdown("---")
    st.subheader("🎯 通用任务处理")
    st.info("💡 **通用任务** 可以处理任何类型的计算任务，不限于预设模板")

    use_custom_task = st.checkbox("使用通用任务（自定义处理逻辑）", help="不使用预设模板，完全自定义任务处理方式")

    custom_map_code = ""
    custom_merge_code = ""

    if use_custom_task:
        st.subheader("自定义任务配置")

        custom_map_code = st.text_area(
            "数据处理代码（每个节点执行的代码）",
            value="""
# 在这里编写每个节点要执行的代码
# __DATA__ 变量包含分配给这个节点的数据片段
# __CHUNK_ID__ 变量是当前数据片段的ID
# __CHUNK_INDEX__ 变量是当前数据片段的索引

# 示例：处理数据
results = []
for item in __DATA__:
    # 在这里处理每个数据项
    processed_item = item * 2  # 示例：将每个数字乘以2
    results.append(processed_item)

# 设置结果（必须设置这个变量）
__result__ = {
    "chunk_id": __CHUNK_ID__,
    "chunk_index": __CHUNK_INDEX__,
    "processed_data": results,
    "count": len(results)
}
print(f"处理了 {len(results)} 项数据")
""",
            height=200,
            help="这段代码将在每个节点上运行，处理分配给该节点的数据片段"
        )

        custom_merge_code = st.text_area(
            "结果合并代码（合并所有节点的结果）",
            value="""
# 在这里编写合并所有节点结果的代码
# __CHUNK_RESULTS__ 变量包含所有节点返回的结果列表

# 示例：合并所有节点的处理结果
all_results = []
total_count = 0

for chunk_result in __CHUNK_RESULTS__:
    if isinstance(chunk_result, dict) and "processed_data" in chunk_result:
        all_results.extend(chunk_result["processed_data"])
        total_count += chunk_result["count"]

# 设置最终合并结果（必须设置这个变量）
__MERGED_RESULT__ = {
    "total_processed": total_count,
    "all_data": all_results
}
print(f"合并完成，总共处理了 {total_count} 项数据")
""",
            height=200,
            help="这段代码将合并所有节点返回的结果"
        )

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("🚀 提交分布式任务", type="primary", width="stretch"):
            if not task_name or not task_description:
                st.error("请填写任务名称和描述")
            elif task_data is None:
                st.error("请输入或上传任务数据")
            else:
                with st.spinner("提交分布式任务中..."):
                    code_template = custom_map_code if use_custom_task else """
results = []
for item in __DATA__:
    results.append(item * 2)
__result__ = {"data": results, "count": len(results)}
"""
                    merge_code = custom_merge_code if use_custom_task else """
all_results = []
for chunk_result in __CHUNK_RESULTS__:
    if isinstance(chunk_result, dict) and "data" in chunk_result:
        all_results.extend(chunk_result["data"])
__MERGED_RESULT__ = {"all_data": all_results}
"""

                    success, result = distributed_client.submit_task(
                        name=task_name,
                        description=task_description,
                        code_template=code_template,
                        data=task_data,
                        chunk_size=chunk_size,
                        max_parallel_chunks=max_parallel_chunks,
                        merge_code=merge_code
                    )

                    if success:
                        task_id = result.get("task_id")

                        if priority > 0:
                            cost_info = container.token_economy_service().estimate_task_cost(
                                max_parallel_chunks, 4096, 600, priority
                            )
                            st.success(f"✅ 分布式任务提交成功！任务ID: `{task_id}` | 预估费用: {cost_info['final_price']} CMP")
                        else:
                            st.success(f"✅ 分布式任务提交成功！任务ID: `{task_id}` | 免费")

                        if 'task_history' not in st.session_state:
                            st.session_state.task_history = []

                        st.session_state.task_history.append({
                            "task_id": task_id,
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "status": "submitted",
                            "code_preview": f"{task_name} (分布式任务)",
                            "type": "分布式任务",
                            "priority": priority
                        })

                        with st.expander("任务详情", expanded=True):
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("任务ID", task_id)
                            with col2:
                                st.metric("分片大小", chunk_size)
                            with col3:
                                st.metric("最大并行分片", max_parallel_chunks)
                            st.metric("数据项数量", len(task_data) if isinstance(task_data, (list, dict)) else 1)
                    else:
                        st.error(f"❌ 提交失败: {result.get('error', '未知错误')}")

    with col_btn2:
        if st.button("⚡ 加速提交 (高优先级)", width="stretch"):
            if not task_name or not task_description:
                st.error("请填写任务名称和描述")
            elif task_data is None:
                st.error("请输入或上传任务数据")
            else:
                with st.spinner("提交加速分布式任务中..."):
                    code_template = custom_map_code if use_custom_task else """
results = []
for item in __DATA__:
    results.append(item * 2)
__result__ = {"data": results, "count": len(results)}
"""
                    merge_code = custom_merge_code if use_custom_task else """
all_results = []
for chunk_result in __CHUNK_RESULTS__:
    if isinstance(chunk_result, dict) and "data" in chunk_result:
        all_results.extend(chunk_result["data"])
__MERGED_RESULT__ = {"all_data": all_results}
"""

                    success, result = distributed_client.submit_task(
                        name=task_name,
                        description=task_description,
                        code_template=code_template,
                        data=task_data,
                        chunk_size=chunk_size,
                        max_parallel_chunks=max_parallel_chunks,
                        merge_code=merge_code
                    )

                    if success:
                        task_id = result.get("task_id")
                        high_priority = min(priority + 5, 10)

                        cost_info = container.token_economy_service().estimate_task_cost(
                            max_parallel_chunks, 4096, 600, high_priority
                        )

                        st.success(f"✅ 加速分布式任务提交成功！任务ID: `{task_id}` | 预估费用: {cost_info['final_price']} CMP")

                        if 'task_history' not in st.session_state:
                            st.session_state.task_history = []

                        st.session_state.task_history.append({
                            "task_id": task_id,
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "status": "submitted",
                            "code_preview": f"{task_name} (分布式任务-加速)",
                            "type": "分布式任务 (加速)",
                            "priority": high_priority
                        })

                        with st.expander("任务详情", expanded=True):
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("任务ID", task_id)
                            with col2:
                                st.metric("分片大小", chunk_size)
                            with col3:
                                st.metric("最大并行分片", max_parallel_chunks)
                            st.metric("数据项数量", len(task_data) if isinstance(task_data, (list, dict)) else 1)
                    else:
                        st.error(f"❌ 提交失败: {result.get('error', '未知错误')}")


def render(user_id: Optional[str] = None):
    """渲染任务提交页面"""
    st.header("📝 提交计算任务")

    distributed_client = container.distributed_task_client()
    task_type = st.radio(
        "选择任务类型",
        ["单节点任务", "分布式任务"],
        horizontal=True,
        disabled=not distributed_client.is_available
    )

    if task_type == "单节点任务":
        _render_single_node_task(user_id)
    else:
        _render_distributed_task(user_id)


__all__ = ["render"]
