# 闲置计算加速器 - 用户使用指南

## 🚀 快速开始

### 第一步：系统激活（必须）
```bash
# 方法1：使用批处理文件（推荐）
双击运行 start_all.bat

# 方法2：使用Python脚本
python auto_start.py

# 方法3：手动启动（按顺序）
1. 启动调度中心：python scheduler/simple_server.py
2. 启动节点客户端：python node/simple_client.py  
3. 启动网页界面：streamlit run web_interface.py
```

**激活状态检查**：
- 调度中心：http://localhost:8000 （显示版本信息）
- 网页界面：http://localhost:8501 （显示控制面板）
- 节点客户端：控制台显示"节点注册成功"

### 第二步：用户注册（首次使用）
1. 打开网页界面 http://localhost:8501
2. 在侧边栏点击"用户管理" → "注册"
3. 填写用户名和邮箱
4. **必须阅读并同意以下协议**：
   - ✅ 文件夹使用协议
   - ✅ 本地操作授权确认
5. 完成注册，系统将在您的电脑创建专属文件夹

### 第三步：使用数据文件（关键步骤）
1. **在本地文件管理器中**找到您的用户数据文件夹：
   ```
   C:\\idle-sense\\node_data\\user_data\\{您的用户ID}
   ```
2. **将您的数据文件**放入此文件夹（CSV、TXT、JSON等）
3. **在网页界面编写脚本**读取您的数据文件

### 第四步：提交计算任务
1. 在"任务提交"标签页输入Python代码
2. 使用系统提供的函数读取您的数据文件
3. 设置资源需求（CPU、内存、超时时间）
4. 点击"提交任务"
5. 系统自动分配空闲节点执行
6. 在"任务监控"标签页查看结果

## 📁 文件夹管理说明

### 系统创建的文件夹结构
```
idle-sense/
├── node_data/           # 节点数据根目录
│   ├── user_data/       # 用户数据文件夹（关键）
│   │   └── {用户ID}/    # 您的专属数据仓库
│   ├── temp_data/       # 临时数据文件夹  
│   │   └── {用户ID}/    # 系统临时文件（自动清理）
│   └── logs/            # 操作日志目录
```

### 文件夹用途（重要）
- **user_data/{用户ID}/**：
  - **您的数据仓库** - 存放您自己的数据集、配置文件等
  - **脚本可读取** - 任务脚本可以直接访问此文件夹的内容
  - **需要您管理** - 系统不会自动删除，需要您自行维护文件
  - **持久化存储** - 重要计算结果可以保存到这里

- **temp_data/{用户ID}/**：
  - **系统临时工作区** - 任务执行过程中的临时文件
  - **自动清理** - 系统自动管理，任务完成后清理
  - **不要存放重要数据** - 请不要在此存放需要长期保存的文件

## 💻 如何在脚本中使用数据文件

### 系统提供的文件操作函数
```python
# 示例：读取用户数据文件夹中的文件
try:
    # 读取用户数据文件
    data_content = read_user_file("my_dataset.csv")
    print(f"成功读取文件内容")
    # 处理您的数据...
except Exception as e:
    print(f"读取失败: {e}")

# 查看用户文件夹中的文件列表
files = list_user_files()
print("您的数据文件:")
for file in files:
    print(f"- {file}")

# 检查特定文件是否存在
if user_file_exists("config.json"):
    print("检测到配置文件")
    config_content = read_user_file("config.json")
    # 使用配置文件...
```

### 完整的使用示例
```python
# 完整的用户数据处理示例

# 1. 检查用户是否提供了数据文件
if user_file_exists("sales_data.csv"):
    print("使用用户提供的销售数据")
    
    # 读取用户数据文件
    data_content = read_user_file("sales_data.csv")
    
    # 处理数据（示例：简单的数据分析）
    lines = data_content.strip().split('\n')
    total_sales = 0
    
    for line in lines[1:]:  # 跳过标题行
        values = line.split(',')
        if len(values) >= 2:
            total_sales += float(values[1])
    
    print(f"总销售额: {total_sales:.2f}")
    
else:
    print("未找到用户数据文件，使用示例数据")
    # 使用默认数据进行计算...

# 2. 使用用户配置文件（如果存在）
if user_file_exists("settings.json"):
    import json
    settings_content = read_user_file("settings.json")
    settings = json.loads(settings_content)
    print(f"使用用户配置: {settings}")
```

## 🔒 安全与合规说明

### 本地操作授权机制
- 所有本地文件操作**必须经您明确授权**
- 系统**不会**在后台进行未告知的操作
- 操作记录**完整保存**在本地日志中
- 您随时可以**查看和核查**所有操作

### 免责声明
1. 所有操作均由您**主动授权**后执行
2. 系统仅执行**单次授权范围内**的操作
3. 操作结果及风险由您**自行承担责任**
4. 如发现未授权操作，请立即停止使用并反馈

## ⚡ 功能特性

### 开源无限制版本
- ✅ **无资源配额限制** - 充分利用您的硬件
- ✅ **无任务数量限制** - 随意提交计算任务  
- ✅ **无使用时间限制** - 24小时可用
- ✅ **跨平台支持** - Windows/macOS/Linux

### 智能调度系统
- 🔍 **自动检测电脑闲置状态**
- ⚖️ **公平任务分配算法**
- 📊 **实时性能监控**
- 🔄 **自动容错恢复**

## 🛠️ 故障排除

### 常见问题解决

#### 错误代码与解决方案对应表
| 错误代码/信息 | 原因分析 | 解决方案 |
|--------------|----------|----------|
| `ConnectionRefusedError: [WinError 10061]` | 调度中心未启动 | 检查调度中心是否运行在localhost:8000 |
| `HTTP 400: 必须同意文件夹使用协议` | 注册时未同意协议 | 重新注册，勾选同意所有协议 |
| `Error: 用户未同意文件夹使用协议` | 任务执行前授权检查失败 | 确认用户已登录并同意协议 |
| `FileNotFoundError: 文件不存在` | 数据文件路径错误 | 检查文件名和路径是否正确 |
| `PermissionError: 只能读取用户数据文件夹` | 脚本尝试访问非法路径 | 确保文件操作在user_data文件夹内 |
| `SyntaxError: invalid syntax` | Python代码语法错误 | 检查代码语法，使用在线Python验证工具 |
| `MemoryError` | 内存不足 | 减少任务内存需求或增加系统内存 |
| `TimeoutError` | 任务执行超时 | 增加任务超时时间或优化代码性能 |

#### 网络连接问题详细排查
1. **检查服务状态**
   ```bash
   # 检查调度中心
   curl http://localhost:8000/
   # 检查节点客户端（查看控制台输出）
   ```

2. **防火墙设置**
   - Windows: 检查Windows Defender防火墙设置
   - 确保允许Python和Streamlit通过防火墙
   - 临时关闭防火墙测试（仅用于排查）

3. **端口占用检查**
   ```bash
   # Windows
   netstat -ano | findstr :8000
   netstat -ano | findstr :8501
   
   # 如果端口被占用
   # 方法1：终止占用进程
   taskkill /PID <进程ID> /F
   # 方法2：修改配置文件中的端口号
   ```

4. **代理和VPN影响**
   - 临时关闭VPN和代理软件
   - 检查系统代理设置
   - 尝试使用127.0.0.1代替localhost

#### 任务执行失败排查步骤
1. **检查代码语法**
   - 使用在线Python验证工具检查语法
   - 确保没有使用危险模块（os, sys等）
   - 检查缩进和括号匹配

2. **检查数据文件**
   - 确认文件在正确的用户数据文件夹
   - 检查文件权限和可读性
   - 验证文件编码为UTF-8

3. **查看详细错误信息**
   - 在任务监控页面查看完整错误信息
   - 检查节点客户端控制台输出
   - 查看调度中心日志文件

### 数据格式要求

#### 支持的文件格式列表
- **文本文件**: `.txt`, `.csv`, `.json`, `.xml`, `.yml`, `.yaml`
- **数据文件**: `.csv`, `.tsv`, `.dat`
- **配置文件**: `.json`, `.ini`, `.cfg`, `.conf`
- **代码文件**: `.py`, `.js`, `.html`, `.css`（仅读取内容）

#### 文件编码要求
- **必须使用UTF-8编码**
- 避免使用GBK、GB2312等中文编码
- 文本文件建议使用无BOM的UTF-8

**检查文件编码方法**:
```python
# 在Python中检查文件编码
import chardet

with open('your_file.csv', 'rb') as f:
    raw_data = f.read()
    result = chardet.detect(raw_data)
    print(f"文件编码: {result['encoding']}")
```

#### 文件大小建议
- **小文件**: < 10MB - 直接读取处理
- **中文件**: 10MB - 100MB - 建议分批处理
- **大文件**: > 100MB - 强烈建议预处理和分批处理

### 性能优化建议

#### 大数据集优化策略
1. **数据预处理**
   ```python
   # 在提交任务前预处理数据
   # 将大文件分割成小文件
   def split_large_file(input_file, chunk_size=100000):
       with open(input_file, 'r', encoding='utf-8') as f:
           header = f.readline()  # 保存标题行
           chunk_num = 0
           while True:
               lines = [header] + [f.readline() for _ in range(chunk_size)]
               if not any(lines[1:]):  # 如果没有数据行
                   break
               
               chunk_file = f"chunk_{chunk_num}.csv"
               with open(chunk_file, 'w', encoding='utf-8') as chunk_f:
                   chunk_f.writelines(lines)
               chunk_num += 1
   ```

2. **分批处理示例**
   ```python
   # 分批处理大数据集
   chunk_files = list_user_files()
   chunk_files = [f for f in chunk_files if f.startswith('chunk_')]
   
   results = []
   for chunk_file in sorted(chunk_files):
       # 处理每个数据块
       data = read_user_file(chunk_file)
       result = process_chunk(data)
       results.append(result)
   
   # 合并结果
   final_result = combine_results(results)
   ```

#### 资源设置详细指导

**CPU设置建议**:
- **轻量任务**: 0.5 - 1.0 核心（简单计算、数据处理）
- **中等任务**: 1.0 - 2.0 核心（机器学习、复杂计算）
- **重量任务**: 2.0 - 4.0 核心（大规模模拟、深度学习）

**内存设置建议**:
- **基础任务**: 256MB - 512MB（简单脚本）
- **数据处理**: 512MB - 2GB（中等数据集）
- **大型计算**: 2GB - 8GB（大数据集、复杂模型）

**超时时间设置**:
- **快速任务**: 60 - 300秒（简单计算）
- **中等任务**: 300 - 1800秒（数据处理）
- **长期任务**: 1800 - 7200秒（复杂计算）

#### 性能监控和优化
1. **任务执行时间监控**
   ```python
   import time
   
   start_time = time.time()
   # 您的代码
   execution_time = time.time() - start_time
   print(f"任务执行时间: {execution_time:.2f}秒")
   ```

2. **内存使用优化**
   - 及时释放不再使用的变量
   - 使用生成器代替列表处理大数据
   - 避免在循环中创建大量临时对象

### 日志文件位置
- 调度中心日志：`logs/scheduler.log`
- 节点操作日志：`node_data/logs/local_operations.log`
- 用户操作日志：`node_data/user_data/{用户ID}/操作记录.log`

## 📞 技术支持

### 获取帮助
- 查看详细文档：阅读项目根目录的README.md
- 报告问题：在GitHub仓库提交Issue
- 社区支持：加入开发者讨论群

### 系统要求
- **操作系统**：Windows 10/11, macOS 10.15+, Linux
- **Python版本**：3.8+
- **内存**：至少4GB可用内存
- **磁盘空间**：至少1GB可用空间

---

## 💡 使用技巧

### 最佳实践
1. **数据文件命名规范**：使用有意义的文件名，如`sales_2024.csv`
2. **文件编码**：确保数据文件使用UTF-8编码
3. **文件大小**：大文件建议分割成多个小文件处理
4. **备份重要数据**：定期备份用户数据文件夹中的重要文件

### 性能优化
1. **数据预处理**：在本地预处理数据，减少计算节点负担
2. **分批处理**：大数据集可以分批提交任务
3. **资源设置**：根据任务复杂度合理设置CPU和内存需求

**开始使用吧！将您的数据文件放入用户数据文件夹，然后在网页界面编写脚本来处理它们。**