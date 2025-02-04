from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type
import inspect

class TaskModule:
    """タスクモジュールの基本クラス"""
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.functions: Dict[str, Dict[str, Any]] = {}

def task_function(
    name: Optional[str] = None,
    description: Optional[str] = None,
    input_schema: Optional[Dict[str, Any]] = None,
    output_schema: Optional[Dict[str, Any]] = None,
    required_tools: Optional[List[str]] = None
):
    """タスク関数を定義するデコレーター"""
    def decorator(func: Callable):
        func_name = name or func.__name__
        func_description = description or func.__doc__ or ""
        
        # 関数のパラメータ情報を取得
        sig = inspect.signature(func)
        params = sig.parameters
        
        # 入力スキーマが指定されていない場合は関数のパラメータから生成
        if input_schema is None:
            generated_schema = {}
            for param_name, param in params.items():
                if param_name == 'self':
                    continue
                param_type = param.annotation if param.annotation != inspect.Parameter.empty else Any
                generated_schema[param_name] = {
                    'type': str(param_type.__name__),
                    'description': '',
                    'required': param.default == inspect.Parameter.empty
                }
            func.input_schema = generated_schema
        else:
            func.input_schema = input_schema
            
        func.output_schema = output_schema or {'type': 'object'}
        func.required_tools = required_tools or []
        func.task_name = func_name
        func.task_description = func_description
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 入力値のバリデーション
            if len(args) > 1:  # selfを除く
                raise ValueError("位置引数は使用できません。キーワード引数を使用してください。")
            
            # 必須パラメータのチェック
            for param_name, schema in func.input_schema.items():
                if schema.get('required', False) and param_name not in kwargs:
                    raise ValueError(f"必須パラメータ '{param_name}' が指定されていません。")
            
            # 関数を実行
            result = await func(*args, **kwargs)
            return result
            
        return wrapper
    return decorator

class ModuleBase:
    """タスクモジュールのベースクラス"""
    def __init__(self):
        self._register_functions()
    
    def _register_functions(self):
        """クラス内のタスク関数を登録"""
        for name, method in inspect.getmembers(self):
            if hasattr(method, 'task_name'):
                if not hasattr(self, 'functions'):
                    self.functions = {}
                self.functions[method.task_name] = {
                    'name': method.task_name,
                    'description': method.task_description,
                    'input_schema': method.input_schema,
                    'output_schema': method.output_schema,
                    'required_tools': method.required_tools,
                    'handler': method
                }

def get_module_functions(module: Type[ModuleBase]) -> Dict[str, Dict[str, Any]]:
    """モジュールから利用可能な関数の情報を取得"""
    instance = module()
    return instance.functions