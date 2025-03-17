import os
import sys
import subprocess
import shutil
import json
import importlib
import venv
from typing import List, Dict, Any, Tuple, Optional
import tempfile
import re

class ProjectEnvironment:
    """
    プロジェクト単位の実行環境を管理するクラス
    各プロジェクトは独自の仮想環境を持ち、必要なパッケージを自動的にインストールする
    """
    def __init__(self, workspace_dir: str, plan_id: str = None):
        """
        Args:
            workspace_dir: ワークスペースのベースディレクトリ
            plan_id: 現在のプランID (Noneの場合はデフォルト環境を使用)
        """
        self.workspace_dir = workspace_dir
        self.plan_id = plan_id
        
        # プロジェクトディレクトリの設定
        if plan_id:
            self.project_dir = os.path.join(workspace_dir, f"project_{plan_id}")
        else:
            self.project_dir = os.path.join(workspace_dir, "default_project")
            
        # 仮想環境のパス
        self.venv_dir = os.path.join(self.project_dir, "venv")
        
        # インストール済みパッケージのリスト
        self.installed_packages = set()
        
        # 自動インストールの設定
        self.auto_install = True
        
        # プロジェクトディレクトリの初期化
        self._init_project_dir()
        
    def _init_project_dir(self):
        """プロジェクトディレクトリを初期化"""
        # プロジェクトディレクトリを作成
        os.makedirs(self.project_dir, exist_ok=True)
        
        # 仮想環境の存在をチェック
        if not os.path.exists(self.venv_dir):
            print(f"Creating virtual environment at {self.venv_dir}...")
            try:
                # 仮想環境を作成
                # uvではなくsysを使ってPythonの直接実行で仮想環境を作成（より確実）
                python_exe = sys.executable
                venv_cmd = [python_exe, "-m", "venv", self.venv_dir]
                result = subprocess.run(venv_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # 仮想環境が正しく作成されたかを確認
                python_paths = [
                    os.path.join(self.venv_dir, "bin", "python3"),
                    os.path.join(self.venv_dir, "bin", "python"),
                ]
                
                python_found = False
                for path in python_paths:
                    if os.path.exists(path):
                        print(f"Created Python virtual environment with interpreter at: {path}")
                        python_found = True
                        break
                
                if not python_found:
                    print("Warning: Python interpreter not found in created venv")
                
                # pip の確認
                pip_paths = [
                    os.path.join(self.venv_dir, "bin", "pip3"),
                    os.path.join(self.venv_dir, "bin", "pip"),
                ]
                
                pip_path = None
                for path in pip_paths:
                    if os.path.exists(path):
                        pip_path = path
                        break
                
                if pip_path:
                    # pip バージョンの確認
                    pip_cmd = [pip_path, "--version"]
                    pip_result = subprocess.run(
                        pip_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    if pip_result.returncode == 0:
                        print(f"Pip version: {pip_result.stdout.strip()}")
                    else:
                        print(f"Pip check failed: {pip_result.stderr}")
                else:
                    # pip がない場合はインストール
                    print("Pip not found. Installing pip...")
                    python_path = python_paths[0] if python_found else sys.executable
                    
                    pip_install_cmd = [python_path, "-m", "ensurepip", "--upgrade"]
                    subprocess.run(pip_install_cmd, check=False)
            
            except Exception as e:
                print(f"Error creating virtual environment: {str(e)}")
                print("Will continue using system Python")

        # フォーマッター（black）をインストール
        try:
            pip_cmd = [self.get_python_path(), "-m", "pip", "install", "black"]
            subprocess.run(
                pip_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            print("Installed black formatter")
        except Exception as e:
            print(f"Could not install black formatter: {str(e)}")

        # インストール済みパッケージリストの読み込み
        packages_file = os.path.join(self.project_dir, "installed_packages.json")
        if os.path.exists(packages_file):
            try:
                with open(packages_file, 'r') as f:
                    self.installed_packages = set(json.load(f))
            except Exception as e:
                print(f"Error loading installed packages: {str(e)}")
                self.installed_packages = set()
        
    def _save_installed_packages(self):
        """インストール済みパッケージリストを保存"""
        packages_file = os.path.join(self.project_dir, "installed_packages.json")
        with open(packages_file, 'w') as f:
            json.dump(list(self.installed_packages), f)
    
    def get_python_path(self) -> str:
        """仮想環境のPythonインタプリタのパスを取得"""
        # 複数のPythonインタープリタの候補を試す
        possible_paths = []
        
        if os.name == 'nt':  # Windows
            possible_paths = [
                os.path.join(self.venv_dir, "Scripts", "python.exe")
            ]
        else:  # Unix/Linux/Mac
            possible_paths = [
                os.path.join(self.venv_dir, "bin", "python"),
                os.path.join(self.venv_dir, "bin", "python3"),
                # Python 3.xの具体的なバージョン
                os.path.join(self.venv_dir, "bin", "python3.9"),
                os.path.join(self.venv_dir, "bin", "python3.10"),
                os.path.join(self.venv_dir, "bin", "python3.11"),
                os.path.join(self.venv_dir, "bin", "python3.12"),
                os.path.join(self.venv_dir, "bin", "python3.13")
            ]
        
        # 最初に見つかった実行可能なPythonを返す
        for path in possible_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path
                
        # 見つからなかった場合は最初のパスを返す（エラーメッセージのため）
        print(f"Warning: Could not find Python interpreter in {self.venv_dir}")
        if possible_paths:
            return possible_paths[0]
        
        # 最悪の場合はシステムのPythonを使用
        return sys.executable
    
    def get_pip_path(self) -> str:
        """仮想環境のpipのパスを取得"""
        # 複数のPipコマンドの候補を試す
        possible_paths = []
        
        if os.name == 'nt':  # Windows
            possible_paths = [
                os.path.join(self.venv_dir, "Scripts", "pip.exe"),
                os.path.join(self.venv_dir, "Scripts", "pip3.exe")
            ]
        else:  # Unix/Linux/Mac
            possible_paths = [
                os.path.join(self.venv_dir, "bin", "pip"),
                os.path.join(self.venv_dir, "bin", "pip3")
            ]
        
        # 最初に見つかった実行可能なPipを返す
        for path in possible_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                return path
        
        # 見つからなかった場合は、Pythonの-m pipを使うパスを返す
        python_path = self.get_python_path()
        return f"{python_path} -m pip"
    
    def is_package_installed(self, package_name: str) -> bool:
        """パッケージがインストール済みかチェック"""
        # キャッシュから確認
        if package_name in self.installed_packages:
            return True
            
        # 実際にインポートを試みて確認
        cmd = [self.get_python_path(), "-c", f"import {package_name}"]
        try:
            result = subprocess.run(cmd, 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   text=True)
            return result.returncode == 0
        except Exception:
            return False
    
    def install_package(self, package_name: str) -> bool:
        """パッケージをインストール"""
        # 既にインストール済みの場合はスキップ
        if self.is_package_installed(package_name):
            return True
                
        print(f"Installing package '{package_name}' in project environment...")
        
        # 複数の方法でインストールを試行
        methods = [
            # 方法1: 仮想環境のpipを使用
            lambda: self._install_with_venv_pip(package_name),
            # 方法2: システムのPythonでpipを使用
            lambda: self._install_with_system_python(package_name),
            # 方法3: コマンドとして直接実行
            lambda: self._install_with_direct_command(package_name)
        ]
        
        for i, method in enumerate(methods):
            try:
                success = method()
                if success:
                    # インストール済みリストに追加
                    self.installed_packages.add(package_name)
                    self._save_installed_packages()
                    return True
            except Exception as e:
                print(f"Method {i+1} failed: {str(e)}")
        
        print(f"Failed to install {package_name} with all methods")
        return False

    def _install_with_venv_pip(self, package_name: str) -> bool:
        """仮想環境のpipを使用してインストール"""
        pip_paths = [
            os.path.join(self.venv_dir, "bin", "pip3"),
            os.path.join(self.venv_dir, "bin", "pip")
        ]
        
        for pip_path in pip_paths:
            if os.path.exists(pip_path):
                cmd = [pip_path, "install", package_name]
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                return result.returncode == 0
        
        return False

    def _install_with_system_python(self, package_name: str) -> bool:
        """システムのPythonを使用してインストール"""
        python_exe = sys.executable
        cmd = [python_exe, "-m", "pip", "install", "--target", 
            os.path.join(self.venv_dir, "lib", "python3.13", "site-packages"), 
            package_name]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.returncode == 0

    def _install_with_direct_command(self, package_name: str) -> bool:
        """直接コマンドを実行してインストール"""
        cmd = f"pip install --target {os.path.join(self.venv_dir, 'lib', 'python3.13', 'site-packages')} {package_name}"
        result = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.returncode == 0
    
    def install_requirements(self, requirements: List[str]) -> bool:
        """複数パッケージをインストール"""
        all_success = True
        
        for package in requirements:
            if not self.install_package(package):
                all_success = False
                
        return all_success
    
    def execute_script(self, script_path: str, args: List[str] = None) -> Tuple[bool, str, str]:
        """
        指定されたスクリプトをプロジェクト環境で実行
        
        Args:
            script_path: 実行するスクリプトのパス
            args: コマンドライン引数
                
        Returns:
            (成功したか, 標準出力, 標準エラー出力)
        """
        # まず直接絶対パスを使用
        python_path = os.path.abspath(os.path.join(self.venv_dir, "bin", "python3"))
        
        # Python3が見つからない場合はpythonを試す
        if not os.path.exists(python_path):
            python_path = os.path.abspath(os.path.join(self.venv_dir, "bin", "python"))
        
        # それでも見つからない場合はシステムのPythonを使用
        if not os.path.exists(python_path):
            print(f"Warning: Python not found in venv at {python_path}, using system Python")
            python_path = sys.executable
        
        # コマンドを構築
        cmd = [python_path, os.path.abspath(script_path)]
        if args:
            cmd.extend(args)
            
        try:
            print(f"Executing: {' '.join(cmd)}")
            
            # サブプロセスとしてスクリプトを実行 (-u オプションでバッファリングを無効化)
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.project_dir,
                bufsize=1
            )
            
            # 出力を読み取る
            stdout, stderr = process.communicate()
            
            success = process.returncode == 0
            return success, stdout, stderr
        except Exception as e:
            error_message = str(e)
            print(f"Error executing script: {error_message}")
            
            # 代替手段：システムのPythonで直接モジュールとして実行
            if "No such file or directory" in error_message:
                try:
                    print(f"Trying fallback: direct execution with system Python")
                    # スクリプト内容を取得
                    with open(script_path, 'r') as f:
                        script_content = f.read()
                    
                    # システムのPythonで直接実行
                    cmd = [sys.executable, "-c", script_content]
                    
                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=self.project_dir
                    )
                    
                    return result.returncode == 0, result.stdout, result.stderr
                except Exception as e2:
                    print(f"Fallback also failed: {str(e2)}")
                    return False, "", f"{error_message}\nFallback error: {str(e2)}"
            
            return False, "", error_message
    
    def execute_code(self, code: str, dependencies: List[str] = None) -> Tuple[bool, Any, str]:
        """
        Pythonコードを実行し、結果を返す
        
        Args:
            code: 実行するPythonコード
            dependencies: 必要な依存パッケージのリスト
            
        Returns:
            (成功したか, 実行結果, エラーメッセージ)
        """
        # 依存パッケージがある場合はインストール
        if dependencies and self.auto_install:
            self.install_requirements(dependencies)
        
        # 一時スクリプトファイルを作成
        script_file = os.path.join(self.project_dir, "temp_script.py")
        with open(script_file, 'w') as f:
            f.write(code)
        
        # スクリプトを実行
        success, stdout, stderr = self.execute_script(script_file)
        
        # 成功した場合は結果を解析
        result = None
        if success:
            # 最後に標準出力された行をresultとして解釈
            if stdout.strip():
                try:
                    result = eval(stdout.strip().split('\n')[-1])
                except:
                    result = stdout.strip()
            else:
                result = None
                
        # 一時ファイルを削除
        try:
            os.remove(script_file)
        except:
            pass
            
        return success, result, stderr
    
    def extract_missing_packages(self, error_message: str) -> List[str]:
        """
        エラーメッセージから不足しているパッケージを検出
        
        Args:
            error_message: エラーメッセージ
            
        Returns:
            不足しているパッケージのリスト
        """
        missing_packages = []
        
        # 'No module named' パターンを検索
        no_module_pattern = r"No module named '([^']+)'"
        matches = re.findall(no_module_pattern, error_message)
        
        for match in matches:
            # モジュール名を正規化（ドットで区切られたものの最初の部分を取得）
            package = match.split('.')[0]
            
            # bs4 -> beautifulsoup4 などの変換
            if package == "bs4":
                package = "beautifulsoup4"
                
            # 標準ライブラリでない場合のみ追加
            if not self._is_stdlib_module(package):
                missing_packages.append(package)
                
        return missing_packages
    
    def _is_stdlib_module(self, module_name: str) -> bool:
        """モジュールが標準ライブラリかどうかを判定"""
        # 一般的な標準ライブラリ
        stdlib_modules = {
            "os", "sys", "math", "random", "datetime", "time", "json", 
            "csv", "re", "collections", "itertools", "functools", "io",
            "pathlib", "shutil", "glob", "argparse", "logging", "unittest",
            "threading", "multiprocessing", "subprocess", "socket", "email",
            "smtplib", "urllib", "http", "xml", "html", "tkinter", "sqlite3",
            "hashlib", "uuid", "tempfile", "copy", "traceback", "gc", "inspect",
            "warnings", "exceptions", "error", "errors", "exception", "warning"
        }
        
        return module_name in stdlib_modules
    
    def execute_with_auto_dependency_resolution(self, code: str, max_attempts: int = 3) -> Tuple[bool, Any, str]:
        """
        コードを実行し、依存関係エラーが発生した場合は自動的に解決
        
        Args:
            code: 実行するPythonコード
            max_attempts: 最大試行回数
            
        Returns:
            (成功したか, 実行結果, エラーメッセージ)
        """
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            
            # コードを実行
            success, result, error = self.execute_code(code)
            
            # 成功したら結果を返す
            if success:
                return True, result, ""
                
            # エラーから不足パッケージを検出
            missing_packages = self.extract_missing_packages(error)
            
            # 不足パッケージがない場合は他のエラー
            if not missing_packages:
                return False, None, error
                
            print(f"Detected missing packages: {', '.join(missing_packages)}")
            
            # パッケージをインストール
            all_installed = self.install_requirements(missing_packages)
            
            # すべてのパッケージをインストールできなかった場合
            if not all_installed:
                print("Could not install all required packages")
                if attempt == max_attempts:
                    return False, None, f"Failed to install required packages: {', '.join(missing_packages)}"
        
        # 最大試行回数に達した場合
        return False, None, "Max attempts reached without success"
    
    def update_requirements_file(self):
        """requirements.txtファイルを作成・更新"""
        requirements_file = os.path.join(self.project_dir, "requirements.txt")
        with open(requirements_file, 'w') as f:
            for package in sorted(self.installed_packages):
                f.write(f"{package}\n")
        
        print(f"Updated requirements file: {requirements_file}")
    
    def get_script_path(self, script_name: str) -> str:
        """プロジェクト内のスクリプトパスを取得"""
        return os.path.join(self.project_dir, script_name)
    
    def save_script(self, script_name: str, code: str) -> str:
        """スクリプトをプロジェクトディレクトリに保存し、必要に応じてフォーマット"""
        script_path = self.get_script_path(script_name)
        
        # コードのフォーマット
        formatted_code = self._format_python_code(code)
        
        with open(script_path, 'w') as f:
            f.write(formatted_code)
        
        return script_path

    def _format_python_code(self, code: str) -> str:
        """既存のフォーマッターを使用してPythonコードをフォーマット"""
        try:
            # タスク情報コードとメインコードを分離（タスク情報は保持）
            task_info_pattern = r'task_info\s*=\s*\{[^}]*\}'
            task_info_match = re.search(task_info_pattern, code)
            task_info_code = task_info_match.group(0) if task_info_match else None
            
            # プレースホルダーの置換（先に行う）
            code = code.replace("{imports}", "# Imports")
            code = code.replace("{main_code}", "# Main code")
            
            # 一時ファイルにコードを書き込む
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.py', delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(code)
            
            # Blackでフォーマット
            try:
                # blackコマンドを実行
                result = subprocess.run(
                    [self.get_python_path(), "-m", "black", "-q", temp_path],
                    check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True
                )
                
                if result.returncode == 0:
                    print("Successfully formatted code with black")
                else:
                    print(f"Black formatter warning: {result.stderr}")
                    
                    # Blackが失敗した場合、インデントの基本的な修正を試みる
                    lines = code.splitlines()
                    fixed_lines = []
                    indent_level = 0
                    
                    for line in lines:
                        stripped = line.strip()
                        if not stripped:  # 空行
                            fixed_lines.append("")
                            continue
                            
                        # ブロック開始の検出
                        if stripped.endswith(':'):
                            fixed_lines.append('    ' * indent_level + stripped)
                            indent_level += 1
                        # ブロック終了の可能性（行頭がキーワードで始まる場合）
                        elif any(stripped.startswith(kw) for kw in ['def ', 'class ', 'if ', 'else:', 'elif ', 'for ', 'while ', 'try:', 'except ', 'finally:', 'with ']):
                            if indent_level > 0 and not stripped.startswith('    '):
                                indent_level -= 1
                            fixed_lines.append('    ' * indent_level + stripped)
                        else:
                            fixed_lines.append('    ' * indent_level + stripped)
                    
                    # 修正したコードを書き込む
                    with open(temp_path, 'w') as f:
                        f.write('\n'.join(fixed_lines))
            except Exception as e:
                print(f"Error using black formatter: {str(e)}")
            
            # フォーマットされたコードを読み込む
            with open(temp_path, 'r') as f:
                formatted_code = f.read()
            
            # 一時ファイルを削除
            os.unlink(temp_path)
            
            # タスク情報コードが保持されているか確認
            if task_info_code and task_info_code not in formatted_code:
                # タスク情報が消えてしまった場合は先頭に追加
                formatted_code = task_info_code + "\n\n" + formatted_code
            
            return formatted_code
        except Exception as e:
            print(f"Error formatting code: {str(e)}")
            # エラーが発生した場合は元のコードを返す（プレースホルダーだけ置換）
            return code.replace("{imports}", "# Imports").replace("{main_code}", "# Main code")