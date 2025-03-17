# core/modular_code_manager.py
from typing import Dict, List, Optional, Any, Tuple
import json
import os
import re
import ast
import importlib
from dataclasses import dataclass
import uuid

@dataclass
class CodeModuleInfo:
    """コードモジュールの情報"""
    name: str
    description: str
    code: str
    dependencies: List[str]
    functionality: List[str]

class ModularCodeManager:
    """コードモジュールの管理と再利用を支援するクラス"""
    
    def __init__(self, workspace_dir: str, graph_rag, llm):
        self.workspace_dir = workspace_dir
        self.graph_rag = graph_rag
        self.llm = llm
        self.modules_dir = os.path.join(workspace_dir, "modules")
        self.modules_index_path = os.path.join(self.modules_dir, "modules_index.json")
        
        # モジュールディレクトリを作成
        os.makedirs(self.modules_dir, exist_ok=True)
        
        # モジュールインデックスの初期化または読み込み
        self.modules_index = self._load_modules_index()
    
    def _load_modules_index(self) -> Dict:
        """モジュールインデックスを読み込み"""
        if os.path.exists(self.modules_index_path):
            try:
                with open(self.modules_index_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading modules index: {e}")
                return {"modules": {}}
        else:
            return {"modules": {}}
    
    def _save_modules_index(self):
        """モジュールインデックスを保存"""
        try:
            with open(self.modules_index_path, 'w') as f:
                json.dump(self.modules_index, f, indent=2)
        except Exception as e:
            print(f"Error saving modules index: {e}")
    
    def extract_reusable_modules(self, task_id: str, task_db, task_description: str = None) -> List[str]:
        """成功したタスクから再利用可能なモジュールを抽出"""
        task = task_db.get_task(task_id)
        
        if not task or task.status.value != "COMPLETED":
            print(f"Task {task_id} is not completed, cannot extract modules.")
            return []
        
        # LLMを使用してコードから再利用可能な部分を特定
        prompt = f"""
        Analyze the following Python code and identify reusable components:
        
        ```python
        {task.code}
        ```
        
        For each reusable component, provide:
        1. Component name (use snake_case): A descriptive name for the function or class
        2. Brief description: What this component does
        3. The exact code of the component: Include all necessary functions and classes
        4. Required dependencies: List of required imports and packages
        5. Functionality tags: 3-5 words describing what this code can do (e.g., "data_processing", "file_handling", "csv_parsing")
        
        Format your response as a JSON array with these fields:
        [
            {{
                "name": "component_name",
                "description": "Brief description",
                "code": "def component_name():\\n    # code here",
                "dependencies": ["package1", "package2"],
                "functionality": ["tag1", "tag2", "tag3"]
            }},
            // More components...
        ]
        
        Only extract meaningful, self-contained components that could be reused in other projects.
        """
        
        try:
            response = self.llm.generate_text(prompt)
            
            # JSONを抽出して解析
            json_pattern = r"\[\s*\{.*\}\s*\]"
            match = re.search(json_pattern, response, re.DOTALL)
            
            if not match:
                # LLM出力から最もJSON配列らしい部分を探す
                response = response.replace("```json", "").replace("```", "").strip()
                
                # 角括弧で囲まれた部分を探す
                if response.startswith("[") and response.endswith("]"):
                    json_str = response
                else:
                    print("Could not extract JSON array from LLM response.")
                    return []
            else:
                json_str = match.group(0)
            
            # JSONをパース
            modules_data = json.loads(json_str)
            module_ids = []
            
            # 各モジュールを保存
            for module_data in modules_data:
                module_name = module_data.get("name", "")
                if not module_name:
                    continue
                    
                # 基本情報の取得
                description = module_data.get("description", "")
                code = module_data.get("code", "")
                dependencies = module_data.get("dependencies", [])
                functionality = module_data.get("functionality", [])
                
                # モジュールの検証
                if not self._validate_module_code(code):
                    print(f"Module {module_name} has invalid code, skipping.")
                    continue
                
                # モジュール情報を作成
                module_info = CodeModuleInfo(
                    name=module_name,
                    description=description,
                    code=code,
                    dependencies=dependencies,
                    functionality=functionality
                )
                
                # モジュールを保存
                module_id = self._save_module(module_info)
                if module_id:
                    module_ids.append(module_id)
                    
                    # GraphRAGにも保存
                    if self.graph_rag:
                        self.graph_rag.store_code_module(
                            name=module_name,
                            description=description,
                            code=code,
                            dependencies=dependencies,
                            functionality=functionality
                        )
            
            return module_ids
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error extracting reusable modules: {e}")
            return []
    
    def _validate_module_code(self, code: str) -> bool:
        """モジュールコードが有効かチェック"""
        try:
            # ASTでパースしてみる
            ast.parse(code)
            
            # 最小サイズをチェック (あまりに小さいコードは意味がない)
            if len(code.strip().split("\n")) < 3:
                return False
            
            return True
        except Exception:
            return False
    
    def _save_module(self, module_info: CodeModuleInfo) -> str:
        """モジュールをファイルとして保存"""
        try:
            # モジュールIDを生成 (名前ベース)
            module_id = str(uuid.uuid4())
            module_name = module_info.name
            
            # ファイル名を作成
            file_name = f"{module_name}_{module_id[:8]}.py"
            file_path = os.path.join(self.modules_dir, file_name)
            
            # モジュールファイルを保存
            with open(file_path, 'w') as f:
                # ドキュメント文字列を追加
                docstring = f'"""\n{module_info.description}\n\nFunctionality: {", ".join(module_info.functionality)}\nDependencies: {", ".join(module_info.dependencies)}\n"""\n\n'
                f.write(docstring + module_info.code)
            
            # インデックスに追加
            self.modules_index["modules"][module_id] = {
                "id": module_id,
                "name": module_name,
                "description": module_info.description,
                "file_path": file_path,
                "dependencies": module_info.dependencies,
                "functionality": module_info.functionality
            }
            
            # インデックスを保存
            self._save_modules_index()
            
            print(f"Saved module {module_name} to {file_path}")
            return module_id
        except Exception as e:
            print(f"Error saving module {module_info.name}: {e}")
            return ""
    
    def get_modules_for_task(self, task_description: str) -> List[Dict]:
        """タスクに関連する再利用可能なモジュールを取得"""
        if self.graph_rag:
            # GraphRAGから関連モジュールを取得
            modules = self.graph_rag.get_relevant_modules(task_description)
            if modules:
                return modules
        
        # GraphRAGが使えない場合はLLMを使用
        return self._get_modules_with_llm(task_description)
    
    def _get_modules_with_llm(self, task_description: str) -> List[Dict]:
        """LLMを使用してタスクに関連するモジュールを選択"""
        if not self.modules_index["modules"]:
            return []
        
        try:
            # モジュール情報をリスト化
            module_list = []
            for module_id, module_info in self.modules_index["modules"].items():
                # モジュールファイルを読み込み
                try:
                    with open(module_info["file_path"], 'r') as f:
                        code = f.read()
                except Exception:
                    continue
                
                module_list.append({
                    "id": module_id,
                    "name": module_info["name"],
                    "description": module_info["description"],
                    "code": code,
                    "dependencies": module_info["dependencies"],
                    "functionality": module_info["functionality"]
                })
                
            if not module_list:
                return []
            
            # LLMを使用して関連モジュールを選択
            modules_json = json.dumps([{
                "id": m["id"],
                "name": m["name"],
                "description": m["description"],
                "functionality": m["functionality"]
            } for m in module_list], indent=2)
            
            prompt = f"""
            Given the following task description:
            "{task_description}"
            
            And these available code modules:
            {modules_json}
            
            Select up to 3 modules that would be most useful for this task.
            Return only a JSON array with the IDs of the selected modules, like this:
            ["id1", "id2", "id3"]
            """
            
            response = self.llm.generate_text(prompt)
            
            # JSONを抽出して解析
            json_pattern = r"\[.*\]"
            match = re.search(json_pattern, response, re.DOTALL)
            
            if not match:
                return []
            
            selected_ids = json.loads(match.group(0))
            
            # 選択されたモジュールの詳細情報を返す
            selected_modules = []
            for module_id in selected_ids:
                for module in module_list:
                    if module["id"] == module_id:
                        selected_modules.append(module)
                        break
            
            return selected_modules
        except Exception as e:
            print(f"Error getting modules with LLM: {e}")
            return []
    
    def incorporate_modules_into_code(self, code: str, modules: List[Dict], llm) -> str:
        """コードに再利用可能なモジュールを組み込む"""
        if not modules:
            return code
        
        try:
            # モジュール情報をプロンプトに整形
            modules_info = "\n\n".join([
                f"Module: {module['name']}\nDescription: {module['description']}\n```python\n{module['code']}\n```"
                for module in modules
            ])
            
            prompt = f"""
            Modify the following code to use these reusable modules:
            
            ORIGINAL CODE:
            ```python
            {code}
            ```
            
            AVAILABLE MODULES:
            {modules_info}
            
            Rewrite the code to import and use these modules instead of duplicating functionality.
            The rewritten code should:
            1. Import the modules from appropriate files (use relative imports like `from .module_name import function_name`)
            2. Use the functions/classes from the modules instead of reimplementing the same functionality
            3. Make minimal changes to preserve the original code's intent and behavior
            4. Add comments to indicate where modules are being used
            
            Only provide the revised code, no explanations.
            """
            
            # LLMでコードを修正
            response = llm.generate_text(prompt)
            
            # コードブロックから修正コードを抽出
            code_pattern = r"```python\s+(.*?)\s+```"
            match = re.search(code_pattern, response, re.DOTALL)
            
            if match:
                modified_code = match.group(1)
            else:
                # コードブロックがない場合はレスポンス全体を使用
                modified_code = response.strip()
            
            return modified_code
        except Exception as e:
            print(f"Error incorporating modules: {e}")
            return code  # エラーが発生した場合は元のコードを返す
    
    def analyze_module_dependencies(self, module_id: str) -> List[Dict]:
        """モジュールの依存関係を分析"""
        if module_id not in self.modules_index["modules"]:
            return []
        
        module_info = self.modules_index["modules"][module_id]
        file_path = module_info["file_path"]
        
        try:
            # モジュールファイルを読み込み
            with open(file_path, 'r') as f:
                code = f.read()
            
            # ASTを使用して依存関係を抽出
            dependencies = self._extract_imports(code)
            
            # 依存関係の詳細情報
            dependency_info = []
            for dep in dependencies:
                # 標準ライブラリかどうかをチェック
                is_stdlib = self._is_stdlib_module(dep)
                
                # インデックス内の他のモジュールかどうかをチェック
                is_internal = False
                internal_id = None
                for mid, info in self.modules_index["modules"].items():
                    if info["name"] == dep:
                        is_internal = True
                        internal_id = mid
                        break
                
                dependency_info.append({
                    "name": dep,
                    "is_stdlib": is_stdlib,
                    "is_internal": is_internal,
                    "internal_id": internal_id
                })
            
            return dependency_info
        except Exception as e:
            print(f"Error analyzing module dependencies: {e}")
            return []
    
    def _extract_imports(self, code: str) -> List[str]:
        """コードからインポート文を抽出"""
        try:
            # ASTを使用してインポート文を解析
            tree = ast.parse(code)
            
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        imports.append(name.name)
                elif isinstance(node, ast.ImportFrom):
                    imports.append(node.module)
            
            # Noneや空文字列を削除
            imports = [imp for imp in imports if imp]
            
            # 重複を削除
            return list(set(imports))
        except Exception:
            # 構文エラーがある場合は正規表現を使用
            import_pattern = r'import\s+([\w.]+)|from\s+([\w.]+)\s+import'
            matches = re.findall(import_pattern, code)
            
            imports = []
            for match in matches:
                if match[0]:  # 'import x' パターン
                    imports.append(match[0])
                elif match[1]:  # 'from x import y' パターン
                    imports.append(match[1])
            
            return list(set(imports))
    
    def _is_stdlib_module(self, module_name: str) -> bool:
        """モジュールが標準ライブラリかどうかを判定"""
        # 一般的な標準ライブラリのリスト
        stdlib_modules = {
            "os", "sys", "math", "random", "datetime", "time", "json", 
            "csv", "re", "collections", "itertools", "functools", "io",
            "pathlib", "shutil", "glob", "argparse", "logging", "unittest",
            "threading", "multiprocessing", "subprocess", "socket", "email",
            "smtplib", "urllib", "http", "xml", "html", "sqlite3", "hashlib",
            "uuid", "tempfile", "copy", "traceback", "gc", "inspect", "warnings",
            "abc", "ast", "asyncio", "bisect", "calendar", "cmath", "concurrent",
            "contextlib", "decimal", "difflib", "enum", "fractions", "gettext",
            "heapq", "hmac", "imaplib", "keyword", "locale", "operator", "pickle",
            "platform", "pprint", "pwd", "queue", "select", "signal", "statistics",
            "string", "struct", "tarfile", "textwrap", "typing", "unicodedata", "wave",
            "weakref", "zipfile", "zlib"
        }
        
        if module_name in stdlib_modules:
            return True
            
        # モジュール名が.で区切られている場合は最初の部分だけ使用
        root_module = module_name.split('.')[0]
        if root_module in stdlib_modules:
            return True
            
        try:
            # 標準ライブラリかどうかをimportlibで確認
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                return False
                
            # site-packagesやdist-packagesにないものは標準ライブラリ
            return "site-packages" not in str(spec.origin) and "dist-packages" not in str(spec.origin)
        except (ModuleNotFoundError, AttributeError):
            return False
    
    def get_module_analytics(self) -> Dict:
        """モジュールの利用統計を取得"""
        if not self.modules_index["modules"]:
            return {"total_modules": 0}
        
        # モジュールの分類 (カテゴリごとの数)
        categories = {}
        for module_id, info in self.modules_index["modules"].items():
            for tag in info.get("functionality", []):
                if tag in categories:
                    categories[tag] += 1
                else:
                    categories[tag] = 1
        
        # 依存関係の統計
        dependencies = {}
        for module_id, info in self.modules_index["modules"].items():
            for dep in info.get("dependencies", []):
                if dep in dependencies:
                    dependencies[dep] += 1
                else:
                    dependencies[dep] = 1
        
        return {
            "total_modules": len(self.modules_index["modules"]),
            "categories": categories,
            "dependencies": dependencies
        }