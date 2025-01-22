import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# .envファイルを読み込む
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '.env')
load_dotenv(env_path)

from .core.workflow_manager import WorkflowManager
from .api.websocket_handler import WebSocketHandler

# FastAPIアプリケーションの初期化
app = FastAPI()

# CORSミドルウェアの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ワークフローマネージャーとWebSocketハンドラーの初期化
workflow_manager = WorkflowManager()
websocket_handler = WebSocketHandler(workflow_manager)

# WebSocketエンドポイント
@app.websocket("/ws")
async def websocket_endpoint(websocket):
    await websocket_handler.handle_connection(websocket)

if __name__ == "__main__":
    import uvicorn
    import sys

    try:
        print("Starting FastAPI server...")
        uvicorn.run(
            "workflow_manager:app",
            host="0.0.0.0",
            port=8000,
            log_level="info",
            reload=True
        )
    except Exception as e:
        print(f"Failed to start FastAPI server: {e}", file=sys.stderr)
        sys.exit(1)