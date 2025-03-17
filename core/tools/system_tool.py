# core/tools/system_tool.py
import os
import sys
import subprocess
import platform
import shutil
from typing import Dict, Any, List, Optional

from .base_tool import BaseTool, ToolResult

class SystemTool(BaseTool):
    """システムコマンド実行と環境情報取得のためのツール"""
    
    def __init__(self):
        super().__init__(
            name="system",
            description="Execute system commands and get environment information"
        )
        
        # 安全に実行できるコマンドのホワイトリスト
        self.safe_commands = {
            "list_dir": self._list_directory,
            "get_env": self._get_environment_vars,
            "check_command": self._check_command_exists,
            "get_platform_info": self._get_platform_info,
            "pip_install": self._pip_install,
            "which": self._which_command,
        }
        
        self.parameters = {
            "command": {
                "type": "string",
                "enum": list(self.safe_commands.keys()) + ["custom"]
            },
            "args": {"type": "object"},
            "custom_command": {"type": "string"},
            "working_dir": {"type": "string"}
        }
    
    def execute(self, command: str, args: Dict = None, **kwargs) -> ToolResult:
        """ツールコマンドを実行"""
        if command == "custom":
            return self._execute_custom_command(
                kwargs.get("custom_command", ""),
                kwargs.get("working_dir")
            )
        
        handler = self.safe_commands.get(command)
        if not handler:
            return ToolResult(False, None, f"Unknown command: {command}")
        
        try:
            return handler(**(args or {}))
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return ToolResult(False, None, f"{str(e)}\n{error_details}")
    
    def _list_directory(self, path: str = ".") -> ToolResult:
        """ディレクトリの内容を一覧表示"""
        try:
            entries = os.listdir(path)
            result = {
                "files": [],
                "directories": []
            }
            
            for entry in entries:
                full_path = os.path.join(path, entry)
                if os.path.isdir(full_path):
                    result["directories"].append(entry)
                else:
                    result["files"].append(entry)
            
            return ToolResult(True, result)
        except Exception as e:
            return ToolResult(False, None, str(e))
    
    def _get_environment_vars(self, vars: List[str] = None) -> ToolResult:
        """環境変数を取得"""
        if vars:
            result = {var: os.environ.get(var) for var in vars}
        else:
            # デフォルトではPYTHONPATHとPATHのみ返す
            result = {
                "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
                "PATH": os.environ.get("PATH", "")
            }
        
        return ToolResult(True, result)
    
    def _check_command_exists(self, command: str) -> ToolResult:
        """コマンドが存在するか確認"""
        command_path = shutil.which(command)
        if command_path:
            return ToolResult(True, {"exists": True, "path": command_path})
        else:
            return ToolResult(True, {"exists": False})
    
    def _get_platform_info(self) -> ToolResult:
        """プラットフォーム情報を取得"""
        info = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "architecture": platform.architecture(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": sys.version,
            "python_implementation": platform.python_implementation()
        }
        
        # Macかどうかの情報を追加
        info["is_mac"] = platform.system() == "Darwin"
        # Linuxかどうかの情報を追加
        info["is_linux"] = platform.system() == "Linux"
        # Windowsかどうかの情報を追加
        info["is_windows"] = platform.system() == "Windows"
        
        return ToolResult(True, info)
    
    def _pip_install(self, package: str, upgrade: bool = False, user: bool = False) -> ToolResult:
        """pipを使ってパッケージをインストール"""
        cmd = [sys.executable, "-m", "pip", "install"]
        
        if upgrade:
            cmd.append("--upgrade")
        
        if user:
            cmd.append("--user")
        
        cmd.append(package)
        
        try:
            process = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return ToolResult(True, {
                "stdout": process.stdout,
                "stderr": process.stderr
            })
        except subprocess.CalledProcessError as e:
            return ToolResult(False, {
                "stdout": e.stdout,
                "stderr": e.stderr
            }, f"Error installing {package}")
    
    def _which_command(self, command: str) -> ToolResult:
        """コマンドの実行パスを取得"""
        path = shutil.which(command)
        if path:
            return ToolResult(True, {"path": path})
        else:
            return ToolResult(False, None, f"Command '{command}' not found")
    
    def _execute_custom_command(self, command: str, working_dir: str = None) -> ToolResult:
        """カスタムシステムコマンドを実行（制限あり）"""
        # セキュリティチェック - 危険なコマンドを拒否
        dangerous_commands = ["rm", "rmdir", "del", "format", "mkfs", "dd"]
        
        # コマンドの最初の部分（コマンド名）を取得
        cmd_parts = command.split()
        if not cmd_parts:
            return ToolResult(False, None, "Empty command")
            
        base_cmd = cmd_parts[0]
        
        # 危険なコマンドをチェック
        if any(base_cmd == cmd or base_cmd.endswith(f"/{cmd}") for cmd in dangerous_commands):
            return ToolResult(False, None, f"Dangerous command '{base_cmd}' is not allowed")
        
        try:
            process = subprocess.run(
                command,
                shell=True,  # シェル経由で実行
                cwd=working_dir,
                check=False,  # エラーでも例外を投げない
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            return ToolResult(
                process.returncode == 0,
                {
                    "stdout": process.stdout,
                    "stderr": process.stderr,
                    "return_code": process.returncode
                },
                None if process.returncode == 0 else f"Command failed with return code {process.returncode}"
            )
        except Exception as e:
            return ToolResult(False, None, f"Error executing command: {str(e)}")