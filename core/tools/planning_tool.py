# core/tools/planning_tool.py
from typing import Dict, List, Any, Optional
import json
import importlib
import sys
import os
import re
from .base_tool import BaseTool, ToolResult
from ..task_database import TaskDatabase, TaskStatus
from ..script_templates import get_template_for_task

class PlanningTool(BaseTool):
    def __init__(self, llm, task_db: TaskDatabase, graph_rag=None, modular_code_manager=None):
        super().__init__(
            name="planning",
            description="A tool for planning and managing the execution of complex tasks"
        )
        self.llm = llm
        self.task_db = task_db
        self.plans = {}
        self._current_plan_id = None
        self.graph_rag = graph_rag  # GraphRAGマネージャー
        self.modular_code_manager = modular_code_manager  # モジュラーコードマネージャー
        
        self.parameters = {
            "command": {
                "type": "string",
                "enum": ["generate_plan", "generate_code", "execute_task", "get_task_status", "get_plan_status"]
            },
            "goal": {"type": "string"},
            "task_id": {"type": "string"},
            "plan_id": {"type": "string"},
            "template_info": {"type": "object"},  # 学習ベースのテンプレート情報
            "modules": {"type": "array"}  # 再利用可能なモジュール情報
        }
    
    def execute(self, command: str, **kwargs) -> ToolResult:
        """プランニングツールを実行"""
        command_handlers = {
            "generate_plan": self._handle_generate_plan,
            "generate_code": self._handle_generate_code,
            "execute_task": self._handle_execute_task,
            "get_task_status": self._handle_get_task_status,
            "get_plan_status": self._handle_get_plan_status
        }
        
        handler = command_handlers.get(command)
        if not handler:
            return ToolResult(False, None, f"Unknown command: {command}")
        
        try:
            return handler(**kwargs)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return ToolResult(False, None, f"{str(e)}\n{error_details}")
    
    def _handle_generate_plan(self, goal: str, template_info: Dict = None, **kwargs) -> ToolResult:
        """目標からプランを生成"""
        # プランをデータベースに作成
        plan_id = self.task_db.add_plan(goal)
        self._current_plan_id = plan_id
        
        # 学習ベースのテンプレート情報を活用
        template_prompt = ""
        if template_info:
            template_prompt = f"""
            Based on similar tasks, the most effective approach has these characteristics:
            - Task type: {template_info.get("task_type", "general")}
            - Key considerations: {', '.join(template_info.get("keywords", [])[:5])}
            
            Consider these insights when creating your plan.
            """
        
        # タスクを生成
        tasks = self.generate_plan(goal, template_prompt)
        
        # タスクをデータベースに追加
        for i, task in enumerate(tasks):
            # 依存関係を処理（インデックスをIDに変換）
            dependencies = []
            for dep_idx in task.get("dependencies", []):
                if isinstance(dep_idx, int) and 0 <= dep_idx < i:
                    # タスクのID順が生成順と同じと仮定
                    dep_task_ids = list(self.task_db.get_tasks_by_plan(plan_id))
                    if dep_idx < len(dep_task_ids):
                        dependencies.append(dep_task_ids[dep_idx].id)
            
            self.task_db.add_task(
                description=task["description"],
                plan_id=plan_id,
                dependencies=dependencies
            )
        
        return ToolResult(True, plan_id)
    
    def _handle_generate_code(self, task_id: str, modules: List[Dict] = None, **kwargs) -> ToolResult:
        """タスク用のPythonコードを生成"""
        task = self.task_db.get_task(task_id)
        if not task:
            return ToolResult(False, None, f"Task with ID {task_id} not found")
        
        try:
            # モジュール情報を考慮してコード生成
            if modules:
                code = self.generate_python_script_with_modules(task, modules)
            else:
                code = self.generate_python_script(task)
            
            # タスクのコードを更新
            self.task_db.update_task_code(task_id, code)
            
            return ToolResult(True, code)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"Code generation error: {str(e)}\n{error_details}")
            return ToolResult(False, None, f"Failed to generate code: {str(e)}")
    
    def _handle_execute_task(self, task_id: str, **kwargs) -> ToolResult:
        """タスクを実行"""
        task = self.task_db.get_task(task_id)
        if not task:
            return ToolResult(False, None, f"Task with ID {task_id} not found")
        
        if not task.code:
            return ToolResult(False, None, f"Task {task_id} has no code to execute")
        
        # タスクのステータスを更新
        self.task_db.update_task(task_id, TaskStatus.RUNNING)
        
        try:
            # 依存関係のチェック
            missing_imports = self._check_imports(task.code)
            if missing_imports:
                return ToolResult(False, None, f"Missing required modules: {', '.join(missing_imports)}")
            
            # Pythonコードを実行
            local_vars = {}
            
            # 実行環境情報
            execution_env = {
                "task_id": task.id,
                "task_description": task.description,
                "plan_id": task.plan_id,
            }
            
            # 実行環境の設定
            global_vars = {
                "__builtins__": __builtins__,
                "task_info": execution_env
            }
            
            # コードを安全に実行
            exec(task.code, global_vars, local_vars)
            
            # 実行結果を取得
            result = local_vars.get("result", "Task executed successfully but no result variable found")
            
            return ToolResult(True, result)
        except ModuleNotFoundError as e:
            # モジュールが見つからないエラー
            module_name = str(e).split("'")[1] if "'" in str(e) else str(e)
            return ToolResult(False, None, f"No module named '{module_name}'")
        except ImportError as e:
            # インポートエラー
            return ToolResult(False, None, f"Import error: {str(e)}")
        except Exception as e:
            # その他のエラー
            import traceback
            tb = traceback.format_exc()
            return ToolResult(False, None, f"{str(e)}\n{tb}")
    
    def _handle_get_task_status(self, task_id: str, **kwargs) -> ToolResult:
        """タスクのステータスを取得"""
        task = self.task_db.get_task(task_id)
        if not task:
            return ToolResult(False, None, f"Task with ID {task_id} not found")
        
        return ToolResult(True, {
            "id": task.id,
            "description": task.description,
            "status": task.status.value,
            "result": task.result
        })
    
    def _handle_get_plan_status(self, plan_id: str, **kwargs) -> ToolResult:
        """プランのステータスを取得"""
        plan = self.task_db.get_plan(plan_id)
        if not plan:
            return ToolResult(False, None, f"Plan with ID {plan_id} not found")
        
        tasks = self.task_db.get_tasks_by_plan(plan_id)
        
        completed = sum(1 for task in tasks if task.status == TaskStatus.COMPLETED)
        failed = sum(1 for task in tasks if task.status == TaskStatus.FAILED)
        pending = sum(1 for task in tasks if task.status == TaskStatus.PENDING)
        running = sum(1 for task in tasks if task.status == TaskStatus.RUNNING)
        
        return ToolResult(True, {
            "id": plan.id,
            "goal": plan.goal,
            "total_tasks": len(tasks),
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "running": running,
            "progress": completed / len(tasks) if tasks else 0
        })
    
    def generate_plan(self, goal: str, template_prompt: str = "") -> List[Dict]:
        """目標からタスクリストを生成"""
        # 過去の学習情報を活用したプランニング
        learning_insights = ""
        if self.graph_rag:
            try:
                # 類似のタスクテンプレートを検索
                similar_templates = self.graph_rag.find_similar_task_templates(goal, limit=2)
                if similar_templates:
                    top_template = similar_templates[0]
                    learning_insights = f"""
                    Based on our experience with similar tasks, consider these insights:
                    - Task type: {top_template["task_type"]}
                    - Key considerations: {', '.join(top_template.get("keywords", [])[:5])}
                    - Success rate: {top_template["success_count"]} successful completions
                    
                    Also, be aware of these common issues:
                    """
                    
                    # 関連するエラーパターンを検索
                    error_patterns = self.graph_rag.find_similar_error_patterns(goal, limit=3)
                    if error_patterns:
                        for pattern in error_patterns:
                            error_type = pattern.get("error_type", "unknown")
                            learning_insights += f"- Watch out for {error_type} errors\n"
            except Exception as e:
                print(f"Error getting learning insights: {str(e)}")
        
        prompt = f"""
        Goal: {goal}
        
        {template_prompt}
        
        {learning_insights}
        
        Break down this goal into a list of sequential tasks that can be accomplished with Python code. 
        For each task:
        1. Provide a clear description
        2. Identify any dependencies (tasks that must be completed first)
        3. Consider necessary libraries and external dependencies
        
        Return the tasks as a JSON array of objects with the following structure:
        {{
            "description": "Task description",
            "dependencies": [], // List of previous task indices (0-based) that must be completed first
            "required_libraries": [] // List of Python libraries that might be needed
        }}
        
        The tasks should be ordered logically, with earlier tasks coming before later dependent tasks.
        Include a first task to import all necessary libraries, and make sure to handle edge cases and errors.
        Aim for tasks that are atomic and focused on a single objective.
        """
        
        response = self.llm.generate_text(prompt)
        
        try:
            # JSONを抽出
            tasks_json = self._extract_json(response)
            tasks = json.loads(tasks_json)
            
            # タスクのフォーマット検証
            for task in tasks:
                if "description" not in task:
                    raise ValueError("Task missing 'description' field")
                if "dependencies" not in task:
                    task["dependencies"] = []
                # 必要なライブラリがない場合は空リストを追加
                if "required_libraries" not in task:
                    task["required_libraries"] = []
            
            return tasks
        except Exception as e:
            raise ValueError(f"Failed to parse plan: {str(e)}")
    
    def generate_python_script(self, task) -> str:
        """タスク用のPythonスクリプトを生成"""
        # プランの目標を取得
        plan = self.task_db.get_plan(task.plan_id)
        goal = plan.goal if plan else "Accomplish the task"
        
        # 依存タスクの情報を取得
        dependent_tasks = []
        for dep_id in task.dependencies:
            dep_task = self.task_db.get_task(dep_id)
            if dep_task:
                dependent_tasks.append({
                    "description": dep_task.description,
                    "status": dep_task.status.value,
                    "result": dep_task.result
                })
        
        # スクリプトテンプレートを取得
        template = get_template_for_task(task.description)
        
        # 学習ベースの強化
        learning_insights = ""
        if self.graph_rag:
            try:
                # 類似のエラーパターンを検索
                similar_errors = self.graph_rag.find_similar_error_patterns(task.description, limit=3)
                if similar_errors:
                    learning_insights += "Based on our analysis of similar tasks, watch out for these common issues:\n"
                    for error in similar_errors:
                        error_type = error.get("error_type", "unknown")
                        learning_insights += f"- {error_type} errors can occur in this kind of task\n"
            except Exception as e:
                print(f"Error getting error patterns: {str(e)}")
        
        # GraphRAGとModularCodeManagerが利用可能な場合、関連情報を追加
        if self.graph_rag and self.modular_code_manager:
            # 再利用可能なモジュールを取得
            modules = self.modular_code_manager.get_modules_for_task(task.description)
            
            if modules:
                modules_info = "\n\n".join([
                    f"Module: {module['name']}\nDescription: {module['description']}\n```python\n{module['code']}\n```"
                    for module in modules[:2]  # 上位2つのみを使用
                ])
                
                learning_insights += f"""
                
                Consider using these reusable modules:
                {modules_info}
                
                Import and use these modules when appropriate instead of duplicating functionality.
                """
        
        prompt = f"""
        Overall Goal: {goal}
        
        Task Description: {task.description}
        
        Dependent Tasks:
        {json.dumps(dependent_tasks, indent=2)}
        
        {learning_insights}
        
        Write a Python script to accomplish this task. The script should:
        1. Be self-contained and handle errors gracefully
        2. Store the final result in a variable called 'result'
        3. Include appropriate comments and error handling
        4. Check if required modules are available and provide helpful error messages
        
        IMPORTANT: Ensure consistent indentation throughout your code. Do not use tabs. Use 4 spaces for indentation.
        
        Follow these best practices:
        - Include all necessary imports at the top
        - Handle potential missing dependencies with try/except blocks
        - Use proper error messages to indicate missing packages
        - For file operations, use 'with' statements and handle file not found errors
        - Include comments explaining complex logic
        - Be sure main code starts at the left margin (column 0) with no leading whitespace
        
        Only provide the code that would replace the `{{main_code}}` part in the template.
        Do not include the template structure or import statements, as they will be added automatically.
        """
        
        # メインコード部分を生成
        main_code = self.llm.generate_code(prompt)
        
        # インポート文を抽出
        import re
        import_pattern = r'import\s+[\w.]+|from\s+[\w.]+\s+import\s+[\w.,\s]+'
        imports = re.findall(import_pattern, main_code)
        imports_text = "\n".join(imports) if imports else "# No additional imports"
        
        # メインコードからインポート文を削除
        main_code_cleaned = re.sub(import_pattern, '', main_code).strip()
        
        # 安全なテンプレート置換のためのディクショナリを作成
        format_dict = {
            "imports": imports_text,
            "main_code": main_code_cleaned,
        }
        
        try:
            # 安全なフォーマット処理
            from string import Template
            t = Template(template)
            full_code = t.safe_substitute(format_dict)
            return full_code
        except Exception as e:
            print(f"Error formatting template: {str(e)}")
            # フォールバック: 基本的なテンプレートを使用
            fallback_template = """
# 必要なライブラリのインポート
{imports}

def main():
    try:
        # メイン処理
        {main_code}
    except Exception as e:
        print(f"Error: {{str(e)}}")
        return str(e)
    
    return "Task completed successfully"

# スクリプト実行
if __name__ == "__main__":
    result = main()
"""
            return fallback_template.format(**format_dict)
    
    def generate_python_script_with_modules(self, task, modules: List[Dict]) -> str:
        """再利用可能なモジュールを活用してPythonスクリプトを生成"""
        # プランの目標を取得
        plan = self.task_db.get_plan(task.plan_id)
        goal = plan.goal if plan else "Accomplish the task"
        
        # 依存タスクの情報を取得
        dependent_tasks = []
        for dep_id in task.dependencies:
            dep_task = self.task_db.get_task(dep_id)
            if dep_task:
                dependent_tasks.append({
                    "description": dep_task.description,
                    "status": dep_task.status.value,
                    "result": dep_task.result
                })
        
        # スクリプトテンプレートを取得
        template = get_template_for_task(task.description)
        
        # モジュール情報をプロンプトに整形
        modules_info = "\n\n".join([
            f"Module: {module['name']}\nDescription: {module['description']}\n```python\n{module['code']}\n```"
            for module in modules[:3]  # 最大3つのモジュールを使用
        ])
        
        prompt = f"""
        Overall Goal: {goal}
        
        Task Description: {task.description}
        
        Dependent Tasks:
        {json.dumps(dependent_tasks, indent=2)}
        
        Available Reusable Modules:
        {modules_info}
        
        Write a Python script to accomplish this task. The script should:
        1. Reuse the provided modules whenever possible
        2. Be self-contained and handle errors gracefully
        3. Store the final result in a variable called 'result'
        4. Include appropriate comments and error handling
        
        IMPORTANT: Ensure consistent indentation throughout your code. Do not use tabs. Use 4 spaces for indentation.
        
        Follow these best practices:
        - Include all necessary imports at the top
        - Import and use the provided modules instead of reimplementing the same functionality
        - Handle potential missing dependencies with try/except blocks
        - For file operations, use 'with' statements and handle file not found errors
        - Add comments to indicate where modules are being used
        - Be sure main code starts at the left margin (column 0) with no leading whitespace
        
        Only provide the code that would replace the `{{main_code}}` part in the template.
        Do not include the template structure, as it will be added automatically.
        """
        
        # メインコード部分を生成
        main_code = self.llm.generate_code(prompt)
        
        # インポート文を抽出
        import re
        import_pattern = r'import\s+[\w.]+|from\s+[\w.]+\s+import\s+[\w.,\s]+'
        imports = re.findall(import_pattern, main_code)
        imports_text = "\n".join(imports) if imports else "# No additional imports"
        
        # メインコードからインポート文を削除
        main_code_cleaned = re.sub(import_pattern, '', main_code).strip()
        
        # 安全なテンプレート置換のためのディクショナリを作成
        format_dict = {
            "imports": imports_text,
            "main_code": main_code_cleaned,
        }
        
        try:
            # 安全なフォーマット処理
            from string import Template
            t = Template(template)
            full_code = t.safe_substitute(format_dict)
            return full_code
        except Exception as e:
            print(f"Error formatting template: {str(e)}")
            # フォールバック: 基本的なテンプレートを使用
            fallback_template = """
# 必要なライブラリのインポート
{imports}

def main():
    try:
        # メイン処理
        {main_code}
    except Exception as e:
        print(f"Error: {{str(e)}}")
        return str(e)
    
    return "Task completed successfully"

# スクリプト実行
if __name__ == "__main__":
    result = main()
"""
            return fallback_template.format(**format_dict)
    
    def _check_imports(self, code: str) -> List[str]:
        """コード内のインポートステートメントから不足モジュールを検出"""
        import_pattern = r'(?:from|import)\s+([\w.]+)'
        imports = re.findall(import_pattern, code)
        
        missing = []
        for imp in imports:
            # モジュール名を取得（from x.y import z の場合は x）
            module_name = imp.split('.')[0]
            
            # 標準ライブラリはスキップ
            if self._is_stdlib_module(module_name):
                continue
                
            # モジュールが利用可能かチェック
            try:
                # bs4は特殊ケース
                if module_name == "bs4":
                    importlib.import_module("bs4")
                else:
                    importlib.import_module(module_name)
            except ImportError:
                # bs4の場合は実際のパッケージ名を追加
                if module_name == "bs4":
                    missing.append("beautifulsoup4")
                else:
                    missing.append(module_name)
                
        return missing
    
    def _is_stdlib_module(self, module_name: str) -> bool:
        """モジュールが標準ライブラリの一部かどうかを判定"""
        # 一般的な標準ライブラリ
        stdlib_modules = {
            "os", "sys", "math", "random", "datetime", "time", "json", 
            "csv", "re", "collections", "itertools", "functools", "io",
            "pathlib", "shutil", "glob", "argparse", "logging", "unittest",
            "threading", "multiprocessing", "subprocess", "socket", "email",
            "smtplib", "urllib", "http", "xml", "html", "tkinter", "sqlite3",
            "hashlib", "uuid", "tempfile", "copy", "traceback", "gc", "inspect"
        }
        
        if module_name in stdlib_modules:
            return True
            
        try:
            # 標準ライブラリかチェック
            spec = importlib.util.find_spec(module_name)
            return spec is not None and (
                spec.origin is not None and
                "site-packages" not in spec.origin and 
                "dist-packages" not in spec.origin
            )
        except (ImportError, AttributeError):
            return False
    
    def _extract_json(self, text: str) -> str:
        """テキストからJSONを抽出"""
        # JSON配列を検索
        json_match = re.search(r'\[[\s\S]*\]', text)
        if json_match:
            return json_match.group(0)
        
        # JSON オブジェクトを検索
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json_match.group(0)
        
        # JSONが見つからない場合は元のテキストを返す
        return text