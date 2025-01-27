import json
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Any
from datetime import datetime

from ..core.workflow_manager import WorkflowManager

class WebSocketHandler:
    def __init__(self, workflow_manager: WorkflowManager):
        self.workflow_manager = workflow_manager
        self.active_connections: Dict[str, WebSocket] = {}
        print("WebSocketハンドラーが初期化されました")

    async def handle_connection(self, websocket: WebSocket):
        """WebSocket接続を処理"""
        connection_id = str(id(websocket))
        try:
            print(f"新しいWebSocket接続を受け入れようとしています... (ID: {connection_id})")
            await websocket.accept()
            self.active_connections[connection_id] = websocket
            print(f"WebSocket接続が確立されました (ID: {connection_id})")
            print(f"現在のアクティブな接続数: {len(self.active_connections)}")

            while True:
                try:
                    data = await websocket.receive_text()
                    print(f"受信したメッセージ (ID: {connection_id}): {data}")
                    
                    # クライアントからのping-pongメッセージを処理
                    if data == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        })
                        continue

                    message = json.loads(data)
                    print(f"パースされたメッセージ: {json.dumps(message, ensure_ascii=False)}")

                    response = await self._process_message(message)
                    print(f"生成された応答: {json.dumps(response, ensure_ascii=False) if isinstance(response, dict) else 'AsyncGenerator'}")

                    if isinstance(response, dict):
                        await websocket.send_json(response)
                    else:
                        # 非同期ジェネレータを処理
                        async for task_response in response:
                            print(f"タスク実行結果: {json.dumps(task_response, ensure_ascii=False)}")
                            await websocket.send_json(task_response)

                except WebSocketDisconnect:
                    print(f"クライアントが正常に切断されました (ID: {connection_id})")
                    break
                except json.JSONDecodeError as e:
                    print(f"JSONデコードエラー (ID: {connection_id}): {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": "無効なJSONフォーマットです"
                    })
                except Exception as e:
                    print(f"メッセージ処理中の予期せぬエラー (ID: {connection_id}): {str(e)}")
                    print(f"エラーの種類: {type(e).__name__}")
                    import traceback
                    print(f"エラーのトレースバック:\n{traceback.format_exc()}")
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"メッセージの処理中にエラーが発生しました: {str(e)}"
                        })
                    except:
                        print(f"エラーメッセージの送信に失敗しました (ID: {connection_id})")
                        break

        except Exception as e:
            print(f"WebSocket接続の確立中にエラーが発生しました (ID: {connection_id}): {str(e)}")
            import traceback
            print(f"エラーのトレースバック:\n{traceback.format_exc()}")
        finally:
            print(f"WebSocket接続をクリーンアップしています (ID: {connection_id})")
            self.active_connections.pop(connection_id, None)
            try:
                await websocket.close()
            except:
                pass
            print(f"接続がクリーンアップされました。残りの接続数: {len(self.active_connections)}")

    async def _process_message(self, message: Dict[str, Any]):
        """メッセージの種類に応じた処理を実行"""
        try:
            message_type = message.get("type")
            print(f"処理するメッセージタイプ: {message_type}")

            if message_type == "message":
                if not message.get("content"):
                    raise ValueError("メッセージの内容が必要です")
                return await self.workflow_manager.process_chat_message(message["content"])

            elif message_type == "create_task":
                if not message.get("task"):
                    raise ValueError("タスクの設定が必要です")
                task = await self.workflow_manager.create_task(message["task"])
                return {
                    "type": "task_created",
                    "task": task
                }

            elif message_type == "execute_task":
                if not message.get("taskId"):
                    raise ValueError("タスクIDが必要です")
                return await self.workflow_manager.execute_task(message["taskId"])

            elif message_type == "execute_all_tasks":
                if not message.get("taskIds"):
                    raise ValueError("タスクIDのリストが必要です")
                # 非同期ジェネレータを返す
                return self.workflow_manager.execute_all_tasks(message["taskIds"])

            elif message_type == "update_task":
                if not message.get("taskId"):
                    raise ValueError("タスクIDが必要です")
                if not message.get("inputs"):
                    raise ValueError("入力値が必要です")
                
                print(f"タスク更新リクエスト - ID: {message['taskId']}, 入力: {message['inputs']}")
                
                try:
                    task_id = int(message["taskId"])
                    inputs = message["inputs"]
                    
                    # タスクの種類を取得して、必須フィールドを決定
                    task = await self.workflow_manager.get_task(task_id)
                    if not task:
                        raise ValueError(f"タスクが見つかりません: {task_id}")
                    
                    # タスクタイプに応じた必須フィールドの検証
                    required_fields = []
                    if task.type == "Create Google Calendar Event":
                        required_fields = ["attendees", "start_time", "end_time", "subject"]
                    elif task.type == "Send Gmail":
                        required_fields = ["to", "subject", "body"]
                    
                    if required_fields:
                        missing_fields = [field for field in required_fields if not inputs.get(field)]
                        if missing_fields:
                            raise ValueError(f"必須フィールドが不足しています: {', '.join(missing_fields)}")
                    
                    result = await self.workflow_manager.update_task(task_id, inputs)
                    print(f"タスク更新結果: {json.dumps(result, ensure_ascii=False)}")
                    
                    return result  # workflow_managerから返される応答をそのまま使用
                    
                except ValueError as e:
                    error_msg = f"タスクの更新に失敗しました: {str(e)}"
                    print(f"値エラー: {error_msg}")
                    return {
                        "type": "error",
                        "message": error_msg
                    }
                except Exception as e:
                    error_msg = f"タスクの更新中に予期せぬエラーが発生しました: {str(e)}"
                    print(f"予期せぬエラー: {error_msg}")
                    return {
                        "type": "error",
                        "message": error_msg
                    }

            elif message_type == "delete_all_tasks":
                return await self.workflow_manager.delete_all_tasks()

            else:
                error_msg = f"不明なメッセージタイプです: {message_type}"
                print(error_msg)
                return {
                    "type": "error",
                    "message": error_msg
                }
                
        except Exception as e:
            error_msg = f"メッセージ処理中の予期せぬエラー: {str(e)}"
            print(error_msg)
            print(f"エラーの詳細: {type(e).__name__}")
            return {
                "type": "error",
                "message": error_msg
            }