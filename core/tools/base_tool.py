from typing import Dict, Any

class ToolResult:
    def __init__(self, success: bool, result: Any = None, error: str = None):
        self.success = success
        self.result = result
        self.error = error

class BaseTool:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.parameters = {}
        
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with the given parameters"""
        raise NotImplementedError("Subclasses must implement execute()")
    
    def to_param(self) -> Dict:
        """Convert the tool to a parameter format understood by the LLM"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }