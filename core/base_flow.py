from typing import Dict, List, Optional, Any
from .base_agent import BaseAgent

class BaseFlow:
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.primary_agent_key: str = None
        self.primary_agent: BaseAgent = None
        
    def execute(self, input_text: str) -> str:
        """Execute the flow with the given input"""
        if not self.primary_agent:
            return "No primary agent set. Please set a primary agent before executing the flow."
        
        return self.primary_agent.run(input_text)
    
    def get_agent(self, key: str) -> Optional[BaseAgent]:
        """Get an agent by key"""
        return self.agents.get(key)
    
    def add_agent(self, key: str, agent: BaseAgent) -> None:
        """Add an agent to the flow"""
        self.agents[key] = agent
        
        # If this is the first agent, set it as the primary agent
        if not self.primary_agent:
            self.set_primary_agent(key)
    
    def set_primary_agent(self, key: str) -> None:
        """Set the primary agent for the flow"""
        if key not in self.agents:
            raise ValueError(f"Agent with key '{key}' not found")
        
        self.primary_agent_key = key
        self.primary_agent = self.agents[key]