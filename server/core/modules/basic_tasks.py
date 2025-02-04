from typing import Dict, Any, List
from ..decorators import ModuleBase, task_function

class BasicTaskModule(ModuleBase):
    """基本的なタスク機能を提供するモジュール"""
    
    @task_function(
        name="create_workflow",
        description="新しいワークフローを作成",
        input_schema={
            "name": {"type": "string", "description": "ワークフロー名", "required": True},
            "description": {"type": "string", "description": "ワークフローの説明"},
            "tasks": {"type": "array", "description": "タスクのリスト", "required": True}
        },
        output_schema={
            "type": "object",
            "properties": {
                "workflow_id": {"type": "string"},
                "created_tasks": {"type": "array"}
            }
        }
    )
    async def create_workflow(self, name: str, description: str = "", tasks: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """新しいワークフローを作成"""
        return {
            "workflow_id": "generated_id",
            "created_tasks": tasks or []
        }

    @task_function(
        name="process_data",
        description="データの処理と変換",
        input_schema={
            "data": {"type": "object", "description": "処理するデータ", "required": True},
            "format": {"type": "string", "description": "出力フォーマット"},
            "filters": {"type": "array", "description": "適用するフィルター"}
        },
        output_schema={
            "type": "object",
            "properties": {
                "processed_data": {"type": "object"},
                "stats": {"type": "object"}
            }
        },
        required_tools=["data_processor"]
    )
    async def process_data(
        self,
        data: Dict[str, Any],
        format: str = "json",
        filters: List[str] = None
    ) -> Dict[str, Any]:
        """データを処理して変換"""
        return {
            "processed_data": data,
            "stats": {
                "processed_items": len(data),
                "format": format,
                "applied_filters": filters or []
            }
        }

    @task_function(
        name="generate_report",
        description="レポートの生成",
        input_schema={
            "data": {"type": "object", "description": "レポートデータ", "required": True},
            "template": {"type": "string", "description": "レポートテンプレート"},
            "format": {"type": "string", "description": "出力フォーマット"}
        },
        output_schema={
            "type": "object",
            "properties": {
                "report_url": {"type": "string"},
                "metadata": {"type": "object"}
            }
        },
        required_tools=["template_engine", "pdf_generator"]
    )
    async def generate_report(
        self,
        data: Dict[str, Any],
        template: str = "default",
        format: str = "pdf"
    ) -> Dict[str, Any]:
        """レポートを生成"""
        return {
            "report_url": f"https://example.com/reports/{template}_{format}",
            "metadata": {
                "template": template,
                "format": format,
                "generated_at": "2025-02-05T00:00:00Z"
            }
        }

    @task_function(
        name="notify_completion",
        description="タスク完了通知の送信",
        input_schema={
            "task_id": {"type": "string", "description": "完了したタスクのID", "required": True},
            "recipients": {"type": "array", "description": "通知先", "required": True},
            "message": {"type": "string", "description": "通知メッセージ"}
        },
        output_schema={
            "type": "object",
            "properties": {
                "notification_id": {"type": "string"},
                "sent_to": {"type": "array"}
            }
        },
        required_tools=["notification_service"]
    )
    async def notify_completion(
        self,
        task_id: str,
        recipients: List[str],
        message: str = None
    ) -> Dict[str, Any]:
        """タスク完了通知を送信"""
        return {
            "notification_id": f"notify_{task_id}",
            "sent_to": recipients,
            "message": message or f"Task {task_id} has been completed"
        }