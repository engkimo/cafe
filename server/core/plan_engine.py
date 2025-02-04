from typing import Dict, List, Any, Optional, Type
import importlib
import inspect
from datetime import datetime
import json
import semantic_kernel as sk
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

from .decorators import WorkflowModule, plan_step
from ..db.task_repository import TaskRepository

class PlanEngine:
    """プラン実行エンジン"""
    def __init__(self, task_repository: TaskRepository):
        self.modules: Dict[str, WorkflowModule] = {}
        self.task_repository = task_repository
        self.execution_history: List[Dict[str, Any]] = []
        
        # Semantic Kernelの初期化
        self.kernel = sk.Kernel()
        
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
                    
                    # Semantic Kernelにスキルとして登録
                    self.kernel.import_skill(instance, instance.name)
                    
                    return instance
                    
            raise ValueError(f"WorkflowModuleが見つかりません: {module_path}")
            
        except Exception as e:
            raise ValueError(f"モジュールのロードエラー: {str(e)}")
    
    async def generate_plan(self, goal: str) -> Dict[str, Any]:
        """目標からプランを生成"""
        try:
            # 利用可能なステップの情報を収集
            available_steps = {}
            for module in self.modules.values():
                for name, method in inspect.getmembers(module):
                    if hasattr(method, 'is_plan_step'):
                        available_steps[method.step_name] = {
                            'name': method.step_name,
                            'description': method.step_description,
                            'input_schema': method.input_schema,
                            'output_schema': method.output_schema,
                            'dependencies': method.dependencies
                        }
            
            # Semantic Kernelを使用してプランを生成
            context = self.kernel.create_new_context()
            context["goal"] = goal
            context["available_steps"] = json.dumps(available_steps, ensure_ascii=False)
            
            # プラン生成のプロンプト
            prompt = """
            目標を達成するために必要なステップを利用可能なステップから選択し、実行プランを生成してください。
            
            利用可能なステップ:
            {{$available_steps}}
            
            目標:
            {{$goal}}
            
            出力は以下のJSON形式で返してください:
            {
                "goal": "目標の説明",
                "steps": [
                    {
                        "name": "ステップ名",
                        "module": "モジュール名",
                        "inputs": {},
                        "expected_outputs": {},
                        "dependencies": []
                    }
                ]
            }
            """
            
            # プランの生成
            plan_function = self.kernel.create_semantic_function(prompt)
            plan_result = await plan_function.invoke_async(context=context)
            plan = json.loads(plan_result.result)
            
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
            
            # Semantic Kernelのコンテキストを作成
            sk_context = self.kernel.create_new_context()
            
            # 各ステップを実行
            for step in plan["steps"]:
                step_context = {
                    "name": step["name"],
                    "start_time": datetime.now().isoformat()
                }
                
                try:
                    # モジュールとステップを取得
                    module = self.modules[step["module"]]
                    step_func = getattr(module, step["name"])
                    
                    # 依存関係のチェック
                    self._check_dependencies(step, execution_context)
                    
                    # 入力の準備
                    inputs = self._prepare_inputs(step, execution_context)
                    for key, value in inputs.items():
                        sk_context[key] = str(value)
                    
                    # ステップを実行
                    result = await step_func(sk_context)
                    
                    # 結果を記録
                    step_context.update({
                        "status": "completed",
                        "outputs": json.loads(result.result),
                        "end_time": datetime.now().isoformat()
                    })
                    results.append(result)
                    
                    # 変数を更新
                    execution_context["variables"].update(json.loads(result.result))
                    
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
    
    def _prepare_inputs(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """ステップの入力を準備"""
        inputs = step.get("inputs", {}).copy()
        
        # 変数の参照を解決
        for key, value in inputs.items():
            if isinstance(value, str) and value.startswith("$"):
                var_name = value[1:]
                if var_name in context["variables"]:
                    inputs[key] = context["variables"][var_name]
                else:
                    raise ValueError(f"変数が見つかりません: {var_name}")
        
        return inputs
    
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