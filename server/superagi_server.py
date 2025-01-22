from typing import Dict, Any, List, Optional, AsyncGenerator
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
                    {"role": "system", "content": """You are a workflow analysis assistant.
Please analyze user requests and suggest automatable workflow tasks.
IMPORTANT: Always respond in English, regardless of the input language.
Always respond in the following JSON format. No other format is accepted.

Example:
{
    "message": "Here are 3 automation tasks: email creation, sending, and result aggregation",
    "suggested_tasks": [
        {
            "type": "Email Creation",
            "name": "Create Sales Email",
            "description": "Create email using template",
            "confidence": 0.9,
            "inputs": {
                "template": "email template",
                "data": "customer data"
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
            system_prompt = """You are a task execution assistant.
Execute the given task and always return JSON in the following format. No other format is accepted.

Example:
{
    "action": "Execute email creation",
    "result": "Created 10 emails using the template",
    "output_data": {
        "processed_items": 10,
        "success_rate": 1.0,
        "details": "All emails were created successfully"
    }
}"""

            task_prompt = f"""Please execute the following task:

Task Information:
- Type: {task['type']}
- Name: {task['name']}
- Input Data: {json.dumps(task['inputs'], ensure_ascii=False)}
- Available Tools: {tools_str}

Please return the result in JSON format."""

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

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket接続が確立されました")

    try:
        while True:
            try:
                data = await websocket.receive_text()
                print(f"受信したメッセージ: {data}")
                message = json.loads(data)

                if message.get("type") == "message":
                    if not message.get("content"):
                        raise ValueError("メッセージの内容が必要です")

                    response = await workflow_manager.process_chat_message(message["content"])
                    print(f"送信するレスポンス: {response}")
                    await websocket.send_json(response)

                elif message.get("type") == "create_task":
                    if not message.get("task"):
                        raise ValueError("タスクの設定が必要です")

                    task = await workflow_manager.create_task(message["task"])
                    response = {
                        "type": "task_created",
                        "task": task
                    }
                    print(f"作成したタスク: {response}")
                    await websocket.send_json(response)

                elif message.get("type") == "execute_task":
                    if not message.get("taskId"):
                        raise ValueError("タスクIDが必要です")

                    response = await workflow_manager.execute_task(message["taskId"])
                    print(f"タスク実行結果: {response}")
                    await websocket.send_json(response)

                elif message.get("type") == "execute_all_tasks":
                    if not message.get("taskIds"):
                        raise ValueError("タスクIDのリストが必要です")

                    async for response in workflow_manager.execute_all_tasks(message["taskIds"]):
                        await websocket.send_json(response)

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "不明なメッセージタイプです"
                    })

            except json.JSONDecodeError:
                print("JSONデコードエラー")
                await websocket.send_json({
                    "type": "error",
                    "message": "無効なJSONフォーマットです"
                })
            except ValueError as e:
                print(f"バリデーションエラー: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
            except Exception as e:
                print(f"メッセージ処理エラー: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"メッセージの処理中にエラーが発生しました: {str(e)}"
                })

    except WebSocketDisconnect:
        print("クライアントが切断されました")
    except Exception as e:
        print(f"WebSocketエラー: {e}")
        try:
            await websocket.close()
        except:
            pass

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