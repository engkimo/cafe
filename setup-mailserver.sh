#!/bin/bash

# 必要なディレクトリの作成
mkdir -p config/mailserver/{postfix-accounts.cf,postfix-relaymap.cf}

# メールアカウントの作成
# パスワードはハッシュ化して保存（docker-mailserver-passwordコマンドを使用）
docker run --rm \
  docker.io/mailserver/docker-mailserver:latest \
  setup email add system@superaiflow.local password123

# Gmailリレー設定の確認
if [ -z "$GMAIL_USER" ] || [ -z "$GMAIL_APP_PASSWORD" ]; then
  echo "エラー: GMAIL_USER と GMAIL_APP_PASSWORD を環境変数に設定してください"
  exit 1
fi

# TLS設定の追加
cat > config/mailserver/postfix-main.cf << EOF
# TLS設定
smtp_tls_security_level = encrypt
smtp_sasl_auth_enable = yes
smtp_sasl_password_maps = texthash:/etc/postfix/sasl_passwd
smtp_sasl_security_options = noanonymous
smtp_sasl_tls_security_options = noanonymous
EOF

# SASL認証情報の設定
cat > config/mailserver/postfix-sasl-password.cf << EOF
[smtp.gmail.com]:587 ${GMAIL_USER}:${GMAIL_APP_PASSWORD}
EOF

echo "メールサーバーのセットアップが完了しました"
echo "以下のコマンドでメールサーバーを起動してください："
echo "docker-compose up -d mailserver"
echo ""
echo "Gmailアプリパスワードの取得方法："
echo "1. Googleアカウントにアクセス: https://myaccount.google.com"
echo "2. セキュリティ > 2段階認証プロセス を有効化"
echo "3. アプリパスワード を生成"
echo "4. 生成されたパスワードを GMAIL_APP_PASSWORD 環境変数に設定"