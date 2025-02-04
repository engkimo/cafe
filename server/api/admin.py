import os
from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession

# データベースURLを環境変数から取得
db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cafe.db")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{db_path}"
)

# データベースエンジンの設定
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    connect_args={"check_same_thread": False}
)

# セッションファクトリの作成
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

router = APIRouter()

@router.get("/health")
async def health_check():
    try:
        async with async_session() as session:
            # 簡単なクエリを実行してデータベース接続を確認
            await session.execute(select(1))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))