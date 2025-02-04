from typing import Dict, Any, Callable, Type, TypeVar, Optional
from functools import wraps
import inspect
import semantic_kernel as sk
from semantic_kernel.kernel import Kernel

T = TypeVar('T')

class ModuleBase:
    """基本モジュールクラス"""
    name: str = ""

def task_function(
    name: str,
    description: str,
    input_schema: Dict[str, Any],
    output_schema: Optional[Dict[str, Any]] = None,
    required_tools: Optional[list[str]] = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """タスク関数を定義するデコレータ"""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # 引数の検証
            if len(args) == 1 and isinstance(args[0], dict):
                context = args[0]
            else:
                context = {}
                for key, value in kwargs.items():
                    context[key] = str(value)

            # 必須パラメータのチェック
            for param_name, param_info in input_schema.items():
                if param_info.get("required", False) and param_name not in context:
                    raise ValueError(f"必須パラメータが不足しています: {param_name}")

            # 関数を実行
            result = await func(self, context)
            return result

        # メタデータを設定
        wrapper.is_task_function = True
        wrapper.task_name = name
        wrapper.task_description = description
        wrapper.input_schema = input_schema
        wrapper.output_schema = output_schema or {}
        wrapper.required_tools = required_tools or []
        
        return wrapper
    return decorator

def plan_step(
    name: str,
    description: str,
    input_schema: Dict[str, Any],
    output_schema: Dict[str, Any],
    dependencies: Optional[list[str]] = None
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """プランのステップを定義するデコレータ"""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # 引数の検証
            if len(args) == 1 and isinstance(args[0], dict):
                context = args[0]
            else:
                context = {}
                for key, value in kwargs.items():
                    context[key] = str(value)

            # 必須パラメータのチェック
            for param_name, param_info in input_schema.items():
                if param_info.get("required", False) and param_name not in context:
                    raise ValueError(f"必須パラメータが不足しています: {param_name}")

            # 関数を実行
            result = await func(self, context)
            return result

        # メタデータを設定
        wrapper.is_plan_step = True
        wrapper.step_name = name
        wrapper.step_description = description
        wrapper.input_schema = input_schema
        wrapper.output_schema = output_schema
        wrapper.dependencies = dependencies or []
        
        return wrapper
    return decorator

def get_module_functions(module_class: Type[T]) -> Dict[str, Dict[str, Any]]:
    """モジュールから利用可能な関数を取得"""
    functions = {}
    
    for name, method in inspect.getmembers(module_class):
        if hasattr(method, 'is_task_function'):
            functions[method.task_name] = {
                'name': method.task_name,
                'description': method.task_description,
                'input_schema': method.input_schema,
                'output_schema': method.output_schema,
                'required_tools': method.required_tools
            }
        elif hasattr(method, 'is_plan_step'):
            functions[method.step_name] = {
                'name': method.step_name,
                'description': method.step_description,
                'input_schema': method.input_schema,
                'output_schema': method.output_schema,
                'dependencies': method.dependencies
            }
            
    return functions