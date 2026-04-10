"""
登录/注册页面 - 使用新架构的用例层

使用示例：
    from src.presentation.streamlit.views import auth_page

    auth_page.render_login()
    auth_page.render_register()
"""

import time

import streamlit as st

from src.core.use_cases.auth import LoginRequest, RegisterRequest
from src.di import container
from src.presentation.streamlit.utils.session_manager import SessionManager


def render_login():
    """渲染登录页面"""
    st.header("🔐 用户登录")
    st.caption("输入您的用户名或用户ID进行登录")

    username_or_id = st.text_input("用户名或用户ID", key="login_username_or_id")

    if st.button("登录", type="primary", key="login_btn"):
        if not username_or_id:
            st.error("请输入用户名或用户ID")
        else:
            with st.spinner("登录中..."):
                use_case = container.login_use_case()
                response = use_case.execute(LoginRequest(
                    username_or_id=username_or_id
                ))

                if response.success:
                    st.success(f"✅ {response.message}")
                    st.session_state.user_session = {
                        "user_id": response.user_id,
                        "username": response.username,
                        "is_local": True
                    }
                    SessionManager.save_to_localstorage(
                        response.user_id,
                        response.username,
                        is_local=True
                    )
                    st.query_params["user_id"] = response.user_id
                    st.query_params["username"] = response.username
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ {response.message}")


def render_register():
    """渲染注册页面"""
    st.header("📝 用户注册")
    st.caption("注册后可直接使用本地登录")

    username = st.text_input(
        "用户名",
        key="reg_username",
        help="用户名只能包含中文、英文和数字，长度不超过20个字符"
    )

    if username:
        use_case = container.register_use_case()
        test_response = use_case.execute(RegisterRequest(username=username))
        if not test_response.success and "格式" in test_response.message:
            st.error(f"用户名格式错误: {test_response.message}")

    st.markdown("### 📁 文件夹位置设置")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**选择文件夹安装位置：**")
        folder_location = st.radio(
            "文件夹位置",
            ["项目目录", "C盘", "D盘"],
            index=0,
            format_func=lambda x: {
                "项目目录": "项目目录 (推荐)",
                "C盘": "C盘",
                "D盘": "D盘"
            }.get(x, x)
        )

    with col2:
        if folder_location == "项目目录":
            st.info("📁 相对路径，便于管理")
        elif folder_location == "C盘":
            st.info("💾 系统盘，启动快")
        elif folder_location == "D盘":
            st.info("💾 数据盘，空间大")

    folder_value = {"项目目录": "project", "C盘": "c", "D盘": "d"}.get(folder_location, "project")

    st.markdown("---")
    st.markdown("### 📋 用户协议与隐私政策")

    with st.expander("📄 用户服务协议（点击展开）", expanded=False):
        st.markdown("""
        **最后更新日期：2024年1月**

        ---

        **一、服务说明**

        闲置计算加速器是一款分布式计算资源调度平台，旨在利用用户设备的闲置计算资源进行分布式任务处理。

        **二、用户注册**

        1. 用户需提供有效的用户名进行注册
        2. 用户名只能包含中文、英文和数字，长度不超过20个字符
        3. 系统将为每位用户生成唯一的用户ID

        **三、用户义务**

        1. 用户不得利用本平台从事违法违规活动
        2. 用户应确保提交的任务代码不包含恶意内容
        3. 用户应遵守当地法律法规

        **四、免责声明**

        1. 本平台按"现状"提供服务，不提供任何明示或暗示的保证
        2. 对于因使用本平台而产生的任何直接或间接损失，平台不承担责任

        **五、服务变更**

        平台保留随时修改或终止服务的权利，恕不另行通知。
        """)

    with st.expander("🔒 隐私政策（点击展开）", expanded=False):
        st.markdown("""
        **最后更新日期：2024年1月**

        ---

        **一、信息收集**

        我们收集以下信息：
        - 用户名和用户ID
        - 设备基本信息（CPU核心数、内存大小、操作系统）
        - 任务执行记录

        **二、信息使用**

        收集的信息用于：
        - 提供分布式计算服务
        - 优化任务调度
        - 改进用户体验

        **三、信息存储**

        - 所有数据仅存储在用户本地设备
        - 我们不会将用户数据上传到远程服务器
        - 用户可随时删除本地数据

        **四、信息共享**

        我们不会与第三方共享用户个人信息。

        **五、用户权利**

        用户有权：
        - 查看个人数据
        - 删除个人数据
        - 停止使用服务
        """)

    with st.expander("🔐 系统权限说明（点击展开）", expanded=False):
        st.markdown("""
        **应用将请求以下权限：**

        | 权限类型 | 用途 | 说明 |
        |---------|------|------|
        | 📁 文件读写 | 数据存储 | 在指定位置创建应用数据目录 |
        | 💻 系统信息 | 资源调度 | 获取CPU、内存等硬件信息 |
        | 🌐 网络通信 | 任务分发 | 与调度服务器通信 |

        **权限范围限制：**

        ✅ **允许的操作：**
        - 在用户指定目录创建应用文件夹
        - 读写应用文件夹内的数据
        - 获取系统硬件配置信息

        ❌ **禁止的操作：**
        - 访问用户指定目录外的文件
        - 读取用户个人文件
        - 收集用户隐私数据
        - 未经授权的网络请求

        **数据安全：**
        - 所有数据本地存储
        - 不上传用户隐私信息
        - 支持用户随时删除数据
        """)

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        agree_terms = st.checkbox("我已阅读并同意《用户服务协议》", key="agree_terms")
    with col2:
        agree_privacy = st.checkbox("我已阅读并同意《隐私政策》", key="agree_privacy")

    agree_permissions = st.checkbox("我授权应用获取上述系统权限", key="agree_permissions")

    agree_all = agree_terms and agree_privacy and agree_permissions

    if not agree_all and (agree_terms or agree_privacy or agree_permissions):
        st.warning("⚠️ 请勾选所有选项以完成注册")

    if st.button(
        "🚀 注册",
        type="primary",
        disabled=not (username and agree_all),
        key="register_btn"
    ):
        if not username:
            st.error("请输入用户名")
        elif not agree_terms:
            st.error("请阅读并同意《用户服务协议》")
        elif not agree_privacy:
            st.error("请阅读并同意《隐私政策》")
        elif not agree_permissions:
            st.error("请授权系统权限")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                status_text.text("正在验证用户名...")
                progress_bar.progress(30)

                use_case = container.register_use_case()
                response = use_case.execute(RegisterRequest(
                    username=username,
                    folder_location=folder_value
                ))

                if response.success:
                    status_text.text("完成注册...")
                    progress_bar.progress(100)

                    st.session_state.user_session = {
                        "user_id": response.user_id,
                        "username": response.username,
                        "is_local": True
                    }
                    SessionManager.save_to_localstorage(
                        response.user_id,
                        response.username,
                        is_local=True
                    )
                    st.query_params["user_id"] = response.user_id
                    st.query_params["username"] = response.username

                    st.success(f"✅ {response.message}")
                    if response.username != username:
                        st.info(f"用户名已调整为: {response.username}")

                    st.info("💡 您现在可以开始使用系统的完整功能了！")
                    time.sleep(2)
                    st.rerun()
                else:
                    progress_bar.empty()
                    status_text.empty()
                    _display_registration_error(response)

            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                st.error(f"注册失败: {str(e)}")


def _display_registration_error(response):
    """根据错误码展示不同的错误提示"""
    error_code = getattr(response, 'error_code', 'UNKNOWN_ERROR')
    message = response.message

    error_suggestions = {
        "PERMISSION_ERROR": {
            "icon": "🔒",
            "suggestion": "💡 建议：请尝试以管理员身份运行程序，或检查目标文件夹的写入权限。"
        },
        "DISK_FULL": {
            "icon": "💾",
            "suggestion": "💡 建议：请清理磁盘空间后重试，或选择其他磁盘作为存储位置。"
        },
        "SYSTEM_ERROR": {
            "icon": "⚠️",
            "suggestion": "💡 建议：请稍后重试，如问题持续请联系技术支持。"
        },
        "DATA_CORRUPTION": {
            "icon": "📂",
            "suggestion": "💡 建议：用户数据可能已损坏，请尝试删除 local_users 目录后重试。"
        },
        "USERNAME_VALIDATION_ERROR": {
            "icon": "✏️",
            "suggestion": "💡 建议：请使用中文、英文或数字，长度不超过20个字符。"
        },
        "UNKNOWN_ERROR": {
            "icon": "❓",
            "suggestion": "💡 建议：请稍后重试，如问题持续请联系技术支持。"
        }
    }

    error_info = error_suggestions.get(error_code, error_suggestions["UNKNOWN_ERROR"])

    st.error(f"{error_info['icon']} {message}")

    if error_info["suggestion"]:
        st.warning(error_info["suggestion"])


def render():
    """渲染登录/注册页面（兼容旧接口）"""
    tab_login, tab_register = st.tabs(["登录", "注册"])

    with tab_login:
        render_login()

    with tab_register:
        render_register()


__all__ = ["render", "render_login", "render_register"]
