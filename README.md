# Cafe - Composite AI Flow Engine

自律的なAIエージェントによるワークフロー自動化システム

## 特徴

- チャットベースのインターフェース
- 自問自答モードによる自動タスク生成
- リアルタイムなワークフロー可視化
- Semantic Kernelによる高度なタスク実行
- MCPによる拡張性

## アーキテクチャ

### フロントエンド
- React + TypeScript
- ReactFlow (ワークフロー可視化)
- WebSocket (リアルタイム通信)

### バックエンド
- FastAPI
- Semantic Kernel
- SQLAlchemy
- Model Context Protocol (MCP)

## セットアップ

1. 依存関係のインストール:
```bash
# フロントエンド
npm install

# バックエンド
pip install -r requirements.txt
```

2. 環境変数の設定:
```bash
cp .env.example .env
```

必要な環境変数:
- OPENAI_API_KEY: OpenAI APIキー
- DATABASE_URL: データベース接続URL

3. データベースのセットアップ:
```bash
npm run db:generate
npm run db:push
```

4. 開発サーバーの起動:
```bash
# フロントエンド
npm run dev

# バックエンド
python -m server.run
```

## 使い方

1. チャットインターフェース
- タスクを自然言語で説明
- 自問自答モードで自動タスク生成
- リアルタイムなフィードバック

2. ワークフロー管理
- タスクの依存関係を可視化
- ドラッグ&ドロップで配置調整
- 実行状況のリアルタイム更新

3. MCPによる拡張
- カスタムツールの追加
- 外部サービスとの連携
- ワークフローの自動化

## 主要コンポーネント

### PlanEngine
- Semantic Kernelを使用したプラン生成
- スキルの管理と実行
- 実行履歴の管理

### WorkflowServer (MCP)
- ワークフローの状態管理
- リアルタイム更新の配信
- カスタムツールの統合

### BasicTaskModule
- 基本的なタスク機能
- Semantic Kernelスキル
- 拡張可能なモジュール設計

## 開発ガイド

### 新しいタスクの追加

1. スキルの定義:
```python
@sk_function(
    description="タスクの説明",
    name="task_name"
)
@sk_function_context_parameter(
    name="param1",
    description="パラメータ1の説明"
)
async def your_task(self, context: SKContext) -> str:
    # タスクの実装
    return str(result)
```

2. MCPサーバーへの登録:
```python
await mcp_server.register_skill("task_name", your_task)
```

### カスタムツールの追加

1. MCPサーバーの作成:
```bash
cd /Users/ohoriryosuke/Documents/Cline/MCP
npx @modelcontextprotocol/create-server your-tool-name
```

2. ツールの実装:
```typescript
class YourTool {
    @sk_function(...)
    async execute(context: SKContext): Promise<string> {
        // ツールの実装
    }
}
```

3. 設定の追加:
```json
{
  "mcpServers": {
    "your-tool": {
      "command": "python",
      "args": ["-m", "your_module"],
      "env": {},
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
```

## トラブルシューティング

1. タスクが失敗する場合:
- ワークフローパネルでエラーメッセージを確認
- 必要なパラメータが正しく設定されているか確認
- 依存関係に問題がないか確認

2. MCPツールの問題:
- ログを確認
- 環境変数が正しく設定されているか確認
- 必要な権限があるか確認

## ライセンス

MIT License - 詳細は[LICENSE](LICENSE)ファイルを参照してください。
