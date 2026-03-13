"""Custom agent framework for Swarm-style multi-agent orchestration."""

import json
from typing import Callable, Optional, List, Dict, Any
from dataclasses import dataclass, field
from openai import OpenAI


@dataclass
class Agent:
    """Agent with instructions, tools, and handoff capabilities."""
    
    name: str
    instructions: str
    functions: List[Callable] = field(default_factory=list)
    model: str = "gpt-4-turbo-preview"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert agent to dictionary for logging."""
        return {
            "name": self.name,
            "instructions": self.instructions,
            "model": self.model,
            "functions": [f.__name__ for f in self.functions],
        }


@dataclass
class Handoff:
    """Represents a handoff to another agent."""
    
    agent: Agent
    context: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


class AgentOrchestrator:
    """Swarm-style agent orchestration with tool calling and handoffs."""
    
    def __init__(self, client: OpenAI, debug: bool = True):
        self.client = client
        self.debug = debug
        self.conversation_history: List[Dict[str, Any]] = []
        self.agent_trace: List[Dict[str, Any]] = []
        
    def run(
        self,
        agent: Agent,
        messages: List[Dict[str, str]],
        context: Dict[str, Any] = None,
        max_turns: int = 20,
    ) -> Dict[str, Any]:
        """
        Run agent orchestration with automatic handoffs.
        
        Args:
            agent: Starting agent
            messages: Initial messages
            context: Shared context across agents
            max_turns: Maximum conversation turns
            
        Returns:
            Final result dictionary
        """
        context = context or {}
        current_agent = agent
        self.conversation_history = messages.copy()
        turn_count = 0
        
        while turn_count < max_turns:
            turn_count += 1
            
            if self.debug:
                print(f"\n{'='*60}")
                print(f"Turn {turn_count}: {current_agent.name}")
                print(f"{'='*60}")
            
            # Log agent execution
            self.agent_trace.append({
                "turn": turn_count,
                "agent": current_agent.name,
                "timestamp": self._get_timestamp(),
            })
            
            # Prepare tools for function calling
            tools = self._prepare_tools(current_agent)
            
            # Add agent instructions as system message
            messages_with_instructions = [
                {"role": "system", "content": current_agent.instructions}
            ] + self.conversation_history
            
            # Call OpenAI with function calling
            response = self.client.chat.completions.create(
                model=current_agent.model,
                messages=messages_with_instructions,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
                temperature=0.3,
            )
            
            message = response.choices[0].message
            
            # Add assistant message to history
            self.conversation_history.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [tc.model_dump() for tc in message.tool_calls] if message.tool_calls else None,
            })
            
            if self.debug and message.content:
                print(f"\n{current_agent.name}: {message.content}")
            
            # Handle tool calls
            if message.tool_calls:
                handoff_result = self._handle_tool_calls(
                    current_agent,
                    message.tool_calls,
                    context
                )
                
                if handoff_result:
                    prev_agent_name = current_agent.name
                    # Agent requested handoff
                    current_agent = handoff_result.agent
                    
                    # Update context with handoff context
                    context.update(handoff_result.context)
                    
                    if self.debug:
                        print(f"\n→ Handoff to {current_agent.name}")
                        if handoff_result.reason:
                            print(f"  Reason: {handoff_result.reason}")
                    
                    # Log handoff
                    self.agent_trace.append({
                        "event": "handoff",
                        "from": prev_agent_name,
                        "to": current_agent.name,
                        "reason": handoff_result.reason,
                        "timestamp": self._get_timestamp(),
                    })

                    # Inject a context-summary message so the receiving agent
                    # can see what keys are available (the LLM cannot introspect
                    # the Python context dict directly).
                    ctx_keys = []
                    if context.get("input_format"):
                        ctx_keys.append(f"input_format={context['input_format']!r}")
                    if context.get("input_type"):
                        ctx_keys.append(f"input_type={context['input_type']!r}")
                    if "study_data" in context:
                        ctx_keys.append("study_data=<populated>")
                    if "report_data" in context:
                        ctx_keys.append("report_data=<populated>")
                    ctx_summary = ", ".join(ctx_keys) if ctx_keys else "none"
                    self.conversation_history.append({
                        "role": "user",
                        "content": (
                            f"Handoff from {prev_agent_name}: {handoff_result.reason}. "
                            f"Shared context keys: {ctx_summary}. "
                            "Please proceed immediately with the appropriate tool call."
                        ),
                    })
                    
                    continue
            
            # Check for explicit pipeline_done signal set by a tool
            if context.get("pipeline_done"):
                if self.debug:
                    print(f"\n✓ Pipeline complete (pipeline_done signal)")
                return {
                    "status": "success",
                    "final_message": message.content or "Pipeline complete.",
                    "context": context,
                    "agent_trace": self.agent_trace,
                }

            # Check if agent finished (no tool calls, no handoff, and is a terminal agent)
            # Only the RenderAgent signals done via pipeline_done flag (set by pipeline_complete tool).
            # Text-based heuristics are intentionally removed to prevent false-positive termination
            # when intermediate agents (NarrativeAgent, etc.) mention "complete" in chat text.
        
        # Max turns reached
        return {
            "status": "max_turns_reached",
            "final_message": "Maximum conversation turns reached",
            "context": context,
            "agent_trace": self.agent_trace,
        }
    
    def _prepare_tools(self, agent: Agent) -> Optional[List[Dict]]:
        """Convert agent functions to OpenAI tool format."""
        if not agent.functions:
            return None
        
        tools = []
        for func in agent.functions:
            # Get function metadata from docstring and annotations
            tool_def = {
                "type": "function",
                "function": {
                    "name": func.__name__,
                    "description": func.__doc__ or f"Execute {func.__name__}",
                    "parameters": self._get_function_parameters(func),
                }
            }
            tools.append(tool_def)
        
        return tools
    
    def _get_function_parameters(self, func: Callable) -> Dict:
        """Extract function parameters for OpenAI tool schema."""
        # Simple parameter extraction - in production, use inspect module
        # For now, return flexible schema
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }
    
    def _handle_tool_calls(
        self,
        agent: Agent,
        tool_calls: List,
        context: Dict[str, Any]
    ) -> Optional[Handoff]:
        """Execute tool calls and handle handoffs."""
        
        handoff_to_return = None
        
        for tool_call in tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
            
            if self.debug:
                print(f"\n→ Calling tool: {func_name}")
                if func_args:
                    print(f"  Args: {func_args}")
            
            # Find function in agent's functions
            func = next((f for f in agent.functions if f.__name__ == func_name), None)
            
            if not func:
                error_msg = f"Function {func_name} not found in {agent.name}"
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"error": error_msg}),
                })
                continue
            
            # Execute function with context
            try:
                # Pass context to function if it accepts it
                import inspect
                sig = inspect.signature(func)
                if "context" in sig.parameters:
                    func_args["context"] = context
                
                result = func(**func_args)
                
                # Check if result is a Handoff
                if isinstance(result, Handoff):
                    # Add tool response BEFORE returning handoff
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({"handoff": result.agent.name, "reason": result.reason}),
                    })
                    handoff_to_return = result
                    continue
                
                # Add tool result to conversation
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result) if not isinstance(result, str) else result,
                })
                
                if self.debug:
                    print(f"  Result: {str(result)[:200]}...")
                
            except Exception as e:
                error_msg = f"Error executing {func_name}: {str(e)}"
                if self.debug:
                    print(f"  Error: {error_msg}")
                
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps({"error": error_msg}),
                })
        
        return handoff_to_return
    
    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
