# 联邦协议文档

## 概述

Idle-Sense 联邦协议定义了多个调度中心之间协作的规范，实现跨组织的算力共享。

## 联邦架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         联邦网络层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Scheduler  │  │  Scheduler  │  │  Scheduler  │              │
│  │   Node A    │◄─┤   Node B    │◄─┤   Node C    │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
│         ▲                ▲                ▲                     │
│         │                │                │                     │
│         └────────────────┴────────────────┘                     │
│                    P2P 通信层                                    │
└─────────────────────────────────────────────────────────────────┘
```

## 核心概念

### 1. 联邦成员

每个调度中心作为联邦的一个成员：

```json
{
  "member_id": "federation-member-001",
  "name": "Organization A",
  "endpoint": "https://scheduler-a.example.com",
  "public_key": "-----BEGIN PUBLIC KEY-----...",
  "capabilities": {
    "max_tasks": 1000,
    "supported_runtimes": ["python", "wasm"]
  },
  "joined_at": "2024-01-01T00:00:00Z"
}
```

### 2. 联邦任务

跨成员执行的任务：

```json
{
  "task_id": "federation-task-001",
  "source_member": "member-001",
  "target_member": "member-002",
  "code": "...",
  "requirements": {
    "runtime": "python",
    "memory_mb": 512,
    "timeout": 300
  },
  "reward": {
    "tokens": 10,
    "currency": "IDLE"
  }
}
```

### 3. 信誉系统

基于 EigenTrust 的去中心化信誉：

```python
class ReputationScore:
    member_id: str
    local_score: float      # 本地评分
    global_score: float     # 全局评分
    positive_votes: int     # 正面投票数
    negative_votes: int     # 负面投票数
    last_updated: datetime
```

## 通信协议

### 1. 成员发现

使用 Kademlia DHT 进行成员发现：

```python
# 查找成员
def find_member(member_id: str) -> MemberInfo:
    """
    通过 DHT 查找成员信息
    
    1. 计算 member_id 的 Kademlia 距离
    2. 查询最近的 k 个节点
    3. 返回成员信息或 None
    """
    pass

# 加入联邦
def join_federation(bootstrap_nodes: list[str]) -> None:
    """
    加入联邦网络
    
    1. 连接到引导节点
    2. 发布自己的成员信息
    3. 同步成员列表
    """
    pass
```

### 2. 任务转发

当本地资源不足时，转发任务到其他成员：

```python
def forward_task(task: Task, target_member: MemberInfo) -> str:
    """
    转发任务到目标成员
    
    1. 验证目标成员能力
    2. 加密任务数据
    3. 发送到目标成员端点
    4. 返回联邦任务ID
    """
    pass
```

### 3. 结果同步

任务执行结果的同步：

```python
def sync_result(federation_task_id: str, result: TaskResult) -> None:
    """
    同步任务结果
    
    1. 验证结果签名
    2. 更新任务状态
    3. 通知源成员
    4. 结算奖励
    """
    pass
```

## 安全机制

### 1. 身份验证

使用公钥基础设施 (PKI)：

```python
class MemberIdentity:
    member_id: str
    public_key: str
    certificate: str      # 由联邦CA签发
    
    def sign(self, data: bytes) -> bytes:
        """使用私钥签名数据"""
        pass
    
    def verify(self, data: bytes, signature: bytes) -> bool:
        """验证签名"""
        pass
```

### 2. 任务加密

端到端加密保护任务数据：

```python
def encrypt_task(task: Task, recipient_public_key: str) -> EncryptedTask:
    """
    加密任务数据
    
    1. 生成临时对称密钥
    2. 使用对称密钥加密任务
    3. 使用接收者公钥加密对称密钥
    4. 返回加密任务
    """
    pass
```

### 3. 访问控制

基于策略的访问控制：

```yaml
# 访问控制策略
policies:
  - name: "allow-trusted-members"
    effect: allow
    condition:
      reputation_score: ">= 0.8"
      
  - name: "deny-blacklisted"
    effect: deny
    condition:
      member_id: ["bad-actor-1", "bad-actor-2"]
      
  - name: "rate-limit"
    effect: throttle
    condition:
      requests_per_minute: 100
```

## 代币经济

### 1. 跨成员结算

```python
class FederationSettlement:
    source_member: str
    target_member: str
    amount: Decimal
    task_ids: list[str]
    timestamp: datetime
    
    def settle(self) -> SettlementResult:
        """
        执行跨成员结算
        
        1. 验证双方余额
        2. 锁定转账金额
        3. 执行原子转账
        4. 记录交易日志
        """
        pass
```

### 2. 定价机制

EIP-1559 风格的动态定价：

```python
def calculate_task_price(task: Task, market_conditions: MarketInfo) -> Decimal:
    """
    计算任务价格
    
    base_fee = market_conditions.base_fee
    priority_fee = task.priority * market_conditions.priority_rate
    gas_estimate = estimate_gas(task)
    
    total_price = (base_fee + priority_fee) * gas_estimate
    return total_price
    """
    pass
```

## Gossip 协议

用于成员间信息传播：

```python
class GossipMessage:
    message_id: str
    message_type: str  # "member_join", "member_leave", "task_forward", etc.
    payload: dict
    timestamp: datetime
    ttl: int           # 传播跳数限制
    
def broadcast(message: GossipMessage) -> None:
    """
    广播消息到联邦网络
    
    1. 选择随机子集节点
    2. 发送消息
    3. 接收者继续传播（TTL递减）
    """
    pass
```

## NAT 穿透

支持 NAT 环境下的通信：

### 1. STUN

```python
def discover_public_endpoint() -> tuple[str, int]:
    """
    通过 STUN 发现公网端点
    
    1. 发送 STUN 请求到 STUN 服务器
    2. 解析响应获取公网 IP 和端口
    3. 返回端点信息
    """
    pass
```

### 2. TURN

作为中继服务器：

```python
class TurnRelay:
    relay_server: str
    allocation: tuple[str, int]
    
    def create_relay(self) -> RelayInfo:
        """
        创建 TURN 中继
        
        1. 向 TURN 服务器请求分配
        2. 获取中继地址和端口
        3. 返回中继信息
        """
        pass
```

### 3. UPnP

自动端口映射：

```python
def setup_upnp_mapping(internal_port: int, external_port: int) -> bool:
    """
    设置 UPnP 端口映射
    
    1. 发现 UPnP 设备
    2. 请求端口映射
    3. 返回是否成功
    """
    pass
```

## 联邦治理

### 1. 提案系统

```python
class Proposal:
    proposal_id: str
    proposer: str
    title: str
    description: str
    changes: dict
    voting_end: datetime
    status: str  # "pending", "approved", "rejected"
    
def submit_proposal(proposal: Proposal) -> None:
    """提交治理提案"""
    pass

def vote(proposal_id: str, vote: str, weight: float) -> None:
    """对提案投票"""
    pass
```

### 2. 投票权重

基于质押和信誉的投票权重：

```python
def calculate_voting_weight(member_id: str) -> float:
    """
    计算投票权重
    
    stake = get_stake(member_id)
    reputation = get_reputation(member_id)
    tenure = get_membership_duration(member_id)
    
    weight = (stake * 0.5) + (reputation * 0.3) + (tenure_factor * 0.2)
    return weight
    """
    pass
```

## 兼容性

### 协议版本

```
FEDERATION_PROTOCOL_VERSION = "1.0.0"
```

### 能力协商

```python
def negotiate_capabilities(remote_member: MemberInfo) -> SharedCapabilities:
    """
    协商共同能力
    
    1. 获取双方能力列表
    2. 找出交集
    3. 返回共享能力
    """
    pass
```

## 监控指标

| 指标 | 说明 |
|------|------|
| federation.members.count | 联邦成员数量 |
| federation.tasks.forwarded | 转发任务数 |
| federation.tasks.received | 接收任务数 |
| federation.settlements.total | 结算总额 |
| federation.latency.p50 | 通信延迟 P50 |
| federation.latency.p99 | 通信延迟 P99 |

---

**最后更新**: 2026-03-28
