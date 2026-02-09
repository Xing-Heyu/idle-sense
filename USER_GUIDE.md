# 算力共享平台与闲置资源利用 - 本地部署用户指南

> **面向有一定基础的用户**：本指南适用于熟悉基本电脑操作和命令行的用户

---

## 🚀 快速开始

### 第一步：本地部署启动（必须）
```bash
# 方法1：使用批处理文件（推荐）
双击运行 start_all.bat

# 方法2：使用Python脚本
python auto_start.py

# 方法3：手动启动（按顺序）
1. 启动调度中心：python scheduler/simple_server.py
2. 启动节点客户端：python node/simple_client.py  
3. 启动网页界面：streamlit run web_interface.py --server.port 8502
```

**部署状态检查**：
- 调度中心：http://localhost:8000 （显示版本信息）
- 网页界面：http://localhost:8502 （显示控制面板）
- 节点客户端：控制台显示"节点注册成功"

### 第二步：用户注册（首次使用）
1. 打开网页界面 http://localhost:8502
2. 在侧边栏点击"用户管理" → "注册"
3. 填写用户名和邮箱
4. **必须阅读并同意以下协议**：
   - ✅ 文件夹使用协议
   - ✅ 本地操作授权确认
5. 完成注册，系统将在您的电脑创建专属文件夹

### 第三步：准备数据文件（关键步骤）
1. **在本地文件管理器中**找到您的用户数据文件夹：
   ```
   C:\idle-sense\node_data\user_data\{您的用户ID}
   ```
2. **将您的数据文件**放入此文件夹（CSV、TXT、JSON等）
3. **在网页界面编写脚本**读取您的数据文件

### 第四步：提交分布式计算任务
1. 在"任务提交"标签页选择"分布式任务"
2. 选择适合的任务类型或使用"通用任务"
3. 配置任务参数（分片大小、并行节点数等）
4. 输入或上传您的数据
5. 点击"提交分布式任务"
6. 系统自动分配多个节点并行执行
7. 在"任务监控"标签页查看合并后的结果

---

## 📁 本地文件夹结构说明

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

---

## 💻 分布式任务开发

### 分布式任务 vs 单节点任务
- **单节点任务**：适合小规模计算，单个节点处理
- **分布式任务**：适合大规模计算，多个节点并行处理，大幅提升效率

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

### 分布式任务开发示例

#### 预设模板任务
```python
# 数据处理模板示例
# 系统自动将大数据分片，每个节点处理一部分
def process_data_chunk(data_chunk):
    results = []
    for item in data_chunk:
        # 处理每个数据项
        processed_item = item * 2  # 示例处理逻辑
        results.append(processed_item)
    return results

# 系统会自动合并所有节点的结果
```

#### 自定义通用任务
```python
# 自定义数据处理代码（每个节点执行）
# __DATA__ 变量包含分配给这个节点的数据片段
# __CHUNK_ID__ 变量是当前数据片段的ID
# __CHUNK_INDEX__ 变量是当前数据片段的索引

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
```

```python
# 自定义结果合并代码（合并所有节点的结果）
# __CHUNK_RESULTS__ 变量包含所有节点返回的结果列表

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
```

---

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

---

## ⚡ 功能特性

### 开源无限制版本
- ✅ **无资源配额限制** - 充分利用您的硬件
- ✅ **无任务数量限制** - 随意提交计算任务  
- ✅ **无使用时间限制** - 24小时可用
- ✅ **跨平台支持** - Windows/macOS/Linux
- ✅ **本地部署** - 数据完全在本地处理，保护隐私

### 分布式计算系统
- 🔍 **自动数据分片** - 大数据自动分割成小块
- ⚖️ **智能任务分配** - 自动分配给多个节点并行处理
- 📊 **实时性能监控** - 监控每个节点的处理状态
- 🔄 **自动容错恢复** - 节点故障时自动重新分配任务

---

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
   netstat -ano | findstr :8502
   
   # 如果端口被占用
   # 方法1：终止占用进程
   taskkill /PID <进程ID> /F
   # 方法2：修改配置文件中的端口号
   ```

#### 分布式任务执行失败排查步骤
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
- **大文件**: > 100MB - 强烈建议使用分布式任务处理

---

## 📈 性能优化建议

### 分布式计算优化策略

#### 数据分片优化
1. **合理设置分片大小**
   - 小数据集：分片大小 10-50
   - 中等数据集：分片大小 50-100
   - 大数据集：分片大小 100-500

2. **并行节点数设置**
   - 小型任务：1-2个节点
   - 中型任务：3-5个节点
   - 大型任务：5-10个节点

#### 大数据集分布式处理示例
```python
# 预处理：将大文件分割成适合分布式处理的格式
def prepare_for_distributed_processing(input_file, output_prefix, chunk_size=1000):
    with open(input_file, 'r', encoding='utf-8') as f:
        header = f.readline()  # 保存标题行
        chunk_num = 0
        chunk_data = []
        
        for line in f:
            chunk_data.append(line)
            if len(chunk_data) >= chunk_size:
                # 写入分片文件
                chunk_file = f"{output_prefix}_chunk_{chunk_num}.csv"
                with open(chunk_file, 'w', encoding='utf-8') as chunk_f:
                    chunk_f.write(header)
                    chunk_f.writelines(chunk_data)
                
                chunk_data = []
                chunk_num += 1
        
        # 处理剩余数据
        if chunk_data:
            chunk_file = f"{output_prefix}_chunk_{chunk_num}.csv"
            with open(chunk_file, 'w', encoding='utf-8') as chunk_f:
                chunk_f.write(header)
                chunk_f.writelines(chunk_data)
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

---

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
3. **合理选择任务类型**：小任务用单节点，大任务用分布式
4. **备份重要数据**：定期备份用户数据文件夹中的重要文件

### 分布式计算优化
1. **数据预处理**：在本地预处理数据，优化分布式处理效率
2. **合理分片**：根据数据量和节点数设置合适的分片大小
3. **资源设置**：根据任务复杂度合理设置CPU和内存需求

---

## 🌟 分布式计算优势

1. **算力共享**：多台电脑并行处理，大幅提升计算效率
2. **自动分片**：系统自动将大数据分割成适合并行处理的小块
3. **智能调度**：自动分配任务给可用节点，实现负载均衡
4. **容错机制**：节点故障时自动重新分配，确保任务完成
5. **本地部署**：数据完全在本地处理，保护隐私和安全

---

**开始使用吧！将您的数据文件放入用户数据文件夹，然后选择合适的任务类型来处理它们。对于大规模数据，强烈推荐使用分布式任务来获得最佳性能。**