import os
import datetime
import json
from typing import Annotated, Dict, Any, List, TypedDict

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from api.chatbot.tools import (
    get_2026_driver_lineup,
    get_2026_regulations,
    get_recent_champions,
    get_driver_stats,
    get_telemetry_comparison
)

load_dotenv()


class ChatResponseOutput(BaseModel):
    """F1 Strategic Intelligence Engine output schema."""
    text_response: str = Field(description="The conversational text answer.")
    metadata: Dict[str, Any] = Field(description="Must include 'timestamp', 'session', and 'entities' (list of IDs like DRV_HAM).")
    visualizations: List[Dict[str, Any]] = Field(default_factory=list, description="List of chart or map configs (e.g. LineChart, BarChart, TrackMap).")
    tables: List[Dict[str, Any]] = Field(default_factory=list, description="List of tables with 'title', 'headers', and 'rows'.")

class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

tools = [
    get_2026_driver_lineup,
    get_2026_regulations,
    get_recent_champions,
    get_driver_stats,
    get_telemetry_comparison
]

# Ensure we have a fallback if key not set
api_key = os.environ.get("GROQ_API_KEY", "")
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0
)

llm_with_tools = llm.bind_tools(tools)
structured_llm = llm.bind(response_format={"type": "json_object"})

def call_model(state: State):
    system_prompt = (
        "You are the F1 Strategic Intelligence Engine (ParcFermé AI). "
        "You have access to tools providing 2026 driver lineups, regulations, history, and telemetry.\n"
        "Your goal is to answer questions using your tools. "
        "Once you have enough context, synthesize an answer. "
        "Include relevant driver ID tokens (e.g. DRV_HAM, DRV_VER, DRV_NOR) in your reasoning so the formatter can extract them.\n"
        "If the user asks for a comparison or telemetry, use get_telemetry_comparison to get the JSON structure and embed it in your final response.\n"
    )
    
    messages = [{"role": "system", "content": system_prompt}] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}
    
tool_node = ToolNode(tools)

def should_continue(state: State):
    messages = state["messages"]
    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "generate_json"

def generate_json(state: State):
    """Take the final reasoning and cast it to our enforced JSON schema."""
    messages = state["messages"]
    
    system_prompt = (
        "You are the ParcFermé formatting agent. Based on the conversation history, "
        "extract the final answer and structure it exactly as requested in this JSON schema:\n"
        "{\n"
        '  "text_response": "The conversational text answer.",\n'
        '  "metadata": {"timestamp": "...", "session": "...", "entities": ["DRV_HAM"]},\n'
        '  "visualizations": [],\n'
        '  "tables": []\n'
        "}\n"
        "Provide only the JSON object, nothing else. Copy tables/visualizations directly from tool outputs if provided.\n"
        f"The current time is {datetime.datetime.utcnow().isoformat()}Z."
    )
    conv = [{"role": "system", "content": system_prompt}] + messages
    result = structured_llm.invoke(conv)
    
    return {"messages": [AIMessage(content=result.content, name="final_json")]}

graph_builder = StateGraph(State)
graph_builder.add_node("agent", call_model)
graph_builder.add_node("tools", tool_node)
graph_builder.add_node("generate_json", generate_json)

graph_builder.add_edge(START, "agent")
graph_builder.add_conditional_edges("agent", should_continue, {"tools": "tools", "generate_json": "generate_json"})
graph_builder.add_edge("tools", "agent")
graph_builder.add_edge("generate_json", END)

memory = MemorySaver()
agent_app = graph_builder.compile(checkpointer=memory)

def chat_with_agent(message: str, thread_id: str = "default_thread") -> Dict[str, Any]:
    if not api_key:
        return {
            "text_response": "GROQ_API_KEY is not configured.",
            "metadata": {"timestamp": datetime.datetime.utcnow().isoformat() + "Z", "session": "Error", "entities": []},
            "visualizations": [],
            "tables": []
        }
        
    config = {"configurable": {"thread_id": thread_id}}
    
    events = agent_app.stream(
        {"messages": [("user", message)]},
        config,
        stream_mode="values"
    )
    
    final_state = None
    for event in events:
        final_state = event
        
    last_msg = final_state["messages"][-1]
    try:
        data = json.loads(last_msg.content)
        # Ensure fallback metadata
        if "metadata" not in data or not data["metadata"]:
            data["metadata"] = {"timestamp": datetime.datetime.utcnow().isoformat() + "Z", "session": "ParcFermé AI", "entities": []}
        return data
    except Exception as e:
        return {
            "text_response": last_msg.content,
            "metadata": {"timestamp": datetime.datetime.utcnow().isoformat() + "Z", "session": "Fallback Agent", "entities": []},
            "visualizations": [],
            "tables": []
        }
