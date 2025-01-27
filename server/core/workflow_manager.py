import os
import json
from typing import Dict, Any, List, AsyncGenerator
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
        self._initialize_openai()
        self._initialize_db()
        self._initialize_components()
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
        async with self.async_session() as session:
            task_repo = TaskRepository(session)
            task = await task_repo.get_task_by_id(task_id)
            
            if not task:
                raise ValueError(f"タスクが見つかりません: {task_id}")

            task_executor = TaskExecutor(self.openai_client, task_repo, self.google_auth)
            # 保存された入力値を使用
            task = await task_repo.get_task_by_id(task_id)
            if not task:
                raise ValueError(f"タスクが見つかりません: {task_id}")
            return await task_executor.execute_task(task)

    async def execute_all_tasks(self, task_ids: List[str]) -> AsyncGenerator[Dict[str, Any], None]:
        """指定された順序でタスクを実行"""
        workflow_run = None
        try:
            # 文字列のタスクIDを整数に変換
            remaining_tasks = [int(task_id) for task_id in task_ids]

            async with self.async_session() as session:
                task_repo = TaskRepository(session)
                workflow_run = await task_repo.create_workflow_run()

                while remaining_tasks:
                    # 実行可能なタスクを取得
                    executable_tasks = []
                    for task_id in remaining_tasks:
                        task = await task_repo.get_task_by_id(task_id)
                        if not task or task.status != "pending":
                            continue

                        # 依存関係のチェック
                        dependencies_satisfied = True
                        for dep_name in task.dependencies:
                            try:
                                print(f"依存タスク '{dep_name}' のチェックを開始")
                                # セッションをリフレッシュして最新の状態を取得
                                await session.refresh(task)
                                
                                # 依存タスクを名前で検索
                                dep_task = await task_repo.get_task_by_name(dep_name)
                                
                                if not dep_task:
                                    print(f"依存タスク '{dep_name}' が見つかりません")
                                    dependencies_satisfied = False
                                    break
                                
                                # セッションをリフレッシュして最新の状態を取得
                                await session.refresh(dep_task)
                                
                                print(f"依存タスク '{dep_name}' の状態: {dep_task.status}")
                                print(f"依存タスク '{dep_name}' の詳細: ID={dep_task.id}, 入力={dep_task.inputs}, 出力={dep_task.outputs}")
                                
                                if dep_task.status != "completed":
                                    print(f"依存タスク '{dep_name}' は完了していません（現在のステータス: {dep_task.status}）")
                                    dependencies_satisfied = False
                                    break
                                else:
                                    print(f"依存タスク '{dep_name}' は正常に完了しています")
                            except Exception as e:
                                print(f"依存タスクのチェックエラー: {str(e)}")
                                dependencies_satisfied = False
                                break

                        if dependencies_satisfied:
                            executable_tasks.append(task_id)

                    if not executable_tasks:
                        # 実行可能なタスクがない場合、残りのタスクにエラーを設定
                        for task_id in remaining_tasks:
                            async with self.async_session() as error_session:
                                error_repo = TaskRepository(error_session)
                                task = await error_repo.get_task_by_id(task_id)
                                if not task:
                                    continue

                                task.status = "failed"
                                await error_repo.update_task(task)

                                for dep_name in task.dependencies:
                                    dep_task = await error_repo.get_task_by_name(dep_name)
                                    
                                    if not dep_task or dep_task.status != "completed":
                                        yield {
                                            "type": "task_executed",
                                            "task": {
                                                "id": task.id,
                                                "name": task.name,
                                                "type": task.type,
                                                "inputs": task.inputs,
                                                "outputs": task.outputs,
                                                "status": task.status,
                                                "dependencies": task.dependencies,
                                                "tools": []
                                            },
                                            "error": f"依存タスク '{dep_name}' が完了していません"
                                        }
                        break

                    # 実行可能なタスクを実行
                    for task_id in executable_tasks:
                        async with self.async_session() as exec_session:
                            exec_repo = TaskRepository(exec_session)
                            task = await exec_repo.get_task_by_id(task_id)
                            if task:
                                task = await exec_repo.get_task_by_id(task_id)
                                if task:
                                    task_executor = TaskExecutor(self.openai_client, exec_repo, self.google_auth)
                                    result = await task_executor.execute_task(task)
                                yield result
                                remaining_tasks.remove(task_id)

                                if result["task"]["status"] != "completed":
                                    # タスクが失敗した場合、依存するタスクもスキップ
                                    tasks = await exec_repo.get_tasks_by_ids(remaining_tasks)
                                    dependent_tasks = [
                                        task.id for task in tasks
                                        if any(dep == result["task"]["name"] for dep in task.dependencies)
                                    ]
                                    
                                    for dep_task_id in dependent_tasks:
                                        remaining_tasks.remove(dep_task_id)

                # ワークフロー実行記録を更新
                async with self.async_session() as final_session:
                    final_repo = TaskRepository(final_session)
                    workflow_run.status = "completed"
                    workflow_run.completed_at = datetime.now()
                    
                    tasks = await final_repo.get_tasks_by_ids([int(task_id) for task_id in task_ids])
                    workflow_run.result = {
                        "executed_tasks": task_ids,
                        "success": all(task.status == "completed" for task in tasks)
                    }
                    
                    await final_repo.update_workflow_run(workflow_run)

        except Exception as e:
            print(f"タスク一括実行エラー: {e}")
            if workflow_run:
                async with self.async_session() as error_session:
                    error_repo = TaskRepository(error_session)
                    workflow_run.status = "failed"
                    workflow_run.completed_at = datetime.now()
                    workflow_run.error = str(e)
                    await error_repo.update_workflow_run(workflow_run)

            yield {
                "type": "error",
                "message": f"タスクの実行中にエラーが発生しました: {str(e)}"
            }

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