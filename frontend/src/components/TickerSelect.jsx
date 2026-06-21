import { useEffect, useMemo, useRef, useState } from "react";

// A searchable ticker picker that works on mobile (native <datalist> doesn't).
// `onChange` receives the plain ticker string, like a normal input.
export default function TickerSelect({
  assets = [], value = "", onChange, placeholder = "Type or pick a ticker",
  required, autoFocus, id,
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const ref = useRef(null);

  useEffect(() => {
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("touchstart", onDoc);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("touchstart", onDoc);
    };
  }, []);

  const matches = useMemo(() => {
    const s = (value || "").trim().toLowerCase();
    const base = s
      ? assets.filter((a) =>
          a.ticker.toLowerCase().includes(s) || (a.name || "").toLowerCase().includes(s))
      : assets;
    return base.slice(0, 60);
  }, [assets, value]);

  const pick = (a) => { onChange(a.ticker.replace(".EGX", "")); setOpen(false); };

  return (
    <div className="combo" ref={ref}>
      <input
        id={id}
        value={value}
        autoFocus={autoFocus}
        required={required}
        placeholder={placeholder}
        autoComplete="off"
        onChange={(e) => { onChange(e.target.value); setOpen(true); setActive(0); }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((i) => Math.min(i + 1, matches.length - 1)); }
          else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
          else if (e.key === "Enter" && open && matches[active]) { e.preventDefault(); pick(matches[active]); }
          else if (e.key === "Escape") setOpen(false);
        }}
      />
      {open && matches.length > 0 && (
        <div className="combo-menu">
          {matches.map((a, i) => (
            <button
              type="button"
              key={a.ticker}
              className={"combo-item" + (i === active ? " active" : "")}
              onClick={() => pick(a)}
            >
              <b>{a.ticker.replace(".EGX", "")}</b>
              <span>{a.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
