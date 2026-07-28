import { useState } from "react";
import PicksView from "../components/PicksView.jsx";

// Two top-level views: the daily buy Suggestions (with per-stock scenario pills),
// and a searchable All-Stocks browser of the whole market.
const VIEWS = [
  { key: "suggestions", icon: "💡", label: "Suggestions" },
  { key: "all", icon: "📋", label: "All stocks" },
];

export default function Dashboard() {
  const [view, setView] = useState(VIEWS[0]);
  return (
    <>
      <div className="container wide" style={{ paddingBottom: 0 }}>
        <div className="tabs">
          {VIEWS.map((v) => (
            <button
              key={v.key}
              type="button"
              className={`tab ${view.key === v.key ? "active" : ""}`}
              onClick={() => setView(v)}
            >
              <span aria-hidden>{v.icon}</span> {v.label}
            </button>
          ))}
        </div>
      </div>
      {view.key === "suggestions" ? (
        <PicksView key="suggestions" mode="suggestions" showKpis title="💡 Today’s suggestions" />
      ) : (
        <PicksView key="all" mode="all" title="📋 All stocks" />
      )}
    </>
  );
}
