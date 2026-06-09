let stages = [];
let activeStageIndex = 0;
let activeStepIndex = 0;
let playTimer = null;
let runStream = null;
let finalCaptureStarted = false;
let finalLines = [];
let activePacket = null;
let visualEvents = [];
const API_BASE = window.location.protocol === "file:" ? "http://127.0.0.1:8011" : "";

const stageNav = document.querySelector("#stageNav");
const sourcePath = document.querySelector("#sourcePath");
const stageKind = document.querySelector("#stageKind");
const stageTitle = document.querySelector("#stageTitle");
const questionText = document.querySelector("#questionText");
const flowSvg = document.querySelector("#flowSvg");
const timeline = document.querySelector("#timeline");
const stepCounter = document.querySelector("#stepCounter");
const toolGrid = document.querySelector("#toolGrid");
const agentGrid = document.querySelector("#agentGrid");
const toolCount = document.querySelector("#toolCount");
const agentCount = document.querySelector("#agentCount");
const prevStep = document.querySelector("#prevStep");
const nextStep = document.querySelector("#nextStep");
const playFlow = document.querySelector("#playFlow");
const runActual = document.querySelector("#runActual");
const runStatus = document.querySelector("#runStatus");
const liveLog = document.querySelector("#liveLog");
const actualResult = document.querySelector("#actualResult");
const logPath = document.querySelector("#logPath");
const currentPacket = document.querySelector("#currentPacket");
const eventFeed = document.querySelector("#eventFeed");
const questionInput = document.querySelector("#questionInput");
const promptInput = document.querySelector("#promptInput");
const toolChecks = document.querySelector("#toolChecks");
const selectedToolCount = document.querySelector("#selectedToolCount");

function defaultPrompt(stageId) {
  return stages.find((stage) => stage.id === stageId)?.systemPrompt || "";
}

function nodeClass(type) {
  if (type === "tool") return "tool";
  if (type === "agent") return "agent";
  if (type === "llm") return "llm";
  if (type === "output") return "output";
  return "";
}

function renderNav() {
  stageNav.innerHTML = stages
    .map(
      (stage, index) => `
        <button class="stage-tab ${index === activeStageIndex ? "active" : ""}" type="button" data-stage="${index}">
          <span>${stage.label}</span>
          <strong>${stage.kind}</strong>
        </button>
      `,
    )
    .join("");
}

function getNode(stage, id) {
  return stage.nodes.find((node) => node.id === id);
}

function edgePath(from, to) {
  const x1 = from.x + 150;
  const y1 = from.y + 30;
  const x2 = to.x;
  const y2 = to.y + 30;
  const dx = Math.max(50, Math.abs(x2 - x1) * 0.45);
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
}

function svgTextLines(text, x, startY, className, maxChars = 18) {
  const words = text.split(/[_\s]+/);
  const lines = [];
  let current = "";

  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length > maxChars && current) {
      lines.push(current);
      current = word;
    } else {
      current = candidate;
    }
  }
  if (current) lines.push(current);

  return `
    <text class="${className}" x="${x}" y="${startY}">
      ${lines.slice(0, 2).map((line, index) => `<tspan x="${x}" dy="${index === 0 ? 0 : 16}">${line}</tspan>`).join("")}
    </text>
  `;
}

function renderFlow(stage) {
  const currentNode = stage.steps[activeStepIndex]?.node;
  const activeEdgeTarget = currentNode;
  const maxX = Math.max(...stage.nodes.map((node) => node.x)) + 180;
  const maxY = Math.max(...stage.nodes.map((node) => node.y)) + 90;

  const edges = stage.edges
    .map((edge) => {
      const from = getNode(stage, edge.from);
      const to = getNode(stage, edge.to);
      const isPacketEdge = activePacket?.from === edge.from && activePacket?.to === edge.to;
      const isActive = isPacketEdge || edge.to === activeEdgeTarget || edge.from === activeEdgeTarget;
      const midX = (from.x + to.x + 150) / 2;
      const midY = (from.y + to.y) / 2 + 18;
      const path = edgePath(from, to);
      return `
        <path class="edge ${isActive ? "active" : ""}" d="${path}"></path>
        <text class="edge-label" x="${midX}" y="${midY}">${edge.label}</text>
        ${
          isPacketEdge
            ? `<circle class="packet-dot" r="7">
                <animateMotion dur="1.1s" repeatCount="indefinite" path="${path}"></animateMotion>
              </circle>`
            : ""
        }
      `;
    })
    .join("");

  const nodes = stage.nodes
    .map((node) => {
      const active = node.id === currentNode;
      const typeText = node.type === "input" ? "input" : node.type;
      return `
        <g class="node ${nodeClass(node.type)} ${active ? "active" : ""}" transform="translate(${node.x}, ${node.y})">
          <rect width="150" height="72"></rect>
          <text class="node-type" x="14" y="21">${typeText}</text>
          ${svgTextLines(node.title, 14, 43, "node-title")}
        </g>
      `;
    })
    .join("");

  flowSvg.setAttribute("viewBox", `0 0 ${maxX} ${maxY}`);
  flowSvg.innerHTML = `
    <defs>
      <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
        <path d="M0,0 L0,6 L9,3 z" fill="#9aaab1"></path>
      </marker>
    </defs>
    ${edges}
    ${nodes}
  `;
}

function renderTimeline(stage) {
  stepCounter.textContent = `${activeStepIndex + 1}/${stage.steps.length}`;
  timeline.innerHTML = stage.steps
    .map(
      (step, index) => `
        <li class="${index === activeStepIndex ? "active" : ""}" data-step="${index}">
          <span class="step-number">${index + 1}</span>
          <div>
            <strong>${step.title}</strong>
            <p>${step.text}</p>
          </div>
        </li>
      `,
    )
    .join("");
}

function renderItems(container, items, emptyText) {
  container.innerHTML = items.length
    ? items
        .map(
          (item) => `
            <article class="item-card">
              <span class="tag ${item.type}">${item.type}</span>
              <strong>${item.name}</strong>
              <p>${item.text}</p>
            </article>
          `,
        )
        .join("")
    : `<article class="item-card"><strong>Không có tool</strong><p>${emptyText}</p></article>`;
}

function renderToolChecks(stage) {
  if (!stage.tools.length) {
    toolChecks.innerHTML = `<div class="tool-check"><span>Stage này không có tool để bật/tắt.</span></div>`;
    selectedToolCount.textContent = "0 selected";
    return;
  }

  toolChecks.innerHTML = stage.tools
    .map(
      (tool) => `
        <label class="tool-check">
          <input type="checkbox" value="${tool.name}" checked />
          <span>
            <strong>${tool.name}</strong>
            <span>${tool.text}</span>
          </span>
        </label>
      `,
    )
    .join("");
  updateSelectedToolCount();
}

function selectedToolNames() {
  return Array.from(toolChecks.querySelectorAll("input[type='checkbox']:checked")).map((input) => input.value);
}

function updateSelectedToolCount() {
  const selected = selectedToolNames().length;
  const total = stages[activeStageIndex].tools.length;
  selectedToolCount.textContent = `${selected}/${total} selected`;
}

function renderStage() {
  const stage = stages[activeStageIndex];
  activeStepIndex = Math.min(activeStepIndex, stage.steps.length - 1);
  sourcePath.textContent = stage.source;
  stageKind.textContent = `${stage.label} / ${stage.kind}`;
  stageTitle.textContent = stage.title;
  questionText.textContent = stage.question;
  toolCount.textContent = `${stage.tools.length} tool`;
  agentCount.textContent = `${stage.agents.length} node`;
  renderNav();
  renderFlow(stage);
  renderTimeline(stage);
  renderItems(toolGrid, stage.tools, "Stage này gọi thẳng model, chưa gắn tool.");
  renderItems(agentGrid, stage.agents, "Không có agent riêng.");
  questionInput.value = stage.question;
  promptInput.value = defaultPrompt(stage.id);
  renderToolChecks(stage);
  resetRunPanel();
}

function setStage(index) {
  activeStageIndex = index;
  activeStepIndex = 0;
  stopPlayback();
  stopRunStream();
  loadVisualizerConfig();
}

function setStep(index) {
  const stage = stages[activeStageIndex];
  activeStepIndex = (index + stage.steps.length) % stage.steps.length;
  renderFlow(stage);
  renderTimeline(stage);
}

function stopPlayback() {
  if (playTimer) {
    clearInterval(playTimer);
    playTimer = null;
  }
  playFlow.innerHTML = `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M8 5v14l11-7z" />
    </svg>
    Chạy luồng
  `;
}

function stopRunStream() {
  if (runStream) {
    runStream.close();
    runStream = null;
  }
}

function resetRunPanel() {
  finalCaptureStarted = false;
  finalLines = [];
  activePacket = null;
  visualEvents = [];
  liveLog.textContent = "";
  actualResult.textContent = "Kết quả cuối sẽ hiện ở đây sau khi chạy stage.";
  currentPacket.innerHTML = `
    <span>Data packet</span>
    <strong>Chưa có dữ liệu chạy thật</strong>
    <p>Bấm Chạy thật để xem dữ liệu đi qua từng node.</p>
  `;
  eventFeed.innerHTML = "";
  logPath.textContent = "";
  setRunStatus("Chưa chạy", "");
}

function setRunStatus(text, className) {
  runStatus.textContent = text;
  runStatus.className = className || "";
}

function appendLog(line) {
  liveLog.textContent += `${line}\n`;
  liveLog.scrollTop = liveLog.scrollHeight;
}

function setStepByNode(nodeId) {
  const stage = stages[activeStageIndex];
  const index = stage.steps.findIndex((step) => step.node === nodeId);
  if (index >= 0) {
    activeStepIndex = index;
    renderFlow(stage);
    renderTimeline(stage);
  }
}

function pushVisualEvent(event) {
  const stage = stages[activeStageIndex];
  activePacket = {
    from: event.from || null,
    to: event.to || event.node,
    node: event.node,
    label: event.label || event.kind || "event",
  };

  visualEvents.unshift({
    label: event.label || event.kind || "Event",
    node: event.node,
    detail: event.detail || "",
  });
  visualEvents = visualEvents.slice(0, 8);

  currentPacket.innerHTML = `
    <span>${event.kind || "data"}</span>
    <strong>${event.label || event.node}</strong>
    <p>${event.detail || "Đang truyền dữ liệu qua luồng chạy thật."}</p>
  `;
  eventFeed.innerHTML = visualEvents
    .map(
      (item) => `
        <li>
          <strong>${item.label}</strong>
          <span>${item.node}${item.detail ? ` - ${item.detail}` : ""}</span>
        </li>
      `,
    )
    .join("");

  if (event.kind === "output" && event.detail) {
    actualResult.textContent = event.detail;
  }

  setStepByNode(event.node);
  renderFlow(stage);
}

function inferNodeFromLog(line) {
  const text = line.toLowerCase();

  if (text.includes("final answer") || text.includes("final answer")) return "final";
  if (text.includes("grounded answer")) return "final";
  if (text.includes("calling llm directly")) return "llm";
  if (text.includes("generating final answer")) return "final";
  if (text.includes("toolmessage")) return "tool_msg";
  if (text.includes("observe")) return "observe";
  if (text.includes("think + act")) return "agent";

  if (text.includes("search_legal_database")) return "search";
  if (text.includes("calculate_damages")) return "damages";
  if (text.includes("check_statute_of_limitations")) return "limit";
  if (text.includes("calculate_penalty")) return "penalty";
  if (text.includes("search_case_law")) return "case";
  if (text.includes("check_compliance_requirements")) return "compliance";
  if (text.includes("search_tax_law")) return "tax_tool";
  if (text.includes("search_compliance_law")) return "comp_tool";

  if (text.includes("[node: analyze_law]")) return "law";
  if (text.includes("[node: check_routing]")) return "router";
  if (text.includes("[node: call_tax_specialist]")) return "tax";
  if (text.includes("[node: call_compliance_specialist]")) return "comp";
  if (text.includes("[node: aggregate]")) return "aggregate";

  if (text.includes("question:")) return "user";
  return null;
}

function updateActualResult(line) {
  const trimmed = line.trim();
  if (!trimmed) {
    if (finalCaptureStarted) finalLines.push("");
    return;
  }

  const lower = trimmed.toLowerCase();
  if (
    lower.includes("final answer") ||
    lower.includes("llm generating final answer") ||
    lower.includes("calling llm directly")
  ) {
    finalCaptureStarted = true;
    finalLines = [];
    actualResult.textContent = "Đang nhận kết quả...";
    return;
  }

  if (!finalCaptureStarted) return;
  if (
    trimmed.startsWith("-") ||
    trimmed.startsWith("=") ||
    trimmed.startsWith("[Improvements") ||
    trimmed.startsWith("[Limitations") ||
    trimmed.startsWith("Next:") ||
    trimmed.startsWith("Stage 5")
  ) {
    if (finalLines.join("").trim()) finalCaptureStarted = false;
    return;
  }

  finalLines.push(line);
  const cleaned = finalLines.join("\n").trim();
  if (cleaned) {
    actualResult.textContent = cleaned;
    actualResult.scrollTop = actualResult.scrollHeight;
  }
}

function runSelectedStage() {
  const stage = stages[activeStageIndex];
  const params = new URLSearchParams({
    question: questionInput.value.trim() || stage.question,
    system_prompt: promptInput.value.trim() || defaultPrompt(stage.id),
    tools: selectedToolNames().join(","),
  });
  stopPlayback();
  stopRunStream();
  resetRunPanel();
  setRunStatus("Đang chạy", "running");
  appendLog(`$ interactive run ${stage.source}`);
  appendLog(`[visualizer] question: ${params.get("question")}`);
  appendLog(`[visualizer] tools: ${params.get("tools") || "(none)"}`);

  runStream = new EventSource(`${API_BASE}/api/run-interactive/${stage.id}?${params.toString()}`);

  runStream.addEventListener("meta", (event) => {
    const data = JSON.parse(event.data);
    logPath.textContent = data.log;
    appendLog(`[visualizer] log file: ${data.log}`);
    appendLog(`[visualizer] python: ${data.python}`);
  });

  runStream.addEventListener("process", (event) => {
    const data = JSON.parse(event.data);
    appendLog(`[visualizer] started real process pid=${data.pid}`);
    appendLog(`[visualizer] source: ${data.source}`);
  });

  runStream.addEventListener("line", (event) => {
    const data = JSON.parse(event.data);
    appendLog(data.text);
    const nodeId = inferNodeFromLog(data.text);
    if (nodeId) setStepByNode(nodeId);
    updateActualResult(data.text);
  });

  runStream.addEventListener("visual", (event) => {
    pushVisualEvent(JSON.parse(event.data));
  });

  runStream.addEventListener("done", (event) => {
    const data = JSON.parse(event.data);
    setRunStatus(data.ok ? "Hoàn tất" : `Lỗi ${data.return_code}`, data.ok ? "ok" : "failed");
    appendLog(`[visualizer] finished with code ${data.return_code}`);
    if (!finalLines.join("").trim()) {
      actualResult.textContent = data.ok
        ? "Stage chạy xong nhưng không tìm thấy marker kết quả cuối trong log."
        : "Stage lỗi. Xem Live run log để biết chi tiết.";
    }
    stopRunStream();
  });

  runStream.onerror = () => {
    setRunStatus("Mất kết nối", "failed");
    appendLog("[visualizer] stream disconnected");
    stopRunStream();
  };
}

stageNav.addEventListener("click", (event) => {
  const button = event.target.closest("[data-stage]");
  if (!button) return;
  setStage(Number(button.dataset.stage));
});

timeline.addEventListener("click", (event) => {
  const item = event.target.closest("[data-step]");
  if (!item) return;
  stopPlayback();
  setStep(Number(item.dataset.step));
});

prevStep.addEventListener("click", () => {
  stopPlayback();
  setStep(activeStepIndex - 1);
});

nextStep.addEventListener("click", () => {
  stopPlayback();
  setStep(activeStepIndex + 1);
});

playFlow.addEventListener("click", () => {
  if (playTimer) {
    stopPlayback();
    return;
  }
  playFlow.innerHTML = `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 5h4v14H6zM14 5h4v14h-4z" />
    </svg>
    Tạm dừng
  `;
  playTimer = setInterval(() => {
    const stage = stages[activeStageIndex];
    const next = activeStepIndex + 1;
    if (next >= stage.steps.length) {
      stopPlayback();
      return;
    }
    setStep(next);
  }, 900);
});

runActual.addEventListener("click", runSelectedStage);
toolChecks.addEventListener("change", updateSelectedToolCount);

async function loadVisualizerConfig() {
  try {
    const response = await fetch(`${API_BASE}/api/visualizer-config`);
    if (!response.ok) throw new Error(`Config request failed: ${response.status}`);
    stages = await response.json();
    activeStageIndex = 0;
    renderStage();
  } catch (error) {
    document.body.innerHTML = `
      <main class="workspace">
        <section class="run-panel">
          <h1>Không tải được visualizer config</h1>
          <pre class="terminal-log">${error.message}</pre>
        </section>
      </main>
    `;
  }
}

loadVisualizerConfig();
