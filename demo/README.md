# 演示脚本集合

这个目录包含各种演示脚本，用于展示闲置计算加速器的完整功能。

## 可用演示

### 1. 单机演示 (`demo_single_machine.py`)
**目的**: 在一台电脑上展示完整流程
**功能**:
- 自动启动调度中心
- 启动计算节点
- 提交演示任务
- 监控任务执行
- 显示系统状态

```bash
python demo/demo_single_machine.py
演示场景 场景1: 快速体验 bash 复制   下载    # 最简单的单机演示
python demo/demo_single_machine.py  场景2: 完整展示 bash 复制   下载    # 1. 启动单机演示（基础功能）
python demo/demo_single_machine.py

# 2. 展示网页界面（用户体验）
python demo/demo_web_interface.py

# 3. 如果有多个电脑，展示分布式计算
python demo/demo_local_network.py  场景3: 教学演示 bash 复制   下载    # 分步骤展示
# 步骤1: 启动调度中心
python scheduler/simple_server.py

# 步骤2: 启动节点（在另一个终端）
python node/simple_client.py --scheduler http://localhost:8000

# 步骤3: 运行网页界面（第三个终端）
streamlit run web_interface.py

# 步骤4: 运行演示任务
python demo/demo_single_machine.py
/////////////////////////////////////////////////////////////////////////////////////////////////////////////
//////////////////////////////////////////////////////////////////////////////////////////////////////////////


一个自定义示例：
# new_demo.py
from demo import demo_base

class CustomDemo(demo_base.BaseDemo):
    def run(self):
        # 自定义演示逻辑
        pass

if __name__ == "__main__":
    demo = CustomDemo()
    demo.run()
