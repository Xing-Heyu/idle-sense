#!/usr/bin/env python3
"""
文件拖放和恢复功能模块
支持拖放文件到网页界面进行任务提交
"""

import base64
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

import streamlit as st


class FileDropManager:
    """文件拖放管理器"""

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="idle_sense_")
        self.uploaded_files = {}

    def save_uploaded_file(self, uploaded_file) -> str:
        """保存上传的文件到临时目录"""
        try:
            # 创建临时文件路径
            file_path = os.path.join(self.temp_dir, uploaded_file.name)

            # 保存文件
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # 记录文件信息
            self.uploaded_files[uploaded_file.name] = {
                "path": file_path,
                "size": uploaded_file.size,
                "type": uploaded_file.type,
                "uploaded_at": time.time()
            }

            return file_path
        except Exception as e:
            st.error(f"保存文件失败: {e}")
            return None

    def get_file_content(self, file_path: str) -> Any:
        """获取文件内容"""
        try:
            file_ext = Path(file_path).suffix.lower()

            if file_ext == '.json':
                with open(file_path, encoding='utf-8') as f:
                    return json.load(f)
            elif file_ext in ['.txt', '.csv', '.log'] or file_ext in ['.py', '.js', '.html', '.css']:
                with open(file_path, encoding='utf-8') as f:
                    return f.read()
            else:
                # 对于二进制文件，返回base64编码
                with open(file_path, 'rb') as f:
                    return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            st.error(f"读取文件失败: {e}")
            return None

    def cleanup(self):
        """清理临时文件"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"清理临时文件失败: {e}")

def create_file_drop_area(title: str = "拖放文件到这里",
                        accepted_types: list[str] = None,
                        help_text: str = None) -> Optional[Any]:
    """创建文件拖放区域"""
    if accepted_types is None:
        accepted_types = ["json", "txt", "csv", "py", "js", "html", "css"]

    if help_text is None:
        help_text = f"支持文件类型: {', '.join(accepted_types)}"

    st.markdown(f"### {title}")
    st.info(help_text)

    # 创建文件上传器
    uploaded_file = st.file_uploader(
        "选择文件或拖放到这里",
        type=accepted_types,
        help=help_text
    )

    if uploaded_file is not None:
        # 显示文件信息
        st.success(f"文件上传成功: {uploaded_file.name}")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("文件名", uploaded_file.name)
        with col2:
            st.metric("文件大小", f"{uploaded_file.size / 1024:.2f} KB")
        with col3:
            st.metric("文件类型", uploaded_file.type)

        # 保存文件
        if 'file_drop_manager' not in st.session_state:
            st.session_state.file_drop_manager = FileDropManager()

        file_path = st.session_state.file_drop_manager.save_uploaded_file(uploaded_file)

        if file_path:
            # 获取文件内容
            content = st.session_state.file_drop_manager.get_file_content(file_path)

            # 显示文件内容预览
            with st.expander("文件内容预览", expanded=True):
                if isinstance(content, (dict, list)):
                    st.json(content)
                else:
                    st.code(content, language=_get_language_from_filename(uploaded_file.name))

            return {
                "name": uploaded_file.name,
                "path": file_path,
                "content": content,
                "size": uploaded_file.size,
                "type": uploaded_file.type
            }

    return None

def _get_language_from_filename(filename: str) -> str:
    """根据文件名获取代码语言"""
    ext = Path(filename).suffix.lower()
    language_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.html': 'html',
        '.css': 'css',
        '.json': 'json',
        '.csv': 'csv',
        '.txt': 'text',
        '.log': 'text'
    }
    return language_map.get(ext, 'text')

def create_data_extraction_interface(file_data: dict[str, Any]) -> Optional[Any]:
    """创建数据提取界面"""
    if not file_data:
        return None

    st.markdown("### 📊 数据提取")

    # 根据文件类型提供不同的提取选项
    file_ext = Path(file_data['name']).suffix.lower()

    if file_ext == '.json':
        return _extract_from_json(file_data)
    elif file_ext in ['.txt', '.csv']:
        return _extract_from_text(file_data)
    elif file_ext == '.py':
        return _extract_from_code(file_data)
    else:
        st.warning("不支持的文件类型进行数据提取")
        return None

def _extract_from_json(file_data: dict[str, Any]) -> Any:
    """从JSON文件中提取数据"""
    content = file_data['content']

    if isinstance(content, dict):
        st.info("检测到JSON对象")
        key_options = list(content.keys())
        selected_key = st.selectbox("选择要提取的键", key_options)

        if selected_key:
            return content[selected_key]
    elif isinstance(content, list):
        st.info("检测到JSON数组")
        return content
    else:
        st.warning("无法识别的JSON结构")
        return None

def _extract_from_text(file_data: dict[str, Any]) -> Any:
    """从文本文件中提取数据"""
    content = file_data['content']

    extraction_method = st.radio(
        "选择提取方法",
        ["按行分割", "按逗号分割", "按空格分割", "正则表达式"]
    )

    if extraction_method == "按行分割":
        return [line.strip() for line in content.split('\n') if line.strip()]
    elif extraction_method == "按逗号分割":
        return [item.strip() for item in content.split(',')]
    elif extraction_method == "按空格分割":
        return content.split()
    elif extraction_method == "正则表达式":
        pattern = st.text_input("输入正则表达式")
        if pattern:
            import re
            return re.findall(pattern, content)

    return None

def _extract_from_code(file_data: dict[str, Any]) -> str:
    """从代码文件中提取代码"""
    return file_data['content']

def create_file_drop_task_interface() -> Optional[tuple[str, Any]]:
    """创建文件拖放任务界面"""
    st.markdown("## 📁 文件拖放任务")

    # 创建文件拖放区域
    file_data = create_file_drop_area(
        title="拖放文件到这里",
        accepted_types=["json", "txt", "csv", "py"],
        help_text="支持JSON、文本、CSV和Python文件。拖放文件后可以提取数据并创建任务。"
    )

    if file_data:
        # 创建数据提取界面
        extracted_data = create_data_extraction_interface(file_data)

        if extracted_data is not None:
            st.success("数据提取成功！")

            # 显示任务创建选项
            st.markdown("### 🚀 创建任务")
            task_name = st.text_input("任务名称", value=f"处理文件: {file_data['name']}")
            st.text_area("任务描述", value=f"使用拖放上传的文件 {file_data['name']} 创建的任务")

            if st.button("创建任务", type="primary"):
                if task_name:
                    return task_name, extracted_data
                else:
                    st.error("请输入任务名称")

    return None
