import json
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Any, AsyncGenerator
from datetime import datetime
import semantic_kernel as sk

from ..core.workflow_manager import WorkflowManager

class WebSocketHandler:
    def __init__(self, workflow_manager: WorkflowManager, plan_executor, mcp_server):
        self.workflow_manager = workflow_manager
        self.plan_executor = plan_executor
        self.mcp_server = mcp_server
        self.active_connections: Dict[str, WebSocket] = {}
        print("WebSocketハンドラーが初期化されました")

    async def broadcast(self, message: Dict[str, Any]):
        """全ての接続中のクライアントにメッセージをブロードキャスト"""
        for connection in self.active_connections.values():
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"ブロードキャスト中のエラー: {str(e)}")

    async def notify_workflow_update(self, update: Dict[str, Any]):
        """ワークフローの更新をクライアントに通知"""
        await self.broadcast({
            "type": "workflow_update",
            "update": update,
            "timestamp": datetime.now().isoformat()
        })

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
                        
                        # ワークフロー更新の通知
                        if response.get("type") in ["task_created", "task_updated", "plan_created"]:
                            await self.notify_workflow_update(response)
                            
                    elif isinstance(response, AsyncGenerator):
                        async for task_response in response:
                            print(f"タスク実行結果: {json.dumps(task_response, ensure_ascii=False)}")
                            await websocket.send_json(task_response)
                            
                            # 実行状況の更新を通知
                            await self.notify_workflow_update({
                                "type": "task_progress",
                                "task": task_response
                            })

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
                return self.workflow_manager.execute_all_tasks(message["taskIds"])

            elif message_type == "update_task":
                if not message.get("taskId") or not message.get("inputs"):
                    raise ValueError("タスクIDと入力値が必要です")
                
                task_id = int(message["taskId"])
                inputs = message["inputs"]
                task = await self.workflow_manager.get_task(task_id)
                
                if not task:
                    raise ValueError(f"タスクが見つかりません: {task_id}")
                
                # Semantic Kernelのコンテキストを作成
                context = self.plan_executor.kernel.create_new_context()
                for key, value in inputs.items():
                    context[key] = str(value)
                
                # タスクを実行
                result = await self.workflow_manager.update_task(task_id, inputs)
                
                # MCPサーバーに更新を通知
                await self.mcp_server.notify_task_progress({
                    "task_id": task_id,
                    "status": "updated",
                    "inputs": inputs,
                    "result": result
                })
                
                return {
                    "type": "task_updated",
                    "task": result
                }

            elif message_type == "delete_all_tasks":
                return await self.workflow_manager.delete_all_tasks()

            elif message_type == "set_auto_save":
                if "enabled" not in message:
                    raise ValueError("enabled パラメータが必要です")
                self.plan_executor.set_auto_save_mode(message["enabled"])
                await self.mcp_server._handle_update_workflow({
                    "workflow_id": "current",
                    "tasks": [],
                    "auto_save": message["enabled"]
                })
                return {
                    "type": "auto_save_updated",
                    "enabled": message["enabled"]
                }

            elif message_type == "create_plan":
                if not message.get("description"):
                    raise ValueError("タスクの説明が必要です")
                    
                # Semantic Kernelを使用してプランを生成
                context = self.plan_executor.kernel.create_new_context()
                context["description"] = message["description"]
                
                tasks = await self.plan_executor.create_plan(message["description"])
                
                # MCPサーバーに新しいプランを通知
                await self.mcp_server._handle_update_workflow({
                    "workflow_id": "current",
                    "tasks": [task.dict() for task in tasks],
                    "auto_save": self.plan_executor.auto_save_mode
                })
                
                return {
                    "type": "plan_created",
                    "tasks": [task.dict() for task in tasks]
                }

            elif message_type == "execute_plan":
                if not message.get("tasks"):
                    raise ValueError("タスクリストが必要です")
                    
                # プランの実行を開始
                execution_result = await self.plan_executor.execute_plan(message["tasks"])
                
                # 実行結果をMCPサーバーに通知
                await self.mcp_server.notify_task_progress({
                    "type": "plan_execution",
                    "status": execution_result["status"],
                    "results": execution_result["results"]
                })
                
                return {
                    "type": "plan_executed",
                    "result": execution_result
                }

            elif message_type == "get_workflow_status":
                if not message.get("workflow_id"):
                    raise ValueError("workflow_id が必要です")
                status = await self.mcp_server._handle_get_workflow_status({
                    "workflow_id": message["workflow_id"]
                })
                return {
                    "type": "workflow_status",
                    "status": status
                }

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