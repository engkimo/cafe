# main.py (プロジェクト環境統合版)
import os
import argparse
import json

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

def main():
    parser = argparse.ArgumentParser(description='Run the AI Agent system')
    parser.add_argument('--goal', type=str, help='The goal to accomplish')
    parser.add_argument('--workspace', type=str, default='./workspace', help='The workspace directory for file operations')
    parser.add_argument('--config', type=str, default='./config.json', help='Configuration file path')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # 設定ファイルのロード
    config = {}
    if os.path.exists(args.config):
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    # Initialize components
    llm = LLM(
        api_key=config.get('openai_api_key'),
        model=config.get('model', 'gpt-4-turbo'),
        temperature=config.get('temperature', 0.7)
    )
    
    # ワークスペースディレクトリを作成
    os.makedirs(args.workspace, exist_ok=True)
    
    # デバッグモードが有効な場合のログ設定
    if args.debug:
        import logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(args.workspace, 'debug.log')),
                logging.StreamHandler()
            ]
        )
    
    # タスクデータベースの初期化（SQLiteに変更）
    db_path = os.path.join(args.workspace, 'tasks.db')
    task_db = TaskDatabase(db_path)
    
    # ツールの初期化
    planning_tool = PlanningTool(llm, task_db)
    project_executor = PythonProjectExecuteTool(args.workspace, task_db)
    file_tool = FileTool(args.workspace)
    docker_tool = DockerExecuteTool(args.workspace)
    system_tool = SystemTool()
    
    # エージェントの初期化
    agent = AutoPlanAgent(
        "AutoPlanAgent", 
        "An agent that automatically plans and executes tasks", 
        llm, 
        task_db,
        args.workspace
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
    
    # ゴールが指定されている場合はフローを実行
    if args.goal:
        print(f"Starting execution with goal: '{args.goal}'")
        print(f"Working directory: {args.workspace}")
        
        result = flow.execute(args.goal)
        print(result)
    else:
        print("Please provide a goal using the --goal argument")
        print("Example: python main.py --goal 'Analyze the data in data.csv and create a visualization'")

if __name__ == "__main__":
    main()