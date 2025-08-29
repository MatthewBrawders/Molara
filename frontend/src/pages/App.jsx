import { useEffect, useState } from "react";
import molaraIcon from "../assets/molara_icon.png";

const API = import.meta.env.VITE_API_BASE_URL || "/api";

export default function App() {
  const [health, setHealth] = useState("checking…");
  const [query, setQuery] = useState("kinase receptor phosphorylation");
  const [results, setResults] = useState([]);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then((j) => setHealth(JSON.stringify(j)))
      .catch(() => setHealth("error"));
  }, []);

  async function doSearch(e) {
    e?.preventDefault();
    setResults([]);
    const res = await fetch(`${API}/search`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query, top_k: 5 }),
    });
    const data = await res.json();
    setResults(Array.isArray(data) ? data : []);
  }

  async function addSample() {
    setAdding(true);
    try {
      await fetch(`${API}/chunks/auto`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          book_title: "Kinase Handbook",
          section: "Intro",
          chunk_idx: 0,
          body:
            "Receptor tyrosine kinases (RTKs) are high-affinity cell surface receptors...",
        }),
      });
      await doSearch();
    } finally {
      setAdding(false);
    }
  }

  return (
    <div className="wrap">
      <div className="topbar">
        <div className="health">health: {health}</div>
      </div>

      <main className="hero">
        <img src={molaraIcon} alt="Molara icon" className="logo-spin" />
        <h1 className="brand">Molara</h1>

        <form onSubmit={doSearch} className="searchbar" role="search">
          <input
            className="search-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask about kinases…"
            aria-label="Search"
          />
          <button className="search-btn" type="submit">Search</button>
        </form>

        <button
          className="ghost-btn"
          type="button"
          onClick={addSample}
          disabled={adding}
          title="Seed one sample chunk, then search"
        >
          {adding ? "Adding…" : "Add sample chunk"}
        </button>
      </main>

      <ul className="results">
        {results.map((r) => (
          <li key={r.id} className="card">
            <div className="meta">
              <b>{r.book_title}</b>
              {r.section ? <span> · {r.section}</span> : null}
              <span> · #{r.chunk_idx}</span>
            </div>
            <p>{r.body}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
