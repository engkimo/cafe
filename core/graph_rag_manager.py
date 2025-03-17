# core/graph_rag_manager.py
import weaviate
from typing import Dict, List, Optional, Any
import os
import uuid
import json
import re
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

class GraphRAGManager:
    """GraphRAGを用いたエラーパターン学習と再利用のためのマネージャー"""
    
    def __init__(self, weaviate_url: str, openai_api_key: str = None):
        self.openai_client = OpenAI(api_key=openai_api_key or os.environ.get("OPENAI_API_KEY"))
        
        # Weaviateクライアントの初期化
        self.client = weaviate.Client(
            url=weaviate_url,
            additional_headers={"X-OpenAI-Api-Key": openai_api_key or os.environ.get("OPENAI_API_KEY")}
        )
        
        # スキーマの初期化確認と必要なら作成
        self._ensure_schema()
        
    def _ensure_schema(self):
        """必要なスキーマの作成・確認"""
        # 現在のスキーマを取得
        try:
            current_schema = self.client.schema.get()
            existing_classes = [c["class"] for c in current_schema["classes"]] if "classes" in current_schema else []
        except Exception as e:
            print(f"Error getting schema: {str(e)}")
            existing_classes = []

        # 作成するクラス定義
        schema_classes = [
            # エラーパターンクラス
            {
                "class": "ErrorPattern",
                "description": "エラーパターンと修正方法",
                "vectorizer": "text2vec-openai",
                "properties": [
                    {"name": "error_message", "dataType": ["text"]},
                    {"name": "error_type", "dataType": ["string"]},
                    {"name": "original_code", "dataType": ["text"]},
                    {"name": "fixed_code", "dataType": ["text"]},
                    {"name": "success_count", "dataType": ["int"]},
                    {"name": "context", "dataType": ["text"]}
                ]
            },
            # タスクテンプレートクラス
            {
                "class": "TaskTemplate",
                "description": "タスク種別ごとのコードテンプレート",
                "vectorizer": "text2vec-openai",
                "properties": [
                    {"name": "task_type", "dataType": ["string"]},
                    {"name": "description", "dataType": ["text"]},
                    {"name": "template_code", "dataType": ["text"]},
                    {"name": "success_count", "dataType": ["int"]},
                    {"name": "keywords", "dataType": ["string[]"]}
                ]
            },
            # 再利用可能なコードモジュールクラス
            {
                "class": "CodeModule",
                "description": "再利用可能なコードモジュール",
                "vectorizer": "text2vec-openai",
                "properties": [
                    {"name": "name", "dataType": ["string"]},
                    {"name": "description", "dataType": ["text"]},
                    {"name": "code", "dataType": ["text"]},
                    {"name": "dependencies", "dataType": ["string[]"]},
                    {"name": "functionality", "dataType": ["string[]"]}
                ]
            }
        ]
        
        # 不足しているクラスを作成
        for class_def in schema_classes:
            if class_def["class"] not in existing_classes:
                print(f"Creating class {class_def['class']}")
                self.client.schema.create_class(class_def)
        
        # クラス関係を追加
        try:
            # ErrorPatternの関係性
            if "ErrorPattern" in existing_classes:
                error_class = self.client.schema.get_class("ErrorPattern")
                error_props = [p["name"] for p in error_class["properties"]]
                
                # relatedTo関係がなければ追加
                if "relatedTo" not in error_props:
                    self.client.schema.property.create(
                        "ErrorPattern",
                        {
                            "name": "relatedTo",
                            "dataType": ["ErrorPattern"],
                            "description": "関連するエラーパターン"
                        }
                    )
                
                # usesModule関係がなければ追加
                if "usesModule" not in error_props:
                    self.client.schema.property.create(
                        "ErrorPattern",
                        {
                            "name": "usesModule",
                            "dataType": ["CodeModule"],
                            "description": "使用するコードモジュール"
                        }
                    )
            
            # TaskTemplateの関係性
            if "TaskTemplate" in existing_classes:
                template_class = self.client.schema.get_class("TaskTemplate")
                template_props = [p["name"] for p in template_class["properties"]]
                
                # usesModule関係がなければ追加
                if "usesModule" not in template_props:
                    self.client.schema.property.create(
                        "TaskTemplate",
                        {
                            "name": "usesModule",
                            "dataType": ["CodeModule"],
                            "description": "使用するコードモジュール"
                        }
                    )
                
                # preventsError関係がなければ追加
                if "preventsError" not in template_props:
                    self.client.schema.property.create(
                        "TaskTemplate",
                        {
                            "name": "preventsError",
                            "dataType": ["ErrorPattern"],
                            "description": "防止するエラーパターン"
                        }
                    )
            
            # CodeModuleの関係性
            if "CodeModule" in existing_classes:
                module_class = self.client.schema.get_class("CodeModule")
                module_props = [p["name"] for p in module_class["properties"]]
                
                # dependsOn関係がなければ追加
                if "dependsOn" not in module_props:
                    self.client.schema.property.create(
                        "CodeModule",
                        {
                            "name": "dependsOn",
                            "dataType": ["CodeModule"],
                            "description": "依存するコードモジュール"
                        }
                    )
        except Exception as e:
            print(f"Error setting up relationships: {str(e)}")
    
    def store_error_pattern(self, error_message, error_type, original_code, fixed_code, context=None):
        """エラーパターンを保存"""
        # 類似エラーパターンを検索
        similar_errors = self.find_similar_error_patterns(error_message, limit=1)
        
        if similar_errors and similar_errors[0]["certainty"] > 0.92:
            # 既存パターンの更新（成功カウントを増加）
            existing_id = similar_errors[0]["id"]
            
            # 成功カウントを取得
            current_count = similar_errors[0]["success_count"]
            
            # 更新処理
            self.client.data_object.update(
                class_name="ErrorPattern",
                uuid=existing_id,
                properties={
                    "success_count": current_count + 1,
                    # 必要に応じて他のフィールドも更新
                    "fixed_code": fixed_code
                }
            )
            
            return existing_id
        else:
            # 新規エラーパターンを作成
            error_id = str(uuid.uuid4())
            
            # Weaviateに保存
            properties = {
                "error_message": error_message,
                "error_type": error_type,
                "original_code": original_code,
                "fixed_code": fixed_code,
                "success_count": 1
            }
            
            if context:
                properties["context"] = context
                
            self.client.data_object.create(
                class_name="ErrorPattern",
                uuid=error_id,
                properties=properties
            )
            
            return error_id
    
    def find_similar_error_patterns(self, error_message, limit=5):
        """類似のエラーパターンを検索"""
        try:
            result = (
                self.client.query
                .get("ErrorPattern", ["error_message", "error_type", "fixed_code", "original_code", "success_count"])
                .with_near_text({"concepts": [error_message]})
                .with_limit(limit)
                .with_additional("certainty")
                .do()
            )
            
            # 結果を整形して返す
            if "data" in result and "Get" in result["data"] and "ErrorPattern" in result["data"]["Get"]:
                patterns = result["data"]["Get"]["ErrorPattern"]
                
                formatted_results = []
                for pattern in patterns:
                    formatted_results.append({
                        "id": pattern["_additional"]["id"],
                        "error_message": pattern["error_message"],
                        "error_type": pattern["error_type"],
                        "fixed_code": pattern["fixed_code"],
                        "original_code": pattern["original_code"],
                        "success_count": pattern["success_count"],
                        "certainty": pattern["_additional"]["certainty"]
                    })
                    
                return formatted_results
            
            return []
        except Exception as e:
            print(f"Error finding similar error patterns: {str(e)}")
            return []
        
    def get_recommended_fix(self, error_message, original_code, task_context=None):
        """エラーに対する推奨修正方法を取得"""
        similar_errors = self.find_similar_error_patterns(error_message)
        
        if not similar_errors:
            return None
            
        # 最適な修正方法を選択
        best_match = similar_errors[0]
        
        # 成功回数が多いパターンを優先
        for pattern in similar_errors[1:]:
            if pattern["success_count"] > best_match["success_count"] * 1.5 and pattern["certainty"] > 0.8:
                best_match = pattern
                
        # コードをAIで適応（オリジナルコードの文脈に合わせる）
        adapted_fix = self._adapt_fix_to_context(
            original_code=original_code,
            error_message=error_message,
            reference_fix=best_match["fixed_code"],
            reference_original=best_match["original_code"]
        )
                
        return {
            "original_error": best_match["error_message"],
            "fixed_code": adapted_fix or best_match["fixed_code"],
            "confidence": best_match["certainty"],
            "success_count": best_match["success_count"]
        }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _adapt_fix_to_context(self, original_code, error_message, reference_fix, reference_original):
        """修正コードを現在のコンテキストに適応させる"""
        try:
            prompt = f"""
            I need to adapt a fix for a Python code error to a new context.
            
            ERROR MESSAGE:
            {error_message}
            
            CURRENT CODE WITH ERROR:
            ```python
            {original_code}
            ```
            
            REFERENCE CODE THAT HAD SIMILAR ERROR:
            ```python
            {reference_original}
            ```
            
            FIX THAT WORKED FOR REFERENCE CODE:
            ```python
            {reference_fix}
            ```
            
            Please adapt the fix to the current code, considering its specific context.
            Only provide the complete fixed code with no explanations or markdown.
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=4000
            )
            
            # Extract the code without any markdown or explanations
            code = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            code = re.sub(r"```python\s+", "", code)
            code = re.sub(r"```\s*", "", code)
            
            return code
        except Exception as e:
            print(f"Error adapting fix to context: {str(e)}")
            return None
        
    def store_task_template(self, task_type, description, template_code, keywords=None):
        """タスクテンプレートを保存"""
        # 類似テンプレートを検索
        similar_templates = self.find_similar_task_templates(description, task_type, limit=1)
        
        if similar_templates and similar_templates[0]["certainty"] > 0.95:
            # 既存テンプレートの更新
            existing_id = similar_templates[0]["id"]
            current_count = similar_templates[0]["success_count"]
            
            self.client.data_object.update(
                class_name="TaskTemplate",
                uuid=existing_id,
                properties={
                    "success_count": current_count + 1,
                    "template_code": template_code  # テンプレートコードを更新
                }
            )
            
            return existing_id
        else:
            # 新規テンプレートを作成
            template_id = str(uuid.uuid4())
            
            properties = {
                "task_type": task_type,
                "description": description,
                "template_code": template_code,
                "success_count": 1
            }
            
            if keywords:
                properties["keywords"] = keywords
                
            self.client.data_object.create(
                class_name="TaskTemplate",
                uuid=template_id,
                properties=properties
            )
            
            return template_id
        
    def find_similar_task_templates(self, task_description, task_type=None, limit=5):
        """類似のタスクテンプレートを検索"""
        try:
            # 基本クエリの構築
            query = (
                self.client.query
                .get("TaskTemplate", ["task_type", "description", "template_code", "success_count", "keywords"])
                .with_near_text({"concepts": [task_description]})
                .with_limit(limit)
                .with_additional("certainty")
            )
            
            # タスクタイプが指定されている場合はフィルタを追加
            if task_type:
                query = query.with_where({
                    "path": ["task_type"],
                    "operator": "Equal",
                    "valueString": task_type
                })
            
            # クエリ実行
            result = query.do()
            
            # 結果を整形して返す
            if "data" in result and "Get" in result["data"] and "TaskTemplate" in result["data"]["Get"]:
                templates = result["data"]["Get"]["TaskTemplate"]
                
                formatted_results = []
                for template in templates:
                    formatted_results.append({
                        "id": template["_additional"]["id"],
                        "task_type": template["task_type"],
                        "description": template["description"],
                        "template_code": template["template_code"],
                        "success_count": template["success_count"],
                        "keywords": template.get("keywords", []),
                        "certainty": template["_additional"]["certainty"]
                    })
                    
                return formatted_results
            
            return []
        except Exception as e:
            print(f"Error finding similar task templates: {str(e)}")
            return []
        
    def get_task_template(self, task_description, task_type=None):
        """タスクに適したテンプレートを取得"""
        similar_templates = self.find_similar_task_templates(task_description, task_type)
        
        if not similar_templates:
            return None
            
        # 最適なテンプレートを選択
        best_match = similar_templates[0]
        
        # 成功回数が多いテンプレートを優先
        for template in similar_templates[1:]:
            if template["success_count"] > best_match["success_count"] * 1.5 and template["certainty"] > 0.85:
                best_match = template
                
        # 適応させたテンプレートを返す
        return {
            "task_type": best_match["task_type"],
            "template_code": best_match["template_code"],
            "confidence": best_match["certainty"],
            "success_count": best_match["success_count"],
            "keywords": best_match.get("keywords", [])
        }
        
    def store_code_module(self, name, description, code, dependencies=None, functionality=None):
        """再利用可能なコードモジュールを保存"""
        # 同名モジュールを検索
        existing_modules = self._find_module_by_name(name)
        
        if existing_modules:
            # 既存モジュールの更新
            existing_id = existing_modules[0]["id"]
            
            properties = {
                "description": description,
                "code": code
            }
            
            if dependencies:
                properties["dependencies"] = dependencies
                
            if functionality:
                properties["functionality"] = functionality
                
            self.client.data_object.update(
                class_name="CodeModule",
                uuid=existing_id,
                properties=properties
            )
            
            return existing_id
        else:
            # 新規モジュールを作成
            module_id = str(uuid.uuid4())
            
            properties = {
                "name": name,
                "description": description,
                "code": code
            }
            
            if dependencies:
                properties["dependencies"] = dependencies
                
            if functionality:
                properties["functionality"] = functionality
                
            self.client.data_object.create(
                class_name="CodeModule",
                uuid=module_id,
                properties=properties
            )
            
            return module_id
    
    def _find_module_by_name(self, name):
        """モジュール名で検索"""
        try:
            result = (
                self.client.query
                .get("CodeModule", ["name", "description", "code", "dependencies", "functionality"])
                .with_where({
                    "path": ["name"],
                    "operator": "Equal",
                    "valueString": name
                })
                .do()
            )
            
            if "data" in result and "Get" in result["data"] and "CodeModule" in result["data"]["Get"]:
                modules = result["data"]["Get"]["CodeModule"]
                
                formatted_results = []
                for module in modules:
                    formatted_results.append({
                        "id": module["_additional"]["id"] if "_additional" in module else None,
                        "name": module["name"],
                        "description": module["description"],
                        "code": module["code"],
                        "dependencies": module.get("dependencies", []),
                        "functionality": module.get("functionality", [])
                    })
                    
                return formatted_results
            
            return []
        except Exception as e:
            print(f"Error finding module by name: {str(e)}")
            return []
        
    def find_code_modules(self, query_text, functionality=None, limit=5):
        """コードモジュールをテキストで検索"""
        try:
            # 基本クエリの構築
            query = (
                self.client.query
                .get("CodeModule", ["name", "description", "code", "dependencies", "functionality"])
                .with_near_text({"concepts": [query_text]})
                .with_limit(limit)
                .with_additional("certainty")
            )
            
            # 機能が指定されている場合はフィルタを追加
            if functionality:
                query = query.with_where({
                    "path": ["functionality"],
                    "operator": "ContainsAny",
                    "valueStringArray": functionality if isinstance(functionality, list) else [functionality]
                })
            
            # クエリ実行
            result = query.do()
            
            # 結果を整形して返す
            if "data" in result and "Get" in result["data"] and "CodeModule" in result["data"]["Get"]:
                modules = result["data"]["Get"]["CodeModule"]
                
                formatted_results = []
                for module in modules:
                    formatted_results.append({
                        "id": module["_additional"]["id"],
                        "name": module["name"],
                        "description": module["description"],
                        "code": module["code"],
                        "dependencies": module.get("dependencies", []),
                        "functionality": module.get("functionality", []),
                        "certainty": module["_additional"]["certainty"]
                    })
                    
                return formatted_results
            
            return []
        except Exception as e:
            print(f"Error finding code modules: {str(e)}")
            return []
        
    def get_relevant_modules(self, task_description, limit=3):
        """タスクに関連する再利用可能なモジュールを取得"""
        try:
            # キーワードを抽出
            keywords = self._extract_keywords(task_description)
            
            # 複数のアプローチでモジュールを検索
            modules_by_text = self.find_code_modules(task_description, limit=limit*2)
            
            # 類似モジュールをスコアでソート
            sorted_modules = sorted(modules_by_text, key=lambda x: x["certainty"], reverse=True)
            
            # トップのモジュールを返す
            return sorted_modules[:limit]
        except Exception as e:
            print(f"Error getting relevant modules: {str(e)}")
            return []
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=3))
    def _extract_keywords(self, text):
        """テキストからキーワードを抽出"""
        try:
            prompt = f"""
            Extract 5-7 technical keywords from this task description:
            "{text}"
            
            Return only a comma-separated list of keywords, no explanations.
            """
            
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=100
            )
            
            keywords = response.choices[0].message.content.strip()
            return [kw.strip() for kw in keywords.split(",")]
        except Exception as e:
            print(f"Error extracting keywords: {str(e)}")
            return []