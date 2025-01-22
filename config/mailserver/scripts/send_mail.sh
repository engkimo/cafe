#!/bin/bash

# エラーハンドリングの設定
set -e

# 終了時の処理
cleanup() {
    exit_code=$?
    echo "Script exiting with code: $exit_code"
    exit $exit_code
}
trap cleanup EXIT

# デバッグ出力の有効化
set -x

# 引数のバリデーション
if [ "$#" -ne 4 ]; then
    echo "Error: Invalid number of arguments"
    echo "Usage: $0 TO SUBJECT BODY FROM"
    exit 1
fi

# メール送信スクリプト
TO="$1"
SUBJECT="$2"
BODY="$3"
FROM="$4"

# 環境変数からの読み込み
SMTP_USER=${RELAY_USER:-"ryosuke.ohori@ulusage.com"}
SMTP_PASS=${RELAY_PASSWORD:-"nfbt qhrk ccih mbdw"}
SMTP_SERVER=${RELAY_HOST:-"smtp.gmail.com"}
SMTP_PORT=${RELAY_PORT:-"587"}

echo "Sending email to: $TO"
echo "From: $FROM"
echo "Subject: $SUBJECT"
echo "Server: $SMTP_SERVER:$SMTP_PORT"

# メール送信の実行
swaks --to "$TO" \
      --from "$FROM" \
      --server "$SMTP_SERVER:$SMTP_PORT" \
      --tls \
      --auth-user "$SMTP_USER" \
      --auth-password "$SMTP_PASS" \
      --header "Subject: $SUBJECT" \
      --body "$BODY" \
      --h-From: "$FROM" \
      --h-Content-Type: "text/plain; charset=UTF-8" \
      --timeout 30

status=$?
if [ $status -ne 0 ]; then
    echo "Error: Failed to send email (exit code: $status)"
    exit $status
fi

echo "Email sent successfully"