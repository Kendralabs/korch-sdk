import { useState } from "react";

// The simplest of the three demos: one agent, one question, one answer. Drives
// dashboard/backend/researcher_router.py's minimal run/stream endpoints.

const DEFAULT_QUESTION = "What is the difference between durable execution and a plain retry loop?";
const DEFAULT_MODEL = "gpt-4o-mini";

export default function ResearcherDemo({ apiBase }: { apiBase: string }) {
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [running, setRunning] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function ask() {
    setRunning(true);
    setAnswer(null);
    setError(null);

    let runId: string;
    try {
      const res = await fetch(`${apiBase}/api/swarm/researcher/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, model }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      ({ run_id: runId } = await res.json());
    } catch (e) {
      setError((e as Error).message);
      setRunning(false);
      return;
    }

    const es = new EventSource(`${apiBase}/api/swarm/researcher/stream/${runId}`);
    es.onmessage = (ev) => {
      let event: { name: string; payload: Record<string, unknown> };
      try {
        event = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (event.name === "run_completed") {
        const status = event.payload.status as string;
        if (status === "completed") {
          setAnswer(String(event.payload.answer ?? ""));
        } else {
          setError(String(event.payload.error ?? "The run failed."));
        }
        setRunning(false);
        es.close();
      }
    };
    es.onerror = () => {
      setError("Connection to the backend was lost.");
      setRunning(false);
      es.close();
    };
  }

  return (
    <div className="rd-root">
      <div className="rd-card">
        <div className="panel-label">Ask the Research Agent</div>
        <div className="form-group">
          <label className="form-label">Question</label>
          <textarea
            className="form-textarea"
            rows={3}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">Model</label>
          <input className="form-input" value={model} disabled={running} onChange={(e) => setModel(e.target.value)} />
        </div>
        <button className="btn btn-primary btn-block" onClick={ask} disabled={running || !question.trim()}>
          {running ? "Thinking…" : "▶ Ask"}
        </button>

        {error && <div className="rd-error">{error}</div>}

        {(running || answer) && (
          <div className="rd-answer">
            <div className="panel-label">Answer</div>
            {running && !answer ? (
              <span className="text-muted text-xs">Waiting for a response…</span>
            ) : (
              <div className="rd-answer-text">{answer}</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
