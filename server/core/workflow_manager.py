import os
import json
import re
from typing import Dict, Any, List, AsyncGenerator, Optional
from datetime import datetime
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from ..auth.google_auth import GoogleAuthManager
from ..db.task_repository import TaskRepository
from ..core.task_executor import TaskExecutor
from ..models import Task, Base

class WorkflowManager:
    def __init__(self):
        """初期化処理を一度だけ実行"""
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self._initialize_openai()
        self._initialize_db()
        self._initialize_components()
        self._initialize_clients()
        self._initialize_tools()
        self.task_patterns = {
            "Record Audio": {
                "required_inputs": ["format", "duration", "quality"],
                "required_outputs": ["audio_file"],
                "dependencies": []
            },
            "Transcribe Audio": {
                "required_inputs": ["audio_file", "language", "model"],
                "required_outputs": ["text"],
                "dependencies": ["Record Audio"]
            },
            "Extract Key Points": {
                "required_inputs": ["text", "language", "max_points"],
                "required_outputs": ["key_points"],
                "dependencies": ["Transcribe Audio"]
            },
            "Create Google Calendar Event": {
                "required_inputs": ["subject", "attendees", "start_time", "end_time"],
                "required_outputs": ["event_id"],
                "dependencies": []
            },
            "Send Gmail": {
                "required_inputs": ["to", "subject", "body"],
                "required_outputs": ["message_id"],
                "dependencies": ["Create Google Calendar Event"]
            }
        }
        print("ワークフローマネージャーの初期化が完了しました")

    def _initialize_openai(self):
        """OpenAI APIクライアントの初期化"""
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY環境変数が設定されていません")

        print(f"WorkflowManager: OpenAI APIキーを使用します: {openai_api_key[:8]}...")
        self.openai_client = AsyncOpenAI(api_key=openai_api_key)
        print("OpenAI APIクライアントの初期化が完了しました")

    def _initialize_db(self):
        """データベース接続の初期化"""
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL環境変数が設定されていません")

        # PostgreSQLのURLをasync用に変換
        async_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
        
        self.engine = create_async_engine(async_url, echo=True)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    def _initialize_components(self):
        """コンポーネントの初期化"""
        self.google_auth = GoogleAuthManager()
        print("Google Calendar APIクライアントの初期化が完了しました")
        
        # TaskRepositoryの初期化
        self.task_repository = TaskRepository(self.async_session())
        
        # TaskExecutorの初期化
        self.task_executor = TaskExecutor(
            openai_client=self.openai_client,
            task_repository=self.task_repository,
            google_auth=self.google_auth
        )

    def _initialize_clients(self):
        # This method is mentioned in the __init__ method but its implementation is not provided in the original file or the new file
        # It's assumed to exist as it's called in the __init__ method
        pass

    def _initialize_tools(self):
        # This method is mentioned in the __init__ method but its implementation is not provided in the original file or the new file
        # It's assumed to exist as it's called in the __init__ method
        pass

    async def process_chat_message(self, message: str) -> Dict[str, Any]:
        """チャットメッセージを処理しAIのレスポンスを返す"""
        try:
            print(f"メッセージを処理中: {message}")
            completion = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "あなたはワークフロー分析アシスタントです。ユーザーのリクエストを分析し、自動化可能なワークフロータスクを提案してください。カレンダー招待を作成する場合は、必ずメール通知も含めてください。"},
                    {"role": "user", "content": message}
                ],
                functions=[{
                    "name": "suggest_workflow_tasks",
                    "description": "ワークフローのタスクを提案する",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string",
                                "description": "提案の説明メッセージ"
                            },
                            "suggested_tasks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {
                                            "type": "string",
                                            "enum": ["Create Google Calendar Event", "Send Gmail"],
                                            "description": "タスクのタイプ"
                                        },
                                        "name": {
                                            "type": "string",
                                            "description": "タスクの名前"
                                        },
                                        "description": {
                                            "type": "string",
                                            "description": "タスクの説明"
                                        },
                                        "confidence": {
                                            "type": "number",
                                            "description": "タスクの確信度（0-1）"
                                        },
                                        "dependencies": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "依存するタスクの名前リスト"
                                        }
                                    },
                                    "required": ["type", "name", "description", "confidence", "dependencies"]
                                }
                            }
                        },
                        "required": ["message", "suggested_tasks"]
                    }
                }],
                function_call={"name": "suggest_workflow_tasks"},
                temperature=0.7,
            )

            try:
                function_call = completion.choices[0].message.function_call
                response_data = json.loads(function_call.arguments)
                print(f"AIレスポンス: {json.dumps(response_data, ensure_ascii=False, indent=2)}")
            except Exception as e:
                print(f"AIレスポンスの解析エラー: {e}")
                response_data = {
                    "message": "タスクの提案に失敗しました",
                    "suggested_tasks": []
                }

            return {
                "type": "message",
                "content": response_data["message"],
                "suggested_tasks": response_data.get("suggested_tasks", [])
            }

        except Exception as e:
            print(f"メッセージ処理エラー: {e}")
            return {
                "type": "error",
                "message": str(e)
            }

    async def create_task(self, task_config: Dict[str, Any]) -> Dict[str, Any]:
        """新しいタスクを作成"""
        try:
            print(f"タスク作成開始: {task_config}")
            async with self.async_session() as session:
                task_repo = TaskRepository(session)
                task = await task_repo.create_task(task_config)
                tools = []
                
                return {
                    "id": task.id,
                    "name": task.name,
                    "type": task.type,
                    "inputs": task.inputs,
                    "outputs": task.outputs,
                    "status": task.status,
                    "dependencies": task.dependencies,
                    "tools": tools
                }

        except Exception as e:
            print(f"タスク作成エラー: {e}")
            raise

    async def execute_task(self, task_id: int) -> Dict[str, Any]:
        """タスクを実行"""
        try:
            async with self.async_session() as session:
                task_repo = TaskRepository(session)
                task = await task_repo.get_task_by_id(task_id)
                
                if not task:
                    raise ValueError(f"タスクが見つかりません: {task_id}")

                # タスクの状態をメモリに同期
                task_dict = {
                    "id": task.id,
                    "name": task.name,
                    "type": task.type,
                    "inputs": task.inputs,
                    "outputs": task.outputs,
                    "status": task.status,
                    "dependencies": task.dependencies
                }
                self.tasks[str(task.id)] = task_dict

                # 依存関係のチェックと入力データの収集
                input_data = task.inputs.copy() if task.inputs else {}
                for dep_name in task.dependencies:
                    dep_task = await task_repo.get_task_by_name(dep_name)
                    if not dep_task:
                        error_msg = f"依存タスク '{dep_name}' が見つかりません"
                        task.status = "failed"
                        task.outputs = {"error": error_msg}
                        await task_repo.update_task(task)
                        task_dict["status"] = "failed"
                        task_dict["outputs"] = {"error": error_msg}
                        return {
                            "type": "task_executed",
                            "task": task_dict,
                            "error": error_msg
                        }
                    
                    if dep_task.status != "completed":
                        error_msg = f"依存タスク '{dep_name}' が完了していません（現在の状態: {dep_task.status}）"
                        task.status = "failed"
                        task.outputs = {"error": error_msg}
                        await task_repo.update_task(task)
                        task_dict["status"] = "failed"
                        task_dict["outputs"] = {"error": error_msg}
                        return {
                            "type": "task_executed",
                            "task": task_dict,
                            "error": error_msg
                        }
                    
                    # 依存タスクの出力を入力データにマージ
                    if dep_task.outputs and isinstance(dep_task.outputs, dict):
                        if "output_data" in dep_task.outputs:
                            input_data.update(dep_task.outputs["output_data"])
                        else:
                            input_data.update(dep_task.outputs)

                # タスクの種類に応じた入力データの準備
                if not input_data:
                    if task.type == "Create Google Calendar Event":
                        input_data = {
                            "subject": "新規ミーティング",
                            "attendees": "dailyrandor@gmail.com",
                            "start_time": "2025-01-23T10:00:00",
                            "end_time": "2025-01-23T11:00:00"
                        }
                    elif task.type == "Send Gmail":
                        input_data = {
                            "to": "dailyrandor@gmail.com",
                            "subject": "ミーティングの招待",
                            "body": "ミーティングに招待されました。"
                        }
                    elif task.type == "Record Audio":
                        input_data = {
                            "format": "mp3",
                            "duration": 3600,
                            "quality": "high"
                        }
                    elif task.type == "Transcribe Audio":
                        input_data = {
                            "language": "ja",
                            "model": "whisper-1"
                        }
                    elif task.type == "Extract Key Points":
                        input_data = {
                            "language": "ja",
                            "max_points": 5
                        }

                # タスクの入力を更新
                task.inputs = input_data
                await task_repo.update_task(task)
                task_dict["inputs"] = input_data

                # タスク実行
                task_executor = TaskExecutor(self.openai_client, task_repo, self.google_auth)
                result = await task_executor.execute_task(task)
                
                # メモリ上のタスク状態を更新
                task_dict.update(result["task"])
                
                return result

        except Exception as e:
            error_msg = f"タスク実行エラー: {str(e)}"
            print(error_msg)
            
            # エラー情報をデータベースに保存
            async with self.async_session() as session:
                task_repo = TaskRepository(session)
                task = await task_repo.get_task_by_id(task_id)
                if task:
                    task.status = "failed"
                    task.outputs = {"error": error_msg}
                    await task_repo.update_task(task)
                    
                    # メモリ上のタスク状態も更新
                    if str(task_id) in self.tasks:
                        self.tasks[str(task_id)]["status"] = "failed"
                        self.tasks[str(task_id)]["outputs"] = {"error": error_msg}
            
            raise

    async def execute_all_tasks(self, task_ids: List[str]) -> AsyncGenerator[Dict[str, Any], None]:
        """指定された順序でタスクを実行"""
        try:
            # タスクリストをデータベースから取得
            tasks = []
            async with self.async_session() as session:
                task_repo = TaskRepository(session)
                for task_id in task_ids:
                    task = await task_repo.get_task_by_id(int(task_id))
                    if task:
                        task_dict = {
                            "id": task.id,
                            "name": task.name,
                            "type": task.type,
                            "inputs": task.inputs,
                            "outputs": task.outputs,
                            "status": task.status,
                            "dependencies": task.dependencies
                        }
                        tasks.append(task_dict)
                        # メモリ上のタスク管理も更新
                        self.tasks[str(task.id)] = task_dict
            
            if not tasks:
                yield {
                    "type": "error",
                    "message": "実行するタスクが見つかりません"
                }
                return

            # ワークフローを最適化
            optimized_tasks = await self.optimize_workflow(tasks)
            
            # 最適化されたタスクの実行順序でIDリストを更新
            task_ids = [str(task["id"]) for task in optimized_tasks]
            remaining_tasks = task_ids.copy()

            while remaining_tasks:
                # 実行可能なタスクを取得
                executable_tasks = self._get_executable_tasks(remaining_tasks)

                if not executable_tasks:
                    # 実行可能なタスクがない場合の処理
                    failed_tasks = []
                    for task_id in remaining_tasks:
                        task = self.tasks[task_id]
                        task["status"] = "failed"
                        failed_tasks.append(task)
                        
                        # 失敗の原因を分析
                        missing_deps = []
                        for dep_name in task["dependencies"]:
                            dep_task = None
                            for t in self.tasks.values():
                                if t["name"] == dep_name:
                                    dep_task = t
                                    break

                            if not dep_task or dep_task["status"] != "completed":
                                missing_deps.append(dep_name)
                        
                        # 失敗情報を記録
                        task["failure_info"] = {
                            "missing_dependencies": missing_deps,
                            "timestamp": datetime.now().isoformat(),
                            "context": "依存タスクの実行失敗"
                        }
                        
                        # データベースを更新
                        async with self.async_session() as session:
                            task_repo = TaskRepository(session)
                            db_task = await task_repo.get_task_by_id(int(task_id))
                            if db_task:
                                db_task.status = "failed"
                                db_task.outputs = {"failure_info": task["failure_info"]}
                                await task_repo.update_task(db_task)
                        
                        yield {
                            "type": "task_executed",
                            "task": task,
                            "error": f"依存タスク {', '.join(missing_deps)} が完了していません"
                        }
                    
                    # 学習データを更新
                    await self._update_task_patterns(failed_tasks)
                    break

                # 実行可能なタスクを実行
                for task_id in executable_tasks:
                    try:
                        result = await self.execute_task(int(task_id))
                        # メモリ上のタスク状態を更新
                        if str(task_id) in self.tasks:
                            self.tasks[str(task_id)].update(result["task"])
                        yield result
                        remaining_tasks.remove(task_id)

                        if result["task"]["status"] != "completed":
                            # タスクが失敗した場合の処理
                            failed_task = result["task"]
                            dependent_tasks = [
                                tid for tid in remaining_tasks
                                if any(
                                    self.tasks[tid]["dependencies"].count(failed_task["name"]) > 0
                                )
                            ]
                            
                            # 失敗情報を記録
                            failed_task["failure_info"] = {
                                "error": result.get("error", "不明なエラー"),
                                "timestamp": datetime.now().isoformat(),
                                "context": "タスク実行失敗"
                            }
                            
                            # 依存タスクも失敗としてマーク
                            for dep_task_id in dependent_tasks:
                                remaining_tasks.remove(dep_task_id)
                                self.tasks[dep_task_id]["status"] = "failed"
                                self.tasks[dep_task_id]["failure_info"] = {
                                    "error": f"依存タスク {failed_task['name']} の失敗",
                                    "timestamp": datetime.now().isoformat(),
                                    "context": "依存関係による失敗"
                                }
                                
                                # データベースを更新
                                async with self.async_session() as session:
                                    task_repo = TaskRepository(session)
                                    db_task = await task_repo.get_task_by_id(int(dep_task_id))
                                    if db_task:
                                        db_task.status = "failed"
                                        db_task.outputs = {"failure_info": self.tasks[dep_task_id]["failure_info"]}
                                        await task_repo.update_task(db_task)
                            
                            # 学習データを更新
                            await self._update_task_patterns([failed_task])
                    except Exception as e:
                        print(f"タスク実行エラー - ID {task_id}: {e}")
                        yield {
                            "type": "error",
                            "message": f"タスク {task_id} の実行中にエラーが発生しました: {str(e)}"
                        }

        except Exception as e:
            print(f"タスク一括実行エラー: {e}")
            yield {
                "type": "error",
                "message": f"タスクの実行中にエラーが発生しました: {str(e)}"
            }

    async def _update_task_patterns(self, failed_tasks: List[Dict[str, Any]]) -> None:
        """タスクパターンを失敗情報に基づいて更新"""
        try:
            for task in failed_tasks:
                task_type = task["type"]
                if task_type in self.task_patterns:
                    pattern = self.task_patterns[task_type]
                    
                    # 失敗情報から学習
                    failure_info = task.get("failure_info", {})
                    if "missing_dependencies" in failure_info:
                        # 必要な依存関係を追加
                        for dep in failure_info["missing_dependencies"]:
                            if dep not in pattern["dependencies"]:
                                pattern["dependencies"].append(dep)
                    
                    # 入力要件の更新
                    if "error" in failure_info:
                        # エラーメッセージを分析して必要な入力を特定
                        prompt = f"""以下のエラーメッセージから、タスクに必要な入力を特定してください：
                        エラー: {failure_info['error']}
                        
                        現在の必要な入力: {pattern['required_inputs']}
                        
                        追加すべき入力があれば、リストで返してください。"""

                        completion = await self.openai_client.chat.completions.create(
                            model="gpt-4",
                            messages=[
                                {"role": "system", "content": "あなたはワークフロー最適化アシスタントです。"},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.7,
                        )

                        try:
                            new_inputs = json.loads(completion.choices[0].message.content)
                            for input_name in new_inputs:
                                if input_name not in pattern["required_inputs"]:
                                    pattern["required_inputs"].append(input_name)
                        except json.JSONDecodeError:
                            print("新しい入力要件の解析に失敗しました")

        except Exception as e:
            print(f"タスクパターンの更新エラー: {e}")

    async def get_task(self, task_id: int) -> Task:
        """タスクを取得"""
        async with self.async_session() as session:
            task_repo = TaskRepository(session)
            return await task_repo.get_task_by_id(task_id)

    async def update_task(self, task_id: int, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """タスクの入力値を更新"""
        try:
            print(f"タスク更新開始 - ID: {task_id}, 入力: {json.dumps(inputs, ensure_ascii=False)}")
            
            async with self.async_session() as session:
                task_repo = TaskRepository(session)
                task = await task_repo.get_task_by_id(task_id)
                
                if not task:
                    raise ValueError(f"タスクが見つかりません: {task_id}")

                # 入力値を更新
                task.inputs = inputs
                await task_repo.update_task(task)
                print(f"タスク更新完了 - ID: {task_id}")

                task_response = {
                    "id": task.id,
                    "name": task.name,
                    "type": task.type,
                    "inputs": task.inputs,
                    "outputs": task.outputs,
                    "status": task.status,
                    "dependencies": task.dependencies,
                    "tools": []
                }
                return {
                    "type": "task_updated",
                    "task": task_response
                }

        except Exception as e:
            print(f"タスク更新エラー - ID: {task_id}, エラー: {str(e)}")
            raise

    async def delete_all_tasks(self) -> Dict[str, Any]:
        """すべてのタスクを削除"""
        try:
            async with self.async_session() as session:
                task_repo = TaskRepository(session)
                await task_repo.delete_all_tasks()
            
            print("すべてのタスクを削除しました")
            return {
                "type": "tasks_deleted",
                "message": "すべてのタスクが削除されました"
            }
        except Exception as e:
            print(f"タスク削除エラー: {e}")
            return {
                "type": "error",
                "message": f"タスクの削除中にエラーが発生しました: {str(e)}"
            }

    async def optimize_workflow(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """ワークフローを最適化し、必要なタスクを追加"""
        try:
            optimized_tasks = tasks.copy()
            
            # 1. タスクパターンに基づく依存関係の修正
            for task in optimized_tasks:
                task_type = task["type"]
                if task_type in self.task_patterns:
                    pattern = self.task_patterns[task_type]
                    # 既存の依存関係をクリア
                    task["dependencies"] = []
                    # パターンから必要な依存関係を追加
                    for dep_task in optimized_tasks:
                        if dep_task["type"] in pattern["dependencies"]:
                            task["dependencies"].append(dep_task["name"])
            
            # 2. 並列実行可能なタスクの識別
            parallel_groups = self._identify_parallel_tasks(optimized_tasks)
            
            # 3. 実行時間の最適化
            optimized_tasks = self._optimize_execution_time(optimized_tasks, parallel_groups)
            
            # 4. 過去の実行結果からの学習を適用
            optimized_tasks = await self._apply_learned_optimizations(optimized_tasks)
            
            # 5. タスクの実行順序を最適化
            optimized_tasks = self._optimize_task_order(optimized_tasks)
            
            return optimized_tasks

        except Exception as e:
            print(f"ワークフロー最適化エラー: {e}")
            return tasks

    def _identify_parallel_tasks(self, tasks: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """並列実行可能なタスクをグループ化"""
        groups = []
        visited = set()
        
        for task in tasks:
            if task["name"] in visited:
                continue
            
            # 同じレベルのタスクを探す（依存関係が同じタスク）
            parallel_group = [task]
            visited.add(task["name"])
            
            for other_task in tasks:
                if other_task["name"] not in visited:
                    if set(other_task["dependencies"]) == set(task["dependencies"]):
                        parallel_group.append(other_task)
                        visited.add(other_task["name"])
            
            if parallel_group:
                groups.append(parallel_group)
        
        return groups

    def _optimize_execution_time(
        self, 
        tasks: List[Dict[str, Any]], 
        parallel_groups: List[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """実行時間を最適化"""
        optimized_order = []
        
        # 並列グループごとに最適な実行順序を決定
        for group in parallel_groups:
            # グループ内のタスクを実行時間の短い順にソート
            sorted_group = sorted(
                group,
                key=lambda t: self._estimate_execution_time(t),
                reverse=True
            )
            optimized_order.extend(sorted_group)
        
        return optimized_order

    def _estimate_execution_time(self, task: Dict[str, Any]) -> float:
        """タスクの実行時間を推定"""
        # タスクタイプごとの基本実行時間
        base_times = {
            "Create Google Calendar Event": 2.0,
            "Send Gmail": 1.5,
            "Record Audio": 0.5,
            "Transcribe Audio": 5.0,
            "Extract Key Points": 3.0
        }
        
        # 基本実行時間を取得
        base_time = base_times.get(task["type"], 1.0)
        
        # 入力データの量による補正
        input_size = len(str(task.get("inputs", {})))
        time_factor = 1.0 + (input_size / 1000)  # 1KB当たり1%増加
        
        # 依存関係の数による補正
        dep_factor = 1.0 + (len(task.get("dependencies", [])) * 0.1)  # 依存1つ当たり10%増加
        
        return base_time * time_factor * dep_factor

    async def _apply_learned_optimizations(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """過去の実行結果から学習した最適化を適用"""
        try:
            # 失敗パターンの分析
            async with self.async_session() as session:
                task_repo = TaskRepository(session)
                for task in tasks:
                    # 同じタイプの過去のタスクを検索
                    similar_tasks = await task_repo.get_tasks_by_type(task["type"])
                    failure_patterns = self._analyze_failure_patterns(similar_tasks)
                    
                    # 失敗を防ぐための追加の依存関係や入力を適用
                    for pattern in failure_patterns:
                        if pattern["missing_input"] and pattern["missing_input"] not in task["inputs"]:
                            # 必要な入力を追加
                            task["inputs"][pattern["missing_input"]] = pattern["default_value"]
                        
                        if pattern["required_dependency"]:
                            # 必要な依存関係を追加
                            if pattern["required_dependency"] not in task["dependencies"]:
                                task["dependencies"].append(pattern["required_dependency"])
            
            return tasks

        except Exception as e:
            print(f"学習済み最適化の適用エラー: {e}")
            return tasks

    def _analyze_failure_patterns(self, tasks: List[Task]) -> List[Dict[str, Any]]:
        """タスクの失敗パターンを分析"""
        patterns = []
        
        for task in tasks:
            if task.status == "failed" and isinstance(task.outputs, dict):
                failure_info = task.outputs.get("failure_info", {})
                
                if "missing_dependencies" in failure_info:
                    for dep in failure_info["missing_dependencies"]:
                        patterns.append({
                            "required_dependency": dep,
                            "missing_input": None,
                            "default_value": None
                        })
                
                if "error" in failure_info:
                    # エラーメッセージから必要な入力を推測
                    error_msg = failure_info["error"]
                    if "required" in error_msg.lower():
                        input_match = re.search(r"'(\w+)' is required", error_msg)
                        if input_match:
                            patterns.append({
                                "required_dependency": None,
                                "missing_input": input_match.group(1),
                                "default_value": self._get_default_value(input_match.group(1))
                            })
        
        return patterns

    def _get_default_value(self, input_name: str) -> Any:
        """入力名に基づいてデフォルト値を返す"""
        defaults = {
            "subject": "新規ミーティング",
            "attendees": "dailyrandor@gmail.com",
            "start_time": "2025-01-23T10:00:00",
            "end_time": "2025-01-23T11:00:00",
            "to": "dailyrandor@gmail.com",
            "body": "ミーティングの内容です。",
            "recording_format": "mp3",
            "language": "ja"
        }
        return defaults.get(input_name)

    async def _generate_input_task(self, required_input: str) -> Optional[Dict[str, Any]]:
        """必要な入力を提供するタスクを生成"""
        try:
            # GPT-4を使用してタスクを生成
            prompt = f"""以下の入力を提供するために必要なタスクを生成してください：
            必要な入力: {required_input}
            
            タスクの形式:
            {{
                "name": "タスク名",
                "type": "タスクタイプ",
                "inputs": {{}},
                "outputs": {{"required_input": "出力の説明"}},
                "dependencies": []
            }}"""

            completion = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "あなたはワークフロー最適化アシスタントです。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
            )

            new_task = json.loads(completion.choices[0].message.content)
            new_task["status"] = "pending"
            return new_task

        except Exception as e:
            print(f"タスク生成エラー: {e}")
            return None

    def _optimize_task_order(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """タスクの実行順序を最適化"""
        # 依存関係グラフの構築
        graph = {}
        for task in tasks:
            graph[task["name"]] = set(task["dependencies"])
        
        # トポロジカルソートで最適な実行順序を決定
        sorted_tasks = []
        visited = set()
        temp = set()
        
        def visit(task_name: str):
            if task_name in temp:
                raise ValueError("循環依存関係が検出されました")
            if task_name in visited:
                return
            
            temp.add(task_name)
            for dep in graph[task_name]:
                visit(dep)
            temp.remove(task_name)
            visited.add(task_name)
            sorted_tasks.append(task_name)
        
        for task in tasks:
            if task["name"] not in visited:
                visit(task["name"])
        
        # ソートされた順序でタスクを並び替え
        task_dict = {task["name"]: task for task in tasks}
        return [task_dict[name] for name in sorted_tasks]

    def _get_executable_tasks(self, remaining_tasks: List[str]) -> List[str]:
        """実行可能なタスクを取得"""
        executable_tasks = []
        for task_id in remaining_tasks:
            task = self.tasks[task_id]
            if task["status"] == "pending":
                dependencies_satisfied = True
                for dep_name in task["dependencies"]:
                    # 依存タスクを探す
                    dep_task = None
                    for t in self.tasks.values():
                        if t["name"] == dep_name:
                            dep_task = t
                            break
                    
                    # 依存タスクが見つからないか、完了していない場合
                    if not dep_task or dep_task["status"] != "completed":
                        dependencies_satisfied = False
                        break
                
                if dependencies_satisfied:
                    executable_tasks.append(task_id)
        
        return executable_tasks