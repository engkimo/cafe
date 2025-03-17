from typing import Dict, Any, Optional
import os
import json
from .base_tool import BaseTool, ToolResult

class FileTool(BaseTool):
    def __init__(self, workspace_dir: str):
        super().__init__(
            name="file",
            description="Read from and write to files in the workspace"
        )
        self.workspace_dir = workspace_dir
        os.makedirs(workspace_dir, exist_ok=True)
        
        self.parameters = {
            "command": {
                "type": "string",
                "enum": ["read", "write", "append", "list", "exists", "delete"]
            },
            "path": {"type": "string"},
            "content": {"type": "string"},
            "format": {
                "type": "string",
                "enum": ["text", "json"],
                "default": "text"
            }
        }
    
    def execute(self, command: str, path: str, content: str = None, format: str = "text", **kwargs) -> ToolResult:
        """Execute a file operation"""
        command_handlers = {
            "read": self._handle_read,
            "write": self._handle_write,
            "append": self._handle_append,
            "list": self._handle_list,
            "exists": self._handle_exists,
            "delete": self._handle_delete
        }
        
        handler = command_handlers.get(command)
        if not handler:
            return ToolResult(False, None, f"Unknown command: {command}")
        
        # Make sure the path is within the workspace directory
        full_path = self._get_safe_path(path)
        if full_path is None:
            return ToolResult(False, None, f"Invalid path: {path} (must be within workspace)")
        
        try:
            return handler(full_path=full_path, content=content, format=format)
        except Exception as e:
            return ToolResult(False, None, str(e))
    
    def _get_safe_path(self, path: str) -> Optional[str]:
        """Get the full path, ensuring it's within the workspace directory"""
        # Normalize the path and make it absolute
        full_path = os.path.normpath(os.path.join(self.workspace_dir, path))
        
        # Check if the path is within the workspace directory
        if not full_path.startswith(self.workspace_dir):
            return None
            
        return full_path
    
    def _handle_read(self, full_path: str, format: str, **kwargs) -> ToolResult:
        """Read from a file"""
        if not os.path.exists(full_path):
            return ToolResult(False, None, f"File not found: {full_path}")
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if format == "json":
                content = json.loads(content)
                
            return ToolResult(True, content)
        except Exception as e:
            return ToolResult(False, None, f"Error reading file: {str(e)}")
    
    def _handle_write(self, full_path: str, content: str, format: str, **kwargs) -> ToolResult:
        """Write to a file"""
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        try:
            if format == "json" and isinstance(content, dict):
                content = json.dumps(content, indent=2)
                
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            return ToolResult(True, f"Successfully wrote to {full_path}")
        except Exception as e:
            return ToolResult(False, None, f"Error writing to file: {str(e)}")
    
    def _handle_append(self, full_path: str, content: str, **kwargs) -> ToolResult:
        """Append to a file"""
        try:
            with open(full_path, 'a', encoding='utf-8') as f:
                f.write(content)
                
            return ToolResult(True, f"Successfully appended to {full_path}")
        except Exception as e:
            return ToolResult(False, None, f"Error appending to file: {str(e)}")
    
    def _handle_list(self, full_path: str, **kwargs) -> ToolResult:
        """List files in a directory"""
        if not os.path.exists(full_path):
            return ToolResult(False, None, f"Directory not found: {full_path}")
        
        if not os.path.isdir(full_path):
            return ToolResult(False, None, f"Not a directory: {full_path}")
        
        try:
            files = os.listdir(full_path)
            return ToolResult(True, files)
        except Exception as e:
            return ToolResult(False, None, f"Error listing directory: {str(e)}")
    
    def _handle_exists(self, full_path: str, **kwargs) -> ToolResult:
        """Check if a file or directory exists"""
        exists = os.path.exists(full_path)
        return ToolResult(True, exists)
    
    def _handle_delete(self, full_path: str, **kwargs) -> ToolResult:
        """Delete a file"""
        if not os.path.exists(full_path):
            return ToolResult(False, None, f"File not found: {full_path}")
        
        try:
            if os.path.isdir(full_path):
                os.rmdir(full_path)  # Only removes empty directories
            else:
                os.remove(full_path)
                
            return ToolResult(True, f"Successfully deleted {full_path}")
        except Exception as e:
            return ToolResult(False, None, f"Error deleting file: {str(e)}")
