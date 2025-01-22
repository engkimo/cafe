#!/bin/bash
set -e

# 基本的なディレクトリ作成
mkdir -p /var/spool/postfix
chmod 755 /var/spool/postfix

# swaksの実行権限確認
which swaks || (echo "Error: swaks is not installed" && exit 1)
chmod +x /usr/local/bin/send_mail.sh

# 実行確認用のメッセージ
echo "Setup completed successfully"
exit 0