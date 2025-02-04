from typing import Dict, List, Any, Optional
import json
from datetime import datetime
import semantic_kernel as sk
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

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
        
        # Semantic Kernel初期化
        self.kernel = sk.Kernel()
        self.registered_skills = {}
        
        self._setup_tools()
        self._setup_resources()
        
        # エラーハンドリング
        self.server.onerror = lambda error: print("[MCP Error]", error)
    
    async def register_skill(self, name: str, skill_function: Any):
        """Semantic Kernelスキルを登録"""
        try:
            self.registered_skills[name] = skill_function
            self.kernel.import_skill(skill_function, name)
            print(f"Registered skill: {name}")
        except Exception as e:
            print(f"Skill registration error: {str(e)}")
            raise
    
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
            "execute_skill",
            "Semantic Kernelスキルを実行",
            {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "実行するスキル名"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "スキルのパラメータ"
                    }
                },
                "required": ["skill_name", "parameters"]
            },
            self._handle_execute_skill
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
    
    async def _handle_execute_skill(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Semantic Kernelスキルを実行"""
        try:
            skill_name = params["skill_name"]
            parameters = params["parameters"]
            
            if skill_name not in self.registered_skills:
                raise McpError(ErrorCode.InvalidRequest, f"Skill not found: {skill_name}")
            
            context = self.kernel.create_new_context()
            for key, value in parameters.items():
                context[key] = str(value)
            
            result = await self.registered_skills[skill_name](context)
            return {"result": result}
            
        except Exception as e:
            raise McpError(ErrorCode.InternalError, str(e))
    
    async def _handle_get_workflow_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """ワークフローの状態を取得"""
        try:
            workflow_id = params["workflow_id"]
            context = self.kernel.create_new_context()
            context["workflow_id"] = workflow_id
            
            status_function = self.kernel.create_semantic_function("""
            ワークフローの状態を分析し、以下の情報を返してください:
            - 全体の進捗状況
            - 現在実行中のタスク
            - 完了したタスク
            - 次に実行予定のタスク
            
            ワークフローID: {{$workflow_id}}
            """)
            
            result = await status_function.invoke_async(context=context)
            return json.loads(result.result)
            
        except Exception as e:
            raise McpError(ErrorCode.InternalError, str(e))
    
    async def _handle_update_workflow(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """ワークフローの状態を更新"""
        try:
            workflow_id = params["workflow_id"]
            tasks = params["tasks"]
            auto_save = params.get("auto_save", False)
            
            context = self.kernel.create_new_context()
            context["workflow_id"] = workflow_id
            context["tasks"] = json.dumps(tasks)
            context["auto_save"] = str(auto_save)
            
            update_function = self.kernel.create_semantic_function("""
            ワークフローの状態を更新し、以下の処理を行ってください:
            1. 各タスクの状態を更新
            2. 依存関係を検証
            3. 自動保存モードの場合はデータを永続化
            
            ワークフローID: {{$workflow_id}}
            タスク: {{$tasks}}
            自動保存: {{$auto_save}}
            """)
            
            result = await update_function.invoke_async(context=context)
            return json.loads(result.result)
            
        except Exception as e:
            raise McpError(ErrorCode.InternalError, str(e))
    
    async def _handle_get_workflow_resource(self, uri: str) -> Dict[str, Any]:
        """ワークフローリソースを取得"""
        try:
            workflow_id = uri.split("/")[1]
            context = self.kernel.create_new_context()
            context["workflow_id"] = workflow_id
            
            resource_function = self.kernel.create_semantic_function("""
            ワークフローの現在の状態を取得し、以下の情報を含むリソースを返してください:
            - タスクの一覧と状態
            - 実行の進捗状況
            - タイムスタンプ
            
            ワークフローID: {{$workflow_id}}
            """)
            
            result = await resource_function.invoke_async(context=context)
            return json.loads(result.result)
            
        except Exception as e:
            raise McpError(ErrorCode.InternalError, str(e))
    
    async def _handle_get_visualization_resource(self, uri: str) -> Dict[str, Any]:
        """ワークフロー可視化データを取得"""
        try:
            workflow_id = uri.split("/")[1]
            context = self.kernel.create_new_context()
            context["workflow_id"] = workflow_id
            
            viz_function = self.kernel.create_semantic_function("""
            ワークフローの可視化データを生成し、以下の情報を含むJSONを返してください:
            - ノード(タスク)の位置と状態
            - エッジ(依存関係)の接続情報
            - レイアウト情報
            
            ワークフローID: {{$workflow_id}}
            """)
            
            result = await viz_function.invoke_async(context=context)
            return json.loads(result.result)
            
        except Exception as e:
            raise McpError(ErrorCode.InternalError, str(e))
    
    async def notify_task_progress(self, progress_data: Dict[str, Any]):
        """タスクの進捗を通知"""
        try:
            context = self.kernel.create_new_context()
            context["progress_data"] = json.dumps(progress_data)
            
            notify_function = self.kernel.create_semantic_function("""
            タスクの進捗を処理し、以下の更新を行ってください:
            1. 進捗状況の更新
            2. 依存タスクへの影響を分析
            3. ワークフロー全体の状態を更新
            
            進捗データ: {{$progress_data}}
            """)
            
            await notify_function.invoke_async(context=context)
            
        except Exception as e:
            print(f"Progress notification error: {str(e)}")
    
    async def run(self):
        """MCPサーバーを起動"""
        print("Workflow MCP server running")
        return self  # サーバーインスタンスを返す