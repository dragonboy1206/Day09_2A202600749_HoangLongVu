"""Instrumented runner used by the interactive visualizer.

The normal stage files are kept intact for class/demo use. This runner mirrors
their flows while accepting a runtime question, system prompt, and selected
tools from the web UI.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.llm import get_llm

DEFAULT_PROMPTS = {
    "stage1": (
        "You are a helpful expert. Answer clearly and concisely. If the question is legal, "
        "explain the legal reasoning; otherwise answer the user's actual question."
    ),
    "stage2": (
        "You are a legal expert with access to selected tools. Use available tools when they "
        "help ground the answer. Explain which evidence came from tools and keep the final "
        "response clear."
    ),
    "stage3": (
        "You are a legal analyst agent. Reason step by step, call only the enabled tools when "
        "useful, observe their results, then produce a comprehensive but concise final answer."
    ),
    "stage4": (
        "You are a senior legal counsel. Analyze the user's question first, then coordinate any "
        "enabled specialist branches and synthesize a clear final answer."
    ),
}

VISUAL_GRAPHS = {
    "stage1": {
        "nodes": [
            {"id": "user", "title": "User Question", "type": "input", "x": 70, "y": 190},
            {"id": "prompt", "title": "System + Human", "type": "llm", "x": 290, "y": 190},
            {"id": "llm", "title": "Qwen LLM", "type": "llm", "x": 510, "y": 190},
            {"id": "answer", "title": "Final Answer", "type": "output", "x": 730, "y": 190},
        ],
        "edges": [
            {"from": "user", "to": "prompt", "label": "messages"},
            {"from": "prompt", "to": "llm", "label": "ainvoke"},
            {"from": "llm", "to": "answer", "label": "content"},
        ],
        "steps": [
            {"node": "user", "title": "Input", "text": "Question value imported from stage file or edited in UI."},
            {"node": "prompt", "title": "Prompt", "text": "System prompt from runner config or edited in UI."},
            {"node": "llm", "title": "LLM call", "text": "get_llm().ainvoke(messages)."},
            {"node": "answer", "title": "Output", "text": "Model response streamed back to the visualizer."},
        ],
        "agents": [{"name": "Qwen LLM", "type": "llm", "text": "Direct model call via common.get_llm()."}],
    },
    "stage2": {
        "nodes": [
            {"id": "user", "title": "User Question", "type": "input", "x": 50, "y": 190},
            {"id": "llm_tools", "title": "LLM + bind_tools", "type": "llm", "x": 250, "y": 190},
            {"id": "search", "title": "search_legal_database", "type": "tool", "x": 480, "y": 90},
            {"id": "damages", "title": "calculate_damages", "type": "tool", "x": 480, "y": 190},
            {"id": "limit", "title": "check_statute_of_limitations", "type": "tool", "x": 480, "y": 290},
            {"id": "tool_msg", "title": "ToolMessage", "type": "output", "x": 705, "y": 190},
            {"id": "final", "title": "Grounded Answer", "type": "output", "x": 925, "y": 190},
        ],
        "edges": [
            {"from": "user", "to": "llm_tools", "label": "question"},
            {"from": "llm_tools", "to": "search", "label": "tool call"},
            {"from": "llm_tools", "to": "damages", "label": "tool call"},
            {"from": "llm_tools", "to": "limit", "label": "tool call"},
            {"from": "search", "to": "tool_msg", "label": "result"},
            {"from": "damages", "to": "tool_msg", "label": "result"},
            {"from": "limit", "to": "tool_msg", "label": "result"},
            {"from": "tool_msg", "to": "final", "label": "second invoke"},
        ],
        "steps": [
            {"node": "user", "title": "Input", "text": "Question passed to stage2 interactive runner."},
            {"node": "llm_tools", "title": "Tool choice", "text": "LLM is bound to selected tools imported from stage2.TOOLS."},
            {"node": "search", "title": "Tool execution", "text": "A stage2 tool function is invoked when selected by the model."},
            {"node": "tool_msg", "title": "Observation", "text": "Tool result is linked back as ToolMessage."},
            {"node": "final", "title": "Synthesis", "text": "LLM generates the grounded final answer."},
        ],
        "agents": [{"name": "LLM with tools", "type": "llm", "text": "Uses stage2.TOOLS through LangChain bind_tools()."}],
    },
    "stage3": {
        "nodes": [
            {"id": "user", "title": "Complex Question", "type": "input", "x": 50, "y": 190},
            {"id": "agent", "title": "create_react_agent", "type": "agent", "x": 270, "y": 190},
            {"id": "legal", "title": "search_legal_database", "type": "tool", "x": 515, "y": 65},
            {"id": "penalty", "title": "calculate_penalty", "type": "tool", "x": 515, "y": 150},
            {"id": "case", "title": "search_case_law", "type": "tool", "x": 515, "y": 235},
            {"id": "compliance", "title": "check_compliance_requirements", "type": "tool", "x": 515, "y": 320},
            {"id": "observe", "title": "Observe Results", "type": "agent", "x": 765, "y": 190},
            {"id": "final", "title": "Final Answer", "type": "output", "x": 965, "y": 190},
        ],
        "edges": [
            {"from": "user", "to": "agent", "label": "input"},
            {"from": "agent", "to": "legal", "label": "act"},
            {"from": "agent", "to": "penalty", "label": "act"},
            {"from": "agent", "to": "case", "label": "act"},
            {"from": "agent", "to": "compliance", "label": "act"},
            {"from": "legal", "to": "observe", "label": "tool result"},
            {"from": "penalty", "to": "observe", "label": "tool result"},
            {"from": "case", "to": "observe", "label": "tool result"},
            {"from": "compliance", "to": "observe", "label": "tool result"},
            {"from": "observe", "to": "agent", "label": "loop"},
            {"from": "observe", "to": "final", "label": "done"},
        ],
        "steps": [
            {"node": "agent", "title": "Think", "text": "LangGraph ReAct agent is created from stage3.TOOLS."},
            {"node": "legal", "title": "Act", "text": "Agent may call a selected stage3 tool."},
            {"node": "observe", "title": "Observe", "text": "ToolMessage is observed by the agent loop."},
            {"node": "final", "title": "Final", "text": "Agent emits the final answer."},
        ],
        "agents": [{"name": "ReAct Agent", "type": "agent", "text": "Created with langgraph.prebuilt.create_react_agent()."}],
    },
    "stage4": {
        "nodes": [
            {"id": "start", "title": "Question", "type": "input", "x": 50, "y": 190},
            {"id": "law", "title": "analyze_law", "type": "agent", "x": 250, "y": 190},
            {"id": "router", "title": "check_routing", "type": "agent", "x": 455, "y": 190},
            {"id": "tax", "title": "Tax Specialist", "type": "agent", "x": 665, "y": 105},
            {"id": "tax_tool", "title": "search_tax_law", "type": "tool", "x": 665, "y": 25},
            {"id": "comp", "title": "Compliance Specialist", "type": "agent", "x": 665, "y": 275},
            {"id": "comp_tool", "title": "search_compliance_law", "type": "tool", "x": 665, "y": 355},
            {"id": "aggregate", "title": "aggregate", "type": "agent", "x": 885, "y": 190},
            {"id": "final", "title": "Final Answer", "type": "output", "x": 1085, "y": 190},
        ],
        "edges": [
            {"from": "start", "to": "law", "label": "entry"},
            {"from": "law", "to": "router", "label": "analysis"},
            {"from": "router", "to": "tax", "label": "Send if tax"},
            {"from": "tax", "to": "tax_tool", "label": "uses"},
            {"from": "tax", "to": "aggregate", "label": "tax_result"},
            {"from": "router", "to": "comp", "label": "Send if compliance"},
            {"from": "comp", "to": "comp_tool", "label": "uses"},
            {"from": "comp", "to": "aggregate", "label": "compliance_result"},
            {"from": "router", "to": "aggregate", "label": "if no specialist"},
            {"from": "aggregate", "to": "final", "label": "END"},
        ],
        "steps": [
            {"node": "law", "title": "Lead attorney", "text": "Calls stage4.analyze_law(state)."},
            {"node": "router", "title": "Router", "text": "Calls stage4.check_routing(state)."},
            {"node": "tax", "title": "Tax branch", "text": "Calls stage4.call_tax_specialist(state)."},
            {"node": "comp", "title": "Compliance branch", "text": "Calls stage4.call_compliance_specialist(state)."},
            {"node": "aggregate", "title": "Aggregate", "text": "Calls stage4.aggregate(state)."},
            {"node": "final", "title": "Final", "text": "Final answer returned from stage graph state."},
        ],
        "agents": [
            {"name": "analyze_law", "type": "agent", "text": "Imported from stages.stage_4_milti_agent.main."},
            {"name": "check_routing", "type": "agent", "text": "Imported from stages.stage_4_milti_agent.main."},
            {"name": "call_tax_specialist", "type": "agent", "text": "Imported from stages.stage_4_milti_agent.main."},
            {"name": "call_compliance_specialist", "type": "agent", "text": "Imported from stages.stage_4_milti_agent.main."},
            {"name": "aggregate", "type": "agent", "text": "Imported from stages.stage_4_milti_agent.main."},
        ],
    },
}


def emit(kind: str, **payload) -> None:
    if "from_" in payload:
        payload["from"] = payload.pop("from_")
    print(f"@@VISUAL@@{json.dumps({'kind': kind, **payload}, ensure_ascii=False)}", flush=True)


def log(message: str) -> None:
    print(message, flush=True)


def config() -> dict:
    raw = os.getenv("STAGE_VISUALIZER_CONFIG", "{}")
    return json.loads(raw)


def selected_tools(all_tools: list, names: list[str]) -> list:
    if not names:
        return []
    allowed = set(names)
    return [tool for tool in all_tools if tool.name in allowed]


def stage_tool_source(stage_module: str, tool_name: str) -> str:
    return f"{stage_module}.{tool_name}()"


async def run_stage1(cfg: dict) -> None:
    question = cfg["question"]
    prompt = cfg["system_prompt"]

    log("STAGE 1: Direct LLM Calling (interactive)")
    log(f"Question: {question}")
    emit("input", node="user", label="Question", detail=question)
    emit("prompt", node="prompt", from_="user", to="prompt", label="System prompt", detail=prompt)

    llm = get_llm()
    messages = [SystemMessage(content=prompt), HumanMessage(content=question)]
    log(">>> Calling LLM directly with custom question + system prompt...")
    emit("llm", node="llm", from_="prompt", to="llm", label="ainvoke(messages)", detail="Sending messages to model")
    response = await llm.ainvoke(messages)

    log("FINAL ANSWER")
    log(response.content)
    emit("output", node="answer", from_="llm", to="answer", label="LLM response", detail=response.content)


async def run_stage2(cfg: dict) -> None:
    from stages.stage_2_rag_tools import main as stage2

    question = cfg["question"]
    prompt = cfg["system_prompt"]
    tools = selected_tools(stage2.TOOLS, cfg.get("tools", []))
    tool_map = {tool.name: tool for tool in tools}

    log("STAGE 2: LLM + RAG / Tools (interactive)")
    log(f"Question: {question}")
    log(f"Enabled tools: {', '.join(tool_map) if tool_map else '(none)'}")
    emit("input", node="user", label="Question", detail=question)
    emit("llm", node="llm_tools", from_="user", to="llm_tools", label="bind_tools", detail=f"{len(tools)} tool(s) enabled")

    llm = get_llm()
    llm_with_tools = llm.bind_tools(tools) if tools else llm
    messages = [SystemMessage(content=prompt), HumanMessage(content=question)]

    response = await llm_with_tools.ainvoke(messages)
    messages.append(response)

    if not getattr(response, "tool_calls", None):
        log("FINAL ANSWER")
        log(response.content)
        emit("output", node="final", from_="llm_tools", to="final", label="Direct answer", detail=response.content)
        return

    for call in response.tool_calls:
        tool_name = call["name"]
        tool = tool_map[tool_name]
        node = {
            "search_legal_database": "search",
            "calculate_damages": "damages",
            "check_statute_of_limitations": "limit",
        }.get(tool_name, "llm_tools")

        log(f"TOOL CALL: {tool_name}")
        log(f"ARGS: {call['args']}")
        emit(
            "tool",
            node=node,
            from_="llm_tools",
            to=node,
            label=tool_name,
            detail=f"{stage_tool_source('stages.stage_2_rag_tools.main', tool_name)} args={json.dumps(call['args'], ensure_ascii=False)}",
        )
        result = await tool.ainvoke(call["args"])
        log(f"TOOL RESULT: {result}")
        emit("data", node="tool_msg", from_=node, to="tool_msg", label=f"{tool_name} result", detail=str(result))
        messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))

    log(">>> LLM generating final answer with linked tool results...")
    emit("llm", node="final", from_="tool_msg", to="final", label="Final synthesis", detail="ToolMessage list returned to model")
    final_response = await llm_with_tools.ainvoke(messages)
    log("FINAL ANSWER")
    log(final_response.content)
    emit("output", node="final", from_="tool_msg", to="final", label="Grounded answer", detail=final_response.content)


async def run_stage3(cfg: dict) -> None:
    from langgraph.prebuilt import create_react_agent
    from stages.stage_3_single_agent import main as stage3

    question = cfg["question"]
    prompt = cfg["system_prompt"]
    tools = selected_tools(stage3.TOOLS, cfg.get("tools", []))

    log("STAGE 3: Single ReAct Agent (interactive)")
    log(f"Question: {question}")
    log(f"Enabled tools: {', '.join(tool.name for tool in tools) if tools else '(none)'}")
    emit("input", node="user", label="Question", detail=question)
    emit("agent", node="agent", from_="user", to="agent", label="create_react_agent", detail=f"{len(tools)} tool(s) enabled")

    graph = create_react_agent(model=get_llm(), tools=tools, prompt=prompt)
    inputs = {"messages": [{"role": "user", "content": question}]}

    async for chunk in graph.astream(inputs, stream_mode="updates"):
        for node_name, update in chunk.items():
            for msg in update.get("messages", []):
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    log(f"THINK + ACT ({node_name})")
                    for call in msg.tool_calls:
                        tool_name = call["name"]
                        target = {
                            "search_legal_database": "legal",
                            "calculate_penalty": "penalty",
                            "search_case_law": "case",
                            "check_compliance_requirements": "compliance",
                        }.get(tool_name, "agent")
                        log(f"TOOL CALL: {tool_name} {call['args']}")
                        emit(
                            "tool",
                            node=target,
                            from_="agent",
                            to=target,
                            label=tool_name,
                            detail=f"{stage_tool_source('stages.stage_3_single_agent.main', tool_name)} args={json.dumps(call['args'], ensure_ascii=False)}",
                        )
                elif msg.type == "tool":
                    log(f"OBSERVE ({node_name}): {msg.content}")
                    emit("data", node="observe", label="Tool observation", detail=msg.content)
                elif msg.type == "ai" and msg.content:
                    log("FINAL ANSWER")
                    log(msg.content)
                    emit("output", node="final", from_="observe", to="final", label="Agent final answer", detail=msg.content)


async def run_stage4(cfg: dict) -> None:
    from stages.stage_4_milti_agent import main as stage4

    question = cfg["question"]
    enabled = set(cfg.get("tools", []))

    log("STAGE 4: Multi-Agent Graph (interactive)")
    log(f"Question: {question}")
    emit("input", node="start", label="Question", detail=question)

    state = {
        "question": question,
        "law_analysis": "",
        "needs_tax": False,
        "needs_compliance": False,
        "tax_result": "",
        "compliance_result": "",
        "final_answer": "",
    }

    emit(
        "agent",
        node="law",
        from_="start",
        to="law",
        label="stage4.analyze_law(state)",
        detail="Calling stages.stage_4_milti_agent.main.analyze_law",
    )
    law_result = await stage4.analyze_law(state)
    state.update(law_result)
    log(f"LAW ANALYSIS: {state['law_analysis']}")

    emit(
        "agent",
        node="router",
        from_="law",
        to="router",
        label="stage4.check_routing(state)",
        detail="Calling stages.stage_4_milti_agent.main.check_routing",
    )
    routing = await stage4.check_routing(state)
    state.update(routing)

    router_wants_tax = bool(state.get("needs_tax"))
    router_wants_compliance = bool(state.get("needs_compliance"))
    state["needs_tax"] = router_wants_tax and "search_tax_law" in enabled
    state["needs_compliance"] = router_wants_compliance and "search_compliance_law" in enabled
    log(
        "ROUTING: "
        f"router_tax={router_wants_tax}, router_compliance={router_wants_compliance}, "
        f"enabled_tax={'search_tax_law' in enabled}, enabled_compliance={'search_compliance_law' in enabled}"
    )

    if state["needs_tax"]:
        emit(
            "agent",
            node="tax",
            from_="router",
            to="tax",
            label="stage4.call_tax_specialist(state)",
            detail="Calling stages.stage_4_milti_agent.main.call_tax_specialist",
        )
        emit(
            "tool",
            node="tax_tool",
            from_="tax",
            to="tax_tool",
            label="search_tax_law",
            detail="Tool is called inside call_tax_specialist() from the stage file",
        )
        tax_result = await stage4.call_tax_specialist(state)
        state.update(tax_result)
        emit("data", node="tax", from_="tax_tool", to="tax", label="Tax specialist result", detail=state["tax_result"])
        log(f"TAX RESULT: {state['tax_result']}")

    if state["needs_compliance"]:
        emit(
            "agent",
            node="comp",
            from_="router",
            to="comp",
            label="stage4.call_compliance_specialist(state)",
            detail="Calling stages.stage_4_milti_agent.main.call_compliance_specialist",
        )
        emit(
            "tool",
            node="comp_tool",
            from_="comp",
            to="comp_tool",
            label="search_compliance_law",
            detail="Tool is called inside call_compliance_specialist() from the stage file",
        )
        compliance_result = await stage4.call_compliance_specialist(state)
        state.update(compliance_result)
        emit("data", node="comp", from_="comp_tool", to="comp", label="Compliance specialist result", detail=state["compliance_result"])
        log(f"COMPLIANCE RESULT: {state['compliance_result']}")

    emit(
        "agent",
        node="aggregate",
        from_="router",
        to="aggregate",
        label="stage4.aggregate(state)",
        detail="Calling stages.stage_4_milti_agent.main.aggregate",
    )
    final_result = await stage4.aggregate(state)
    state.update(final_result)
    log("FINAL ANSWER")
    log(state["final_answer"])
    emit("output", node="final", from_="aggregate", to="final", label="Final answer", detail=state["final_answer"])


async def main() -> None:
    load_dotenv()
    cfg = config()
    stage = cfg["stage"]
    runners = {
        "stage1": run_stage1,
        "stage2": run_stage2,
        "stage3": run_stage3,
        "stage4": run_stage4,
    }
    await runners[stage](cfg)


if __name__ == "__main__":
    asyncio.run(main())
