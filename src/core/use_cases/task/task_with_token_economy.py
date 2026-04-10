"""
集成代币经济的任务用例

包含：
- 任务提交时的代币扣除
- 任务完成时的代币奖励
- 声誉系统集成
- 贡献证明生成
"""

import time
from dataclasses import dataclass
from typing import Any, Optional

from legacy.token_economy import ResourceMetrics
from src.core.entities import TaskFactory, TaskStatus
from src.core.interfaces.repositories import ITaskRepository
from src.core.interfaces.services import ISchedulerService
from src.core.services import TokenEconomyService
from src.core.services.contribution_proof_service import ContributionProofService
from src.core.services.merit_rank_service import MeritRankEngine
from src.infrastructure.audit import AuditAction, AuditLogger


@dataclass
class SubmitTaskWithTokenRequest:
    """带代币经济的任务提交请求"""

    code: str
    user_id: Optional[str] = None
    timeout: int = 300
    cpu: float = 1.0
    memory: int = 512
    priority: float = 0.0


@dataclass
class SubmitTaskWithTokenResponse:
    """带代币经济的任务提交响应"""

    success: bool
    task_id: str = ""
    message: str = ""
    cost_estimate: Optional[dict[str, Any]] = None
    account_info: Optional[dict[str, Any]] = None


@dataclass
class CompleteTaskWithTokenRequest:
    """完成任务并发放奖励请求"""

    task_id: str
    result: str
    quality_score: float = 1.0
    execution_time_seconds: float = 0.0
    peak_memory_mb: float = 0.0


@dataclass
class CompleteTaskWithTokenResponse:
    """完成任务响应"""

    success: bool
    message: str = ""
    reward_info: Optional[dict[str, Any]] = None
    contribution_proof_id: Optional[str] = None


class SubmitTaskWithTokenEconomyUseCase:
    """
    集成代币经济的任务提交流程

    功能：
    1. 估算任务成本
    2. 检查用户余额
    3. 扣除代币
    4. 提交任务
    5. 记录审计日志
    """

    def __init__(
        self,
        task_repository: ITaskRepository,
        scheduler_service: ISchedulerService,
        token_economy_service: TokenEconomyService,
        audit_logger: AuditLogger,
    ):
        self._task_repository = task_repository
        self._scheduler_service = scheduler_service
        self._token_economy = token_economy_service
        self._audit_logger = audit_logger

    def execute(self, request: SubmitTaskWithTokenRequest) -> SubmitTaskWithTokenResponse:
        """
        执行带代币经济的任务提交

        Args:
            request: 任务提交请求

        Returns:
            提交响应
        """
        if not request.user_id:
            return SubmitTaskWithTokenResponse(success=False, message="需要用户ID才能提交任务")

        try:
            cost_estimate = self._token_economy.estimate_task_cost(
                cpu=request.cpu,
                memory=request.memory,
                timeout=request.timeout,
                priority=request.priority,
            )

            final_price = cost_estimate["final_price"]

            economy = self._token_economy.economy
            account = economy.get_account(request.user_id)

            if account is None:
                account = economy.create_account(
                    request.user_id, initial_balance=self._token_economy._initial_balance
                )

            if account.balance < final_price:
                return SubmitTaskWithTokenResponse(
                    success=False,
                    message=f"余额不足。需要: {final_price:.4f} CMP, 当前: {account.balance:.4f} CMP",
                    cost_estimate=cost_estimate,
                    account_info=self._token_economy.get_account_info(request.user_id),
                )

            task = TaskFactory.create(
                code=request.code,
                user_id=request.user_id,
                timeout=request.timeout,
                cpu=request.cpu,
                memory=request.memory,
            )

            scheduler_result = self._scheduler_service.submit_task(
                code=task.code,
                timeout=task.timeout,
                cpu=task.cpu_request,
                memory=task.memory_request,
                user_id=task.user_id,
            )

            if not scheduler_result[0]:
                return SubmitTaskWithTokenResponse(
                    success=False,
                    message=f"提交到调度器失败: {scheduler_result[1].get('error', '未知错误')}",
                )

            task.task_id = scheduler_result[1].get("task_id", task.task_id)
            self._task_repository.save(task)

            resources = ResourceMetrics(
                cpu_seconds=request.cpu * request.timeout,
                memory_gb_seconds=(request.memory / 1024) * request.timeout,
            )

            economy = self._token_economy.economy
            economy.create_task_payment(
                task_id=task.task_id,
                requester=request.user_id,
                total_budget=final_price,
                resources=resources,
                priority=int(request.priority),
            )

            self._audit_logger.log(
                action=AuditAction.TASK_SUBMIT,
                user_id=request.user_id,
                resource_type="task",
                resource_id=task.task_id,
                details={
                    "task_id": task.task_id,
                    "cost": final_price,
                    "cpu": request.cpu,
                    "memory": request.memory,
                    "timeout": request.timeout,
                },
            )

            return SubmitTaskWithTokenResponse(
                success=True,
                task_id=task.task_id,
                message="任务提交成功",
                cost_estimate=cost_estimate,
                account_info=self._token_economy.get_account_info(request.user_id),
            )

        except Exception as e:
            return SubmitTaskWithTokenResponse(success=False, message=f"提交任务失败: {str(e)}")


class CompleteTaskWithTokenEconomyUseCase:
    """
    集成代币经济的任务完成流程

    功能：
    1. 完成任务
    2. 计算并发放奖励
    3. 更新声誉
    4. 生成贡献证明
    5. 记录审计日志
    """

    def __init__(
        self,
        task_repository: ITaskRepository,
        scheduler_service: ISchedulerService,
        token_economy_service: TokenEconomyService,
        merit_rank_engine: MeritRankEngine,
        contribution_proof_service: ContributionProofService,
        audit_logger: AuditLogger,
    ):
        self._task_repository = task_repository
        self._scheduler_service = scheduler_service
        self._token_economy = token_economy_service
        self._merit_rank = merit_rank_engine
        self._contribution_proof = contribution_proof_service
        self._audit_logger = audit_logger

    def execute(self, request: CompleteTaskWithTokenRequest) -> CompleteTaskWithTokenResponse:
        """
        执行任务完成并发放奖励

        Args:
            request: 完成任务请求

        Returns:
            完成响应
        """
        try:
            task = self._task_repository.get_by_id(request.task_id)
            if not task:
                return CompleteTaskWithTokenResponse(
                    success=False, message=f"任务ID '{request.task_id}' 不存在"
                )

            if task.status in [TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED]:
                return CompleteTaskWithTokenResponse(
                    success=False, message=f"任务已处于 {task.status.value} 状态"
                )

            task.status = TaskStatus.COMPLETED
            task.result = request.result
            task.completed_at = time.time()
            self._task_repository.save(task)

            scheduler_success = self._scheduler_service.complete_task(
                task_id=request.task_id, result=request.result
            )

            if not scheduler_success:
                return CompleteTaskWithTokenResponse(
                    success=False, message="调度器标记任务完成失败"
                )

            reward_info = None
            contribution_proof_id = None
            node_address = task.assigned_node or "unknown"

            if task.user_id and node_address != "unknown":
                resource_metrics = ResourceMetrics(
                    cpu_seconds=request.execution_time_seconds,
                    memory_gb_seconds=(request.peak_memory_mb / 1024)
                    * request.execution_time_seconds,
                )

                economy = self._token_economy.economy
                reward_amount, tx = economy.reward_worker(
                    task_id=request.task_id,
                    worker_address=node_address,
                    actual_resources=resource_metrics,
                    quality_score=request.quality_score,
                )

                if reward_amount > 0:
                    reward_info = {"worker_reward": reward_amount, "quality_bonus": 0, "refund": 0}

                economy.finalize_task(task_id=request.task_id)

                if request.quality_score >= 0.8:
                    self._merit_rank.record_task_completion(
                        node_address=node_address,
                        requester_address=task.user_id,
                        quality_score=request.quality_score,
                    )
                else:
                    self._merit_rank.record_task_failure(
                        node_address=node_address, requester_address=task.user_id
                    )

                proof = self._contribution_proof.generate_proof(
                    node_address=node_address,
                    task_id=request.task_id,
                    resource_metrics=resource_metrics,
                    quality_score=request.quality_score,
                    code_length=len(task.code),
                    reputation=self._merit_rank.get_reputation(node_address),
                )
                contribution_proof_id = proof.proof_id

            self._audit_logger.log(
                action=AuditAction.TASK_COMPLETE,
                user_id=task.user_id or "system",
                resource_type="task",
                resource_id=request.task_id,
                details={
                    "task_id": request.task_id,
                    "node_address": node_address,
                    "quality_score": request.quality_score,
                    "reward_info": reward_info,
                    "contribution_proof_id": contribution_proof_id,
                },
            )

            return CompleteTaskWithTokenResponse(
                success=True,
                message="任务完成成功",
                reward_info=reward_info,
                contribution_proof_id=contribution_proof_id,
            )

        except Exception as e:
            return CompleteTaskWithTokenResponse(success=False, message=f"完成任务失败: {str(e)}")


__all__ = [
    "SubmitTaskWithTokenEconomyUseCase",
    "SubmitTaskWithTokenRequest",
    "SubmitTaskWithTokenResponse",
    "CompleteTaskWithTokenEconomyUseCase",
    "CompleteTaskWithTokenRequest",
    "CompleteTaskWithTokenResponse",
]
