from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import os
import httpx
from dotenv import load_dotenv
from pathlib import Path
from contextlib import asynccontextmanager
from openai import AsyncOpenAI

from .core.workflow_manager import WorkflowManager
from .core.plan_executor import PlanExecutor
from .core.mcp.workflow_server import WorkflowServer
from .core.modules.basic_tasks import BasicTaskModule
from .api.websocket_handler import WebSocketHandler

# .envファイルを読み込む
current_dir = Path(__file__).parent.parent  # プロジェクトのルートディレクトリ
env_path = current_dir / '.env'
load_dotenv(env_path)

# OpenAI APIキーの確認
openai_api_key = os.getenv('OPENAI_API_KEY')
if not openai_api_key:
    raise ValueError("OPENAI_API_KEYが環境変数に設定されていません。.envファイルを確認してください。")
print(f"OpenAI APIキーが設定されています: {openai_api_key[:8]}...")

# グローバル変数
workflow_manager = None
websocket_handler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時の処理
    global workflow_manager, websocket_handler
    
    # OpenAI クライアントの初期化
    openai_client = AsyncOpenAI(api_key=openai_api_key)
    
    # WorkflowManager の初期化
    workflow_manager = WorkflowManager()
    
    # PlanExecutor の初期化
    modules = [BasicTaskModule()]
    plan_executor = PlanExecutor(
        task_executor=workflow_manager.task_executor,
        task_repository=workflow_manager.task_repository,
        modules=modules
    )
    
    # MCP WorkflowServer の初期化
    mcp_server = WorkflowServer()
    await mcp_server.run()
    
    # WebSocketHandler の初期化
    websocket_handler = WebSocketHandler(
        workflow_manager=workflow_manager,
        plan_executor=plan_executor,
        mcp_server=mcp_server
    )
    
    print("全てのコンポーネントが初期化されました")
    yield
    
    # シャットダウン時の処理
    if websocket_handler:
        for ws in websocket_handler.active_connections.values():
            try:
                await ws.close()
            except:
                pass
    
    # MCP サーバーのクリーンアップ
    if mcp_server:
        try:
            await mcp_server.server.close()
        except:
            pass

app = FastAPI(lifespan=lifespan)

# CORSの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 開発環境では全てのオリジンを許可
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocketエンドポイント
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print("新しいWebSocket接続リクエストを受信しました")
    try:
        await websocket_handler.handle_connection(websocket)
    except Exception as e:
        print(f"WebSocketエンドポイントでエラーが発生: {str(e)}")
        import traceback
        print(f"エラーのトレースバック:\n{traceback.format_exc()}")
        try:
            await websocket.close()
        except:
            pass

# Vite開発サーバーへのプロキシエンドポイント
@app.get("/{path:path}")
async def proxy_vite(path: str, request: Request):
    async with httpx.AsyncClient() as client:
        vite_url = f"http://localhost:5173/{path}"
        try:
            response = await client.get(vite_url)
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
        except httpx.RequestError:
            return Response(status_code=404)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "5001"))
    
    print(f"Starting server on port {port}...")
    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        reload_dirs=["server"],
        log_level="debug"  # デバッグログを有効化
    )