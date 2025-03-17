from typing import Dict, List, Optional, Any
from .base_flow import BaseFlow
from .task_database import TaskDatabase, TaskStatus
from .base_agent import BaseAgent

class PlanningFlow(BaseFlow):
    def __init__(self, llm, task_db: TaskDatabase):
        super().__init__()
        self.llm = llm
        self.planning_tool = None  # Will be set later
        self.executor_keys: List[str] = []
        self.active_plan_id: str = None
        self.current_step_index: int = 0
        self.task_db = task_db
        
    def set_planning_tool(self, planning_tool):
        self.planning_tool = planning_tool
        
    def execute(self, input_text: str) -> str:
        """Execute the planning flow with the given input"""
        # Use the primary agent to generate a plan
        if not self.primary_agent:
            return "No primary agent set. Please set a primary agent before executing the flow."
        
        # Generate and execute the plan
        response = self.primary_agent.execute_plan(input_text)
        
        # Start monitoring the execution of the plan
        self.monitor_execution()
        
        return response
    
    def get_executor(self, step_type: str) -> Optional[BaseAgent]:
        """Get an appropriate executor agent for a step type"""
        for key in self.executor_keys:
            agent = self.get_agent(key)
            if agent and step_type.lower() in agent.name.lower():
                return agent
        
        # Default to primary agent if no specific executor found
        return self.primary_agent
    
    def monitor_execution(self) -> None:
        """Monitor and manage the execution of the current plan"""
        if not self.active_plan_id:
            return
        
        # Check for failed tasks
        failed_tasks = self.task_db.get_failed_tasks()
        
        for task in failed_tasks:
            # Try to handle failed tasks
            self.handle_task_failure(task.id)
    
    def handle_task_failure(self, task_id: str) -> None:
        """Handle a failed task by attempting to repair it"""
        # Use the primary agent to repair the task
        if isinstance(self.primary_agent, AutoPlanAgent):  # Assuming AutoPlanAgent has repair capability
            success = self.primary_agent.repair_failed_task(task_id)
            
            if not success:
                # Log the failure for human intervention
                print(f"Failed to automatically repair task {task_id}. Human intervention may be required.")
