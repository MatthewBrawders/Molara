import { useEffect, useMemo, useState } from "react";
import molaraIcon from "../assets/molara_icon.png";

const API = import.meta.env.VITE_API_BASE_URL || "/api";

export default function App() {
  const [health, setHealth] = useState({ ok: false, raw: "checking…" });
  const [mode, setMode] = useState("search"); // "search" | "ask"
  const [query, setQuery] = useState("kinase receptor phosphorylation");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // results
  const [results, setResults] = useState([]); // /search
  const [answer, setAnswer] = useState("");   // /query or stream
  const [sources, setSources] = useState([]); // citations from stream final event

  const apiHealthy = !!health.ok;

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/health`);
        const j = await r.json();
        setHealth({ ok: !!j?.ok, raw: JSON.stringify(j) });
      } catch {
        setHealth({ ok: false, raw: "error" });
      }
    })();
  }, []);

  async function doSearch(e) {
    e?.preventDefault();
    setError("");
    setLoading(true);
    setResults([]);
    setAnswer("");
    setSources([]);
    try {
      if (mode === "search") {
        const res = await fetch(`${API}/search`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ query, top_k: 5 }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setResults(Array.isArray(data) ? data : []);
      } else {
        // STREAMING ASK
        await askStream(query, 5);
      }
    } catch (err) {
      setError(err?.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  async function askStream(question, top_k = 5) {
    setAnswer("");
    setSources([]);
    const res = await fetch(`${API}/query/stream`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question, top_k }),
    });
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      // parse SSE: split on blank lines, keep remainder in buffer
      let idx;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const rawEvt = buf.slice(0, idx);
        buf = buf.slice(idx + 2);

        // "data: {...}" lines -> combine
        const dataLines = rawEvt
          .split("\n")
          .filter((ln) => ln.startsWith("data:"))
          .map((ln) => ln.slice(5).trim());
        if (!dataLines.length) continue;

        try {
          const payload = JSON.parse(dataLines.join(""));
          if (payload.delta) {
            setAnswer((prev) => prev + payload.delta);
          }
          if (payload.final) {
            setSources(Array.isArray(payload.sources) ? payload.sources : []);
          }
        } catch {
          // ignore malformed chunk
        }
      }
    }
  }

  async function addSample() {
    setError("");
    setLoading(true);
    try {
      await fetch(`${API}/chunks/auto`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          book_title: "Kinase Handbook",
          section: "Intro",
          chunk_idx: 0,
          body:
            "Receptor tyrosine kinases (RTKs) are high-affinity cell surface receptors that regulate growth and differentiation by phosphorylating substrate proteins within signaling pathways.",
        }),
      });
      await doSearch();
    } catch (err) {
      setError(err?.message || "Insert failed");
    } finally {
      setLoading(false);
    }
  }

  const healthLabel = useMemo(() => {
    if (health.raw === "checking…") return "checking…";
    return apiHealthy ? "ok" : "error";
  }, [apiHealthy, health.raw]);

  return (
    <div className="wrap">
      <div className="topbar">
        <div className={`health ${apiHealthy ? "ok" : "bad"}`}>
          health: {healthLabel}
        </div>
      </div>

      <main className="hero">
        <img src={molaraIcon} alt="Molara icon" className="logo-spin" />
        <h1 className="brand">Molara</h1>

        {/* mode tabs */}
        <div className="tabs" role="tablist" aria-label="Mode">
          <button
            role="tab"
            aria-selected={mode === "search"}
            className={`tab ${mode === "search" ? "active" : ""}`}
            onClick={() => setMode("search")}
          >
            Search
          </button>
          <button
            role="tab"
            aria-selected={mode === "ask"}
            className={`tab ${mode === "ask" ? "active" : ""}`}
            onClick={() => setMode("ask")}
          >
            Ask (AI)
          </button>
        </div>

        <form onSubmit={doSearch} className="searchbar" role="search">
          <input
            className="search-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={mode === "search" ? "Search in your corpus…" : "Ask with RAG…"}
            aria-label="Search"
          />
          <button className="search-btn" type="submit" disabled={loading}>
            {loading ? (mode === "search" ? "Searching…" : "Asking…") : (mode === "search" ? "Search" : "Ask")}
          </button>
        </form>

        <button
          className="ghost-btn"
          type="button"
          onClick={addSample}
          disabled={loading}
          title="Seed one sample chunk, then run"
        >
          {loading ? "Loading…" : "Add sample chunk"}
        </button>

        <div className="health-raw" aria-live="polite">
          <code>{health.raw}</code>
        </div>

        {error ? <div className="error">{error}</div> : null}
      </main>

      {/* RESULTS */}
      {mode === "search" ? (
        <ul className="results">
          {results.map((r) => (
            <li key={r.id ?? `${r.book_title}-${r.section}-${r.chunk_idx}`} className="card">
              <div className="meta">
                <b>{r.book_title}</b>
                {r.section ? <span> · {r.section}</span> : null}
                <span> · #{r.chunk_idx}</span>
                {"score" in r && r.score != null ? (
                  <span className="badge">score: {Number(r.score).toFixed(4)}</span>
                ) : null}
              </div>
              <p>{r.body}</p>
            </li>
          ))}
          {!loading && results.length === 0 && (
            <li className="card empty">No results yet. Try a different query.</li>
          )}
        </ul>
      ) : (
        <section className="ask-wrap">
          {answer ? (
            <article className="answer card">
              <h2 className="answer-title">Answer</h2>
              <div className="answer-body">
                <RichTextWithCitations text={answer} />
              </div>
              {sources?.length ? (
                <>
                  <h3 className="sources-title">Sources</h3>
                  <ul className="sources">
                    {sources.map((s, i) => (
                      <li key={s.id ?? `${s.book_title}-${s.section}-${s.chunk_idx}`}>
                        <span className="badge">[{i + 1}]</span>{" "}
                        <b>{s.book_title}</b>
                        {s.section ? <span> · {s.section}</span> : null}
                        <span> · #{s.chunk_idx}</span>
                        {"score" in s && s.score != null ? (
                          <span className="muted"> · score {Number(s.score).toFixed(4)}</span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </>
              ) : null}
          </article>
          ) : (
            !loading && <div className="card empty">No answer yet. Ask something!</div>
          )}
        </section>
      )}
    </div>
  );
}

function RichTextWithCitations({ text }) {
  const parts = useMemo(() => text.split(/(\[[0-9]+\])/g).filter(Boolean), [text]);
  return (
    <p>
      {parts.map((p, i) =>
        /^\[[0-9]+\]$/.test(p) ? (
          <sup key={i} className="cite">{p}</sup>
        ) : (
          <span key={i}>{p}</span>
        )
      )}
    </p>
  );
}
