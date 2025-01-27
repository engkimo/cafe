#!/usr/bin/env node
import json
from typing import Dict, Any, List
from datetime import datetime
from openai import AsyncOpenAI

from ..auth.google_auth import GoogleAuthManager
from ..db.task_repository import TaskRepository
from ..models import Task
from ..docker_manager import docker_manager

class TaskExecutor:
    def __init__(self, openai_client: AsyncOpenAI, task_repository: TaskRepository, google_auth: GoogleAuthManager):
        self.openai_client = openai_client
        self.task_repository = task_repository
        self.google_auth = google_auth
        self._initialize_tools()

    def _initialize_tools(self):
        """利用可能なツールの初期化"""
        self.available_tools = {
            'Email Creation': ['text_generation', 'template_engine'],
            'Email Sending': ['mail_service'],
            'Data Processing': ['csv', 'database'],
            'Slack Integration': ['slack_service'],
            'Calendar Invitation Creation': ['calendar_service', 'template_engine'],
            'Calendar Invitation Sending': ['calendar_service', 'mail_service'],
            'Send Gmail': ['gmail_service'],
        }

        self.tool_schemas = {
            'Send Gmail': {
                'inputs': {
                    'to': {'type': 'string', 'description': '送信先メールアドレス'},
                    'subject': {'type': 'string', 'description': 'メールの件名'},
                    'body': {'type': 'string', 'description': 'メールの本文'},
                },
                'outputs': {
                    'success': {'type': 'boolean', 'description': '送信成功したかどうか'},
                    'message_id': {'type': 'string', 'description': '送信されたメールのID'},
                }
            }
        }

    async def execute_task(self, task: Task) -> Dict[str, Any]:
        """タスクを実行"""
        try:
            print(f"タスク実行開始: ID={task.id}, 名前={task.name}, タイプ={task.type}")
            print(f"タスクの依存関係: {task.dependencies}")
            print(f"タスクの入力: {task.inputs}")
            
            # タスクのステータスを実行中に更新
            task.status = "running"
            await self.task_repository.update_task(task)
            
            if task.type == "Create Google Calendar Event":
                result = await self._execute_calendar_event_task(task)
            elif task.type == "Send Gmail":
                result = await self._execute_gmail_task(task)
            else:
                raise ValueError(f"未対応のタスクタイプ: {task.type}")
            
            print(f"タスク実行完了: ID={task.id}")
            print(f"実行結果: {result}")
            return result
            
        except Exception as e:
            print(f"タスク実行エラー: ID={task.id}, エラー={str(e)}")
            task.status = "failed"
            await self.task_repository.update_task(task)
            raise

    async def _execute_calendar_event_task(self, task: Task) -> Dict[str, Any]:
        """カレンダーイベントタスクを実行"""
        try:
            # デフォルト値の設定
            if not task.inputs:
                task.inputs = {}
            
            if not task.inputs.get("subject"):
                task.inputs["subject"] = "新規ミーティング"
            if not task.inputs.get("attendees"):
                task.inputs["attendees"] = "dailyrandor@gmail.com"
            if not task.inputs.get("start_time") or not task.inputs.get("end_time"):
                default_date = datetime(2025, 1, 23)
                task.inputs["start_time"] = default_date.replace(hour=10, minute=0, second=0).isoformat()
                task.inputs["end_time"] = default_date.replace(hour=11, minute=0, second=0).isoformat()

            print(f"カレンダーイベント作成開始: {task.inputs}")

            # カレンダーイベントの作成
            event = {
                'summary': task.inputs["subject"],
                'start': {
                    'dateTime': task.inputs["start_time"],
                    'timeZone': 'Asia/Tokyo',
                },
                'end': {
                    'dateTime': task.inputs["end_time"],
                    'timeZone': 'Asia/Tokyo',
                },
                'attendees': [
                    {'email': email.strip()}
                    for email in task.inputs["attendees"].split(',')
                    if email.strip()
                ],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 30},
                    ],
                },
            }

            print(f"カレンダーイベント設定: {event}")
            result = self.google_auth.create_calendar_event(event)
            
            task.outputs = {
                "action": "Googleカレンダーイベントの作成",
                "result": "ミーティングがスケジュールされました",
                "event_id": result["event_id"],
                "event_link": result["event_link"],
                "output_data": {
                    "attendees": task.inputs["attendees"],
                    "start_time": task.inputs["start_time"],
                    "end_time": task.inputs["end_time"],
                    "subject": task.inputs["subject"]
                }
            }
            
            # タスクのステータスを更新
            task.status = "completed"
            await self.task_repository.update_task(task)
            
            # レスポンスを返す
            return {
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
                }
            }
            
        except Exception as e:
            print(f"カレンダーイベント作成エラー: {str(e)}")
            task.status = "failed"
            task.outputs = {"error": str(e)}
            await self.task_repository.update_task(task)
            raise

    async def _execute_gmail_task(self, task: Task) -> Dict[str, Any]:
        """Gmailタスクを実行"""
        try:
            # 入力値の設定
            if not task.inputs:
                task.inputs = {}

            # 依存タスクから情報を取得
            if task.dependencies:
                try:
                    # 依存タスクを取得
                    dep_tasks = await self.task_repository.get_tasks_by_name(task.dependencies[0])
                    if dep_tasks:
                        # 最新の完了済み依存タスクを取得
                        dep_task = next((t for t in dep_tasks if t.status == "completed"), None)
                        if dep_task and dep_task.outputs:
                            event_data = dep_task.outputs.get("output_data", {})
                            task.inputs = {
                                "to": event_data.get("attendees", "dailyrandor@gmail.com"),
                                "subject": f"ミーティングの招待: {event_data.get('subject', '新規ミーティング')}",
                                "body": f"""
ミーティングの招待状をお送りします。

日時: {event_data.get('start_time', '')} から {event_data.get('end_time', '')}
"""
                            }
                        else:
                            print("完了済みの依存タスクが見つかりません")
                            task.inputs = {
                                "to": "dailyrandor@gmail.com",
                                "subject": "ミーティングの招待",
                                "body": "ミーティングの招待メールです。"
                            }
                    else:
                        print("依存タスクが見つかりません")
                        task.inputs = {
                            "to": "dailyrandor@gmail.com",
                            "subject": "ミーティングの招待",
                            "body": "ミーティングの招待メールです。"
                        }
                except Exception as e:
                    print(f"依存タスクの情報取得エラー: {str(e)}")
                    task.inputs = {
                        "to": "dailyrandor@gmail.com",
                        "subject": "ミーティングの招待",
                        "body": "ミーティングの招待メールです。"
                    }
            else:
                task.inputs = {
                    "to": "dailyrandor@gmail.com",
                    "subject": "ミーティングの招待",
                    "body": "ミーティングの招待メールです。"
                }

            print(f"メール送信開始: {task.inputs}")

            # メールサーバーコンテナでコマンドを実行
            try:
                container = docker_manager.client.containers.get('cafe-mailserver')
                exec_result = container.exec_run(
                    [
                        "/usr/local/bin/send_mail.sh",
                        task.inputs["to"],
                        task.inputs["subject"],
                        task.inputs["body"],
                        "ryosuke.ohori@ulusage.com"
                    ],
                    environment={
                        "DEBUG": "1",
                        "RELAY_HOST": "smtp.gmail.com",
                        "RELAY_PORT": "587",
                        "RELAY_USER": "ryosuke.ohori@ulusage.com",
                        "RELAY_PASSWORD": "nfbt qhrk ccih mbdw"
                    },
                    workdir="/usr/local/bin",
                    user="root"
                )

                output = exec_result.output.decode() if exec_result.output else ""
                print(f"メール送信結果: {output}")

                if exec_result.exit_code != 0:
                    raise Exception(f"メール送信に失敗しました: {output}")

                task.outputs = {
                    "action": "メール送信",
                    "result": "招待メールを送信しました",
                    "message_id": "sent",
                    "output": output,
                    "exit_code": exec_result.exit_code
                }
                
                # タスクのステータスを更新
                task.status = "completed"
                await self.task_repository.update_task(task)
                
                # レスポンスを返す
                return {
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
                    }
                }

            except Exception as e:
                print(f"メール送信エラー: {str(e)}")
                task.status = "failed"
                task.outputs = {"error": str(e)}
                await self.task_repository.update_task(task)
                raise

        except Exception as e:
            task.outputs = {"success": False, "error": str(e)}
            task.status = "failed"
            await self.task_repository.update_task(task)
            raise

    async def _execute_generic_task(self, task: Task, tools: List[str]) -> None:
        """一般的なタスクを実行（OpenAI APIを使用）"""
        tools_str = ", ".join(tools)
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
- タイプ: {task.type}
- 名前: {task.name}
- 入力データ: {json.dumps(task.inputs, ensure_ascii=False)}
- 利用可能なツール: {tools_str}

必ずJSONフォーマットで結果を返してください。"""

        try:
            completion = await self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": task_prompt}
                ],
                temperature=0.7,
            )

            result = json.loads(completion.choices[0].message.content)
            task.outputs = result
        except json.JSONDecodeError as e:
            raise Exception("AIの応答をJSONとして解析できませんでした")
        except Exception as e:
            print(f"タスク実行エラー: {str(e)}")
            raise

    def _create_task_response(self, task: Task, tools: List[str]) -> Dict[str, Any]:
        """タスクのレスポンスを作成"""
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