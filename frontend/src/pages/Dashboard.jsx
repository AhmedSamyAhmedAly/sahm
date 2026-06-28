import { useState } from "react";
import PicksView from "../components/PicksView.jsx";

// Four risk/return profiles. Each tab fixes a target band + confidence floor and
// shows only buy-rated picks. "Best value" uses the auto best-play (most profit
// per day at high confidence). Two labels are honest about the impossible asks:
// nothing in stocks is truly "zero risk", and you can't max profit+speed+safety
// all at once — "Best value" is the efficiency pick.
const TABS = [
  {
    key: "value", icon: "⭐", label: "Best value",
    sub: "Most profit for the time, at high confidence — the cream (may be few or none).",
    band: null, minConf: 0.85, ratings: ["super_strong_buy", "strong_buy"],
  },
  {
    key: "balanced", icon: "⚖️", label: "Balanced",
    sub: "+5% target in ~30 days · medium profit, medium risk (~80% reach it).",
    band: { target: 0.05, horizon: 30 }, minConf: 0, ratings: ["super_strong_buy", "strong_buy", "buy"],
  },
  {
    key: "aggressive", icon: "🔥", label: "Aggressive",
    sub: "+10% target in ~10 days · high profit, high risk — size small (~40% reach it).",
    band: { target: 0.10, horizon: 10 }, minConf: 0, ratings: ["super_strong_buy", "strong_buy", "buy"],
  },
  {
    key: "safe", icon: "🛡️", label: "Safest",
    sub: "+3% target in ~40 days · lowest risk, longer hold (~88% reach it). No stock is truly zero-risk.",
    band: { target: 0.03, horizon: 40 }, minConf: 0.85, ratings: ["super_strong_buy", "strong_buy", "buy"],
  },
];

export default function Dashboard() {
  const [active, setActive] = useState(TABS[0]);
  return (
    <>
      <div className="container wide" style={{ paddingBottom: 0 }}>
        <div className="tabs">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={`tab ${active.key === t.key ? "active" : ""}`}
              onClick={() => setActive(t)}
            >
              <span aria-hidden>{t.icon}</span> {t.label}
            </button>
          ))}
        </div>
      </div>
      <PicksView key={active.key} tab={active} showKpis title={`${active.icon} ${active.label}`} />
    </>
  );
}
