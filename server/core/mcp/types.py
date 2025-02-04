from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

class ErrorCode(str, Enum):
    """MCPエラーコード"""
    InvalidRequest = "invalid_request"
    MethodNotFound = "method_not_found"
    InvalidParams = "invalid_params"
    InternalError = "internal_error"
    ResourceNotFound = "resource_not_found"

class McpError(Exception):
    """MCPエラー"""
    def __init__(self, code: ErrorCode, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

class ToolSchema(BaseModel):
    """ツールのスキーマ定義"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None

class ResourceSchema(BaseModel):
    """リソースのスキーマ定義"""
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: str = "application/json"

class ResourceTemplateSchema(BaseModel):
    """リソーステンプレートのスキーマ定義"""
    uri_template: str
    name: str
    description: Optional[str] = None
    mime_type: str = "application/json"

class ServerInfo(BaseModel):
    """サーバー情報"""
    name: str
    version: str
    capabilities: Dict[str, Any]

class ServerCapabilities(BaseModel):
    """サーバーの機能"""
    tools: Dict[str, ToolSchema] = {}
    resources: Dict[str, ResourceSchema] = {}
    resource_templates: List[ResourceTemplateSchema] = []