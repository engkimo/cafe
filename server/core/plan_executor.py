from typing import Dict, List, Any, Optional, Set
import asyncio
from datetime import datetime
import json
import semantic_kernel as sk

from .task_executor import TaskExecutor
from .decorators import ModuleBase, get_module_functions
from ..models import Task
from ..db.task_repository import TaskRepository

class PlanExecutor:
    """プラン実行を管理するクラス"""
    def __init__(
        self,
        task_executor: TaskExecutor,
        task_repository: TaskRepository,
        modules: List[ModuleBase]
    ):
        self.task_executor = task_executor
        self.task_repository = task_repository
        self.modules = modules
        self.auto_save_mode = False
        self._available_functions = self._load_module_functions()
        
        # Semantic Kernelの初期化
        self.kernel = sk.Kernel()
        
        # プラン生成用のプロンプト
        self.plan_prompt = """
        与えられたタスクを実行可能なサブタスクに分解し、それぞれの依存関係を特定してください。

        タスク:
        {{$input}}

        利用可能な関数:
        {{$available_functions}}

        出力は以下のJSON形式で返してください:
        {
            "tasks": [
                {
                    "name": "タスク名",
                    "type": "関数タイプ",
                    "inputs": {},
                    "dependencies": []
                }
            ]
        }
        """
        
        # コード生成用のプロンプト
        self.code_prompt = """
        以下のタスクを実行するPythonコードを生成してください:

        タスク名: {{$task_name}}
        タイプ: {{$task_type}}
        入力: {{$inputs}}

        必要なライブラリ:
        - google-auth
        - google-auth-oauthlib
        - google-auth-httplib2
        - google-api-python-client

        出力は実行可能なPythonコードのみを返してください。
        """
        
    def _load_module_functions(self) -> Dict[str, Dict[str, Any]]:
        """全モジュールから利用可能な関数を読み込む"""
        functions = {}
        for module in self.modules:
            module_functions = get_module_functions(module.__class__)
            functions.update(module_functions)
        return functions
    
    def set_auto_save_mode(self, enabled: bool):
        """自動保存モードの設定"""
        self.auto_save_mode = enabled
        
    async def create_plan(self, task_description: str) -> List[Task]:
        """タスク説明からプランを生成"""
        try:
            # OpenAI APIを使用してプランを生成
            messages = [
                {
                    "role": "system",
                    "content": self.plan_prompt.replace(
                        "{{$input}}", task_description
                    ).replace(
                        "{{$available_functions}}", 
                        json.dumps(self._available_functions, ensure_ascii=False, indent=2)
                    )
                }
            ]
            
            response = await self.task_executor.openai_client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )
            
            plan = json.loads(response.choices[0].message.content)
            
            tasks = []
            for task_info in plan["tasks"]:
                # コードを生成
                code_messages = [
                    {
                        "role": "system",
                        "content": self.code_prompt.replace(
                            "{{$task_name}}", task_info["name"]
                        ).replace(
                            "{{$task_type}}", task_info["type"]
                        ).replace(
                            "{{$inputs}}", 
                            json.dumps(task_info.get("inputs", {}), ensure_ascii=False, indent=2)
                        )
                    }
                ]
                
                code_response = await self.task_executor.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=code_messages,
                    temperature=0.7,
                    max_tokens=2000
                )
                
                task = Task(
                    id=len(tasks) + 1,
                    name=task_info["name"],
                    type=task_info["type"],
                    inputs=task_info.get("inputs", {}),
                    outputs={},
                    status="pending",
                    dependencies=task_info.get("dependencies", []),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    code=code_response.choices[0].message.content
                )
                tasks.append(task)
                
                if self.auto_save_mode:
                    await self.task_repository.create_task(task)
            
            return tasks
            
        except Exception as e:
            print(f"プラン生成エラー: {str(e)}")
            raise
    
    def _get_execution_order(self, tasks: List[Task]) -> List[Task]:
        """タスクの実行順序を決定(トポロジカルソート)"""
        # 依存関係グラフの構築
        graph: Dict[str, Set[str]] = {task.name: set(task.dependencies) for task in tasks}
        
        # 実行順序を格納するリスト
        execution_order = []
        # 依存関係のないタスクを格納するセット
        no_deps = {task.name for task in tasks if not task.dependencies}
        
        while no_deps:
            # 依存関係のないタスクを1つ取り出す
            current = no_deps.pop()
            execution_order.append(current)
            
            # このタスクに依存する他のタスクの依存関係を更新
            for task_name, deps in graph.items():
                if current in deps:
                    deps.remove(current)
                    if not deps:
                        no_deps.add(task_name)
        
        # 循環依存関係のチェック
        if len(execution_order) != len(tasks):
            raise ValueError("タスクの依存関係に循環が存在します")
        
        # タスク名から実際のTaskオブジェクトに変換
        return [next(task for task in tasks if task.name == name) for name in execution_order]
    
    async def execute_plan(self, tasks: List[Task]) -> List[Dict[str, Any]]:
        """プランを実行"""
        results = []
        execution_order = self._get_execution_order(tasks)
        
        for task in execution_order:
            try:
                # タスクの実行
                result = await self.task_executor.execute_task(task)
                results.append(result)
                
                if self.auto_save_mode:
                    # 実行結果をDBに保存
                    await self.task_repository.update_task(task)
                    
                # MCPサーバーに進捗を通知
                await self._notify_mcp_progress(task)
                
            except Exception as e:
                print(f"タスク実行エラー: {str(e)}")
                task.status = "failed"
                task.outputs = {"error": str(e)}
                
                if self.auto_save_mode:
                    await self.task_repository.update_task(task)
                raise
        
        return results
    
    async def _notify_mcp_progress(self, task: Task):
        """MCPサーバーに進捗を通知"""
        if not hasattr(self, 'workflow_server'):
            return
            
        try:
            await self.workflow_server.notify_task_progress({
                "task_id": task.id,
                "status": task.status,
                "outputs": task.outputs
            })
        except Exception as e:
            print(f"MCP通知エラー: {str(e)}")