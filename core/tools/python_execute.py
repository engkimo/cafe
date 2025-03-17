from typing import Dict, Any, List, Optional
import io
import sys
import traceback
import re
import importlib
from contextlib import redirect_stdout, redirect_stderr
from .base_tool import BaseTool, ToolResult

class PythonExecuteTool(BaseTool):
    def __init__(self, package_manager=None):
        super().__init__(
            name="python_execute",
            description="Execute Python code and return the result"
        )
        self.parameters = {
            "code": {
                "type": "string",
                "description": "The Python code to execute"
            },
            "auto_install": {
                "type": "boolean",
                "description": "Automatically install missing dependencies",
                "default": True
            }
        }
        self.package_manager = package_manager
        
    def execute(self, code: str, auto_install: bool = True, **kwargs) -> ToolResult:
        """Execute Python code and return the result"""
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        # 依存関係の事前チェック
        missing_imports = self._check_imports(code)
        
        # パッケージマネージャが使用可能で自動インストールが有効な場合
        if missing_imports and auto_install and self.package_manager:
            installed_packages = []
            for package in missing_imports:
                print(f"Attempting to install missing package: {package}")
                result = self.package_manager.execute(command="install", package=package)
                if result.success:
                    installed_packages.append(package)
                    print(f"Successfully installed {package}")
                else:
                    print(f"Failed to install {package}: {result.error}")
            
            # インストール後に再度依存関係をチェック
            missing_imports = self._check_imports(code)
            if missing_imports:
                packages_str = ", ".join(missing_imports)
                return ToolResult(
                    False, 
                    None, 
                    f"Still missing required packages: {packages_str}. Please install them manually."
                )
        elif missing_imports:
            packages_str = ", ".join(missing_imports)
            return ToolResult(
                False, 
                None, 
                f"Missing required packages: {packages_str}. Set auto_install=True to install automatically."
            )
        
        try:
            # Define a dictionary for local variables
            local_vars = {}
            
            # Execute the code, capturing stdout and stderr
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code, {"__builtins__": __builtins__}, local_vars)
            
            # Get the captured output
            stdout = stdout_capture.getvalue()
            stderr = stderr_capture.getvalue()
            
            # Check if there's a result variable
            result = local_vars.get("result", None)
            
            return ToolResult(
                success=True,
                result={
                    "result": result,
                    "stdout": stdout,
                    "stderr": stderr,
                    "variables": {k: str(v) for k, v in local_vars.items() if not k.startswith("_")}
                }
            )
        except ModuleNotFoundError as e:
            # モジュールが見つからないエラーを特別に処理
            module_name = str(e).split("'")[1] if "'" in str(e) else str(e)
            error_msg = f"No module named '{module_name}'"
            
            # パッケージマネージャが使用可能で自動インストールが有効な場合
            if auto_install and self.package_manager:
                print(f"ModuleNotFoundError: {error_msg}. Attempting to install...")
                result = self.package_manager.execute(command="install", package=module_name)
                if result.success:
                    print(f"Successfully installed {module_name}. Retrying execution...")
                    # 再度実行を試みる
                    return self.execute(code, auto_install=False)  # 再帰呼び出しの場合は自動インストールを無効に
                else:
                    return ToolResult(
                        False,
                        {
                            "stdout": stdout_capture.getvalue(),
                            "stderr": stderr_capture.getvalue()
                        },
                        f"Failed to install {module_name}: {result.error}"
                    )
            
            return ToolResult(
                False,
                {
                    "stdout": stdout_capture.getvalue(),
                    "stderr": stderr_capture.getvalue()
                },
                error_msg
            )
        except Exception as e:
            # その他のエラーをキャプチャ
            # トレースバックを取得
            exc_type, exc_value, exc_traceback = sys.exc_info()
            error_details = traceback.format_exception(exc_type, exc_value, exc_traceback)
            
            return ToolResult(
                False,
                {
                    "stdout": stdout_capture.getvalue(),
                    "stderr": stderr_capture.getvalue()
                },
                f"Error: {str(e)}\n{''.join(error_details)}"
            )
    
    def _check_imports(self, code: str) -> List[str]:
        """コード内のimportステートメントから、不足しているモジュールを検出"""
        import_pattern = r'(?:from|import)\s+([\w.]+)'
        imports = re.findall(import_pattern, code)
        
        missing = []
        for imp in imports:
            # モジュール名を取得（from x.y import z の場合は x）
            module_name = imp.split('.')[0]
            
            # 標準ライブラリはスキップ
            if self._is_stdlib_module(module_name):
                continue
                
            # モジュールが利用可能かチェック
            try:
                # bs4は特殊ケース
                if module_name == "bs4":
                    importlib.import_module("bs4")
                else:
                    importlib.import_module(module_name)
            except ImportError:
                # bs4の場合は実際のパッケージ名を追加
                if module_name == "bs4":
                    missing.append("beautifulsoup4")
                else:
                    missing.append(module_name)
                
        return missing
    
    def _is_stdlib_module(self, module_name: str) -> bool:
        """モジュールが標準ライブラリの一部かどうかを判定"""
        # 一般的な標準ライブラリ
        stdlib_modules = {
            "os", "sys", "math", "random", "datetime", "time", "json", 
            "csv", "re", "collections", "itertools", "functools", "io",
            "pathlib", "shutil", "glob", "argparse", "logging", "unittest",
            "threading", "multiprocessing", "subprocess", "socket", "email",
            "smtplib", "urllib", "http", "xml", "html", "tkinter", "sqlite3",
            "hashlib", "uuid", "tempfile", "copy", "traceback", "gc", "inspect"
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