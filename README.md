markdown 复制   下载    # idle-sense

一个跨平台的电脑闲置状态检测库，用于判断电脑是否处于"真闲置"状态。

## 🎯 项目背景

这是 **[公共算力共享项目](https://github.com/Xing-Heyu/public-compute-vision)** 的核心技术组件。

## 📦 安装
```bash
pip install idle-sense  🚀 快速开始 python 复制   下载    from idle_sense import is_idle
import time

while True:
    if is_idle():
        print(f"{time.ctime()} - 电脑闲置中")
    else:
        print(f"{time.ctime()} - 电脑使用中")
time.sleep(30) 支持的系统 • Windows 10/11 ✅ • macOS 10.15+ ✅ • Linux ⏳（规划中）项目结构 文本 复制 下载 idle-sense/
├── idle_sense/          
│   ├── __init__.py     
│   ├── core.py         
│   ├── windows.py      
│   └── macos.py        
├── examples/           
├── tests/              
└── pyproject.toml 开发团队 • 架构设计：邢赫宇 • Windows实现：[队友A名字] • macOS实现：[队友B名字] 许可证 MIT License - 详见 LICENSE 文件 文本 复制 下载


