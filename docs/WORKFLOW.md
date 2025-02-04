# ワークフロー自動化システム

## 概要

このシステムは、チャットベースのインターフェースを通じてタスクを自動生成し、実行するワークフロー自動化システムです。主な特徴は:

- 自問自答モードによる自動タスク生成
- リアルタイムなワークフロー可視化
- データベースによるタスク管理
- MCPを活用した拡張性

## 主な機能

### 1. 自問自答モード

チャット画面右上のトグルスイッチで有効化できます。有効時の動作:

- タスクの自動生成と保存
- ワークフローの自動更新
- 実行状況のリアルタイム反映

### 2. タスク生成と実行

システムは以下のタイプのタスクを生成・実行できます:

- データ処理タスク
- レポート生成タスク
- 通知タスク
- カスタムタスク(MCPで拡張可能)

### 3. ワークフロー可視化

ReactFlowを使用したインタラクティブなワークフロー表示:

- タスクの依存関係の表示
- 実行状況のリアルタイム更新
- ドラッグ&ドロップによる配置調整

### 4. MCP拡張

Model Context Protocol (MCP)を使用して機能を拡張できます:

1. 新しいツールの追加:
```bash
cd /Users/ohoriryosuke/Documents/Cline/MCP
npx @modelcontextprotocol/create-server your-tool-name
```

2. ツールの実装:
```typescript
@task_function(
    name="your_task",
    description="タスクの説明",
    input_schema={
        "param1": {"type": "string", "description": "パラメータ1"},
        "param2": {"type": "number", "description": "パラメータ2"}
    }
)
async def your_task(self, param1: str, param2: float):
    # タスクの実装
    return {"result": "処理結果"}
```

3. MCPサーバーの設定:
```json
{
  "mcpServers": {
    "your-tool": {
      "command": "python",
      "args": ["-m", "your_module"],
      "cwd": "/path/to/your/tool",
      "env": {},
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
```

## 使用例

1. チャットでタスクを説明:
```
ユーザー: データを処理して、結果をレポートにまとめて、チームに通知してください。
```

2. システムが自動的に:
- タスクを分析
- 実行可能なサブタスクに分解
- 依存関係を特定
- ワークフローを生成

3. 実行と監視:
- ワークフローパネルで進捗を確認
- 必要に応じて手動で介入
- 完了時に通知を受信

## トラブルシューティング

1. タスクが失敗する場合:
- ワークフローパネルでエラーメッセージを確認
- 必要なパラメータが正しく設定されているか確認
- 依存関係に問題がないか確認

2. MCPツールの問題:
- ログを確認
- 環境変数が正しく設定されているか確認
- 必要な権限があるか確認

## 設定

設定ファイルの場所:
- MCP設定: `~/Library/Application Support/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/cline_mcp_settings.json`
- カスタムモード: `~/Library/Application Support/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/cline_custom_modes.json`