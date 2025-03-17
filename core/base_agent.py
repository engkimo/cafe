from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any, Optional
import datetime

class AgentState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    ERROR = "error"

class Memory:
    def __init__(self):
        self.conversation_history = []
        self.working_memory = {}
        
    def add_message(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content, "timestamp": datetime.datetime.now()})
        
    def get_recent_messages(self, n: int = 10):
        return self.conversation_history[-n:]
    
    def set_working_memory(self, key: str, value: Any):
        self.working_memory[key] = value
        
    def get_working_memory(self, key: str) -> Any:
        return self.working_memory.get(key)

class BaseAgent:
    def __init__(self, name: str, description: str, llm):
        self.name = name
        self.description = description
        self.llm = llm
        self.memory = Memory()
        self.state = AgentState.IDLE
        self.system_prompt = "You are an AI assistant that helps users accomplish tasks."
        self.next_step_prompt = "What should I do next to accomplish the user's request?"
        
    def run(self, request: str) -> str:
        """Process a user request and return a response"""
        self.state = AgentState.RUNNING
        self.memory.add_message("user", request)
        
        response = self.step()
        
        self.memory.add_message("assistant", response)
        self.state = AgentState.IDLE
        return response
    
    def step(self) -> str:
        """Take a single reasoning step"""
        messages = self.memory.get_recent_messages()
        prompt = self._build_prompt(messages)
        
        response = self.llm.generate_text(prompt)
        return response
    
    def _build_prompt(self, messages):
        """Build a prompt for the LLM using conversation history"""
        prompt = [{"role": "system", "content": self.system_prompt}]
        for message in messages:
            prompt.append({"role": message["role"], "content": message["content"]})
        return prompt