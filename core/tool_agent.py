from typing import Dict, List, Optional, Any
from .base_agent import BaseAgent, AgentState

class ToolCollection:
    def __init__(self):
        self.tools = {}
        
    def add_tool(self, tool):
        self.tools[tool.name] = tool
        
    def get_tool(self, name: str):
        return self.tools.get(name)
    
    def list_tools(self):
        return list(self.tools.keys())
    
    def tool_descriptions(self):
        return [tool.to_param() for tool in self.tools.values()]

class ToolCallResult:
    def __init__(self, tool_name: str, success: bool, result: Any, error: Optional[str] = None):
        self.tool_name = tool_name
        self.success = success
        self.result = result
        self.error = error

class ToolAgent(BaseAgent):
    def __init__(self, name: str, description: str, llm):
        super().__init__(name, description, llm)
        self.available_tools = ToolCollection()
        self.system_prompt += " You can use tools to help you accomplish tasks."
        
    def step(self) -> str:
        """Take a step using tools if necessary"""
        messages = self.memory.get_recent_messages()
        prompt = self._build_prompt(messages)
        
        # Get response from LLM with potential tool calls
        response = self.llm.generate_text(prompt)
        
        # Parse response for tool calls
        tool_calls = self._parse_tool_calls(response)
        
        if tool_calls:
            # Execute tool calls and get results
            tool_results = self.handle_tool_calls(tool_calls)
            
            # Add tool results to memory
            for result in tool_results:
                self.memory.add_message("tool", 
                                      f"Tool: {result.tool_name}\nSuccess: {result.success}\nResult: {result.result}" +
                                      (f"\nError: {result.error}" if result.error else ""))
            
            # Take another step to process the tool results
            return self.step()
        
        return response
    
    def _parse_tool_calls(self, response: str) -> List[Dict]:
        """Parse tool calls from the LLM response"""
        # Placeholder implementation - this would need to be adapted to your LLM's format
        tool_calls = []
        # Parsing logic here
        return tool_calls
    
    def handle_tool_calls(self, tool_calls: List[Dict]) -> List[ToolCallResult]:
        """Execute tool calls and return the results"""
        results = []
        
        for call in tool_calls:
            tool_name = call.get("name")
            tool_args = call.get("arguments", {})
            
            tool = self.available_tools.get_tool(tool_name)
            if not tool:
                results.append(ToolCallResult(tool_name, False, None, f"Tool '{tool_name}' not found"))
                continue
            
            try:
                result = tool.execute(**tool_args)
                results.append(ToolCallResult(tool_name, True, result))
            except Exception as e:
                results.append(ToolCallResult(tool_name, False, None, str(e)))
                
        return results
    
    def _build_prompt(self, messages):
        """Build a prompt for the LLM that includes tool descriptions"""
        prompt = super()._build_prompt(messages)
        
        # Add tool descriptions to the system prompt
        tool_desc = f"Available tools: {self.available_tools.tool_descriptions()}"
        prompt[0]["content"] += "\n\n" + tool_desc
        
        return prompt