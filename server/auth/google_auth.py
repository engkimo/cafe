import os
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import webbrowser

class GoogleAuthManager:
    def __init__(self):
        self.calendar_service = None
        self._initialize_calendar_service()

    def _initialize_calendar_service(self):
        """Google Calendar APIクライアントの初期化"""
        try:
            SCOPES = ['https://www.googleapis.com/auth/calendar']
            creds = None

            # トークンファイルが存在する場合は読み込む
            token_path = 'token.pickle'
            if os.path.exists(token_path):
                with open(token_path, 'rb') as token:
                    creds = pickle.load(token)

            # 認証情報が無効または存在しない場合は新規取得
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    client_id = os.getenv('GMAIL_CLIENT_ID')
                    client_secret = os.getenv('GMAIL_CLIENT_SECRET')
                    if not client_id or not client_secret:
                        raise ValueError("GMAIL_CLIENT_ID または GMAIL_CLIENT_SECRET が設定されていません")
                    
                    flow = InstalledAppFlow.from_client_config(
                        {
                            "installed": {
                                "client_id": client_id,
                                "client_secret": client_secret,
                                "redirect_uris": ["http://localhost:8080/"],
                                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                "token_uri": "https://oauth2.googleapis.com/token"
                            }
                        },
                        SCOPES
                    )
                    # ローカルサーバーを起動して認証を行う
                    creds = flow.run_local_server(port=8080)

                # 認証情報を保存
                with open(token_path, 'wb') as token:
                    pickle.dump(creds, token)

            self.calendar_service = build('calendar', 'v3', credentials=creds)
            print("Google Calendar APIクライアントの初期化が完了しました")
        except Exception as e:
            print(f"Google Calendar APIクライアントの初期化エラー: {e}")
            self.calendar_service = None

    def get_calendar_service(self):
        """Google Calendar APIサービスを取得"""
        if not self.calendar_service:
            raise ValueError("Google Calendar APIが初期化されていません")
        return self.calendar_service

    def create_calendar_event(self, event_data):
        """カレンダーイベントを作成"""
        if not self.calendar_service:
            raise ValueError("Google Calendar APIが初期化されていません")

        try:
            created_event = self.calendar_service.events().insert(
                calendarId='primary',
                body=event_data,
                sendUpdates='all'
            ).execute()

            return {
                'event_id': created_event['id'],
                'event_link': created_event['htmlLink']
            }
        except Exception as e:
            raise Exception(f"カレンダーイベントの作成エラー: {str(e)}")