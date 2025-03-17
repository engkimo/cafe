# core/script_templates.py
"""
Pythonスクリプトのテンプレートを提供するモジュール
"""

# 依存関係を適切に処理するスクリプトテンプレート
DEPENDENCY_AWARE_TEMPLATE = """
# 必要なライブラリのインポート
{imports}

def main():
    try:
        # メイン処理
{main_code}
        
    except ImportError as e:
        # 必要なパッケージがない場合のエラー処理
        missing_module = str(e).split("'")[1] if "'" in str(e) else str(e)
        result = f"エラー: 必要なモジュール '{missing_module}' がインストールされていません。"
        print(result)
        print(f"次のコマンドでインストールしてください: pip install {missing_module}")
        return result
        
    except Exception as e:
        # その他のエラー処理
        import traceback
        error_details = traceback.format_exc()
        result = f"エラー: {{str(e)}}"
        print(result)
        print(error_details)
        return result

# スクリプト実行
if __name__ == "__main__":
    result = main()
"""

# データ分析用スクリプトテンプレート
DATA_ANALYSIS_TEMPLATE = """
# 必要なライブラリのインポート
try:
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    from datetime import datetime, timedelta
    import os
    import json
    import csv
except ImportError as e:
    missing_module = str(e).split("'")[1] if "'" in str(e) else str(e)
    result = f"エラー: 必要なモジュール '{missing_module}' がインストールされていません。"
    print(result)
    if missing_module == "pandas":
        print("pandasをインストールするには: pip install pandas")
    elif missing_module == "numpy":
        print("numpyをインストールするには: pip install numpy")
    elif missing_module == "matplotlib":
        print("matplotlibをインストールするには: pip install matplotlib")
    else:
        print(f"次のコマンドでインストールしてください: pip install {missing_module}")
    # 実行を終了
    raise

def main():
    try:
        # メイン処理
{main_code}
        
    except Exception as e:
        # エラー処理
        import traceback
        error_details = traceback.format_exc()
        result = f"エラー: {{str(e)}}"
        print(result)
        print(error_details)
        return result

# スクリプト実行
result = main()
"""

# Webスクレイピング用スクリプトテンプレート
WEB_SCRAPING_TEMPLATE = """
# 必要なライブラリのインポート
try:
    import requests
    from bs4 import BeautifulSoup
    import re
    import json
    import os
except ImportError as e:
    missing_module = str(e).split("'")[1] if "'" in str(e) else str(e)
    result = f"エラー: 必要なモジュール '{missing_module}' がインストールされていません。"
    print(result)
    if missing_module == "bs4":
        print("BeautifulSoup4をインストールするには: pip install beautifulsoup4")
    elif missing_module == "requests":
        print("requestsをインストールするには: pip install requests")
    else:
        print(f"次のコマンドでインストールしてください: pip install {missing_module}")
    # 実行を終了
    raise

def main():
    try:
        # メイン処理
{main_code}
        
    except Exception as e:
        # エラー処理
        import traceback
        error_details = traceback.format_exc()
        result = f"エラー: {{str(e)}}"
        print(result)
        print(error_details)
        return result

# スクリプト実行
result = main()
"""

def get_template_for_task(task_description, required_libraries=None):
    """
    タスクの説明に基づいて適切なテンプレートを選択
    
    Args:
        task_description (str): タスクの説明
        required_libraries (list, optional): 必要なライブラリのリスト
        
    Returns:
        str: 適切なテンプレート
    """
    # タスクの説明を小文字に変換
    task_lower = task_description.lower()
    
    # データ分析関連のキーワード
    data_analysis_keywords = [
        'csv', 'pandas', 'numpy', 'データ分析', 'データ処理', 'グラフ', 'matplotlib',
        'statistics', '統計', 'データフレーム', 'dataframe', '計算', 'calculate'
    ]
    
    # Webスクレイピング関連のキーワード
    web_scraping_keywords = [
        'web', 'スクレイピング', 'scraping', 'html', 'requests', 'beautifulsoup',
        'bs4', 'ウェブ', 'サイト', 'site', 'url', 'http'
    ]
    
    # キーワードに基づいてテンプレートを選択
    template = None
    if any(keyword in task_lower for keyword in data_analysis_keywords):
        template = DATA_ANALYSIS_TEMPLATE
    elif any(keyword in task_lower for keyword in web_scraping_keywords):
        template = WEB_SCRAPING_TEMPLATE
    else:
        template = DEPENDENCY_AWARE_TEMPLATE
    
    # テンプレート内のプレースホルダーを検証
    import re
    placeholders = re.findall(r'{([^{}]*)}', template)
    
    # 基本的なプレースホルダー
    required_placeholders = {"imports", "main_code"}
    
    # 不明なプレースホルダーがある場合は修正
    if set(placeholders) - required_placeholders:
        print(f"Warning: Template has unknown placeholders. Using basic template.")
        # 基本テンプレートを使用（インデントに注意）
        template = """
# 必要なライブラリのインポート
{imports}

def main():
    try:
        # メイン処理
{main_code}
    except Exception as e:
        print(f"Error: {{str(e)}}")
        return str(e)
    
    return "Task completed successfully"

# スクリプト実行
if __name__ == "__main__":
    result = main()
"""
    
    # 念のため、テンプレート内の中括弧をエスケープ（f文字列内の中括弧のみ）
    template = re.sub(r'f"([^"]*){([^{}]*)}([^"]*)"', r'f"\1{{\2}}\3"', template)
    template = re.sub(r"f'([^']*){([^{}]*)}([^']*)'", r"f'\1{{\2}}\3'", template)
    
    return template