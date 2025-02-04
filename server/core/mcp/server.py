from typing import Dict, Any, Optional, Callable, Awaitable, TypeVar, Generic
import json
import asyncio
from .types import (
    ServerInfo,
    ServerCapabilities,
    ToolSchema,
    ResourceSchema,
    ResourceTemplateSchema,
    McpError,
    ErrorCode
)

T = TypeVar('T')

class Server:
    """MCPサーバーの基本実装"""
    def __init__(self, info: Dict[str, Any], capabilities: Dict[str, Any]):
        self.info = ServerInfo(**info)
        self.capabilities = ServerCapabilities(**capabilities)
        self._tools: Dict[str, ToolSchema] = {}
        self._tool_handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}
        self._resources: Dict[str, ResourceSchema] = {}
        self._resource_handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}
        self._resource_templates: Dict[str, ResourceTemplateSchema] = {}
        self._resource_template_handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}
        self.onerror: Optional[Callable[[Exception], None]] = None

    def add_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable[..., Awaitable[Any]],
        output_schema: Optional[Dict[str, Any]] = None
    ) -> None:
        """ツールを登録"""
        tool_schema = ToolSchema(
            name=name,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema
        )
        self._tools[name] = tool_schema
        self._tool_handlers[name] = handler
        self.capabilities.tools[name] = tool_schema

    def add_resource(
        self,
        uri: str,
        name: str,
        mime_type: str,
        handler: Callable[..., Awaitable[Any]],
        description: Optional[str] = None
    ) -> None:
        """リソースを登録"""
        resource_schema = ResourceSchema(
            uri=uri,
            name=name,
            description=description,
            mime_type=mime_type
        )
        self._resources[uri] = resource_schema
        self._resource_handlers[uri] = handler
        self.capabilities.resources[uri] = resource_schema

    def add_resource_template(
        self,
        uri_template: str,
        name: str,
        mime_type: str,
        handler: Callable[..., Awaitable[Any]],
        description: Optional[str] = None
    ) -> None:
        """リソーステンプレートを登録"""
        template_schema = ResourceTemplateSchema(
            uri_template=uri_template,
            name=name,
            description=description,
            mime_type=mime_type
        )
        self._resource_templates[uri_template] = template_schema
        self._resource_template_handlers[uri_template] = handler
        self.capabilities.resource_templates.append(template_schema)

    async def execute_tool(self, name: str, params: Dict[str, Any]) -> Any:
        """ツールを実行"""
        if name not in self._tools:
            raise McpError(ErrorCode.MethodNotFound, f"Tool not found: {name}")
        
        try:
            handler = self._tool_handlers[name]
            return await handler(params)
        except McpError:
            raise
        except Exception as e:
            if self.onerror:
                self.onerror(e)
            raise McpError(ErrorCode.InternalError, str(e))

    async def get_resource(self, uri: str) -> Any:
        """リソースを取得"""
        if uri in self._resources:
            try:
                handler = self._resource_handlers[uri]
                return await handler(uri)
            except McpError:
                raise
            except Exception as e:
                if self.onerror:
                    self.onerror(e)
                raise McpError(ErrorCode.InternalError, str(e))

        # リソーステンプレートの処理
        for template_uri, handler in self._resource_template_handlers.items():
            try:
                if self._match_uri_template(template_uri, uri):
                    return await handler(uri)
            except McpError:
                raise
            except Exception as e:
                if self.onerror:
                    self.onerror(e)
                raise McpError(ErrorCode.InternalError, str(e))

        raise McpError(ErrorCode.ResourceNotFound, f"Resource not found: {uri}")

    def _match_uri_template(self, template: str, uri: str) -> bool:
        """URIテンプレートとURIのマッチング"""
        template_parts = template.split('/')
        uri_parts = uri.split('/')
        
        if len(template_parts) != len(uri_parts):
            return False
        
        for t, u in zip(template_parts, uri_parts):
            if t.startswith('{') and t.endswith('}'):
                continue
            if t != u:
                return False
        
        return True

    async def close(self) -> None:
        """サーバーをクリーンアップ"""
        pass  # 必要に応じてクリーンアップ処理を実装