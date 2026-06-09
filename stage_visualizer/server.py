"""Run the stage visualizer web app and stream real stage logs."""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = Path(__file__).resolve().parent
RUNS_DIR = APP_DIR / "runs"
VENV_PYTHON = ROOT_DIR / ".venv" / "Scripts" / "python.exe"

STAGES = {
    "stage1": ROOT_DIR / "stages" / "stage_1_direct_llm" / "main.py",
    "stage2": ROOT_DIR / "stages" / "stage_2_rag_tools" / "main.py",
    "stage3": ROOT_DIR / "stages" / "stage_3_single_agent" / "main.py",
    "stage4": ROOT_DIR / "stages" / "stage_4_milti_agent" / "main.py",
}
RUNNER = APP_DIR / "runner.py"
STAGE_MODULES = {
    "stage1": "stages.stage_1_direct_llm.main",
    "stage2": "stages.stage_2_rag_tools.main",
    "stage3": "stages.stage_3_single_agent.main",
    "stage4": "stages.stage_4_milti_agent.main",
}
STAGE_LABELS = {
    "stage1": ("Stage 1", "Direct LLM", "Gọi LLM trực tiếp"),
    "stage2": ("Stage 2", "RAG + Tools", "LLM gọi tool theo vòng lặp thủ công"),
    "stage3": ("Stage 3", "Single ReAct Agent", "Một agent tự lặp Think - Act - Observe"),
    "stage4": ("Stage 4", "Multi-Agent Graph", "Nhiều agent chuyên môn chạy song song"),
}

app = FastAPI(title="Stage Flow Visualizer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=APP_DIR), name="static")


@app.get("/")
def index() -> RedirectResponse:
    return RedirectResponse("/static/index.html")


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def python_executable() -> str:
    return str(VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable))


def tool_metadata(tool) -> dict:
    description = getattr(tool, "description", "") or ""
    if not description and getattr(tool, "func", None):
        description = getattr(tool.func, "__doc__", "") or ""
    return {
        "name": tool.name,
        "type": "tool",
        "text": " ".join(description.strip().split()) or f"Tool imported from stage module: {tool.name}",
    }


def stage_tools(stage_id: str, module) -> list[dict]:
    if hasattr(module, "TOOLS"):
        return [tool_metadata(tool) for tool in module.TOOLS]
    if stage_id == "stage4":
        return [
            tool_metadata(module.search_tax_law),
            tool_metadata(module.search_compliance_law),
        ]
    return []


@app.get("/api/visualizer-config")
def visualizer_config() -> list[dict]:
    from stage_visualizer import runner

    configs = []
    for stage_id, module_name in STAGE_MODULES.items():
        module = importlib.import_module(module_name)
        label, kind, title = STAGE_LABELS[stage_id]
        visual = runner.VISUAL_GRAPHS[stage_id]
        configs.append(
            {
                "id": stage_id,
                "label": label,
                "kind": kind,
                "title": title,
                "source": str(STAGES[stage_id].relative_to(ROOT_DIR)),
                "question": getattr(module, "QUESTION", ""),
                "systemPrompt": runner.DEFAULT_PROMPTS[stage_id],
                "nodes": visual["nodes"],
                "edges": visual["edges"],
                "steps": visual["steps"],
                "tools": stage_tools(stage_id, module),
                "agents": visual["agents"],
            }
        )
    return configs


def visual_event(stage_id: str, line: str) -> dict | None:
    text = line.lower()

    if "question:" in text:
        return {"node": "user" if stage_id != "stage4" else "start", "kind": "input", "label": "Question"}

    if stage_id == "stage1":
        if "calling llm directly" in text:
            return {"node": "llm", "from": "prompt", "to": "llm", "kind": "llm", "label": "ainvoke(messages)"}
        if line and not line.startswith(("=", "-", "[", "STAGE", "Question:", ">>>", "Next:")):
            return {"node": "answer", "from": "llm", "to": "answer", "kind": "output", "label": "LLM response"}

    if stage_id == "stage2":
        if "asking llm" in text:
            return {"node": "llm_tools", "from": "user", "to": "llm_tools", "kind": "llm", "label": "bind_tools + invoke"}
        if "tool:" in text and "search_legal_database" in text:
            return {"node": "search", "from": "llm_tools", "to": "search", "kind": "tool", "label": "Tool call"}
        if "tool:" in text and "calculate_damages" in text:
            return {"node": "damages", "from": "llm_tools", "to": "damages", "kind": "tool", "label": "Tool call"}
        if "tool:" in text and "check_statute_of_limitations" in text:
            return {"node": "limit", "from": "llm_tools", "to": "limit", "kind": "tool", "label": "Tool call"}
        if "result:" in text:
            return {"node": "tool_msg", "kind": "data", "label": "Tool result -> ToolMessage"}
        if "generating final answer" in text:
            return {"node": "final", "from": "tool_msg", "to": "final", "kind": "output", "label": "Grounded answer"}

    if stage_id == "stage3":
        if "think + act" in text:
            return {"node": "agent", "from": "user", "to": "agent", "kind": "agent", "label": "Think + Act"}
        tool_map = {
            "search_legal_database": "legal",
            "calculate_penalty": "penalty",
            "search_case_law": "case",
            "check_compliance_requirements": "compliance",
        }
        for tool_name, node in tool_map.items():
            if tool_name in text:
                return {"node": node, "from": "agent", "to": node, "kind": "tool", "label": tool_name}
        if "observe" in text or "result:" in text:
            return {"node": "observe", "kind": "data", "label": "Tool result observed"}
        if "final answer" in text:
            return {"node": "final", "from": "observe", "to": "final", "kind": "output", "label": "Final answer"}

    if stage_id == "stage4":
        node_map = {
            "[node: analyze_law]": ("law", "start", "law", "Lead attorney"),
            "[node: check_routing]": ("router", "law", "router", "Routing JSON"),
            "[node: call_tax_specialist]": ("tax", "router", "tax", "Tax branch"),
            "[node: call_compliance_specialist]": ("comp", "router", "comp", "Compliance branch"),
            "[node: aggregate]": ("aggregate", None, "aggregate", "Aggregate"),
        }
        for marker, (node, from_node, to_node, label) in node_map.items():
            if marker in text:
                event = {"node": node, "kind": "agent", "label": label}
                if from_node and to_node:
                    event.update({"from": from_node, "to": to_node})
                return event
        if "final answer" in text:
            return {"node": "final", "from": "aggregate", "to": "final", "kind": "output", "label": "Final answer"}

    return None


@app.get("/api/stages")
def list_stages() -> dict:
    return {
        stage_id: {
            "path": str(path.relative_to(ROOT_DIR)),
            "exists": path.exists(),
        }
        for stage_id, path in STAGES.items()
    }


@app.get("/api/run/{stage_id}")
async def run_stage(stage_id: str) -> StreamingResponse:
    stage_path = STAGES.get(stage_id)
    if stage_path is None:
        raise HTTPException(status_code=404, detail="Unknown stage")
    if not stage_path.exists():
        raise HTTPException(status_code=404, detail=f"Missing stage file: {stage_path}")

    async def stream():
        load_dotenv(ROOT_DIR / ".env")
        RUNS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_path = RUNS_DIR / f"{stage_id}-{timestamp}.log"

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        yield sse(
            "meta",
            {
                "stage": stage_id,
                "source": str(stage_path.relative_to(ROOT_DIR)),
                "log": str(log_path.relative_to(ROOT_DIR)),
                "python": python_executable(),
                "has_api_key": bool(env.get("DASHSCOPE_API_KEY")),
                "started_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
        yield sse(
            "visual",
            {
                "node": "user" if stage_id != "stage4" else "start",
                "kind": "process",
                "label": "Process started",
                "detail": str(stage_path.relative_to(ROOT_DIR)),
            },
        )

        with log_path.open("w", encoding="utf-8") as log_file:
            process = await asyncio.create_subprocess_exec(
                python_executable(),
                "-u",
                str(stage_path),
                cwd=ROOT_DIR,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            yield sse(
                "process",
                {
                    "pid": process.pid,
                    "python": python_executable(),
                    "source": str(stage_path.relative_to(ROOT_DIR)),
                },
            )

            assert process.stdout is not None
            async for raw_line in process.stdout:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                log_file.write(line + "\n")
                log_file.flush()
                yield sse("line", {"text": line})
                event = visual_event(stage_id, line)
                if event:
                    event["detail"] = line[:400]
                    yield sse("visual", event)

            return_code = await process.wait()
            yield sse(
                "done",
                {
                    "return_code": return_code,
                    "ok": return_code == 0,
                    "log": str(log_path.relative_to(ROOT_DIR)),
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                },
            )

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/run-interactive/{stage_id}")
async def run_interactive_stage(
    stage_id: str,
    question: str,
    system_prompt: str,
    tools: str = "",
) -> StreamingResponse:
    if stage_id not in STAGES:
        raise HTTPException(status_code=404, detail="Unknown stage")
    if not RUNNER.exists():
        raise HTTPException(status_code=404, detail="Missing visualizer runner")

    async def stream():
        load_dotenv(ROOT_DIR / ".env")
        RUNS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_path = RUNS_DIR / f"{stage_id}-interactive-{timestamp}.log"
        tool_names = [name for name in tools.split(",") if name]

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        env["STAGE_VISUALIZER_CONFIG"] = json.dumps(
            {
                "stage": stage_id,
                "question": question,
                "system_prompt": system_prompt,
                "tools": tool_names,
            },
            ensure_ascii=False,
        )

        yield sse(
            "meta",
            {
                "stage": stage_id,
                "source": str(RUNNER.relative_to(ROOT_DIR)),
                "log": str(log_path.relative_to(ROOT_DIR)),
                "python": python_executable(),
                "has_api_key": bool(env.get("DASHSCOPE_API_KEY")),
                "started_at": datetime.now().isoformat(timespec="seconds"),
            },
        )

        with log_path.open("w", encoding="utf-8") as log_file:
            process = await asyncio.create_subprocess_exec(
                python_executable(),
                "-u",
                str(RUNNER),
                cwd=ROOT_DIR,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            yield sse(
                "process",
                {
                    "pid": process.pid,
                    "python": python_executable(),
                    "source": str(RUNNER.relative_to(ROOT_DIR)),
                    "mode": "interactive",
                },
            )

            assert process.stdout is not None
            async for raw_line in process.stdout:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if line.startswith("@@VISUAL@@"):
                    try:
                        yield sse("visual", json.loads(line.removeprefix("@@VISUAL@@")))
                    except json.JSONDecodeError:
                        yield sse("line", {"text": line})
                    continue
                log_file.write(line + "\n")
                log_file.flush()
                yield sse("line", {"text": line})

            return_code = await process.wait()
            yield sse(
                "done",
                {
                    "return_code": return_code,
                    "ok": return_code == 0,
                    "log": str(log_path.relative_to(ROOT_DIR)),
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                },
            )

    return StreamingResponse(stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("stage_visualizer.server:app", host="127.0.0.1", port=8011, reload=False)
