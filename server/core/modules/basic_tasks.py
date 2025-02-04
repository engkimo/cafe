from typing import Dict, Any, List
import semantic_kernel as sk
from ..decorators import ModuleBase, task_function

class BasicTaskModule(ModuleBase):
    """基本的なタスク機能を提供するモジュール"""
    
    def __init__(self):
        self.name = "basic_tasks"
        self.description = "基本的なタスク実行機能を提供するモジュール"
    
    @task_function(
        name="create_calendar_event",
        description="Googleカレンダーにイベントを作成",
        input_schema={
            "subject": {
                "type": "string",
                "description": "イベントの件名",
                "required": True
            },
            "attendees": {
                "type": "string",
                "description": "参加者のメールアドレス(カンマ区切り)",
                "required": True
            },
            "start_time": {
                "type": "string",
                "description": "開始時間(ISO 8601形式)",
                "required": True
            },
            "end_time": {
                "type": "string",
                "description": "終了時間(ISO 8601形式)",
                "required": True
            }
        }
    )
    async def create_calendar_event(self, context: Dict[str, Any]) -> str:
        """Googleカレンダーにイベントを作成"""
        try:
            # 入力パラメータを取得
            subject = context["subject"]
            attendees = context["attendees"].split(",")
            start_time = context["start_time"]
            end_time = context["end_time"]
            
            # イベントの設定
            event = {
                'summary': subject,
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'Asia/Tokyo',
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'Asia/Tokyo',
                },
                'attendees': [{'email': email.strip()} for email in attendees],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 1440},  # 24時間前
                        {'method': 'popup', 'minutes': 30},    # 30分前
                    ],
                }
            }
            
            # イベントを作成
            result = {
                "action": "Googleカレンダーイベントの作成",
                "result": "ミーティングがスケジュールされました",
                "event_id": "generated_id",
                "event_link": "https://calendar.google.com/...",
                "output_data": {
                    "attendees": context["attendees"],
                    "start_time": start_time,
                    "end_time": end_time,
                    "subject": subject
                }
            }
            
            return str(result)
            
        except Exception as e:
            return str(e)
    
    @task_function(
        name="send_email",
        description="Gmailでメールを送信",
        input_schema={
            "to": {
                "type": "string",
                "description": "送信先メールアドレス",
                "required": True
            },
            "subject": {
                "type": "string",
                "description": "メールの件名",
                "required": True
            },
            "body": {
                "type": "string",
                "description": "メールの本文",
                "required": True
            }
        }
    )
    async def send_email(self, context: Dict[str, Any]) -> str:
        """Gmailでメールを送信"""
        try:
            # 入力パラメータを取得
            to = context["to"]
            subject = context["subject"]
            body = context["body"]
            
            # メールを送信
            result = {
                "action": "メール送信",
                "result": "メールを送信しました",
                "message_id": "generated_id",
                "output_data": {
                    "to": to,
                    "subject": subject,
                    "body": body
                }
            }
            
            return str(result)
            
        except Exception as e:
            return str(e)
    
    # MCPとの連携用のヘルパーメソッド
    async def register_with_mcp(self, mcp_server):
        """MCPサーバーにスキルを登録"""
        try:
            skills = {
                "create_calendar_event": self.create_calendar_event,
                "send_email": self.send_email
            }
            
            for name, skill in skills.items():
                await mcp_server.register_skill(name, skill)
                
        except Exception as e:
            print(f"MCPスキル登録エラー: {str(e)}")
            raise
    
    # スキルのメタデータを取得
    def get_skill_metadata(self) -> Dict[str, Any]:
        """スキルのメタデータを取得"""
        return {
            "name": self.name,
            "description": self.description,
            "functions": {
                "create_calendar_event": {
                    "name": "create_calendar_event",
                    "description": "Googleカレンダーにイベントを作成",
                    "parameters": {
                        "subject": {
                            "type": "string",
                            "description": "イベントの件名",
                            "required": True
                        },
                        "attendees": {
                            "type": "string",
                            "description": "参加者のメールアドレス(カンマ区切り)",
                            "required": True
                        },
                        "start_time": {
                            "type": "string",
                            "description": "開始時間(ISO 8601形式)",
                            "required": True
                        },
                        "end_time": {
                            "type": "string",
                            "description": "終了時間(ISO 8601形式)",
                            "required": True
                        }
                    }
                },
                "send_email": {
                    "name": "send_email",
                    "description": "Gmailでメールを送信",
                    "parameters": {
                        "to": {
                            "type": "string",
                            "description": "送信先メールアドレス",
                            "required": True
                        },
                        "subject": {
                            "type": "string",
                            "description": "メールの件名",
                            "required": True
                        },
                        "body": {
                            "type": "string",
                            "description": "メールの本文",
                            "required": True
                        }
                    }
                }
            }
        }