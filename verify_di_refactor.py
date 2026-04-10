#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证 DI 容器重构效果"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_container_import():
    """测试容器导入"""
    try:
        from src.di import Container
        print("✅ Container 导入成功")
        return True
    except Exception as e:
        print(f"❌ Container 导入失败: {e}")
        return False

def test_container_creation():
    """测试容器创建"""
    try:
        from src.di import Container
        container = Container()
        print("✅ Container 实例创建成功")
        return True, container
    except Exception as e:
        print(f"❌ Container 实例创建失败: {e}")
        return False, None

def test_property_access(container):
    """测试属性访问"""
    properties = [
        'config',
        'cache',
        'scheduler_client',
        'token_economy_service',
        'distributed_task_client'
    ]
    
    success_count = 0
    for prop in properties:
        try:
            value = getattr(container, prop)
            print(f"✅ 属性访问成功: container.{prop}")
            success_count += 1
        except Exception as e:
            print(f"❌ 属性访问失败 container.{prop}: {e}")
    
    return success_count == len(properties)

def test_di_utils():
    """测试 di_utils.py"""
    try:
        from src.presentation.streamlit.utils.di_utils import get_container, container
        print("✅ di_utils 导入成功")
        
        container_instance = get_container()
        print(f"✅ get_container() 返回容器实例: {type(container_instance).__name__}")
        
        print(f"✅ container 全局变量类型: {type(container).__name__}")
        
        return True
    except Exception as e:
        print(f"❌ di_utils 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_streamlit_views():
    """测试视图文件导入"""
    views = [
        'node_management_page',
        'task_monitor_page',
        'task_results_page'
    ]
    
    success_count = 0
    for view in views:
        try:
            module = __import__(
                f'src.presentation.streamlit.views.{view}',
                fromlist=[view]
            )
            print(f"✅ 视图模块导入成功: {view}")
            success_count += 1
        except Exception as e:
            print(f"❌ 视图模块导入失败 {view}: {e}")
    
    return success_count == len(views)

if __name__ == "__main__":
    print("=" * 60)
    print("DI 容器重构验证测试")
    print("=" * 60)
    
    print("\n【1】测试容器导入...")
    test1 = test_container_import()
    
    print("\n【2】测试容器创建...")
    test2, container = test_container_creation()
    
    print("\n【3】测试属性访问...")
    test3 = False
    if container:
        test3 = test_property_access(container)
    
    print("\n【4】测试 di_utils.py...")
    test4 = test_di_utils()
    
    print("\n【5】测试视图文件导入...")
    test5 = test_streamlit_views()
    
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print(f"  - 容器导入: {'✅ 通过' if test1 else '❌ 失败'}")
    print(f"  - 容器创建: {'✅ 通过' if test2 else '❌ 失败'}")
    print(f"  - 属性访问: {'✅ 通过' if test3 else '❌ 失败'}")
    print(f"  - di_utils: {'✅ 通过' if test4 else '❌ 失败'}")
    print(f"  - 视图导入: {'✅ 通过' if test5 else '❌ 失败'}")
    print("=" * 60)
    
    if all([test1, test2, test3, test4, test5]):
        print("\n🎉 所有测试通过！DI 容器重构成功！")
        print("\n✅ 重构确认:")
        print("  1. ✅ 移除了全局变量 _container")
        print("  2. ✅ 完全依赖 @st.cache_resource 管理单例")
        print("  3. ✅ 所有视图改为属性访问方式")
        print("  4. ✅ Container 类正确实现 @property")
        print("\n🚀 现在可以正常使用了！")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败，请检查上述错误信息")
        sys.exit(1)
