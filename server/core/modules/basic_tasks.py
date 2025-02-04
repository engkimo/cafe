from typing import Dict, Any, List
import semantic_kernel as sk
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
        }
    )
    async def create_workflow(self, context: Dict[str, Any]) -> str:
        """新しいワークフローを作成"""
        name = context["name"]
        description = context.get("description", "")
        tasks = context.get("tasks", [])
        
        result = {
            "workflow_id": "generated_id",
            "created_tasks": tasks
        }
        return str(result)

    @task_function(
        name="process_data",
        description="データの処理と変換",
        input_schema={
            "data": {"type": "object", "description": "処理するデータ", "required": True},
            "format": {"type": "string", "description": "出力フォーマット"},
            "filters": {"type": "array", "description": "適用するフィルター"}
        }
    )
    async def process_data(self, context: Dict[str, Any]) -> str:
        """データを処理して変換"""
        data = context["data"]
        format = context.get("format", "json")
        filters = context.get("filters", [])
        
        result = {
            "processed_data": data,
            "stats": {
                "processed_items": len(data),
                "format": format,
                "applied_filters": filters
            }
        }
        return str(result)

    @task_function(
        name="generate_report",
        description="レポートの生成",
        input_schema={
            "data": {"type": "object", "description": "レポートデータ", "required": True},
            "template": {"type": "string", "description": "レポートテンプレート"},
            "format": {"type": "string", "description": "出力フォーマット"}
        }
    )
    async def generate_report(self, context: Dict[str, Any]) -> str:
        """レポートを生成"""
        data = context["data"]
        template = context.get("template", "default")
        format = context.get("format", "pdf")
        
        result = {
            "report_url": f"https://example.com/reports/{template}_{format}",
            "metadata": {
                "template": template,
                "format": format,
                "generated_at": "2025-02-05T00:00:00Z"
            }
        }
        return str(result)

    @task_function(
        name="notify_completion",
        description="タスク完了通知の送信",
        input_schema={
            "task_id": {"type": "string", "description": "完了したタスクのID", "required": True},
            "recipients": {"type": "array", "description": "通知先", "required": True},
            "message": {"type": "string", "description": "通知メッセージ"}
        }
    )
    async def notify_completion(self, context: Dict[str, Any]) -> str:
        """タスク完了通知を送信"""
        task_id = context["task_id"]
        recipients = context["recipients"]
        message = context.get("message", f"Task {task_id} has been completed")
        
        result = {
            "notification_id": f"notify_{task_id}",
            "sent_to": recipients,
            "message": message
        }
        return str(result)

    # MCPとの連携用のヘルパーメソッド
    async def register_with_mcp(self, mcp_server):
        """MCPサーバーにスキルを登録"""
        try:
            skills = {
                "create_workflow": self.create_workflow,
                "process_data": self.process_data,
                "generate_report": self.generate_report,
                "notify_completion": self.notify_completion
            }
            
            for name, skill in skills.items():
                await mcp_server.register_skill(name, skill)
                
        except Exception as e:
            print(f"MCPスキル登録エラー: {str(e)}")
            raise