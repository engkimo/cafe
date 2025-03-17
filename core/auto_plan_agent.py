# core/auto_plan_agent.py
from typing import Dict, List, Optional, Any
from .tool_agent import ToolAgent
from .task_database import TaskDatabase, Task, TaskStatus
from .project_environment import ProjectEnvironment
import re
import os
import sys
import time

class AutoPlanAgent(ToolAgent):
    def __init__(
        self, 
        name: str, 
        description: str, 
        llm, 
        task_db: TaskDatabase, 
        workspace_dir: str,
        graph_rag=None,
        modular_code_manager=None
    ):
        super().__init__(name, description, llm)
        self.planner = None  # Will be set later
        self.task_db = task_db
        self.workspace_dir = workspace_dir
        self.project_executor = None  # Will be set later
        self.graph_rag = graph_rag  # GraphRAGマネージャー
        self.modular_code_manager = modular_code_manager  # モジュラーコードマネージャー
        
        self.system_prompt += " You are specialized in breaking down complex tasks into smaller steps, generating Python code to accomplish each step, and repairing failed steps."
        
        # プロジェクト環境のキャッシュ
        self.environments = {}
    
    def set_planner(self, planner):
        self.planner = planner
        self.available_tools.add_tool(planner)
    
    def set_project_executor(self, project_executor):
        self.project_executor = project_executor
        self.available_tools.add_tool(project_executor)
    
    def set_graph_rag(self, graph_rag):
        """GraphRAGマネージャーを設定"""
        self.graph_rag = graph_rag
    
    def set_modular_code_manager(self, modular_code_manager):
        """モジュラーコードマネージャーを設定"""
        self.modular_code_manager = modular_code_manager
    
    def _get_environment(self, plan_id: str) -> ProjectEnvironment:
        """プロジェクト環境を取得（キャッシュがあればそれを使用）"""
        if plan_id not in self.environments:
            self.environments[plan_id] = ProjectEnvironment(self.workspace_dir, plan_id)
        return self.environments[plan_id]
        
    def execute_plan(self, goal: str) -> str:
        """Generate and execute a plan for a given goal with enhanced learning capabilities"""
        if not self.planner:
            return "Planner not set. Please set a planner tool before executing a plan."
        
        if not self.project_executor:
            return "Project executor not set. Please set a project executor before executing a plan."
        
        # タスク種別の分析
        task_type = self._analyze_task_type(goal)
        
        # 学習ベースのテンプレート活用
        template = None
        if self.graph_rag:
            template = self.graph_rag.get_task_template(goal, task_type)
            if template:
                print(f"Using task template with confidence {template['confidence']:.2f}")
        
        # Generate a plan using the planning tool with template insight
        plan_params = {
            "command": "generate_plan", 
            "goal": goal
        }
        
        if template:
            plan_params["template_info"] = {
                "task_type": template["task_type"],
                "confidence": template["confidence"],
                "keywords": template.get("keywords", [])
            }
            
        plan_result = self.planner.execute(**plan_params)
        
        if not plan_result.success:
            return f"Failed to generate plan: {plan_result.error}"
        
        plan_id = plan_result.result
        self.memory.set_working_memory("active_plan_id", plan_id)
        
        # プロジェクト環境を初期化
        env = self._get_environment(plan_id)
        
        # Execute the tasks in the plan
        tasks = self.task_db.get_tasks_by_plan(plan_id)
        
        # 実行前にモジュール再利用の機会を探る
        modules_by_task = {}
        if self.modular_code_manager:
            for task in tasks:
                relevant_modules = self.modular_code_manager.get_modules_for_task(task.description)
                if relevant_modules:
                    modules_by_task[task.id] = relevant_modules
                    print(f"Found {len(relevant_modules)} relevant modules for task {task.id}")
        
        # タスク実行と自己修復のメインループ
        for task in tasks:
            if task.status == TaskStatus.PENDING:
                # 再利用モジュールの適用を考慮したコード生成
                modules = modules_by_task.get(task.id, [])
                
                # Generate Python code for the task if not already generated
                if not task.code:
                    code_params = {
                        "command": "generate_code",
                        "task_id": task.id
                    }
                    
                    if modules:
                        code_params["modules"] = modules
                        
                    code_result = self.planner.execute(**code_params)
                    
                    if not code_result.success:
                        self.task_db.update_task(
                            task_id=task.id,
                            status=TaskStatus.FAILED,
                            result=f"Failed to generate code: {code_result.error}"
                        )
                        continue
                    
                    # 生成したコードを保存
                    self.task_db.update_task_code(task.id, code_result.result)
                
                # 最大修復試行回数
                max_repair_attempts = 3
                current_attempt = 0
                
                while current_attempt < max_repair_attempts:
                    current_attempt += 1
                    
                    # Execute the task using project executor
                    execute_result = self.project_executor.execute(
                        command="execute_task",
                        task_id=task.id
                    )
                    
                    if execute_result.success:
                        print(f"Task {task.id} executed successfully")
                        
                        # 成功したタスクからモジュールを抽出（学習）
                        if self.modular_code_manager and current_attempt == 1:  # 初回成功時のみ
                            try:
                                extracted_modules = self.modular_code_manager.extract_reusable_modules(
                                    task.id, self.task_db, task.description
                                )
                                if extracted_modules:
                                    print(f"Extracted {len(extracted_modules)} reusable modules from task {task.id}")
                            except Exception as e:
                                print(f"Error extracting modules: {str(e)}")
                                
                        # タスクテンプレートを保存（学習）
                        if self.graph_rag and current_attempt == 1:  # 初回成功時のみ
                            try:
                                task_obj = self.task_db.get_task(task.id)
                                if task_obj and task_obj.code:
                                    self.graph_rag.store_task_template(
                                        task_type=task_type,
                                        description=task_obj.description,
                                        template_code=task_obj.code,
                                        keywords=self._extract_keywords(task_obj.description)
                                    )
                                    print(f"Stored task template for {task_type}")
                            except Exception as e:
                                print(f"Error storing task template: {str(e)}")
                                
                        break  # タスク成功
                    
                    # タスク失敗時の処理
                    print(f"Task {task.id} execution failed: {execute_result.error}")
                    
                    if current_attempt < max_repair_attempts:
                        # 失敗したタスクの修復を試みる
                        repair_success = self.repair_failed_task(task.id)
                        if not repair_success:
                            print(f"Failed to repair task {task.id} after attempt {current_attempt}")
                            # 修復失敗時のクールダウン
                            time.sleep(1)  
                    else:
                        print(f"Task {task.id} failed after {max_repair_attempts} repair attempts")
        
        # Generate final summary
        summary = self.generate_plan_summary(plan_id)
        
        # プロジェクトの依存関係ファイルを更新
        env.update_requirements_file()
        
        return summary
    
    def repair_failed_task(self, task_id: str) -> bool:
        """失敗したタスクを自動修復（学習機能強化版）"""
        task = self.task_db.get_task(task_id)
        
        if task.status != TaskStatus.FAILED:
            return True  # タスクは失敗していない
        
        # エラーメッセージを取得
        error_message = task.result
        
        # プロジェクト環境を取得
        env = self._get_environment(task.plan_id)
        
        # ==== GraphRAGが利用可能な場合、過去の修正パターンを検索 ====
        if self.graph_rag:
            try:
                # 推奨修正方法を取得
                recommended_fix = self.graph_rag.get_recommended_fix(
                    error_message=error_message,
                    original_code=task.code,
                    task_context=task.description
                )
                
                if recommended_fix and recommended_fix["confidence"] > 0.75:
                    print(f"Found similar error pattern with confidence {recommended_fix['confidence']:.2f}")
                    # 推奨された修正を適用
                    fixed_code = recommended_fix["fixed_code"]
                    
                    # 修正コードを保存
                    self.task_db.update_task_code(task_id, fixed_code)
                    
                    # 修正したコードを実行
                    execute_result = self.project_executor.execute(
                        command="execute_task",
                        task_id=task_id
                    )
                    
                    if execute_result.success:
                        print(f"Task {task_id} execution succeeded with learned fix")
                        # タスクのステータスを更新
                        self.task_db.update_task(
                            task_id=task_id,
                            status=TaskStatus.COMPLETED,
                            result=execute_result.result
                        )
                        
                        # エラーパターンの成功カウントを更新（学習強化）
                        self.graph_rag.store_error_pattern(
                            error_message=error_message,
                            error_type=self._classify_error(error_message),
                            original_code=task.code,
                            fixed_code=fixed_code,
                            context=task.description
                        )
                        
                        return True
                    else:
                        print(f"Learned fix did not resolve the issue: {execute_result.error}")
            except Exception as e:
                print(f"Error applying learned fix: {str(e)}")
        
        # ==== 依存パッケージ問題の対応 ====
        # エラーメッセージから不足パッケージを検出
        missing_packages = env.extract_missing_packages(error_message)
        
        # 不足パッケージがある場合はインストール
        if missing_packages:
            print(f"Installing missing packages: {', '.join(missing_packages)}")
            env.install_requirements(missing_packages)
            
            # パッケージインストール後に再実行
            execute_result = self.project_executor.execute(
                command="execute_task",
                task_id=task_id
            )
            
            if execute_result.success:
                print(f"Task {task_id} execution succeeded after installing missing packages")
                # タスクのステータスを更新
                self.task_db.update_task(
                    task_id=task_id,
                    status=TaskStatus.COMPLETED,
                    result=execute_result.result
                )
                
                # 成功した修正をGraphRAGに記録（学習）
                if self.graph_rag:
                    # パッケージ不足エラーとその修正方法を記録
                    self.graph_rag.store_error_pattern(
                        error_message=error_message,
                        error_type="missing_package",
                        original_code=task.code,
                        fixed_code=task.code,  # パッケージの問題はコードを変更せずに解決
                        context=f"Installed packages: {', '.join(missing_packages)}"
                    )
                
                return True
        
        # ==== LLMを使用したコード修正 ====
        print(f"Trying to repair task {task_id} by modifying code")
        
        # エラー種別の分析
        error_type = self._classify_error(error_message)
        
        # LLMを使用してエラーを分析し、コードを修正
        repair_prompt = f"""
        The following Python code has failed with error type: {error_type}
        
        ```python
        {task.code}
        ```
        
        The error is:
        ```
        {error_message}
        ```
        
        Please analyze the error and generate a fixed version of the code.
        Focus on these aspects:
        1. Fix the specific error mentioned in the error message
        2. Handle potential dependency issues and error cases properly
        3. Ensure proper indentation and syntax
        4. Add appropriate error handling for similar failures
        
        Only provide the fixed code, no explanations or markdown.
        """
        
        fixed_code = self.llm.generate_code(repair_prompt)
        
        # 修正したコードを保存
        self.task_db.update_task_code(task_id, fixed_code)
        
        # 修正したコードを実行
        execute_result = self.project_executor.execute(
            command="execute_task",
            task_id=task_id
        )
        
        if execute_result.success:
            print(f"Task {task_id} execution succeeded after code repair")
            # タスクのステータスを更新
            self.task_db.update_task(
                task_id=task_id,
                status=TaskStatus.COMPLETED,
                result=execute_result.result
            )
            
            # 成功した修正をGraphRAGに記録（学習）
            if self.graph_rag:
                self.graph_rag.store_error_pattern(
                    error_message=error_message,
                    error_type=error_type,
                    original_code=task.code,
                    fixed_code=fixed_code,
                    context=task.description
                )
                print(f"Stored successful error fix pattern for {error_type}")
            
            return True
        else:
            print(f"Task {task_id} repair failed: {execute_result.error}")
            # タスクのステータスを更新
            self.task_db.update_task(
                task_id=task_id,
                status=TaskStatus.FAILED,
                result=f"Repair attempt failed: {execute_result.error}"
            )
            return False
    
    def _classify_error(self, error_message: str) -> str:
        """エラーメッセージからエラーの種類を分類"""
        error_types = {
            "SyntaxError": ["SyntaxError", "invalid syntax"],
            "IndentationError": ["IndentationError", "expected an indented block"],
            "ImportError": ["ImportError", "ModuleNotFoundError", "No module named"],
            "NameError": ["NameError", "name '", "is not defined"],
            "TypeError": ["TypeError", "takes", "argument", "expected"],
            "ValueError": ["ValueError", "invalid literal"],
            "AttributeError": ["AttributeError", "has no attribute"],
            "FileNotFoundError": ["FileNotFoundError", "No such file or directory"],
            "KeyError": ["KeyError"],
            "IndexError": ["IndexError", "list index out of range"],
            "ZeroDivisionError": ["ZeroDivisionError", "division by zero"],
            "PermissionError": ["PermissionError", "Permission denied"]
        }
        
        for error_type, patterns in error_types.items():
            if any(pattern in error_message for pattern in patterns):
                return error_type
        
        return "UnknownError"
    
    def _analyze_task_type(self, goal: str) -> str:
        """目標からタスクの種類を分析"""
        # タスク種別の判定パターン
        task_patterns = {
            "data_analysis": ["データ分析", "data analysis", "analyze data", "statistics", "統計", "csv", "pandas", "plot", "graph", "グラフ"],
            "web_scraping": ["スクレイピング", "scraping", "web", "html", "beautifulsoup", "bs4", "requests"],
            "file_processing": ["ファイル処理", "file", "read file", "write file", "ファイル読み込み", "ファイル書き込み"],
            "text_processing": ["テキスト処理", "text processing", "nlp", "自然言語処理", "natural language"],
            "database": ["データベース", "database", "sql", "sqlite", "mysql", "postgres"],
            "api_integration": ["api", "rest", "http", "request", "endpoint"],
            "image_processing": ["画像処理", "image", "図", "picture", "photo", "写真"],
            "automation": ["自動化", "automation", "automate", "batch", "バッチ", "定期実行"]
        }
        
        # シンプルなパターンマッチング
        goal_lower = goal.lower()
        for task_type, keywords in task_patterns.items():
            if any(keyword.lower() in goal_lower for keyword in keywords):
                return task_type
        
        # デフォルトのタスク種別
        return "general_task"
    
    def _extract_keywords(self, text: str) -> List[str]:
        """テキストからキーワードを抽出"""
        try:
            # LLMを使用してキーワードを抽出
            prompt = f"Extract 5-7 technical keywords from this text. Return only comma-separated keywords, no explanations:\n\n{text}"
            response = self.llm.generate_text(prompt)
            
            # カンマで分割してリスト化
            keywords = [kw.strip() for kw in response.split(",")]
            return keywords
        except Exception as e:
            print(f"Error extracting keywords: {str(e)}")
            # シンプルな抽出をフォールバックとして使用
            words = re.findall(r'\b\w+\b', text.lower())
            return [w for w in words if len(w) > 4][:5]  # 長めの単語を最大5つ
    
    def generate_plan_summary(self, plan_id: str) -> str:
        """プラン実行の要約を生成"""
        tasks = self.task_db.get_tasks_by_plan(plan_id)
        
        completed = sum(1 for task in tasks if task.status == TaskStatus.COMPLETED)
        failed = sum(1 for task in tasks if task.status == TaskStatus.FAILED)
        pending = sum(1 for task in tasks if task.status == TaskStatus.PENDING)
        running = sum(1 for task in tasks if task.status == TaskStatus.RUNNING)
        
        # プロジェクト環境を取得
        env = self._get_environment(plan_id)
        
        # インストールされたパッケージのリスト
        installed_packages = list(env.installed_packages)
        
        summary = f"""
        Plan execution summary:
        - Total tasks: {len(tasks)}
        - Completed: {completed}
        - Failed: {failed}
        - Pending: {pending}
        - Running: {running}
        
        Environment:
        - Project directory: {env.project_dir}
        - Installed packages: {', '.join(installed_packages) if installed_packages else 'None'}
        
        """
        
        if completed > 0:
            summary += "Completed tasks:\n"
            for task in tasks:
                if task.status == TaskStatus.COMPLETED:
                    # 結果が長い場合は省略
                    result_summary = task.result
                    if result_summary and len(result_summary) > 100:
                        result_summary = result_summary[:100] + "..."
                    summary += f"- {task.description}: Success\n"
        
        if failed > 0:
            summary += "\nFailed tasks:\n"
            for task in tasks:
                if task.status == TaskStatus.FAILED:
                    # エラーメッセージが長い場合は省略
                    error_summary = task.result
                    if error_summary and len(error_summary) > 100:
                        error_summary = error_summary[:100] + "..."
                    summary += f"- {task.description}: {error_summary}\n"
        
        # 学習分析情報
        if self.modular_code_manager:
            try:
                analytics = self.modular_code_manager.get_module_analytics()
                if analytics and analytics["total_modules"] > 0:
                    summary += f"\nLearning insights:\n"
                    summary += f"- Reusable modules available: {analytics['total_modules']}\n"
                    
                    # 主要なモジュールカテゴリ
                    if "categories" in analytics and analytics["categories"]:
                        top_categories = sorted(analytics["categories"].items(), key=lambda x: x[1], reverse=True)[:3]
                        summary += f"- Top module categories: {', '.join([f'{cat}({count})' for cat, count in top_categories])}\n"
            except Exception as e:
                print(f"Error getting module analytics: {str(e)}")
        
        return summary