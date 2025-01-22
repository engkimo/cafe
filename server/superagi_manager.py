from typing import Dict, Any, List, Optional
import asyncio
import json
import os
from openai import AsyncOpenAI

class WorkflowManager:
    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.agents = {}
        self._initialize_clients()
        self._initialize_tools()

    def _initialize_clients(self):
        """APIクライアントの初期化"""
        self.openai_client = AsyncOpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )

    def _initialize_tools(self):
        """エージェントで利用可能なツールの初期化"""
        self.available_tools = {
            'email_creation': ['text_generation', 'template_engine'],
            'email_sending': ['email'],
            'data_storage': ['csv', 'database'],
            'task_management': ['tasks', 'text_generation'],
        }

    async def process_chat_message(self, message: str) -> Dict[str, Any]:
        """チャットメッセージを処理しAIのレスポンスを返す"""
        try:
            # GPT-4でメッセージを分析
            completion = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": """あなたはワークフロー分析アシスタントです。
                    ユーザーのリクエストを分析し、自動化可能なワークフロータスクを提案してください。
                    応答は以下のJSON形式で返してください：
                    {
                        "message": "分析結果とユーザーへの応答",
                        "suggested_tasks": [
                            {
                                "type": "タスクの種類",
                                "name": "タスク名",
                                "description": "タスクの説明",
                                "confidence": 0.0から1.0の信頼度,
                                "inputs": {},
                                "dependencies": []
                            }
                        ]
                    }"""},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
            )

            # レスポンスの解析
            try:
                response_content = completion.choices[0].message.content
                response_data = json.loads(response_content)
            except (json.JSONDecodeError, AttributeError) as e:
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
            raise

    async def create_task(self, task_type: str, task_config: Dict[str, Any]) -> str:
        """新しいタスクを作成"""
        try:
            # タスクタイプに応じたツールを取得
            tools = self.available_tools.get(task_type, [])

            task_id = f"{task_type}_{len(self.tasks)}"
            self.tasks[task_id] = {
                "type": task_type,
                "name": task_config.get("name", ""),
                "inputs": task_config.get("inputs", {}),
                "dependencies": task_config.get("dependencies", []),
                "status": "pending",
                "tools": tools
            }

            print(f"タスクを作成しました - ID {task_id}: {self.tasks[task_id]}")
            return task_id

        except Exception as e:
            print(f"タスク作成エラー: {e}")
            raise

    async def execute_task(self, task_id: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """タスクを実行"""
        if task_id not in self.tasks:
            raise ValueError(f"タスクが見つかりません: {task_id}")

        task = self.tasks[task_id]
        task["status"] = "running"

        try:
            # タスク実行プロンプトの作成
            tools_str = ", ".join(task["tools"])
            prompt = f"""以下のタスクを実行してください。利用可能なツール: {tools_str}
            タスクの種類: {task['type']}
            入力データ: {json.dumps(inputs)}

            以下の情報を含む応答を生成してください：
            1. 実行したアクション
            2. アクションの結果
            3. 出力データ

            応答はJSON形式で返してください。"""

            # GPT-4でタスクを実行
            completion = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "あなたはタスク実行アシスタントです。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
            )

            result = completion.choices[0].message.content
            task["status"] = "completed"
            return {
                "status": "completed",
                "output": result
            }

        except Exception as e:
            task["status"] = "failed"
            print(f"タスク実行エラー: {e}")
            raise

workflow_manager = WorkflowManager()