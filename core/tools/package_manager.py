import subprocess
import sys
import os
import shutil
import importlib
import pkg_resources
from typing import List, Dict, Any, Tuple, Set
import re
import time

from .base_tool import BaseTool, ToolResult

class PackageManagerTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="package_manager",
            description="Install, update, or check Python packages"
        )
        self.parameters = {
            "command": {
                "type": "string",
                "enum": ["install", "check", "list", "find_dependencies"]
            },
            "package": {"type": "string"},
            "version": {"type": "string"},
            "code": {"type": "string"}
        }
        
        # 利用可能なインストーラーを検索
        self.installers = self._find_installers()
        self.preferred_installer = self._select_preferred_installer()
        
        # インストール試行回数を制限する
        self.install_attempts = {}
        self.max_attempts = 2
        
        # 一般的な依存関係のマッピング
        self.common_dependencies = {
            "pandas": ["numpy"],
            "matplotlib": ["numpy"],
            "seaborn": ["matplotlib", "pandas"],
            "scikit-learn": ["numpy", "scipy"],
            "bs4": ["beautifulsoup4"],
            "beautifulsoup4": [],
            "requests": [],
            "flask": [],
            "django": [],
            "tensorflow": ["numpy"],
            "torch": ["numpy"],
            "nltk": [],
            "openpyxl": [],
        }
        
        # 標準的なインストール方法が失敗した場合に使うフォールバックコマンド
        self.fallback_commands = [
            # フォールバック1: システムのpip
            lambda pkg: ["pip", "install", pkg],
            # フォールバック2: pipのフルパス
            lambda pkg: [shutil.which("pip"), "install", pkg] if shutil.which("pip") else None,
            # フォールバック3: uvのpipコマンド
            lambda pkg: [shutil.which("uv"), "pip", "install", pkg] if shutil.which("uv") else None,
            # フォールバック4: pythonの-m pip
            lambda pkg: [sys.executable, "-m", "pip", "install", pkg],
        ]
        
    def _find_installers(self) -> List[Dict[str, Any]]:
        """利用可能なすべてのパッケージインストーラーを検索"""
        installers = []
        
        # 1. uvコマンドをチェック
        uv_path = shutil.which("uv")
        if uv_path:
            installers.append({
                "type": "uv",
                "path": uv_path,
                "command": [uv_path, "pip", "install"],
                "priority": 4  # 最優先
            })
            
        # 2. pipコマンドをチェック
        pip_path = shutil.which("pip")
        if pip_path:
            installers.append({
                "type": "pip_cmd",
                "path": pip_path,
                "command": [pip_path, "install"],
                "priority": 3
            })
        
        # 3. pip3コマンドをチェック
        pip3_path = shutil.which("pip3")
        if pip3_path:
            installers.append({
                "type": "pip3_cmd",
                "path": pip3_path,
                "command": [pip3_path, "install"],
                "priority": 2
            })
            
        # 4. Python -m pipをチェック
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "--version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                check=True, 
                text=True
            )
            installers.append({
                "type": "pip_module",
                "path": sys.executable,
                "command": [sys.executable, "-m", "pip", "install"],
                "priority": 1
            })
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
            
        return installers
    
    def _select_preferred_installer(self) -> Dict[str, Any]:
        """優先度に基づいて推奨インストーラーを選択"""
        if not self.installers:
            return {
                "type": None,
                "path": None,
                "command": None,
                "priority": 0,
                "found": False,
                "message": "No package installer found."
            }
            
        # 優先度順にソート
        sorted_installers = sorted(self.installers, key=lambda x: x["priority"], reverse=True)
        
        # 最も優先度の高いインストーラーを選択
        preferred = sorted_installers[0]
        preferred["found"] = True
        preferred["message"] = f"Using '{preferred['type']}' package installer."
        
        return preferred
        
    def execute(self, command: str, **kwargs) -> ToolResult:
        """依存パッケージの管理を実行"""
        command_handlers = {
            "install": self._handle_install,
            "check": self._handle_check,
            "list": self._handle_list,
            "find_dependencies": self._handle_find_dependencies
        }
        
        handler = command_handlers.get(command)
        if not handler:
            return ToolResult(False, None, f"Unknown command: {command}")
        
        try:
            return handler(**kwargs)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return ToolResult(False, None, f"{str(e)}\n{error_details}")
    
    def _handle_install(self, package: str, version: str = None, **kwargs) -> ToolResult:
        """パッケージをインストール"""
        package_spec = package
        if version:
            package_spec = f"{package}=={version}"
            
        # パッケージとその依存関係をインストール
        try:
            print(f"Installing package: {package_spec}")
            
            # インストール試行回数をチェック
            if package in self.install_attempts:
                if self.install_attempts[package] >= self.max_attempts:
                    return ToolResult(False, None, 
                        f"Max install attempts reached for {package_spec}. Skipping further attempts.")
                self.install_attempts[package] += 1
            else:
                self.install_attempts[package] = 1
            
            # インストーラーが見つからなかった場合、フォールバック方法を試す
            if not self.preferred_installer["found"]:
                return self._install_with_fallbacks(package_spec)
                
            # 推奨インストーラーでインストール
            cmd = self.preferred_installer["command"] + [package_spec]
            
            print(f"Running command: {' '.join(cmd)}")
            
            # サブプロセスでインストールを実行
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                print(f"Installation failed with {self.preferred_installer['type']}: {stderr}")
                # フォールバック方法を試す
                return self._install_with_fallbacks(package_spec)
            
            # インストール後にimportしてテスト
            try:
                if package == "beautifulsoup4":
                    importlib.import_module("bs4")
                else:
                    importlib.import_module(package)
                return ToolResult(True, f"Successfully installed {package_spec}\n{stdout}")
            except ImportError as e:
                print(f"Package installed but import failed: {str(e)}")
                # フォールバック方法を試す
                return self._install_with_fallbacks(package_spec)
                
        except Exception as e:
            print(f"Error installing package: {str(e)}")
            # フォールバック方法を試す
            return self._install_with_fallbacks(package_spec)
    
    def _install_with_fallbacks(self, package_spec: str) -> ToolResult:
        """複数のフォールバック方法でパッケージインストールを試みる"""
        for get_cmd in self.fallback_commands:
            try:
                cmd = get_cmd(package_spec)
                if not cmd:
                    continue
                    
                print(f"Trying fallback: {' '.join(cmd)}")
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                stdout, stderr = process.communicate()
                
                if process.returncode == 0:
                    print(f"Fallback installation succeeded")
                    
                    # インストール後に少し待機（パッケージが利用可能になるまで）
                    time.sleep(1)
                    
                    # インポートテスト
                    package = package_spec.split("==")[0]
                    try:
                        if package == "beautifulsoup4":
                            importlib.import_module("bs4")
                        else:
                            importlib.import_module(package)
                        return ToolResult(True, f"Successfully installed {package_spec} with fallback method")
                    except ImportError:
                        print(f"Package installed but import failed")
                        continue
            except Exception as e:
                print(f"Fallback install error: {str(e)}")
                continue
                
        # 直接コマンドのインポート
        try:
            package = package_spec.split("==")[0]
            # システムレベルでのインストールを試みる
            os.system(f"pip install {package_spec}")
            
            # インポートテスト
            try:
                if package == "beautifulsoup4":
                    importlib.import_module("bs4")
                else:
                    importlib.import_module(package)
                return ToolResult(True, f"Successfully installed {package_spec} with system command")
            except ImportError:
                pass
        except:
            pass
            
        return ToolResult(False, None, f"Failed to install {package_spec} with all available methods")
    
    def _handle_check(self, package: str, **kwargs) -> ToolResult:
        """パッケージが利用可能かチェック"""
        try:
            # パッケージ名の正規化（bs4 -> beautifulsoup4など）
            if package == "bs4":
                actual_package = "beautifulsoup4"
            else:
                actual_package = package
                
            # インストール済みかチェック
            try:
                if package == "beautifulsoup4":
                    importlib.import_module("bs4")
                else:
                    importlib.import_module(package)
                return ToolResult(True, {"installed": True, "version": self._get_package_version(actual_package)})
            except ImportError:
                # インストールされていない場合
                return ToolResult(True, {"installed": False})
                
        except Exception as e:
            return ToolResult(False, None, f"Error checking package: {str(e)}")
    
    def _handle_list(self, **kwargs) -> ToolResult:
        """インストール済みパッケージの一覧を取得"""
        try:
            installed_packages = pkg_resources.working_set
            packages = {pkg.key: pkg.version for pkg in installed_packages}
            return ToolResult(True, packages)
        except Exception as e:
            return ToolResult(False, None, f"Error listing packages: {str(e)}")
    
    def _handle_find_dependencies(self, code: str, **kwargs) -> ToolResult:
        """コード内の依存パッケージを検出"""
        try:
            # importステートメントを検出するパターン
            import_pattern = r'(?:from|import)\s+([\w.]+)'
            imports = re.findall(import_pattern, code)
            
            # モジュール名を正規化（サブモジュールからルートモジュールへ）
            modules = set()
            for imp in imports:
                # ドットで分割して最初の部分を取得（ルートモジュール）
                root_module = imp.split('.')[0]
                modules.add(root_module)
            
            # 必要なパッケージのリストを作成
            required_packages = []
            for module in modules:
                # 標準ライブラリのモジュールは除外
                if self._is_stdlib_module(module):
                    continue
                    
                # 特殊なマッピング（bs4 -> beautifulsoup4など）
                if module == "bs4":
                    required_packages.append("beautifulsoup4")
                else:
                    required_packages.append(module)
            
            # 依存関係も含めた完全なリストを構築
            all_dependencies = set(required_packages)
            for pkg in required_packages:
                if pkg in self.common_dependencies:
                    all_dependencies.update(self.common_dependencies[pkg])
            
            # 存在しないパッケージを除外（例: 'errors'はパッケージではない）
            filtered_dependencies = set()
            for pkg in all_dependencies:
                # 一般的な非パッケージ名をフィルタリング
                if pkg not in ['errors', 'error', 'exceptions', 'exception', 'warnings', 'warning']:
                    filtered_dependencies.add(pkg)
            
            return ToolResult(True, list(filtered_dependencies))
            
        except Exception as e:
            return ToolResult(False, None, f"Error finding dependencies: {str(e)}")
    
    def _is_stdlib_module(self, module_name: str) -> bool:
        """モジュールが標準ライブラリの一部かどうかを判定"""
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
        
        if module_name in stdlib_modules:
            return True
            
        try:
            # 標準ライブラリにあるかをチェック
            spec = importlib.util.find_spec(module_name)
            return spec is not None and (
                spec.origin is not None and 
                "site-packages" not in spec.origin and 
                "dist-packages" not in spec.origin
            )
        except (ImportError, AttributeError):
            return False
    
    def _get_package_version(self, package_name: str) -> str:
        """パッケージのバージョンを取得"""
        try:
            return pkg_resources.get_distribution(package_name).version
        except:
            return "unknown"

    def ensure_dependencies(self, code: str) -> Tuple[bool, List[str], List[str]]:
        """コードの実行に必要な依存関係をすべてインストール"""
        # 依存関係を検出
        deps_result = self._handle_find_dependencies(code=code)
        if not deps_result.success:
            return False, [], [deps_result.error]
            
        required_packages = deps_result.result
        if not required_packages:  # 依存関係がない場合
            return True, [], []
            
        installed = []
        errors = []
        
        # 各パッケージをインストール
        for package in required_packages:
            check_result = self._handle_check(package=package)
            
            if check_result.success and check_result.result.get("installed", False):
                # すでにインストール済み
                installed.append(package)
                continue
                
            # インストールを実行
            install_result = self._handle_install(package=package)
            if install_result.success:
                installed.append(package)
            else:
                errors.append(f"Failed to install {package}: {install_result.error}")
                
        success = len(errors) == 0
        if not success and errors:
            print(f"Warning: Some dependencies could not be installed: {', '.join(errors)}")
        
        return success, installed, errors