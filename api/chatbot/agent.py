"""
ParcFermé AI — LangGraph Agent with Query Understanding Layer.

Architecture:

    START
      ↓
    query_understanding  (LLM entity extraction + local scoring)
      ↓
    confidence_gate  (conditional router)
      ├─ ≥ 0.85  →  agent  (LLM + tool calls)
      ├─ 0.50–0.84  →  clarification  (targeted question)
      └─ < 0.50  →  rephrase  (request more detail)
           ↓                        ↓
         [tools ←→ agent]    generate_json
           ↓
         answer_validator
           ├─ pass  →  generate_json
           └─ fail  →  clarification
                          ↓
                       generate_json
                          ↓
                         END
"""

import os
import datetime
import json
import logging
from typing import Annotated, Dict, Any, List, TypedDict, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
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
    get_telemetry_comparison,
)
from api.chatbot.query_understanding import (
    analyze_query,
    build_enhanced_query,
    build_clarification,
    build_validation_prompt,
    parse_validation_result,
    parse_llm_extraction,
    EXTRACTION_SYSTEM_PROMPT,
    VALIDATION_SYSTEM_PROMPT,
    build_llm_extraction_prompt,
    HIGH_CONFIDENCE,
    MEDIUM_CONFIDENCE,
)

load_dotenv()
logger = logging.getLogger(__name__)


# ── Output schema ──────────────────────────────────────────────────────
class ChatResponseOutput(BaseModel):
    """F1 Strategic Intelligence Engine output schema."""
    text_response: str = Field(description="The conversational text answer.")
    metadata: Dict[str, Any] = Field(
        description="Must include 'timestamp', 'session', and 'entities' (list of IDs like DRV_HAM)."
    )
    visualizations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of chart or map configs (e.g. LineChart, BarChart, TrackMap).",
    )
    tables: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of tables with 'title', 'headers', and 'rows'.",
    )


# ── State ──────────────────────────────────────────────────────────────
class State(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    # Query understanding output (populated by query_understanding node)
    query_analysis: Optional[Dict[str, Any]]
    # Cross-turn entity memory (persisted via MemorySaver checkpointer)
    resolved_entities: Optional[List[Dict[str, Any]]]
    # Original user prompt (preserved for validation)
    original_prompt: Optional[str]


# ── LLM + Tools ────────────────────────────────────────────────────────
tools = [
    get_2026_driver_lineup,
    get_2026_regulations,
    get_recent_champions,
    get_driver_stats,
    get_telemetry_comparison,
]

api_key = os.environ.get("GROQ_API_KEY", "").strip()
os.environ["GROQ_API_KEY"] = api_key

llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0)
llm_with_tools = llm.bind_tools(tools)
structured_llm = llm.bind(response_format={"type": "json_object"})


# ═══════════════════════════════════════════════════════════════════════
#  NODE 1: QUERY UNDERSTANDING
# ═══════════════════════════════════════════════════════════════════════

def query_understanding(state: State):
    """
    Extract intent + entities via LLM, score confidence, decide routing.
    Uses conversation memory for pronoun resolution.
    """
    messages = state["messages"]
    # Find the latest human message
    user_msg = ""
    for m in reversed(messages):
        if isinstance(m, HumanMessage) or getattr(m, "type", "") == "human":
            user_msg = m.content if hasattr(m, "content") else str(m)
            break

    if not user_msg:
        # Fallback: treat entire last message as the prompt
        user_msg = str(messages[-1].content) if messages else ""

    # Retrieve cross-turn entity memory
    conv_entities = state.get("resolved_entities") or []

    # ── LLM-powered extraction ──────────────────────────────────────
    llm_result = None
    try:
        extraction_prompt = build_llm_extraction_prompt(user_msg, conv_entities)
        extraction_response = structured_llm.invoke([
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": extraction_prompt},
        ])
        llm_result = parse_llm_extraction(extraction_response.content)
    except Exception as e:
        logger.warning("LLM extraction failed, falling back to local: %s", e)

    # ── Run full analysis pipeline ──────────────────────────────────
    analysis = analyze_query(
        user_prompt=user_msg,
        conversation_entities=conv_entities,
        llm_extraction=llm_result,
    )

    # ── Update cross-turn entity memory ─────────────────────────────
    new_entities = list(conv_entities)  # copy
    for d in analysis["entities"].get("drivers", []):
        # Avoid duplicates
        if not any(e.get("id") == d["id"] for e in new_entities):
            new_entities.append(d)
    # Keep last 10 entities to avoid unbounded growth
    new_entities = new_entities[-10:]

    return {
        "query_analysis": analysis,
        "resolved_entities": new_entities,
        "original_prompt": user_msg,
    }


# ═══════════════════════════════════════════════════════════════════════
#  NODE 2: CONFIDENCE GATE (conditional edge)
# ═══════════════════════════════════════════════════════════════════════

def confidence_gate(state: State):
    """Route based on confidence score."""
    analysis = state.get("query_analysis") or {}
    confidence = analysis.get("confidence", 0.0)

    if confidence >= HIGH_CONFIDENCE:
        return "agent"
    elif confidence >= MEDIUM_CONFIDENCE:
        return "clarification"
    else:
        return "rephrase"


# ═══════════════════════════════════════════════════════════════════════
#  NODE 3a: CLARIFICATION (medium confidence)
# ═══════════════════════════════════════════════════════════════════════

def clarification_node(state: State):
    """Return a targeted clarification — no LLM call needed."""
    analysis = state.get("query_analysis") or {}
    msg = analysis.get("clarification_message") or (
        "I need more details to answer accurately. "
        "Could you specify the drivers, Grand Prix, or session?"
    )
    return {
        "messages": [AIMessage(content=msg, name="clarification")],
    }


# ═══════════════════════════════════════════════════════════════════════
#  NODE 3b: REPHRASE (low confidence)
# ═══════════════════════════════════════════════════════════════════════

def rephrase_node(state: State):
    """Return a rephrase request — no LLM call needed."""
    analysis = state.get("query_analysis") or {}
    issues = analysis.get("issues", [])
    reason = issues[0] if issues else "Your query is too ambiguous for me to process."

    msg = (
        f"I'm not confident I understand your question. {reason}\n\n"
        "Please rephrase with more specific details. For example:\n"
        "- Name the drivers, teams, or Grand Prix\n"
        "- Specify the session (Qualifying, Race)\n"
        '- Example: "Compare Hamilton vs Verstappen at Monza qualifying"'
    )
    return {
        "messages": [AIMessage(content=msg, name="rephrase")],
    }


# ═══════════════════════════════════════════════════════════════════════
#  NODE 4: AGENT (main reasoning + tool use)
# ═══════════════════════════════════════════════════════════════════════

AGENT_SYSTEM_PROMPT = """\
You are the F1 Strategic Intelligence Engine (ParcFermé AI).
You have access to tools providing 2026 driver lineups, regulations, history, and telemetry.

BEFORE ANSWERING, follow these rules strictly:

1. Use the Enhanced Query (EQ) provided below — it contains resolved entities and intent.
2. Never invent missing driver names, races, sessions, or telemetry values.
3. Never fabricate speed, braking, lap-time, or corner data that did not come from a tool.
4. If the EQ says two entities are the same driver, DO NOT compare them — the clarification node already handled this.
5. DO NOT use `get_telemetry_comparison` UNLESS the intent is "telemetry" AND all required fields (drivers, GP, session) are provided.
6. If the user asks generally "Tell me about X", use `get_driver_stats`. Do NOT generate map/chart visualizations unless explicitly requested.
7. Include entity IDs (e.g. DRV_HAM) in your reasoning so the formatter can extract them.
8. Answer ONLY what the user asked. Do not add unrequested information.
9. Include uncertainty explicitly instead of guessing. Say "I don't have data on X" rather than making it up.
10. Define any specialized F1 terms you use (X-Mode, Z-Mode, DRS, MGU-H, etc.).

{enhanced_query}
"""


def call_model(state: State):
    """Main agent LLM call with Enhanced Query injected."""
    analysis = state.get("query_analysis") or {}
    eq = analysis.get("enhanced_query") or ""

    system_prompt = AGENT_SYSTEM_PROMPT.format(
        enhanced_query=f"--- Enhanced Query ---\n{eq}" if eq else ""
    )

    # Prune conversation history to last 6 messages (Groq TPM limit)
    recent_messages = state["messages"][-6:] if len(state["messages"]) > 6 else state["messages"]
    while recent_messages and getattr(recent_messages[0], "type", "") == "tool":
        recent_messages.pop(0)

    messages = [{"role": "system", "content": system_prompt}] + recent_messages
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


# ═══════════════════════════════════════════════════════════════════════
#  NODE 5: TOOL ROUTING (conditional edge from agent)
# ═══════════════════════════════════════════════════════════════════════

tool_node = ToolNode(tools)


def should_continue(state: State):
    """Route: tools if tool_calls present, else answer_validator."""
    messages = state["messages"]
    last_message = messages[-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "answer_validator"


# ═══════════════════════════════════════════════════════════════════════
#  NODE 6: ANSWER VALIDATOR
# ═══════════════════════════════════════════════════════════════════════

def answer_validator(state: State):
    """
    Validate the agent's answer against the original prompt.
    If validation fails, redirect to clarification with failure reason.
    """
    messages = state["messages"]
    analysis = state.get("query_analysis") or {}
    original = state.get("original_prompt") or ""

    # Get the agent's proposed answer
    proposed = messages[-1].content if messages else ""

    try:
        validation_prompt = build_validation_prompt(
            original_prompt=original,
            intent=analysis.get("intent", "general"),
            entities=analysis.get("entities", {}),
            proposed_answer=proposed,
        )

        val_response = structured_llm.invoke([
            {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
            {"role": "user", "content": validation_prompt},
        ])

        result = parse_validation_result(val_response.content)

        if not result.get("passed", True):
            failures = result.get("failures", [])
            failure_reasons = "; ".join(
                f'{f["check"]}: {f["reason"]}' for f in failures
            )
            logger.warning("Answer validation failed: %s", failure_reasons)

            # Store validation failure info so clarification node can use it
            analysis["validation_failures"] = failures
            analysis["clarification_message"] = (
                f"I generated an answer but it didn't pass quality checks: "
                f"{failure_reasons}. Let me re-examine your question."
            )
            return {
                "query_analysis": analysis,
                "messages": [],  # Don't add the bad answer
            }

    except Exception as e:
        logger.warning("Answer validation LLM call failed, passing through: %s", e)

    # Validation passed — proceed as-is
    return {}


def validation_router(state: State):
    """Route after validation: pass → generate_json, fail → clarification."""
    analysis = state.get("query_analysis") or {}
    if analysis.get("validation_failures"):
        return "clarification"
    return "generate_json"


# ═══════════════════════════════════════════════════════════════════════
#  NODE 7: GENERATE JSON (format final response)
# ═══════════════════════════════════════════════════════════════════════

def generate_json(state: State):
    """Cast the final reasoning to the enforced JSON schema."""
    messages = state["messages"]
    analysis = state.get("query_analysis") or {}

    # Extract entity IDs for metadata
    entity_ids = [
        d["id"]
        for d in analysis.get("entities", {}).get("drivers", [])
    ]

    system_prompt = (
        "You are the ParcFermé formatting agent. Based on the conversation history, "
        "extract the final answer and structure it exactly as this JSON schema:\n"
        "{\n"
        '  "text_response": "The conversational text answer.",\n'
        '  "metadata": {"timestamp": "...", "session": "...", "entities": ' + json.dumps(entity_ids) + '},\n'
        '  "visualizations": [],\n'
        '  "tables": []\n'
        "}\n"
        "Provide only the JSON object, nothing else. Copy tables/visualizations directly from tool outputs if provided.\n"
        f"The current time is {datetime.datetime.utcnow().isoformat()}Z."
    )
    conv = [{"role": "system", "content": system_prompt}] + messages
    result = structured_llm.invoke(conv)

    return {"messages": [AIMessage(content=result.content, name="final_json")]}


# ═══════════════════════════════════════════════════════════════════════
#  GRAPH ASSEMBLY
# ═══════════════════════════════════════════════════════════════════════

graph_builder = StateGraph(State)

# Nodes
graph_builder.add_node("query_understanding", query_understanding)
graph_builder.add_node("clarification", clarification_node)
graph_builder.add_node("rephrase", rephrase_node)
graph_builder.add_node("agent", call_model)
graph_builder.add_node("tools", tool_node)
graph_builder.add_node("answer_validator", answer_validator)
graph_builder.add_node("generate_json", generate_json)

# Edges
graph_builder.add_edge(START, "query_understanding")

graph_builder.add_conditional_edges(
    "query_understanding",
    confidence_gate,
    {
        "agent": "agent",
        "clarification": "clarification",
        "rephrase": "rephrase",
    },
)

graph_builder.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        "answer_validator": "answer_validator",
    },
)

graph_builder.add_edge("tools", "agent")

graph_builder.add_conditional_edges(
    "answer_validator",
    validation_router,
    {
        "generate_json": "generate_json",
        "clarification": "clarification",
    },
)

graph_builder.add_edge("clarification", "generate_json")
graph_builder.add_edge("rephrase", "generate_json")
graph_builder.add_edge("generate_json", END)

# Compile with memory checkpointer for cross-turn entity persistence
memory = MemorySaver()
agent_app = graph_builder.compile(checkpointer=memory)


# ═══════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════════

def chat_with_agent(message: str, thread_id: str = "default_thread") -> Dict[str, Any]:
    if not api_key:
        return {
            "text_response": "GROQ_API_KEY is not configured.",
            "metadata": {
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "session": "Error",
                "entities": [],
            },
            "visualizations": [],
            "tables": [],
        }

    config = {"configurable": {"thread_id": thread_id}}

    try:
        events = agent_app.stream(
            {"messages": [("user", message)]},
            config,
            stream_mode="values",
        )

        final_state = None
        for event in events:
            final_state = event

        last_msg = final_state["messages"][-1]
        try:
            data = json.loads(last_msg.content)
            if "metadata" not in data or not data["metadata"]:
                data["metadata"] = {
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "session": "ParcFermé AI",
                    "entities": [],
                }
            return data
        except Exception:
            return {
                "text_response": last_msg.content,
                "metadata": {
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "session": "Fallback Agent",
                    "entities": [],
                },
                "visualizations": [],
                "tables": [],
            }

    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "rate limit" in error_str.lower():
            return {
                "text_response": (
                    "⚠️ **Telemetry Overload!** ParcFermé AI is currently processing "
                    "too many complex requests (Groq TPM rate limit reached). "
                    "Please wait 60 seconds and try again."
                ),
                "metadata": {
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "session": "System Defense",
                    "entities": [],
                },
                "visualizations": [],
                "tables": [],
            }
        return {
            "text_response": (
                f"⚠️ **Neural Pathway Fault:** An unexpected error crashed the agent "
                f"thread: `{error_str}`"
            ),
            "metadata": {
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "session": "System Defense",
                "entities": [],
            },
            "visualizations": [],
            "tables": [],
        }
