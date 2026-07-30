import { useState, useCallback, useEffect, useRef } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  Node,
  BackgroundVariant,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";

// ────────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────────
type RunStatus = "idle" | "running" | "paused" | "done" | "error";
type Scenario = "scenario1" | "scenario2" | "scenario3" | "scenario4";
type Tab = "logs" | "audit";

interface LogEntry {
  ts: string;
  tag: "system" | "superstep" | "thinking" | "done" | "error" | "hitl";
  msg: string;
}
interface AuditEntry {
  superstep: number;
  msg: string;
  tt: string;
}
interface AgentDef {
  id: string;
  role: string;
  model: string;
  goal: string;
}

// ────────────────────────────────────────────────────────────
// Scenarios config
// ────────────────────────────────────────────────────────────
const SCENARIOS: { id: Scenario; title: string; desc: string; defaultObjective: string }[] = [
  {
    id: "scenario1",
    title: "Architect Auto-Plan",
    desc: "Korch auto-decomposes your goal into a multi-agent plan.",
    defaultObjective: "Research and summarize the top 3 AI agent frameworks in 2025.",
  },
  {
    id: "scenario2",
    title: "Swarm Designer",
    desc: "Build a custom multi-agent topology with explicit edges.",
    defaultObjective: "Write a comprehensive market analysis for the EV sector.",
  },
  {
    id: "scenario3",
    title: "Tool-Augmented Research",
    desc: "Agents with web_search and calculate_tax tools to do financial analysis.",
    defaultObjective: "Verify Acme Corp revenue and calculate a 15% tax obligation.",
  },
  {
    id: "scenario4",
    title: "HITL Governance",
    desc: "Run with a human-in-the-loop checkpoint before superstep 1.",
    defaultObjective: "Analyze and summarize the risks in the supply chain document.",
  },
];

// The concrete Bedrock model id varies by AWS region (cross-region inference profile prefix
// us./eu./apac./au./global. or a bare foundation-model id) — configurable at build time via
// VITE_BEDROCK_MODEL so a redeploy to a different region never needs a source change.
const BEDROCK_MODEL = `bedrock/${import.meta.env.VITE_BEDROCK_MODEL ?? "us.anthropic.claude-sonnet-4-20250514-v1:0"}`;

const DEFAULT_AGENTS: AgentDef[] = [
  { id: "researcher",  role: "Researcher",  model: BEDROCK_MODEL, goal: "Find information from the web." },
  { id: "analyst",     role: "Analyst",     model: BEDROCK_MODEL, goal: "Analyze collected data." },
  { id: "writer",      role: "Writer",      model: BEDROCK_MODEL, goal: "Produce the final report." },
];
const DEFAULT_EDGES = [["researcher","analyst"],["analyst","writer"]];

const MODELS = [
  BEDROCK_MODEL,
  "openai/gpt-4o",
  "openai/gpt-4o-mini",
  "anthropic/claude-3-5-sonnet-20241022-v2",
];

// Empty string in production (behind the nginx reverse proxy, same-origin /api/*); defaults to the
// local dev backend otherwise. Configure via VITE_API_BASE at build time (see .env.example).
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

// ────────────────────────────────────────────────────────────
// Custom Node Component
// ────────────────────────────────────────────────────────────
interface NodeData { role: string; model: string; status: RunStatus; lastMsg?: string; }
function AgentNode({ data }: { data: NodeData }) {
  return (
    <div className={`knode ${data.status}`}>
      <div className="knode-header">
        <span className="knode-dot" />
        <span className="knode-role">{data.role}</span>
      </div>
      <div className="knode-model">{data.model.split("/").pop()}</div>
      {data.lastMsg && <div className="knode-msg">{data.lastMsg}</div>}
    </div>
  );
}
const nodeTypes = { agentNode: AgentNode };

// ────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────
function nowStr() {
  return new Date().toISOString().slice(11, 23);
}
function agentsToFlowNodes(agents: AgentDef[]): Node[] {
  return agents.map((a, i) => ({
    id: a.id,
    type: "agentNode",
    position: { x: 140 + i * 200, y: 120 },
    data: { role: a.role, model: a.model, status: "idle" as RunStatus, lastMsg: "" },
  }));
}
function edgesToFlowEdges(edges: string[][]): Edge[] {
  return edges.map(([s, t]) => ({
    id: `${s}-${t}`,
    source: s,
    target: t,
    markerEnd: { type: MarkerType.ArrowClosed, color: "#4d82b8" },
    style: { stroke: "#4d82b8", strokeWidth: 2 },
  }));
}

// ────────────────────────────────────────────────────────────
// Config Modal
// ────────────────────────────────────────────────────────────
function ConfigModal({ onClose }: { onClose: () => void }) {
  const [openai, setOpenai] = useState("");
  const [anthropic, setAnthropic] = useState("");
  const [bedrock, setBedrock] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await fetch(`${API_BASE}/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ openai_key: openai, anthropic_key: anthropic, bedrock_token: bedrock }),
      });
      setSaved(true);
      setTimeout(onClose, 900);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-title">⚙ API Configuration</div>
        <div className="modal-sub">Set provider API keys. Keys are stored in memory for this session only.</div>
        <div className="config-field">
          <label>OpenAI API Key</label>
          <input type="password" placeholder="sk-..." value={openai} onChange={e=>setOpenai(e.target.value)} />
        </div>
        <div className="config-field">
          <label>Anthropic API Key</label>
          <input type="password" placeholder="sk-ant-..." value={anthropic} onChange={e=>setAnthropic(e.target.value)} />
        </div>
        <div className="config-field">
          <label>AWS Bedrock Bearer Token</label>
          <input type="password" placeholder="bedrock-api-key-..." value={bedrock} onChange={e=>setBedrock(e.target.value)} />
        </div>
        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saved ? "✓ Saved!" : saving ? "Saving..." : "Save Keys"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────
// HITL Modal
// ────────────────────────────────────────────────────────────
function HITLModal({ runId, onDone }: { runId: string; onDone: () => void }) {
  const [feedback, setFeedback] = useState("");
  const [loading, setLoading] = useState(false);

  async function decide(action: "approve" | "reject") {
    setLoading(true);
    try {
      await fetch(`${API_BASE}/api/runs/${runId}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback }),
      });
      onDone();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <div className="modal-title" style={{ color: "var(--amber)" }}>⏸ Human-in-the-Loop Checkpoint</div>
        <div className="modal-sub">
          The swarm has paused before superstep 1 for operator approval. Review the objective and decide whether to proceed.
        </div>
        <div className="config-field">
          <label>Feedback / Instructions (optional)</label>
          <input
            type="text"
            placeholder="Proceed as planned…"
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            style={{ fontFamily: "var(--font)" }}
          />
        </div>
        <div className="modal-actions">
          <button className="btn btn-danger" onClick={() => decide("reject")} disabled={loading}>✗ Reject & Halt</button>
          <button className="btn btn-success" onClick={() => decide("approve")} disabled={loading}>
            {loading ? "…" : "✓ Approve & Continue"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────
// Add Agent Form
// ────────────────────────────────────────────────────────────
function AddAgentForm({ onAdd, onCancel }: { onAdd: (a: AgentDef) => void; onCancel: () => void }) {
  const [id, setId]     = useState("");
  const [role, setRole] = useState("");
  const [model, setModel] = useState(MODELS[0]);
  const [goal, setGoal] = useState("");

  function submit() {
    if (!id.trim() || !role.trim()) return;
    onAdd({ id: id.trim().toLowerCase().replace(/\s+/g,"-"), role: role.trim(), model, goal });
  }

  return (
    <div className="add-agent-form">
      <div className="form-group">
        <label className="form-label">Agent ID (unique)</label>
        <input className="form-input" placeholder="e.g. summarizer" value={id} onChange={e=>setId(e.target.value)} />
      </div>
      <div className="form-group">
        <label className="form-label">Role</label>
        <input className="form-input" placeholder="e.g. Summarizer" value={role} onChange={e=>setRole(e.target.value)} />
      </div>
      <div className="form-group">
        <label className="form-label">Model</label>
        <select className="form-select" value={model} onChange={e=>setModel(e.target.value)}>
          {MODELS.map(m=><option key={m} value={m}>{m}</option>)}
        </select>
      </div>
      <div className="form-group">
        <label className="form-label">Goal / Instruction</label>
        <textarea className="form-textarea" placeholder="Describe what this agent does..." value={goal} onChange={e=>setGoal(e.target.value)} />
      </div>
      <div className="flex gap-2 mt-2">
        <button className="btn btn-ghost btn-sm" onClick={onCancel}>Cancel</button>
        <button className="btn btn-primary btn-sm" onClick={submit}>+ Add Agent</button>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────
// Main App
// ────────────────────────────────────────────────────────────
export default function App() {
  // Scenario config
  const [scenario, setScenario] = useState<Scenario>("scenario1");
  const [objective, setObjective] = useState(SCENARIOS[0].defaultObjective);
  const [maxSupersteps, setMaxSupersteps] = useState(8);
  const [trustThreshold, setTrustThreshold] = useState(0.5);
  const [agents, setAgents] = useState<AgentDef[]>(DEFAULT_AGENTS);
  const [rawEdges, setRawEdges] = useState<string[][]>(DEFAULT_EDGES);
  const [showAddAgent, setShowAddAgent] = useState(false);
  const [edgesText, setEdgesText] = useState(DEFAULT_EDGES.map(e=>e.join("->")).join(", "));

  // UI state
  const [runStatus, setRunStatus] = useState<RunStatus>("idle");
  const [runId, setRunId]         = useState<string | null>(null);
  const [tab, setTab]             = useState<Tab>("logs");
  const [logs, setLogs]           = useState<LogEntry[]>([]);
  const [audit, setAudit]         = useState<AuditEntry[]>([]);
  const [showConfig, setShowConfig] = useState(false);
  const [showHITL, setShowHITL]   = useState(false);
  const [trustScore, setTrustScore] = useState<number | null>(null);
  const [finalAnswer, setFinalAnswer] = useState<string | null>(null);
  const [superstep, setSuperstep] = useState(0);

  // React Flow state
  const [rfNodes, setRfNodes, onNodesChange] = useNodesState([]);
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState([]);
  const logEndRef = useRef<HTMLDivElement>(null);
  const sseRef    = useRef<EventSource | null>(null);

  // Auto-scroll logs
  useEffect(() => { logEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [logs]);

  // Build flow graph when scenario/agents/edges change
  useEffect(() => {
    if (scenario === "scenario1") {
      setRfNodes([]);
      setRfEdges([]);
    } else {
      setRfNodes(agentsToFlowNodes(agents));
      setRfEdges(edgesToFlowEdges(rawEdges));
    }
  }, [scenario, agents, rawEdges]);

  function pushLog(tag: LogEntry["tag"], msg: string) {
    setLogs(prev => [...prev, { ts: nowStr(), tag, msg }]);
  }

  function updateNodeStatus(agentId: string, status: RunStatus, lastMsg?: string) {
    setRfNodes(prev => prev.map(n =>
      n.id === agentId ? { ...n, data: { ...n.data, status, lastMsg: lastMsg ?? n.data.lastMsg } } : n
    ));
  }

  function resetAll() {
    setRunStatus("idle");
    setRunId(null);
    setLogs([]);
    setAudit([]);
    setTrustScore(null);
    setFinalAnswer(null);
    setSuperstep(0);
    setRfNodes(prev => prev.map(n => ({ ...n, data: { ...n.data, status: "idle", lastMsg: "" } })));
    sseRef.current?.close();
  }

  async function startRun() {
    resetAll();
    pushLog("system", `Starting ${scenario} — connecting to backend...`);

    // Parse edges from text for scenario2/3/4
    let parsedEdges = rawEdges;
    if (edgesText.trim()) {
      parsedEdges = edgesText.split(",").map(s => s.trim().split("->").map(x=>x.trim())).filter(e=>e.length===2);
      setRawEdges(parsedEdges);
    }

    let body: Record<string,unknown> = {
      scenario,
      objective,
      max_supersteps: maxSupersteps,
      use_temporal: false,
      trust_threshold: trustThreshold,
    };

    if (scenario !== "scenario1") {
      body.agents = agents.map(a => ({
        id: a.id, role: a.role, model: a.model,
        goal: a.goal, backstory: "", tools: scenario === "scenario3" ? ["web_search","calculate_tax"] : [],
      }));
      body.edges = parsedEdges;
    }

    let data: { run_id: string };
    try {
      const res = await fetch(`${API_BASE}/api/runs/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json();
        pushLog("error", `Backend error: ${JSON.stringify(err.detail)}`);
        setRunStatus("error");
        return;
      }
      data = await res.json();
    } catch (e: unknown) {
      pushLog("error", `Cannot reach backend at ${API_BASE}. Is it running? (${(e as Error).message})`);
      setRunStatus("error");
      return;
    }

    setRunId(data.run_id);
    setRunStatus("running");
    pushLog("system", `Run created: ${data.run_id}`);

    // Open SSE stream
    const es = new EventSource(`${API_BASE}/api/runs/${data.run_id}/stream`);
    sseRef.current = es;

    es.onmessage = (ev) => {
      let event: { name: string; payload: Record<string,unknown>; run_id: string };
      try { event = JSON.parse(ev.data); } catch { return; }

      const { name, payload } = event;

      if (name === "status_change") {
        const status = payload.status as string;
        pushLog(
          status === "completed" ? "done" : status === "failed" || status === "cancelled" ? "error" : status === "governance_paused" ? "hitl" : "system",
          `Status → ${status}${payload.final_answer ? ": " + String(payload.final_answer).slice(0,200) : ""}${payload.message ? " — " + String(payload.message) : ""}`
        );

        if (status === "running") {
          setRunStatus("running");
          setAudit(prev => [...prev, { superstep: 0, msg: `Run started: ${payload.objective}`, tt: new Date().toISOString() }]);
        } else if (status === "governance_paused") {
          setRunStatus("paused");
          setShowHITL(true);
          if (typeof payload.trust_score === "number") setTrustScore(payload.trust_score);
          pushLog("hitl", `HITL pause at superstep ${payload.superstep}. Trust score: ${payload.trust_score}`);
        } else if (status === "completed") {
          setRunStatus("done");
          setFinalAnswer(String(payload.final_answer ?? ""));
          if (typeof payload.trust_score === "number") setTrustScore(payload.trust_score);
          // mark all nodes done
          setRfNodes(prev => prev.map(n => ({ ...n, data: { ...n.data, status: "done" } })));
          es.close();
        } else if (status === "failed") {
          setRunStatus("error");
          pushLog("error", `Run failed: ${payload.error}`);
          setRfNodes(prev => prev.map(n => ({ ...n, data: { ...n.data, status: "error" } })));
          es.close();
        } else if (status === "cancelled") {
          setRunStatus("error");
          setShowHITL(false);
          pushLog("error", `Run cancelled: ${payload.message ?? "Rejected by operator."}`);
          setRfNodes(prev => prev.map(n => ({ ...n, data: { ...n.data, status: "error" } })));
          es.close();
        }
      }

      if (name === "superstep") {
        const ss = payload.superstep as number ?? 0;
        setSuperstep(ss);
        pushLog("superstep", `Superstep ${ss} completed (status=${payload.status})`);
        setAudit(prev => [...prev, { superstep: ss, msg: `Superstep ${ss}: ${payload.status}`, tt: new Date().toISOString() }]);
      }

      if (name === "agent_thinking") {
        const { agent_id, status: s, model } = payload as { agent_id:string; status:string; model:string; error?:string };
        if (s === "thinking") {
          pushLog("thinking", `[${agent_id}] → ${model}: thinking...`);
          updateNodeStatus(agent_id, "running", "thinking…");
        } else if (s === "done") {
          pushLog("thinking", `[${agent_id}] → response ready`);
          updateNodeStatus(agent_id, "done");
        } else if (s === "error") {
          pushLog("error", `[${agent_id}] → error: ${payload.error}`);
          updateNodeStatus(agent_id, "error");
        }
      }

      // Auto-build nodes for scenario1 (Korch autonomous)
      if (name === "superstep" && scenario === "scenario1" && rfNodes.length === 0) {
        setRfNodes([{
          id: "korch-orchestrator",
          type: "agentNode",
          position: { x: 200, y: 150 },
          data: { role: "Korch Orchestrator", model: "auto", status: "running" as RunStatus },
        }]);
      }
    };

    es.onerror = () => {
      if (runStatus !== "done" && runStatus !== "error") {
        pushLog("error", "SSE stream lost. The run may have completed.");
        setRunStatus("error");
      }
      es.close();
    };
  }

  function handleHITLDone() {
    setShowHITL(false);
    setRunStatus("running");
    pushLog("hitl", "Operator decision submitted — resuming execution...");
  }

  function handleScenarioChange(s: Scenario) {
    setScenario(s);
    const sc = SCENARIOS.find(x => x.id === s)!;
    setObjective(sc.defaultObjective);
    if (s !== "scenario1") {
      setAgents(DEFAULT_AGENTS);
      setRawEdges(DEFAULT_EDGES);
      setEdgesText(DEFAULT_EDGES.map(e=>e.join("->")).join(", "));
    }
  }

  const onRFConnect = useCallback(
    (conn: Connection) => setRfEdges((eds) => addEdge({ ...conn, markerEnd: { type: MarkerType.ArrowClosed } }, eds)),
    [setRfEdges]
  );

  const trustClass = trustScore === null ? "" : trustScore >= 0.7 ? "trust-high" : trustScore >= 0.4 ? "trust-medium" : "trust-low";

  return (
    <div className="app">
      {/* ── Topbar ── */}
      <header className="topbar">
        <div className="topbar-logo">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5"/>
            <line x1="12" y1="2" x2="12" y2="22"/><line x1="2" y1="8.5" x2="22" y2="8.5"/>
            <line x1="2" y1="15.5" x2="22" y2="15.5"/>
          </svg>
          Korchestrator SDK
        </div>
        <span className="topbar-version">v0.1.0</span>
        <div className="topbar-spacer" />
        {trustScore !== null && (
          <span className={`trust-badge ${trustClass}`}>
            ⬡ Trust {(trustScore * 100).toFixed(0)}%
          </span>
        )}
        <div className="topbar-status">
          <span className={`status-dot ${runStatus === "idle" ? "" : runStatus}`} />
          {runStatus === "idle" ? "Idle" : runStatus === "running" ? `Running · step ${superstep}` :
           runStatus === "paused" ? "Awaiting HITL" : runStatus === "done" ? "Completed" : "Error"}
        </div>
        <button className="btn btn-ghost btn-sm" id="config-btn" onClick={() => setShowConfig(true)}>⚙ Config</button>
      </header>

      {/* ── Main grid ── */}
      <div className="main-grid">

        {/* ── Left: Control Panel ── */}
        <aside className="panel-left">

          {/* Scenario selector */}
          <div className="panel-section">
            <div className="panel-label">Scenarios</div>
            {SCENARIOS.map(s => (
              <div
                key={s.id}
                id={`scenario-${s.id}`}
                className={`scenario-card ${scenario === s.id ? "active" : ""}`}
                onClick={() => handleScenarioChange(s.id)}
              >
                <div className="scenario-card-title">{s.title}</div>
                <div className="scenario-card-desc">{s.desc}</div>
              </div>
            ))}
          </div>

          {/* Run config */}
          <div className="panel-section">
            <div className="panel-label">Objective</div>
            <div className="form-group">
              <textarea
                className="form-textarea"
                id="objective-input"
                rows={3}
                value={objective}
                onChange={e => setObjective(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Max supersteps</label>
              <div className="range-row">
                <input type="range" min={1} max={20} value={maxSupersteps} onChange={e => setMaxSupersteps(+e.target.value)} />
                <span className="range-val">{maxSupersteps}</span>
              </div>
            </div>
            {scenario === "scenario4" && (
              <div className="form-group">
                <label className="form-label">Trust threshold (HITL trigger)</label>
                <div className="range-row">
                  <input type="range" min={0} max={1} step={0.05} value={trustThreshold} onChange={e => setTrustThreshold(+e.target.value)} />
                  <span className="range-val">{trustThreshold.toFixed(2)}</span>
                </div>
              </div>
            )}
          </div>

          {/* Agents (for scenario2/3/4) */}
          {scenario !== "scenario1" && (
            <div className="panel-section" style={{ flex: 1, overflowY: "auto" }}>
              <div className="panel-label flex justify-between items-center">
                <span>Agents</span>
                <button className="btn btn-ghost btn-sm btn-icon" id="add-agent-btn" onClick={() => setShowAddAgent(p=>!p)} title="Add agent">+</button>
              </div>
              <div className="agent-chip-list">
                {agents.map((a, i) => (
                  <div key={a.id} className="agent-chip">
                    <div>
                      <div className="agent-chip-role">{a.role}</div>
                      <div className="agent-chip-model">{a.id}</div>
                    </div>
                    <button
                      className="btn btn-ghost btn-sm btn-icon text-red"
                      style={{ fontSize: "12px" }}
                      onClick={() => setAgents(prev => prev.filter((_,j)=>j!==i))}
                    >✕</button>
                  </div>
                ))}
              </div>
              {showAddAgent && (
                <AddAgentForm
                  onAdd={(a) => { setAgents(prev => [...prev, a]); setShowAddAgent(false); }}
                  onCancel={() => setShowAddAgent(false)}
                />
              )}
              <div className="form-group mt-2">
                <label className="form-label">Edges (id1→id2, id2→id3)</label>
                <input
                  className="form-input text-xs font-mono"
                  id="edges-input"
                  value={edgesText}
                  onChange={e => setEdgesText(e.target.value)}
                  placeholder="researcher->analyst, analyst->writer"
                />
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="panel-section">
            {runStatus === "idle" || runStatus === "done" || runStatus === "error" ? (
              <button className="btn btn-primary btn-block" id="run-btn" onClick={startRun}>
                ▶ Run {SCENARIOS.find(s=>s.id===scenario)?.title}
              </button>
            ) : (
              <button className="btn btn-danger btn-block" id="stop-btn" onClick={resetAll}>
                ■ Cancel Run
              </button>
            )}

            {/* Progress */}
            {runStatus === "running" && (
              <div style={{ marginTop: 10 }}>
                <div className="flex justify-between text-xs text-muted">
                  <span>Superstep {superstep}</span><span>/{maxSupersteps}</span>
                </div>
                <div className="progress-bar mt-1">
                  <div className="progress-fill" style={{ width: `${Math.min((superstep/maxSupersteps)*100, 100)}%` }} />
                </div>
              </div>
            )}

            {/* Final answer peek */}
            {finalAnswer && (
              <div style={{ marginTop: 10, padding: "8px 10px", background: "rgba(50,200,120,0.08)", border: "1px solid rgba(50,200,120,0.25)", borderRadius: "var(--radius-sm)", fontSize: 11, color: "var(--teal)", maxHeight: 80, overflowY: "auto", fontFamily: "var(--font)", lineHeight: 1.5 }}>
                <strong>Final Answer:</strong> {finalAnswer}
              </div>
            )}
          </div>
        </aside>

        {/* ── Center: React Flow Canvas ── */}
        <main className="flow-center">
          <div className="flow-toolbar">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--blue)" strokeWidth="2">
              <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
              <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
            </svg>
            <span style={{ fontSize: 12, color: "var(--text-2)", fontWeight: 600 }}>Execution Graph</span>
            <span className="topbar-version">{SCENARIOS.find(s=>s.id===scenario)?.title}</span>
          </div>
          <div className="flow-canvas-wrap">
            {rfNodes.length === 0 && scenario === "scenario1" ? (
              <div className="empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5"/>
                  <line x1="12" y1="2" x2="12" y2="22"/><line x1="2" y1="8.5" x2="22" y2="8.5"/>
                </svg>
                <h3>Korch Auto-Plan Mode</h3>
                <p>The agent graph will be constructed automatically at runtime. Start a run to see the graph populate live.</p>
              </div>
            ) : rfNodes.length === 0 ? (
              <div className="empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <h3>No Agents Defined</h3>
                <p>Add agents in the left panel to build your topology.</p>
              </div>
            ) : (
              <ReactFlow
                nodes={rfNodes}
                edges={rfEdges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onRFConnect}
                nodeTypes={nodeTypes}
                fitView
                fitViewOptions={{ padding: 0.3 }}
                minZoom={0.3}
                maxZoom={2}
              >
                <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="rgba(255,255,255,0.07)" />
                <Controls showInteractive={false} />
                <MiniMap
                  nodeColor={(n) => {
                    const s = (n.data as NodeData).status;
                    return s === "running" ? "#32c878" : s === "done" ? "#34cdc4" : s === "error" ? "#dc3232" : "#4d82b8";
                  }}
                  maskColor="rgba(9,9,15,0.85)"
                />
              </ReactFlow>
            )}
          </div>
        </main>

        {/* ── Right: Logs + Audit ── */}
        <aside className="panel-right">
          <div className="tabs">
            <div className={`tab ${tab === "logs" ? "active" : ""}`} id="logs-tab" onClick={() => setTab("logs")}>
              ⌨ Logs <span style={{ fontFamily:"var(--mono)", fontSize:10, marginLeft:4, color:"var(--text-3)" }}>{logs.length}</span>
            </div>
            <div className={`tab ${tab === "audit" ? "active" : ""}`} id="audit-tab" onClick={() => setTab("audit")}>
              📋 Audit Trail <span style={{ fontFamily:"var(--mono)", fontSize:10, marginLeft:4, color:"var(--text-3)" }}>{audit.length}</span>
            </div>
          </div>

          {tab === "logs" ? (
            <div className="log-terminal" id="log-terminal">
              {logs.length === 0 && (
                <span className="text-muted">Logs will appear here when a run starts…</span>
              )}
              {logs.map((l, i) => (
                <div key={i} className="log-entry">
                  <span className="log-time">{l.ts}</span>
                  <span className={`log-tag ${l.tag}`}>{l.tag}</span>
                  <span className="log-msg">{l.msg}</span>
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          ) : (
            <div className="audit-trail" id="audit-trail">
              {audit.length === 0 && (
                <span className="text-muted text-xs">Audit entries will appear here…</span>
              )}
              {audit.map((a, i) => (
                <div key={i} className="audit-entry">
                  <div className="audit-superstep">Superstep {a.superstep} · {new Date(a.tt).toLocaleTimeString()}</div>
                  <div className="audit-msg">{a.msg}</div>
                </div>
              ))}
            </div>
          )}
        </aside>
      </div>

      {/* ── Modals ── */}
      {showConfig && <ConfigModal onClose={() => setShowConfig(false)} />}
      {showHITL && runId && <HITLModal runId={runId} onDone={handleHITLDone} />}
    </div>
  );
}
