# 设计决策文档

## 🎯 核心设计原则

### 1. 用户无感知原则
**决策**: 闲置检测必须准确，绝不干扰电脑正常使用
**实现**:
- 多重条件验证（空闲时间 + CPU使用率 + 内存使用率 + 屏幕状态）
- 保守阈值设置（宁可错过，不可误判）
- 实时资源监控，超出阈值立即停止

### 2. 提供者安全第一原则
**决策**: 计算节点安全比任务执行更重要
**实现**:
- 沙箱环境执行任务
- 严格的资源限制（CPU、内存、磁盘、网络）
- 任务完成后自动清理所有临时文件
- 默认禁止网络访问

### 3. 最小可行方案原则
**决策**: 先实现核心功能，再逐步优化扩展
**实现**:
- 内存存储而非数据库（简化部署）
- 简单的先进先出调度（初期）
- 基础HTTP API（无复杂协议）

## 🔍 闲置判定算法设计

### 问题定义
如何准确判断"个人电脑真闲置"？

### 算法设计

```python
def is_truly_idle() -> bool:
    """
    五重验证的闲置判定算法
    全部条件满足才返回True
    """
    # 1. 用户无操作时间 > 5分钟
    idle_time = get_user_idle_time()
    
    # 2. CPU使用率 < 30%
    cpu_usage = get_cpu_usage()
    
    # 3. 内存使用率 < 70%
    memory_usage = get_memory_usage()
    
    # 4. 屏幕已锁定或无前台应用
    screen_locked = is_screen_locked()
    
    # 5. 正在充电或无电池设备
    is_charging = is_power_charging()
    has_battery = has_battery()
    
    return all([
        idle_time > 300,           # 条件1: 5分钟无操作
        cpu_usage < 30.0,          # 条件2: CPU空闲70%以上
        memory_usage < 70.0,       # 条件3: 内存充足
        screen_locked,             # 条件4: 屏幕锁定
        is_charging or not has_battery  # 条件5: 不消耗用户电量
    ])
```

### 设计理由

1. **300秒阈值**: 避免短暂离开误判（接电话、取物品）
2. **CPU<30%**: 保留足够资源保证系统流畅
3. **内存<70%**: 防止内存压力影响用户体验
4. **屏幕锁定**: 物理层面确保用户不在使用
5. **充电状态**: 只使用电网电源，不消耗电池

## 🛡️ 安全边界设计

### 执行环境隔离

```python
class SafeExecutionEnvironment:
    def execute_safely(self, code: str) -> str:
        # 1. 创建临时工作目录
        temp_dir = self._create_temp_directory()
        
        # 2. 设置资源限制
        self._set_resource_limits(
            max_cpu_time=300,      # 5分钟CPU时间
            max_memory_mb=1024,    # 1GB内存限制
            max_disk_mb=100        # 100MB磁盘限制
        )
        
        # 3. 网络访问控制
        if not self.config.allow_network:
            self._disable_network_access()
        
        # 4. 在受限环境中执行
        result = self._run_in_sandbox(code, temp_dir)
        
        # 5. 强制清理（即使异常）
        self._force_cleanup(temp_dir)
        
        return result
```

### 安全措施分层

1. **进程隔离**: 每个任务在独立进程中运行
2. **资源限制**: 限制CPU、内存、磁盘使用
3. **权限降级**: 以非特权用户身份运行
4. **文件沙箱**: 限制文件系统访问范围
5. **网络控制**: 默认禁止所有网络访问

## ⚖️ 公平调度算法

### 设计目标

- 奖励高贡献节点，但不让新节点饿死
- 考虑等待时间，防止无限期等待
- 简单易懂，易于实现和维护

### 算法实现

```python
def calculate_node_priority(node: NodeInfo) -> float:
    """
    计算节点优先级（数值越低优先级越高）
    """
    # 基础等待时间（等待越久优先级越高）
    wait_score = -node.wait_time_seconds * 0.6
    
    # 贡献度奖励（但有上限）
    contribution = min(node.tasks_completed * 0.1, 10.0)
    contrib_score = -contribution * 0.3
    
    # 新人加成（前10个任务）
    newcomer_bonus = 0
    if node.tasks_completed < 10:
        newcomer_bonus = 20 - node.tasks_completed * 2
    newcomer_score = -newcomer_bonus * 0.1
    
    # 防饥饿：等待超过5分钟自动最高优先级
    if node.wait_time_seconds > 300:
        return float('-inf')
    
    # 冷却期：最近执行过的降低优先级
    if time.time() - node.last_task_time < 1800:  # 30分钟
        wait_score *= 0.5
    
    return wait_score + contrib_score + newcomer_score
```

### 调度策略参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 等待时间权重 | 60% | 主要考虑因素 |
| 贡献度权重 | 30% | 适度奖励贡献 |
| 新人加成权重 | 10% | 保证新节点机会 |
| 贡献度上限 | 10分 | 防止过度倾斜 |
| 防饥饿阈值 | 300秒 | 5分钟自动最高优先级 |
| 冷却时间 | 1800秒 | 30分钟内降低优先级 |

## 📡 通信协议设计

### 任务格式

```json
{
  "task_id": "uuid-v4",
  "code": "print('Hello World')",
  "timeout": 300,
  "resources": {
    "cpu": 1.0,
    "memory": 512
  },
  "created_at": "2024-01-01T00:00:00Z"
}
```

### 节点心跳格式

```json
{
  "node_id": "macbook-pro-001",
  "status": "idle",
  "resources": {
    "cpu_cores": 8,
    "memory_mb": 16384,
    "platform": "macOS"
  },
  "idle_since": "2024-01-01T00:05:00Z"
}
```

### 设计考虑

1. **简单JSON**: 易于解析和调试
2. **明确字段**: 避免歧义
3. **时间戳**: ISO 8601格式，标准化
4. **资源单位**: 统一使用标准单位（MB、核心数）

## ⚙️ 配置系统设计

### 分层配置优先级

1. 命令行参数 (最高优先级)
2. 环境变量
3. 配置文件 (`config/config.yaml`)
4. 默认值 (最低优先级，安全保守)

### 关键配置项

```yaml
# 调度中心配置
scheduler:
  host: "0.0.0.0"
  port: 8000
  max_queue_size: 1000
  result_ttl: 3600

# 节点配置
node:
  scheduler_url: "http://localhost:8000"
  check_interval: 30
  idle_threshold: 300
  max_task_time: 300
  
# 安全配置
security:
  max_memory_mb: 1024
  network_access: false
  auto_cleanup: true
```

## 🔄 扩展性考虑

### 水平扩展设计

- 调度中心可多实例部署
- Redis作为共享任务队列
- 负载均衡器分发请求
- 无状态设计，易于扩展

### 未来扩展点

1. **GPU计算支持**: 检测GPU闲置状态
3. **去中心化调度**: 基于区块链的信誉系统
4. **节能模式**: 电价低谷时更积极调度

### 插件架构预留

```python
# 插件系统接口
class Plugin:
    def initialize(self, config):
        pass
    
    def process(self, data):
        pass
    
    def cleanup(self):
        pass

# 插件注册机制
PLUGIN_REGISTRY = {
    "detectors": {},
    "schedulers": {},
    "executors": {}
}
```

## 📊 性能与可靠性

### 性能目标

- 任务调度延迟 < 100ms
- 支持1000+节点并发
- 内存使用 < 512MB（基础运行）
- 启动时间 < 5秒

### 可靠性措施

1. **任务持久化**: 定期保存到磁盘
2. **心跳检测**: 节点健康状态监控
3. **自动恢复**: 进程崩溃后自动重启
4. **优雅降级**: 部分功能失败不影响核心

### 监控指标

- 活跃节点数量
- 任务队列长度
- 平均任务执行时间
- 系统资源使用率
- 错误率统计

## 🎨 用户体验设计

### 网页界面原则

1. **简洁直观**: 功能明确，无冗余信息
2. **实时反馈**: 任务状态实时更新
3. **渐进披露**: 高级功能隐藏，需要时展开
4. **一致性**: 界面元素和行为一致

### API设计原则

1. **RESTful风格**: 资源导向，HTTP方法明确
2. **一致响应格式**: 统一成功/错误响应结构
3. **版本管理**: API版本化，向后兼容
4. **详细文档**: 每个端点有明确说明和示例

## 🔍 技术选型理由

### Python

- **理由**: 快速开发，丰富的科学计算库
- **替代方案**: Go（性能更好但开发速度慢）
- **权衡**: 选择开发速度而非极致性能

### FastAPI

- **理由**: 现代异步框架，自动API文档
- **替代方案**: Flask（更轻量但功能较少）
- **权衡**: 选择功能完整性和开发效率

### 内存存储

- **理由**: 简化部署，无需外部数据库
- **替代方案**: Redis（性能更好但增加依赖）
- **权衡**: 选择简单性，未来可替换

### Streamlit

- **理由**: 快速构建数据应用，无需前端知识
- **替代方案**: React + FastAPI（更灵活但复杂）
- **权衡**: 选择开发速度，专注后端逻辑

---

**最后更新**: 2026-03-28
