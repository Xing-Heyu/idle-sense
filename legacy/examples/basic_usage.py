"""
idle-sense 基础使用示例
"""

import time

from idle_sense import is_idle


def monitor_idle_status(interval: int = 30):
    """
    监控电脑闲置状态

    Args:
        interval: 检测间隔（秒）
    """
    print("开始监控电脑闲置状态...")
    print("按 Ctrl+C 停止")
    print("-" * 50)

    try:
        while True:
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")

            if is_idle():
                status = "🔵 闲置中（可安全贡献算力）"
            else:
                status = "🔴 使用中（请勿打扰）"

            print(f"[{current_time}] {status}")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n监控已停止")
    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    # 基础测试
    print("idle-sense 测试")
    print("=" * 50)

    # 单次检测
    print("单次检测结果:")
    print(f"是否闲置: {'是' if is_idle() else '否'}")

    print("\n" + "=" * 50)

    # 询问是否开始持续监控
    choice = input("是否开始持续监控？(y/n): ")
    if choice.lower() == 'y':
        monitor_idle_status(interval=30)
    else:
        print("测试结束")
