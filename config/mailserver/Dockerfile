FROM ubuntu:22.04

# 必要なパッケージをインストール（非対話モードを設定）
ENV DEBIAN_FRONTEND=noninteractive

# タイムゾーンを設定
ENV TZ=Asia/Tokyo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# シグナルハンドリングスクリプトを作成
RUN echo '#!/bin/bash\ntrap "exit 0" SIGTERM SIGINT\ntail -f /dev/null & wait' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

# 必要なパッケージをインストール
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    swaks \
    ca-certificates \
    libnet-ssleay-perl \
    libio-socket-ssl-perl \
    && rm -rf /var/lib/apt/lists/*

# スクリプトをコピー
COPY setup.sh /usr/local/bin/setup.sh
COPY scripts/send_mail.sh /usr/local/bin/send_mail.sh

# 実行権限を設定
RUN chmod 755 /usr/local/bin/setup.sh && \
    chmod 755 /usr/local/bin/send_mail.sh && \
    /usr/local/bin/setup.sh

# 作業ディレクトリを設定
WORKDIR /usr/local/bin

# エントリーポイントを設定
ENTRYPOINT ["/entrypoint.sh"]