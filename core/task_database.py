# core/task_database.py
import os
import sqlite3
import uuid
import json
import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"

class Task:
    def __init__(self, 
                 description: str, 
                 plan_id: str, 
                 dependencies: List[str] = None, 
                 code: str = None,
                 task_id: str = None):
        self.id = task_id or str(uuid.uuid4())
        self.description = description
        self.plan_id = plan_id
        self.code = code
        self.dependencies = dependencies or []
        self.status = TaskStatus.PENDING
        self.result = None
        self.created_at = datetime.datetime.now()
        self.updated_at = datetime.datetime.now()
    
    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "plan_id": self.plan_id,
            "code": self.code,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "result": self.result,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data):
        task = cls(
            description=data["description"],
            plan_id=data["plan_id"],
            dependencies=data.get("dependencies", []),
            code=data.get("code"),
            task_id=data["id"]
        )
        task.status = TaskStatus(data["status"])
        task.result = data.get("result")
        task.created_at = datetime.datetime.fromisoformat(data["created_at"])
        task.updated_at = datetime.datetime.fromisoformat(data["updated_at"])
        return task

class Plan:
    def __init__(self, goal: str, plan_id: str = None):
        self.id = plan_id or str(uuid.uuid4())
        self.goal = goal
        self.tasks = []
        self.status = TaskStatus.PENDING
        self.created_at = datetime.datetime.now()
        self.updated_at = datetime.datetime.now()

class TaskDatabase:
    def __init__(self, db_path: str):
        """
        Args:
            db_path: SQLiteデータベースファイルのパス
        """
        self.db_path = db_path
        self.connection = None
        self._init_database()
    
    def _init_database(self):
        """データベースの初期化とテーブル作成"""
        # データベースディレクトリが存在しない場合は作成
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)

        # データベースに接続
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        
        cursor = self.connection.cursor()

        # plansテーブル作成
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)

        # tasksテーブル作成
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                description TEXT NOT NULL,
                code TEXT,
                status TEXT NOT NULL,
                result TEXT,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                FOREIGN KEY (plan_id) REFERENCES plans (id)
            )
        """)

        # task_dependenciesテーブル作成
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_dependencies (
                task_id TEXT NOT NULL,
                dependency_id TEXT NOT NULL,
                PRIMARY KEY (task_id, dependency_id),
                FOREIGN KEY (task_id) REFERENCES tasks (id),
                FOREIGN KEY (dependency_id) REFERENCES tasks (id)
            )
        """)

        # error_historyテーブル作成
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS error_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                error_message TEXT NOT NULL,
                attempted_fix TEXT,
                success BOOLEAN NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks (id)
            )
        """)

        self.connection.commit()
    
    def add_plan(self, goal: str) -> str:
        """新しいプランを追加してIDを返す"""
        plan = Plan(goal)
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO plans (id, goal, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                plan.id,
                plan.goal,
                plan.status.value,
                plan.created_at.isoformat(),
                plan.updated_at.isoformat(),
            ),
        )
        self.connection.commit()
        return plan.id

    def add_task(
        self, description: str, plan_id: str, dependencies: List[str] = None, code: str = None
    ) -> str:
        """新しいタスクを追加してIDを返す"""
        task = Task(description, plan_id, dependencies, code)
        cursor = self.connection.cursor()
        # タスクの追加
        cursor.execute(
            """
            INSERT INTO tasks (id, plan_id, description, code, status, result, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.plan_id,
                task.description,
                task.code,
                task.status.value,
                task.result,
                task.created_at.isoformat(),
                task.updated_at.isoformat(),
            ),
        )

        # 依存関係の追加
        if dependencies:
            for dep_id in dependencies:
                cursor.execute(
                    """
                    INSERT INTO task_dependencies (task_id, dependency_id)
                    VALUES (?, ?)
                    """,
                    (task.id, dep_id),
                )

        self.connection.commit()
        return task.id

    def update_task(
        self, task_id: str, status: TaskStatus = None, result: str = None
    ) -> None:
        """タスクのステータスや結果を更新"""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task with ID {task_id} not found")

        if status is not None:
            task.status = status

        if result is not None:
            task.result = result

        task.updated_at = datetime.datetime.now()

        cursor = self.connection.cursor()
        cursor.execute(
            """
            UPDATE tasks
            SET status = ?, result = ?, updated_at = ?
            WHERE id = ?
            """,
            (task.status.value, task.result, task.updated_at.isoformat(), task.id),
        )
        self.connection.commit()

    def update_task_code(self, task_id: str, code: str) -> None:
        """タスクのコードを更新"""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task with ID {task_id} not found")

        task.code = code
        task.updated_at = datetime.datetime.now()

        cursor = self.connection.cursor()
        cursor.execute(
            """
            UPDATE tasks
            SET code = ?, updated_at = ?
            WHERE id = ?
            """,
            (task.code, task.updated_at.isoformat(), task.id),
        )
        self.connection.commit()

    def get_task(self, task_id: str) -> Optional[Task]:
        """IDでタスクを取得"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()

        if not row:
            return None

        # 依存関係を取得
        cursor.execute(
            "SELECT dependency_id FROM task_dependencies WHERE task_id = ?",
            (task_id,),
        )
        dependencies = [dep[0] for dep in cursor.fetchall()]

        # Taskオブジェクトを作成
        task_dict = dict(row)
        task_dict["dependencies"] = dependencies

        return Task.from_dict(task_dict)

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """IDでプランを取得"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM plans WHERE id = ?", (plan_id,))
        row = cursor.fetchone()

        if not row:
            return None

        # プランに属するタスクIDを取得
        cursor.execute("SELECT id FROM tasks WHERE plan_id = ?", (plan_id,))
        task_ids = [task[0] for task in cursor.fetchall()]

        # Planオブジェクトを作成
        plan_dict = dict(row)
        plan = Plan(goal=plan_dict["goal"], plan_id=plan_dict["id"])
        plan.tasks = task_ids
        plan.status = TaskStatus(plan_dict["status"])
        
        # 日付文字列をdatetimeオブジェクトに変換
        plan.created_at = datetime.datetime.fromisoformat(plan_dict["created_at"])
        plan.updated_at = datetime.datetime.fromisoformat(plan_dict["updated_at"])

        return plan

    def get_tasks_by_plan(self, plan_id: str) -> List[Task]:
        """プランに属するすべてのタスクを取得"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM tasks WHERE plan_id = ?", (plan_id,))
        rows = cursor.fetchall()

        tasks = []
        for row in rows:
            task_id = row["id"]
            # 依存関係を取得
            cursor.execute(
                "SELECT dependency_id FROM task_dependencies WHERE task_id = ?",
                (task_id,),
            )
            dependencies = [dep[0] for dep in cursor.fetchall()]

            # Taskオブジェクトを作成
            task_dict = dict(row)
            task_dict["dependencies"] = dependencies

            tasks.append(Task.from_dict(task_dict))

        return tasks

    def get_failed_tasks(self) -> List[Task]:
        """失敗したすべてのタスクを取得"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM tasks WHERE status = ?", (TaskStatus.FAILED.value,))
        rows = cursor.fetchall()

        tasks = []
        for row in rows:
            task_id = row["id"]
            # 依存関係を取得
            cursor.execute(
                "SELECT dependency_id FROM task_dependencies WHERE task_id = ?",
                (task_id,),
            )
            dependencies = [dep[0] for dep in cursor.fetchall()]

            # Taskオブジェクトを作成
            task_dict = dict(row)
            task_dict["dependencies"] = dependencies

            tasks.append(Task.from_dict(task_dict))

        return tasks

    def get_pending_tasks(self) -> List[Task]:
        """未実行のすべてのタスクを取得"""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM tasks WHERE status = ?", (TaskStatus.PENDING.value,))
        rows = cursor.fetchall()

        tasks = []
        for row in rows:
            task_id = row["id"]
            # 依存関係を取得
            cursor.execute(
                "SELECT dependency_id FROM task_dependencies WHERE task_id = ?",
                (task_id,),
            )
            dependencies = [dep[0] for dep in cursor.fetchall()]

            # Taskオブジェクトを作成
            task_dict = dict(row)
            task_dict["dependencies"] = dependencies

            tasks.append(Task.from_dict(task_dict))

        return tasks

    def get_runnable_tasks(self) -> List[Task]:
        """実行可能なタスク（依存関係がすべて完了）を取得"""
        pending_tasks = self.get_pending_tasks()
        runnable = []

        for task in pending_tasks:
            # 依存関係がすべて完了しているかチェック
            dependencies_met = True
            for dep_id in task.dependencies:
                dep_task = self.get_task(dep_id)
                if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                    dependencies_met = False
                    break

            if dependencies_met:
                runnable.append(task)

        return runnable
        
    def add_error_history(self, task_id: str, error_message: str, attempted_fix: str = None, success: bool = False) -> int:
        """エラー履歴を追加する"""
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO error_history (task_id, error_message, attempted_fix, success, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                task_id,
                error_message,
                attempted_fix,
                success,
                datetime.datetime.now().isoformat(),
            ),
        )
        self.connection.commit()
        return cursor.lastrowid

    def get_error_history(self, task_id: str) -> List[Dict]:
        """タスクのエラー履歴を取得"""
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT * FROM error_history
            WHERE task_id = ?
            ORDER BY timestamp DESC
            """,
            (task_id,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def add_error_pattern(self, pattern: str, solution: str) -> int:
        """エラーパターンと解決策を追加"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO error_patterns (pattern, solution, success_count, failure_count, last_used)
                VALUES (?, ?, 0, 0, ?)
                """,
                (pattern, solution, datetime.datetime.now().isoformat()),
            )
            conn.commit()
            return cursor.lastrowid

    def update_error_pattern_stats(
        self, pattern_id: int, success: bool
    ) -> None:
        """エラーパターンの成功/失敗カウントを更新"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if success:
                cursor.execute(
                    """
                    UPDATE error_patterns
                    SET success_count = success_count + 1, last_used = ?
                    WHERE id = ?
                    """,
                    (datetime.datetime.now().isoformat(), pattern_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE error_patterns
                    SET failure_count = failure_count + 1, last_used = ?
                    WHERE id = ?
                    """,
                    (datetime.datetime.now().isoformat(), pattern_id),
                )
            conn.commit()

    def find_similar_errors(self, error_message: str, limit: int = 5) -> List[Dict]:
        """類似したエラーパターンを検索"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # エラーメッセージからキーワードを抽出
            keywords = [word for word in error_message.split() if len(word) > 3]
            if not keywords:
                return []
                
            # LIKE句を使った検索条件を構築
            conditions = []
            params = []
            for keyword in keywords:
                conditions.append("pattern LIKE ?")
                params.append(f"%{keyword}%")
                
            query = f"""
            SELECT *, 
                  (success_count * 1.0 / (success_count + failure_count + 0.01)) as success_rate
            FROM error_patterns
            WHERE {" OR ".join(conditions)}
            ORDER BY success_rate DESC, last_used DESC
            LIMIT ?
            """
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]