import os
import json
import asyncio
import docker
from typing import Dict, Optional, List
from pathlib import Path
from datetime import datetime

class DockerManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DockerManager, cls).__new__(cls)
            cls._instance.client = None
            cls._instance.build_path = None
        return cls._instance

    def __init__(self):
        if self.client is None:
            self.client = docker.from_env()
            self.build_path = Path(__file__).parent / "docker_builds"
            self.build_path.mkdir(exist_ok=True)
            print("DockerManagerが初期化されました")

    def _create_calendar_dockerfile(self, config: Dict) -> str:
        """カレンダー用のDockerfileを生成"""
        return f"""FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \\
    apt-get install -y --no-install-recommends \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV GOOGLE_CLIENT_ID={config['credentials'].get('clientId', '')}
ENV GOOGLE_CLIENT_SECRET={config['credentials'].get('clientSecret', '')}
ENV GOOGLE_REFRESH_TOKEN={config['credentials'].get('refreshToken', '')}

COPY calendar_service.py .
CMD ["python", "calendar_service.py"]
"""

    def _create_calendar_service(self) -> str:
        """カレンダー用のサービスコードを生成"""
        return '''
import os
import json
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def create_calendar_service():
    creds = Credentials.from_authorized_user_info({
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "refresh_token": os.getenv("GOOGLE_REFRESH_TOKEN"),
        "token_uri": "https://oauth2.googleapis.com/token",
    })
    
    return build('calendar', 'v3', credentials=creds)

def create_calendar_event(service, event_data):
    event = {
        'summary': event_data['summary'],
        'description': event_data.get('description', ''),
        'start': {
            'dateTime': event_data['start_time'],
            'timeZone': event_data.get('timezone', 'Asia/Tokyo'),
        },
        'end': {
            'dateTime': event_data['end_time'],
            'timeZone': event_data.get('timezone', 'Asia/Tokyo'),
        },
        'attendees': [{'email': email} for email in event_data.get('attendees', [])],
        'reminders': {
            'useDefault': True
        },
    }

    return service.events().insert(calendarId='primary', body=event, sendUpdates='all').execute()

def main():
    service = create_calendar_service()
    
    while True:
        try:
            input_data = input()
            data = json.loads(input_data)
            
            if data['action'] == 'create_event':
                result = create_calendar_event(service, data['event'])
                print(json.dumps({
                    'success': True,
                    'event_id': result['id'],
                    'html_link': result['htmlLink']
                }))
            else:
                print(json.dumps({
                    'success': False,
                    'error': '不明なアクション'
                }))
                
        except Exception as e:
            print(json.dumps({
                'success': False,
                'error': str(e)
            }))

if __name__ == '__main__':
    main()
'''

    def _create_mail_dockerfile(self, config: Dict) -> str:
        """メール送信用のDockerfileを生成"""
        return f"""FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \\
    apt-get install -y --no-install-recommends \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV MAIL_HOST={config.get('host', 'mail.cafe.local')}
ENV MAIL_PORT={config.get('port', '587')}
ENV MAIL_USERNAME={config.get('username', 'system@cafe.local')}
ENV MAIL_PASSWORD={config.get('password', '')}
ENV MAIL_FROM={config.get('from', 'system@cafe.local')}
ENV MAIL_ENCRYPTION={config.get('encryption', 'tls')}

COPY mail_service.py .
CMD ["python", "mail_service.py"]
"""

    def _create_mail_service(self) -> str:
        """メール送信用のサービスコードを生成"""
        return '''
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate

def create_message(sender, to, subject, message_text):
    message = MIMEMultipart()
    message['To'] = to
    message['From'] = sender
    message['Subject'] = subject
    message['Date'] = formatdate()

    body = MIMEText(message_text)
    message.attach(body)

    return message

def send_mail(message):
    host = os.getenv('MAIL_HOST')
    port = int(os.getenv('MAIL_PORT', '587'))
    username = os.getenv('MAIL_USERNAME')
    password = os.getenv('MAIL_PASSWORD')
    encryption = os.getenv('MAIL_ENCRYPTION', 'tls')

    try:
        if encryption == 'tls':
            server = smtplib.SMTP(host, port)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(host, port)

        server.login(username, password)
        server.send_message(message)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending mail: {str(e)}")
        return False

def main():
    while True:
        try:
            input_data = input()
            data = json.loads(input_data)
            
            message = create_message(
                data.get('sender', os.getenv('MAIL_FROM')),
                data['to'],
                data['subject'],
                data['body']
            )
            
            success = send_mail(message)
            
            print(json.dumps({
                'success': success,
                'error': None if success else 'Failed to send email'
            }))
            
        except Exception as e:
            print(json.dumps({
                'success': False,
                'error': str(e)
            }))

if __name__ == '__main__':
    main()
'''

    async def build_service_image(
        self,
        service: str,
        name: str,
        tag: str,
        config: Dict
    ) -> Dict[str, str]:
        """サービス用のDockerイメージをビルド"""
        build_dir = self.build_path / f"{service}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        build_dir.mkdir(exist_ok=True)

        try:
            if service == "mail":
                # Dockerfile生成
                dockerfile_content = self._create_mail_dockerfile(config)
                (build_dir / "Dockerfile").write_text(dockerfile_content)

                # サービスコード生成
                service_code = self._create_mail_service()
                (build_dir / "mail_service.py").write_text(service_code)

                # requirements.txt生成
                requirements = """
# メール送信に必要な最小限のパッケージ
"""
                (build_dir / "requirements.txt").write_text(requirements)

                # イメージビルド
                image, _ = self.client.images.build(
                    path=str(build_dir),
                    tag=f"{name}:{tag}",
                    rm=True
                )

                return {
                    "status": "success",
                    "message": f"イメージ {name}:{tag} のビルドが完了しました",
                    "image_id": image.id
                }

            elif service == "calendar":
                # Dockerfile生成
                dockerfile_content = self._create_gmail_dockerfile(config)
                (build_dir / "Dockerfile").write_text(dockerfile_content)

                # サービスコード生成
                service_code = self._create_gmail_service()
                (build_dir / "gmail_service.py").write_text(service_code)

                # requirements.txt生成
                requirements = """
google-auth-oauthlib==1.0.0
google-auth-httplib2==0.1.0
google-api-python-client==2.86.0
"""
                (build_dir / "requirements.txt").write_text(requirements)

                # イメージビルド
                image, _ = self.client.images.build(
                    path=str(build_dir),
                    tag=f"{name}:{tag}",
                    rm=True
                )

                return {
                    "status": "success",
                    "message": f"イメージ {name}:{tag} のビルドが完了しました",
                    "image_id": image.id
                }

            else:
                return {
                    "status": "error",
                    "message": f"サービス {service} は未対応です"
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"イメージのビルド中にエラーが発生しました: {str(e)}"
            }

    async def run_service_container(
        self,
        image_name: str,
        tag: str,
        input_data: Dict
    ) -> Dict:
        """サービスコンテナを実行"""
        try:
            # コマンドが指定されている場合は実行
            command = input_data.get("command")
            if command:
                container = self.client.containers.run(
                    f"{image_name}:{tag}",
                    command=command,
                    name=input_data.get("container_name"),
                    network_mode="host",
                    remove=True
                )
                output = container.decode()
            else:
                # 通常のサービス実行
                container = self.client.containers.run(
                    f"{image_name}:{tag}",
                    detach=True,
                    stdin_open=True,
                    environment=input_data.get("env", {}),
                )

                # 入力データを標準入力に送信
                container.exec_run(
                    "python -c \"import json; print(json.dumps({}))\"".format(
                        json.dumps(input_data)
                    )
                )

                # 結果を取得
                output = container.logs().decode()
                container.remove(force=True)

            try:
                result = json.loads(output)
                return {
                    "status": "success",
                    "result": result
                }
            except json.JSONDecodeError:
                return {
                    "status": "error",
                    "message": f"サービスの出力を解析できませんでした: {output}"
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"コンテナの実行中にエラーが発生しました: {str(e)}"
            }

    def list_images(self) -> List[Dict]:
        """ビルド済みのイメージ一覧を取得"""
        try:
            images = self.client.images.list()
            return [
                {
                    "id": image.id,
                    "tags": image.tags,
                    "created": image.attrs["Created"],
                    "size": image.attrs["Size"]
                }
                for image in images
            ]
        except Exception as e:
            return []

    def remove_image(self, image_name: str, tag: str) -> Dict:
        """イメージを削除"""
        try:
            self.client.images.remove(f"{image_name}:{tag}")
            return {
                "status": "success",
                "message": f"イメージ {image_name}:{tag} を削除しました"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"イメージの削除中にエラーが発生しました: {str(e)}"
            }

# シングルトンインスタンスを作成
docker_manager = DockerManager()