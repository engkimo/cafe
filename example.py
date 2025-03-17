# example.py (プロジェクト環境統合版)
import os
from dotenv import load_dotenv

from core.llm import LLM
from core.task_database import TaskDatabase
from core.tools.planning_tool import PlanningTool
from core.tools.python_project_execute import PythonProjectExecuteTool
from core.tools.file_tool import FileTool
# 新しいツールをインポート
from core.tools.docker_execute import DockerExecuteTool
from core.tools.system_tool import SystemTool
from core.auto_plan_agent import AutoPlanAgent
from core.planning_flow import PlanningFlow

# .env ファイルから環境変数をロード
load_dotenv()

def setup_agent_system(workspace_dir="./workspace"):
    """Set up the AI Agent system with all necessary components"""
    # ワークスペースディレクトリを作成
    os.makedirs(workspace_dir, exist_ok=True)
    
    # LLMの初期化
    llm = LLM(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_MODEL", "gpt-4-turbo")
    )
    
    # タスクデータベースの初期化（SQLiteに変更）
    db_path = os.path.join(workspace_dir, "tasks.db")
    task_db = TaskDatabase(db_path)
    
    # ツールの初期化
    planning_tool = PlanningTool(llm, task_db)
    project_executor = PythonProjectExecuteTool(workspace_dir, task_db)
    file_tool = FileTool(workspace_dir)
    docker_tool = DockerExecuteTool(workspace_dir)
    system_tool = SystemTool()
    
    # エージェントの初期化
    agent = AutoPlanAgent(
        "AutoPlanAgent", 
        "An agent that automatically plans, executes, and repairs tasks", 
        llm, 
        task_db,
        workspace_dir
    )
    agent.set_planner(planning_tool)
    agent.set_project_executor(project_executor)
    agent.available_tools.add_tool(file_tool)
    agent.available_tools.add_tool(docker_tool)
    agent.available_tools.add_tool(system_tool)
    
    # フローの初期化
    flow = PlanningFlow(llm, task_db)
    flow.add_agent("auto_plan", agent)
    flow.set_planning_tool(planning_tool)
    
    return flow

def main():
    # エージェントシステムのセットアップ
    flow = setup_agent_system()
    
    # タスク1: データ分析
    print("--- Example 1: Data Analysis ---")
    goal1 = """
    1. Create a CSV file with random data (10 rows, 3 columns: date, value1, value2)
    2. Read the CSV file and calculate statistics
    3. Generate a summary report with the findings
    """
    
    result1 = flow.execute(goal1)
    print(result1)
    
    # タスク2: Webデータ処理
    print("\n--- Example 2: Web Processing ---")
    goal2 = """
    1. Create a Python script that generates a simple HTML page with a table of data
    2. Save the HTML to a file
    3. Create another script that reads the HTML file, extracts the table data, and calculates the sum of all numerical values
    """
    
    result2 = flow.execute(goal2)
    print(result2)
    
    # # タスク3: エラー修復が必要なタスク
    print("\n--- Example 3: Task with Potential Failures ---")
    goal3 = """
    1. Create a Python function that attempts to parse a JSON string with intentional errors
    2. Implement error handling to fix the JSON string
    3. Save the corrected JSON to a file
    """
    
    result3 = flow.execute(goal3)
    print(result3)

if __name__ == "__main__":
    main()