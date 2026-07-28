// Your open positions — what you actually bought — kept in localStorage so the app
// can watch them and tell you when to act (target hit / stop hit / time's up).
// Selling well is half of trading (Point 5); this is the "exit coach".
import { useEffect, useState } from "react";

const KEY = "sahm_positions";
const EVT = "sahm-positions";

export function getPositions() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || [];
  } catch {
    return [];
  }
}

function save(list) {
  localStorage.setItem(KEY, JSON.stringify(list));
  window.dispatchEvent(new Event(EVT));
}

export function usePositions() {
  const [positions, setPositions] = useState(getPositions);
  useEffect(() => {
    const sync = () => setPositions(getPositions());
    window.addEventListener(EVT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(EVT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  const add = (pos) => save([...getPositions(), { id: `${Date.now()}-${Math.random()}`, ...pos }]);
  const remove = (id) => save(getPositions().filter((p) => p.id !== id));
  return { positions, add, remove };
}

// What should you do about a held position right now?
export function positionStatus(pos, price) {
  const daysHeld = pos.date
    ? Math.floor((Date.now() - new Date(pos.date).getTime()) / 86400000)
    : null;
  if (price != null && pos.stop && price <= pos.stop)
    return { kind: "stop", label: "🛑 Stop hit — consider getting out" };
  if (price != null && pos.target && price >= pos.target)
    return { kind: "target", label: "🎯 Target hit — consider taking profit" };
  if (pos.horizon && daysHeld != null && daysHeld > pos.horizon)
    return { kind: "time", label: `⏰ Held ${daysHeld}d (planned ~${pos.horizon}d) — reassess` };
  return { kind: "hold", label: "Holding", daysHeld };
}
