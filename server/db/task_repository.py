from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from typing import List, Optional, Dict, Any
from datetime import datetime
import json

from ..models import Task, WorkflowRun

class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(self, task_data: Dict[str, Any]) -> Task:
        """新しいタスクを作成"""
        task = Task(
            name=task_data["name"],
            type=task_data["type"],
            inputs=task_data.get("inputs", {}),
            outputs=task_data.get("outputs", {}),
            status="pending",
            dependencies=task_data.get("dependencies", [])
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get_task_by_id(self, task_id: int) -> Optional[Task]:
        """IDに基づいてタスクを取得"""
        query = select(Task).where(Task.id == task_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_tasks_by_name(self, task_name: str) -> List[Task]:
        """名前による複数タスクの取得（作成日時でソート）"""
        result = await self.session.execute(
            select(Task)
            .where(Task.name == task_name)
            .order_by(Task.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_task_by_name(self, task_name: str) -> Optional[Task]:
        """名前に基づいてタスクを取得"""
        query = select(Task).where(Task.name == task_name)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_task(self, task: Task) -> None:
        """タスクを更新"""
        await self.session.commit()

    async def delete_all_tasks(self) -> None:
        """すべてのタスクを削除"""
        await self.session.execute(delete(Task))
        await self.session.commit()

    async def create_workflow_run(self) -> WorkflowRun:
        """新しいワークフロー実行記録を作成"""
        workflow_run = WorkflowRun(
            status="running",
            result={},
            started_at=datetime.now()
        )
        self.session.add(workflow_run)
        await self.session.commit()
        await self.session.refresh(workflow_run)
        return workflow_run

    async def update_workflow_run(self, workflow_run: WorkflowRun) -> None:
        """ワークフロー実行記録を更新"""
        await self.session.commit()

    async def get_tasks_by_ids(self, task_ids: List[int]) -> List[Task]:
        """複数のタスクをIDで取得"""
        result = await self.session.execute(
            select(Task).where(Task.id.in_(task_ids))
        )
        return result.scalars().all()

    async def get_dependent_tasks(self, task_name: str) -> List[Task]:
        """指定されたタスクに依存する他のタスクを取得"""
        result = await self.session.execute(
            select(Task).where(Task.dependencies.contains([task_name]))
        )
        return result.scalars().all()

    async def get_tasks_by_type(self, task_type: str) -> List[Task]:
        """タイプに基づいてタスクを取得"""
        query = select(Task).where(Task.type == task_type)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_all_tasks(self) -> List[Task]:
        """すべてのタスクを取得"""
        query = select(Task)
        result = await self.session.execute(query)
        return result.scalars().all()