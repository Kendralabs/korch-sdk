import { useRef, useState } from "react";

// A small, self-contained panel for the real-OpenAI support-escalation swarm
// (dashboard/backend/support_escalation_router.py). Deliberately independent of the rest of
// App.tsx's ReactFlow/scenario state — its own inputs, its own SSE stream, its own log.

const DEFAULT_OBJECTIVE =
  "Handle this customer support escalation: 'My recurring subscription payment failed twice " +
  "this week even though I have sufficient funds. I need this resolved today.'";

const AGENT_IDS = ["triage", "researcher", "resolver", "reviewer"] as const;
const DEFAULT_MODELS: Record<(typeof AGENT_IDS)[number], string> = {
  triage: "gpt-4o-mini",
  researcher: "gpt-4o-mini",
  resolver: "gpt-4o",
  reviewer: "gpt-4o-mini",
};

interface LogLine {
  ts: string;
  text: string;
}

function nowStr() {
  return new Date().toISOString().slice(11, 23);
}

export default function SupportEscalationDemo({ apiBase }: { apiBase: string }) {
  const [objective, setObjective] = useState(DEFAULT_OBJECTIVE);
  const [models, setModels] = useState(DEFAULT_MODELS);
  const [running, setRunning] = useState(false);
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [resolution, setResolution] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  function pushLog(text: string) {
    setLogs((prev) => [...prev, { ts: nowStr(), text }]);
  }

  async function run() {
    setRunning(true);
    setLogs([]);
    setResolution(null);
    esRef.current?.close();

    pushLog("Starting support-escalation swarm…");
    let runId: string;
    try {
      const res = await fetch(`${apiBase}/api/swarm/support-escalation/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ objective, agent_models: models }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      ({ run_id: runId } = await res.json());
    } catch (e) {
      pushLog(`Failed to start run: ${(e as Error).message}`);
      setRunning(false);
      return;
    }
    pushLog(`Run created: ${runId}`);

    const es = new EventSource(`${apiBase}/api/swarm/support-escalation/stream/${runId}`);
    esRef.current = es;

    es.onmessage = (ev) => {
      let event: { name: string; payload: Record<string, unknown> };
      try {
        event = JSON.parse(ev.data);
      } catch {
        return;
      }
      const { name, payload } = event;

      if (name === "superstep") {
        pushLog(`Superstep ${payload.superstep} completed (status=${payload.status})`);
      }

      if (name === "status_change") {
        const status = payload.status as string;
        pushLog(`Status → ${status}`);
        if (status === "completed") {
          setResolution(String(payload.resolution ?? payload.final_answer ?? ""));
          setRunning(false);
          es.close();
        } else if (status === "failed") {
          pushLog(`Run failed: ${payload.error}`);
          setRunning(false);
          es.close();
        }
      }
    };

    es.onerror = () => {
      if (running) pushLog("SSE stream lost. The run may have completed.");
      es.close();
      setRunning(false);
    };
  }

  return (
    <div className="main-grid">
      <aside className="panel-left">
        <div className="panel-section">
          <div className="panel-label">Customer Support Escalation (real OpenAI models)</div>
          <div className="form-group">
            <label className="form-label">Objective</label>
            <textarea
              className="form-textarea"
              rows={4}
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
            />
          </div>
          {AGENT_IDS.map((id) => (
            <div className="form-group" key={id}>
              <label className="form-label">{id} model</label>
              <input
                className="form-input"
                value={models[id]}
                onChange={(e) => setModels((prev) => ({ ...prev, [id]: e.target.value }))}
              />
            </div>
          ))}
        </div>
        <div className="panel-section">
          <button className="btn btn-primary btn-block" onClick={run} disabled={running}>
            {running ? "Running…" : "▶ Run Escalation Swarm"}
          </button>
          <p className="text-xs text-muted" style={{ marginTop: 8 }}>
            Set <code>OPENAI_API_KEY</code> in <code>dashboard/backend/.env</code> to use real
            models; otherwise this runs against a deterministic offline stand-in.
          </p>
        </div>
      </aside>

      <main className="panel-main">
        <div className="log-terminal" style={{ height: "100%" }}>
          {logs.length === 0 && (
            <span className="text-muted">Logs will appear here when a run starts…</span>
          )}
          {logs.map((l, i) => (
            <div key={i} className="log-entry">
              <span className="log-time">{l.ts}</span>
              <span className="log-msg">{l.text}</span>
            </div>
          ))}
        </div>
      </main>

      <aside className="panel-right">
        <div className="panel-section">
          <div className="panel-label">Resolution</div>
          {resolution ? (
            <div className="audit-entry">
              <div className="audit-msg">{resolution}</div>
            </div>
          ) : (
            <span className="text-muted text-xs">
              The reviewer-approved resolution will appear here once the swarm completes.
            </span>
          )}
        </div>
      </aside>
    </div>
  );
}
