from typing import Dict, List, Any, Optional, Type
import importlib
import inspect
from datetime import datetime
import json
import semantic_kernel as sk

from .decorators import WorkflowModule, plan_step
from ..db.task_repository import TaskRepository

class PlanEngine:
    """プラン実行エンジン"""
    def __init__(self, task_repository: TaskRepository):
        self.modules: Dict[str, WorkflowModule] = {}
        self.task_repository = task_repository
        self.execution_history: List[Dict[str, Any]] = []
        
        # プラン生成用のプロンプト
        self.plan_prompt = """
        与えられた目標を達成するために、利用可能なスキルを使用して実行プランを生成してください。

        目標:
        {{$input}}

        利用可能なスキル:
        {{$available_skills}}

        出力は以下のJSON形式で返してください:
        {
            "tasks": [
                {
                    "name": "タスク名",
                    "type": "スキル名",
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
        
    async def load_module(self, module_path: str) -> WorkflowModule:
        """モジュールを動的にロード"""
        try:
            # モジュールをインポート
            module = importlib.import_module(module_path)
            
            # WorkflowModuleのサブクラスを探す
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, WorkflowModule) and 
                    obj != WorkflowModule):
                    # インスタンス化してモジュールを登録
                    instance = obj()
                    self.modules[instance.name] = instance
                    return instance
                    
            raise ValueError(f"WorkflowModuleが見つかりません: {module_path}")
            
        except Exception as e:
            raise ValueError(f"モジュールのロードエラー: {str(e)}")
    
    async def generate_plan(self, goal: str) -> Dict[str, Any]:
        """目標からプランを生成"""
        try:
            # 利用可能なスキルの情報を収集
            available_skills = {}
            for module in self.modules.values():
                metadata = module.get_skill_metadata()
                available_skills.update(metadata["functions"])
            
            # OpenAI APIを使用してプランを生成
            messages = [
                {
                    "role": "system",
                    "content": self.plan_prompt.replace(
                        "{{$input}}", goal
                    ).replace(
                        "{{$available_skills}}", 
                        json.dumps(available_skills, ensure_ascii=False, indent=2)
                    )
                }
            ]
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )
            
            plan = json.loads(response.choices[0].message.content)
            
            # 各タスクのコードを生成
            for task in plan["tasks"]:
                code_messages = [
                    {
                        "role": "system",
                        "content": self.code_prompt.replace(
                            "{{$task_name}}", task["name"]
                        ).replace(
                            "{{$task_type}}", task["type"]
                        ).replace(
                            "{{$inputs}}", 
                            json.dumps(task.get("inputs", {}), ensure_ascii=False, indent=2)
                        )
                    }
                ]
                
                code_response = await self.openai_client.chat.completions.create(
                    model="gpt-4",
                    messages=code_messages,
                    temperature=0.7,
                    max_tokens=2000
                )
                
                task["code"] = code_response.choices[0].message.content
            
            return plan
            
        except Exception as e:
            raise ValueError(f"プラン生成エラー: {str(e)}")
    
    async def execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """プランを実行"""
        try:
            results = []
            execution_context = {
                "plan_id": str(datetime.now().timestamp()),
                "start_time": datetime.now().isoformat(),
                "variables": {},
                "steps": []
            }
            
            # 各ステップを実行
            for step in plan["steps"]:
                step_context = {
                    "name": step["name"],
                    "start_time": datetime.now().isoformat()
                }
                
                try:
                    # 依存関係のチェック
                    self._check_dependencies(step, execution_context)
                    
                    # コードを実行
                    if "code" in step:
                        # ローカル変数として実行コンテキストを作成
                        local_vars = {
                            "inputs": step.get("inputs", {}),
                            "outputs": {}
                        }
                        
                        # コードを実行
                        exec(step["code"], {}, local_vars)
                        
                        # 結果を記録
                        step_context.update({
                            "status": "completed",
                            "outputs": local_vars.get("outputs", {}),
                            "end_time": datetime.now().isoformat()
                        })
                        results.append(local_vars.get("outputs", {}))
                    
                except Exception as e:
                    step_context.update({
                        "status": "failed",
                        "error": str(e),
                        "end_time": datetime.now().isoformat()
                    })
                    raise
                    
                finally:
                    execution_context["steps"].append(step_context)
            
            # 実行履歴を保存
            execution_context["end_time"] = datetime.now().isoformat()
            self.execution_history.append(execution_context)
            
            return {
                "status": "completed",
                "results": results,
                "context": execution_context
            }
            
        except Exception as e:
            raise ValueError(f"プラン実行エラー: {str(e)}")
    
    def _check_dependencies(self, step: Dict[str, Any], context: Dict[str, Any]):
        """依存関係をチェック"""
        for dep in step.get("dependencies", []):
            found = False
            for completed_step in context["steps"]:
                if completed_step["name"] == dep and completed_step["status"] == "completed":
                    found = True
                    break
            if not found:
                raise ValueError(f"依存ステップが完了していません: {dep}")
    
    async def get_execution_history(self) -> List[Dict[str, Any]]:
        """実行履歴を取得"""
        return self.execution_history
    
    async def save_execution_result(self, result: Dict[str, Any]):
        """実行結果を保存"""
        try:
            # 実行結果をDBに保存
            await self.task_repository.create_execution_result({
                "plan_id": result["context"]["plan_id"],
                "start_time": result["context"]["start_time"],
                "end_time": result["context"]["end_time"],
                "status": result["status"],
                "steps": result["context"]["steps"]
            })
        except Exception as e:
            print(f"実行結果の保存エラー: {str(e)}")