from typing import Dict, Any, List, Optional
import json
from datetime import datetime
from .server import Server
from .types import McpError, ErrorCode

class WorkflowServer:
    """ワークフロー管理用のMCPサーバー"""
    
    def __init__(self):
        self.server = Server(
            {
                "name": "workflow-server",
                "version": "0.1.0",
                "capabilities": {
                    "resources": {},
                    "tools": {},
                    "resource_templates": []
                }
            },
            {}
        )
        
        self._setup_tools()
        self._setup_resources()
        
        # エラーハンドリング
        self.server.onerror = lambda error: print("[MCP Error]", error)
    
    def _setup_tools(self):
        """利用可能なツールを設定"""
        self.server.add_tool(
            "get_workflow_status",
            "ワークフローの現在の状態を取得",
            {
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "ワークフローID"
                    }
                },
                "required": ["workflow_id"]
            },
            self._handle_get_workflow_status
        )
        
        self.server.add_tool(
            "update_workflow",
            "ワークフローの状態を更新",
            {
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "ワークフローID"
                    },
                    "tasks": {
                        "type": "array",
                        "description": "更新されたタスクリスト"
                    },
                    "auto_save": {
                        "type": "boolean",
                        "description": "自動保存モードの状態"
                    }
                },
                "required": ["workflow_id", "tasks"]
            },
            self._handle_update_workflow
        )
        
        self.server.add_tool(
            "get_workflow_history",
            "ワークフローの実行履歴を取得",
            {
                "type": "object",
                "properties": {
                    "workflow_id": {
                        "type": "string",
                        "description": "ワークフローID"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "取得する履歴の最大数"
                    }
                },
                "required": ["workflow_id"]
            },
            self._handle_get_workflow_history
        )
    
    def _setup_resources(self):
        """利用可能なリソースを設定"""
        self.server.add_resource_template(
            "workflow://{workflow_id}/status",
            "ワークフローの状態",
            "application/json",
            self._handle_get_workflow_resource
        )
        
        self.server.add_resource_template(
            "workflow://{workflow_id}/visualization",
            "ワークフローの可視化データ",
            "application/json",
            self._handle_get_visualization_resource
        )
    
    async def _handle_get_workflow_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """ワークフローの状態を取得"""
        try:
            workflow_id = params["workflow_id"]
            # TODO: 実際のワークフロー状態の取得処理を実装
            return {
                "workflow_id": workflow_id,
                "status": "running",
                "progress": 0.75,
                "current_task": "task_3",
                "updated_at": datetime.now().isoformat()
            }
        except Exception as e:
            raise McpError(ErrorCode.InternalError, str(e))
    
    async def _handle_update_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """ワークフローの状態を更新"""
        try:
            workflow_id = params["workflow_id"]
            tasks = params["tasks"]
            auto_save = params.get("auto_save", False)
            
            # TODO: 実際のワークフロー更新処理を実装
            return {
                "workflow_id": workflow_id,
                "updated_tasks": len(tasks),
                "auto_save_enabled": auto_save,
                "updated_at": datetime.now().isoformat()
            }
        except Exception as e:
            raise McpError(ErrorCode.InternalError, str(e))
    
    async def _handle_get_workflow_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """ワークフローの実行履歴を取得"""
        try:
            workflow_id = params["workflow_id"]
            limit = params.get("limit", 10)
            
            # TODO: 実際の履歴取得処理を実装
            return {
                "workflow_id": workflow_id,
                "history": [
                    {
                        "timestamp": datetime.now().isoformat(),
                        "action": "task_completed",
                        "task_id": "task_1",
                        "status": "success"
                    }
                ],
                "total_entries": 1
            }
        except Exception as e:
            raise McpError(ErrorCode.InternalError, str(e))
    
    async def _handle_get_workflow_resource(self, uri: str) -> Dict[str, Any]:
        """ワークフローリソースを取得"""
        try:
            workflow_id = uri.split("/")[1]
            return {
                "workflow_id": workflow_id,
                "status": "running",
                "tasks": [
                    {
                        "id": "task_1",
                        "name": "データ処理",
                        "status": "completed"
                    }
                ]
            }
        except Exception as e:
            raise McpError(ErrorCode.InternalError, str(e))
    
    async def _handle_get_visualization_resource(self, uri: str) -> Dict[str, Any]:
        """ワークフロー可視化データを取得"""
        try:
            workflow_id = uri.split("/")[1]
            return {
                "workflow_id": workflow_id,
                "nodes": [
                    {
                        "id": "task_1",
                        "type": "task",
                        "position": {"x": 100, "y": 100},
                        "data": {"label": "データ処理"}
                    }
                ],
                "edges": []
            }
        except Exception as e:
            raise McpError(ErrorCode.InternalError, str(e))
    
    async def run(self):
        """MCPサーバーを起動"""
        print("Workflow MCP server running")
        return self  # サーバーインスタンスを返す