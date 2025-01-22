from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
import os
from pathlib import Path
from .workflow_manager import app as workflow_app, workflow_manager

app = FastAPI()

# CORSの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 開発環境用
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# workflow_managerのルートをマウント
app.mount("/api", workflow_app)

# WebSocketエンドポイントを直接このアプリケーションで処理
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket接続が確立されました")

    try:
        while True:
            try:
                data = await websocket.receive_text()
                print(f"受信したメッセージ: {data}")
                
                # workflow_manager のメソッドを直接呼び出し
                import json
                message = json.loads(data)
                
                if message.get("type") == "message":
                    response = await workflow_manager.process_chat_message(message["content"])
                    await websocket.send_json(response)
                
                elif message.get("type") == "create_task":
                    task = await workflow_manager.create_task(message["task"])
                    await websocket.send_json({
                        "type": "task_created",
                        "task": task
                    })
                
                elif message.get("type") == "execute_task":
                    response = await workflow_manager.execute_task(message["taskId"])
                    await websocket.send_json(response)
                
                elif message.get("type") == "execute_all_tasks":
                    async for response in workflow_manager.execute_all_tasks(message["taskIds"]):
                        await websocket.send_json(response)
                
                elif message.get("type") == "delete_all_tasks":
                    response = workflow_manager.delete_all_tasks()
                    await websocket.send_json(response)
                
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "不明なメッセージタイプです"
                    })

            except WebSocketDisconnect:
                print("クライアントが切断されました")
                break
            except Exception as e:
                print(f"WebSocketエラー: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": str(e)
                })
    except Exception as e:
        print(f"WebSocket接続エラー: {e}")
        try:
            await websocket.close()
        except:
            pass

# 開発環境かどうかを判定
is_development = os.getenv("NODE_ENV") == "development"

if is_development:
    # 開発環境では、Viteの開発サーバーにプロキシ
    from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
    import httpx

    @app.get("/{path:path}")
    async def proxy_vite(path: str, request: Request):
        async with httpx.AsyncClient() as client:
            # Vite開発サーバーへプロキシ
            vite_url = f"http://localhost:5173/{path}"
            try:
                response = await client.get(vite_url)
                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
            except httpx.RequestError:
                # Vite開発サーバーに接続できない場合は404を返す
                return Response(status_code=404)
else:
    # 本番環境では、ビルドされた静的ファイルを配信
    static_dir = Path(__file__).parent.parent / "client" / "dist"
    if static_dir.exists() and (static_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")
    
        @app.get("/{path:path}")
        async def serve_static(path: str):
            static_file = static_dir / path
            if not static_file.exists() or static_file.is_dir():
                return FileResponse(str(static_dir / "index.html"))
            return FileResponse(str(static_file))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "5001"))
    
    print(f"Starting server on port {port}...")
    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        reload_dirs=["server"]
    )