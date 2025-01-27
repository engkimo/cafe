from typing import Dict, Any, List, Optional, AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import json
import asyncio
import os
from openai import AsyncOpenAI

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaskConfig(BaseModel):
    name: str = Field(..., description="タスク名")
    type: str = Field(..., description="タスクのタイプ")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="タスクの入力データ")
    dependencies: List[str] = Field(default_factory=list, description="依存タスクのリスト")

class WorkflowManager:
    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self._initialize_clients()
        self._initialize_tools()

    def _initialize_clients(self):
        """APIクライアントの初期化"""
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("OPENAI_API_KEY環境変数が設定されていません")

        try:
            self.openai_client = AsyncOpenAI(
                api_key=os.getenv('OPENAI_API_KEY')
            )
            print("OpenAI APIクライアントの初期化が完了しました")
        except Exception as e:
            print(f"OpenAI APIクライアントの初期化エラー: {e}")
            raise

    def _initialize_tools(self):
        """エージェントで利用可能なツールの初期化"""
        self.available_tools = {
            'Email Creation': ['text_generation', 'template_engine'],
            'Email Sending': ['email'],
            'Data Processing': ['csv', 'database'],
        }

    async def process_chat_message(self, message: str) -> Dict[str, Any]:
        """チャットメッセージを処理しAIのレスポンスを返す"""
        try:
            print(f"メッセージを処理中: {message}")
            completion = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": """あなたはワークフロー分析アシスタントです。
ユーザーのリクエストを分析し、自動化可能なワークフロータスクを提案してください。
必ず以下のJSON形式で応答してください。他の形式は受け付けません。

例：
{
    "message": "3つの自動化タスクを提案します：メール作成、送信、結果集計",
    "suggested_tasks": [
        {
            "type": "Email Creation",
            "name": "Create Sales Email",
            "description": "テンプレートを使用してメールを作成",
            "confidence": 0.9,
            "inputs": {
                "template": "メールテンプレート",
                "data": "顧客データ"
            },
            "dependencies": []
        }
    ]
}"""},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
            )

            try:
                response_content = completion.choices[0].message.content
                print(f"AIレスポンス: {response_content}")
                response_data = json.loads(response_content)
            except json.JSONDecodeError as e:
                print(f"AIレスポンスの解析エラー: {e}")
                response_data = {
                    "message": completion.choices[0].message.content,
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
            task_type = task_config["type"]
            tools = self.available_tools.get(task_type, [])
            task_id = f"{task_type}_{len(self.tasks)}"

            task = {
                "id": task_id,
                "type": task_type,
                "name": task_config.get("name", ""),
                "inputs": task_config.get("inputs", {}),
                "outputs": {},
                "status": "pending",
                "dependencies": task_config.get("dependencies", []),
                "tools": tools
            }

            self.tasks[task_id] = task
            print(f"タスクを作成しました - ID {task_id}: {task}")
            return task

        except Exception as e:
            print(f"タスク作成エラー: {e}")
            raise

    async def execute_task(self, task_id: str) -> Dict[str, Any]:
        """タスクを実行"""
        if task_id not in self.tasks:
            raise ValueError(f"タスクが見つかりません: {task_id}")

        task = self.tasks[task_id]
        task["status"] = "running"
        print(f"タスク実行開始 - ID {task_id}")

        try:
            tools_str = ", ".join(task["tools"])
            system_prompt = """あなたはタスク実行アシスタントです。
与えられたタスクを実行し、必ず以下の形式でJSONを返してください。他の形式は受け付けません。

例：
{
    "action": "メール作成の実行",
    "result": "テンプレートを使用して10件のメールを作成しました",
    "output_data": {
        "processed_items": 10,
        "success_rate": 1.0,
        "details": "すべてのメールが正常に作成されました"
    }
}"""

            task_prompt = f"""以下のタスクを実行してください：

タスク情報：
- タイプ: {task['type']}
- 名前: {task['name']}
- 入力データ: {json.dumps(task['inputs'], ensure_ascii=False)}
- 利用可能なツール: {tools_str}

必ずJSONフォーマットで結果を返してください。"""

            completion = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": task_prompt}
                ],
                temperature=0.7,
            )

            try:
                result = json.loads(completion.choices[0].message.content)
                task["outputs"] = result
                task["status"] = "completed"
                print(f"タスク完了 - ID {task_id}: {result}")
                return {
                    "type": "task_executed",
                    "task": task
                }
            except json.JSONDecodeError as e:
                print(f"JSON解析エラー: {e}")
                print(f"AIの応答: {completion.choices[0].message.content}")
                task["status"] = "failed"
                return {
                    "type": "task_executed",
                    "task": task,
                    "error": "AIの応答をJSONとして解析できませんでした"
                }

        except Exception as e:
            task["status"] = "failed"
            print(f"タスク実行エラー - ID {task_id}: {e}")
            return {
                "type": "task_executed",
                "task": task,
                "error": str(e)
            }

    def _get_executable_tasks(self, tasks_to_check: List[str]) -> List[str]:
        """実行可能なタスク（依存関係が満たされているタスク）を取得"""
        executable = []
        for task_id in tasks_to_check:
            if task_id not in self.tasks:
                continue

            task = self.tasks[task_id]
            if task["status"] != "pending":
                continue

            # 依存関係のチェック
            dependencies_satisfied = True
            for dep_name in task["dependencies"]:
                dep_task = None
                for t in self.tasks.values():
                    if t["name"] == dep_name:
                        dep_task = t
                        break

                if not dep_task or dep_task["status"] != "completed":
                    dependencies_satisfied = False
                    break

            if dependencies_satisfied:
                executable.append(task_id)

        return executable

    async def execute_all_tasks(self, task_ids: List[str]) -> AsyncGenerator[Dict[str, Any], None]:
        """指定された順序でタスクを実行"""
        try:
            remaining_tasks = task_ids.copy()

            while remaining_tasks:
                # 実行可能なタスクを取得
                executable_tasks = self._get_executable_tasks(remaining_tasks)

                if not executable_tasks:
                    # 実行可能なタスクがない場合、残りのタスクにエラーを設定
                    for task_id in remaining_tasks:
                        task = self.tasks[task_id]
                        task["status"] = "failed"
                        for dep_name in task["dependencies"]:
                            dep_task = None
                            for t in self.tasks.values():
                                if t["name"] == dep_name:
                                    dep_task = t
                                    break

                            if not dep_task or dep_task["status"] != "completed":
                                yield {
                                    "type": "task_executed",
                                    "task": task,
                                    "error": f"依存タスク '{dep_name}' が完了していません"
                                }
                    break

                # 実行可能なタスクを実行
                for task_id in executable_tasks:
                    result = await self.execute_task(task_id)
                    yield result
                    remaining_tasks.remove(task_id)

                    if result["task"]["status"] != "completed":
                        # タスクが失敗した場合、依存するタスクもスキップ
                        dependent_tasks = [
                            tid for tid in remaining_tasks
                            if any(
                                self.tasks[tid]["dependencies"].count(self.tasks[task_id]["name"]) > 0
                            )
                        ]
                        for dep_task_id in dependent_tasks:
                            remaining_tasks.remove(dep_task_id)

        except Exception as e:
            print(f"タスク一括実行エラー: {e}")
            yield {
                "type": "error",
                "message": f"タスクの実行中にエラーが発生しました: {str(e)}"
            }

workflow_manager = WorkflowManager()

if __name__ == "__main__":
    import uvicorn
    import sys

    try:
        print("Starting FastAPI server...")
        uvicorn.run(
            "server.superagi_server:app",
            host="0.0.0.0",
            port=8000,
            log_level="info",
            reload=True,
            reload_dirs=["server"]
        )
    except Exception as e:
        print(f"Failed to start FastAPI server: {e}", file=sys.stderr)
        sys.exit(1)