# core/tools/docker_execute.py
import os
import tempfile
import subprocess
import json
from typing import Dict, Any, List, Optional

from .base_tool import BaseTool, ToolResult

class DockerExecuteTool(BaseTool):
    """Dockerを使用してコードを実行するツール"""
    
    def __init__(self, workspace_dir: str):
        super().__init__(
            name="docker_execute",
            description="Execute code in a Docker container"
        )
        self.workspace_dir = workspace_dir
        # Dockerfile用のテンプレート
        self.dockerfile_template = """
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "{script_name}"]
"""
        self.parameters = {
            "command": {
                "type": "string",
                "enum": ["run", "build", "check"]
            },
            "code": {"type": "string"},
            "requirements": {"type": "array", "items": {"type": "string"}},
            "task_id": {"type": "string"}
        }
    
    def execute(self, command: str, **kwargs) -> ToolResult:
        """ツールコマンドを実行"""
        command_handlers = {
            "run": self._handle_run,
            "build": self._handle_build,
            "check": self._handle_check,
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
    
    def _handle_run(self, code: str, requirements: List[str] = None, **kwargs) -> ToolResult:
        """Dockerコンテナ内でコードを実行"""
        # 一時ディレクトリを作成
        with tempfile.TemporaryDirectory(dir=self.workspace_dir) as temp_dir:
            # コードファイルを作成
            script_name = "script.py"
            script_path = os.path.join(temp_dir, script_name)
            with open(script_path, "w") as f:
                f.write(code)
            
            # requirements.txtを作成
            if requirements:
                req_path = os.path.join(temp_dir, "requirements.txt")
                with open(req_path, "w") as f:
                    f.write("\n".join(requirements))
            else:
                # デフォルトの依存関係
                req_path = os.path.join(temp_dir, "requirements.txt")
                with open(req_path, "w") as f:
                    f.write("numpy\npandas\nmatplotlib\nrequests\nbeautifulsoup4\n")
            
            # Dockerfileを作成
            dockerfile_path = os.path.join(temp_dir, "Dockerfile")
            with open(dockerfile_path, "w") as f:
                f.write(self.dockerfile_template.format(script_name=script_name))
            
            # Dockerイメージをビルド
            image_name = f"ai_agent_task_{os.path.basename(temp_dir)}"
            build_cmd = ["docker", "build", "-t", image_name, "."]
            
            try:
                subprocess.run(
                    build_cmd,
                    cwd=temp_dir,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            except subprocess.CalledProcessError as e:
                return ToolResult(False, None, f"Docker build error: {e.stderr}")
            
            # Dockerコンテナを実行
            run_cmd = ["docker", "run", "--rm", image_name]
            
            try:
                process = subprocess.run(
                    run_cmd,
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
                    "stderr": e.stderr,
                    "stdout": e.stdout
                }, "Docker run error")
    
    def _handle_build(self, requirements: List[str] = None, **kwargs) -> ToolResult:
        """カスタムDockerイメージをビルド"""
        # 一時ディレクトリを作成
        with tempfile.TemporaryDirectory(dir=self.workspace_dir) as temp_dir:
            # requirements.txtを作成
            if requirements:
                req_path = os.path.join(temp_dir, "requirements.txt")
                with open(req_path, "w") as f:
                    f.write("\n".join(requirements))
            else:
                # デフォルトの依存関係
                req_path = os.path.join(temp_dir, "requirements.txt")
                with open(req_path, "w") as f:
                    f.write("numpy\npandas\nmatplotlib\nrequests\nbeautifulsoup4\n")
            
            # 最小限のPythonスクリプトを作成
            script_path = os.path.join(temp_dir, "script.py")
            with open(script_path, "w") as f:
                f.write('print("Image built successfully!")')
            
            # Dockerfileを作成
            dockerfile_path = os.path.join(temp_dir, "Dockerfile")
            with open(dockerfile_path, "w") as f:
                f.write(self.dockerfile_template.format(script_name="script.py"))
            
            # Dockerイメージをビルド
            image_name = f"ai_agent_base_{os.path.basename(temp_dir)}"
            build_cmd = ["docker", "build", "-t", image_name, "."]
            
            try:
                process = subprocess.run(
                    build_cmd,
                    cwd=temp_dir,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                return ToolResult(True, {
                    "image_name": image_name,
                    "build_output": process.stdout
                })
            except subprocess.CalledProcessError as e:
                return ToolResult(False, None, f"Docker build error: {e.stderr}")
    
    def _handle_check(self, **kwargs) -> ToolResult:
        """Dockerがインストールされているか確認"""
        try:
            process = subprocess.run(
                ["docker", "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return ToolResult(True, {
                "installed": True,
                "version": process.stdout.strip()
            })
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ToolResult(True, {
                "installed": False
            })