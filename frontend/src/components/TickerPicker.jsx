import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api.js";

// Searchable ticker picker. A plain <datalist> chokes on a 12k-option US universe
// (browsers silently truncate or fail to render it), so we filter in memory and
// show only the top matches as you type.
const MAX_SHOWN = 40;

export default function TickerPicker({ value, onChange, market, placeholder = "Search ticker or name" }) {
  const [all, setAll] = useState([]);
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(0);
  const boxRef = useRef(null);

  useEffect(() => {
    let dead = false;
    // Load every market's list so you can track a holding from either exchange.
    Promise.all([api.tickers("EGX").catch(() => []), api.tickers("US").catch(() => [])])
      .then(([a, b]) => { if (!dead) setAll([...(a || []), ...(b || [])]); });
    return () => { dead = true; };
  }, []);

  useEffect(() => {
    const onDoc = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const matches = useMemo(() => {
    const q = (value || "").trim().toLowerCase();
    if (!q) {
      // No query yet: show this market's names first so the list is never empty.
      return all.filter((c) => c.ticker.endsWith(`.${market}`)).slice(0, MAX_SHOWN);
    }
    const starts = [], contains = [];
    for (const c of all) {
      const t = c.ticker.toLowerCase(), n = (c.name || "").toLowerCase();
      if (t.startsWith(q)) starts.push(c);
      else if (t.includes(q) || n.includes(q)) contains.push(c);
      if (starts.length >= MAX_SHOWN) break;
    }
    return [...starts, ...contains].slice(0, MAX_SHOWN);
  }, [all, value, market]);

  const pick = (c) => { onChange(c.ticker); setOpen(false); };

  const onKey = (e) => {
    if (!open) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setHi((h) => Math.min(h + 1, matches.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setHi((h) => Math.max(h - 1, 0)); }
    else if (e.key === "Enter" && matches[hi]) { e.preventDefault(); pick(matches[hi]); }
    else if (e.key === "Escape") setOpen(false);
  };

  return (
    <div className="tickerpick" ref={boxRef}>
      <input
        value={value}
        placeholder={all.length ? placeholder : "Loading tickers…"}
        onChange={(e) => { onChange(e.target.value.toUpperCase()); setOpen(true); setHi(0); }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKey}
        autoComplete="off"
      />
      {open && matches.length > 0 && (
        <div className="tickerpick-list">
          {matches.map((c, i) => (
            <button key={c.ticker} type="button"
              className={"tickerpick-item" + (i === hi ? " hi" : "")}
              onMouseEnter={() => setHi(i)}
              onClick={() => pick(c)}>
              <b>{c.ticker.split(".")[0]}</b>
              <small>{c.name || ""}</small>
              <span className="tickerpick-ex">{c.ticker.split(".").pop()}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
