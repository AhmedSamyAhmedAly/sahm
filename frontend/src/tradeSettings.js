// Shared, persisted trade settings (your capital + how much you'll risk per trade)
// and the position-size math. Kept in localStorage so every pick can size itself,
// and synced across components via a tiny event.
import { useEffect, useState } from "react";

const CAP_KEY = "sahm_capital";
const RISK_KEY = "sahm_risk_pct";
const EVT = "sahm-trade-settings";

export const getCapital = () => Number(localStorage.getItem(CAP_KEY)) || 0;
export const getRiskPct = () => {
  const v = Number(localStorage.getItem(RISK_KEY));
  return v > 0 ? v : 1; // default: risk 1% of capital per trade
};

export function useTradeSettings() {
  const [capital, setCap] = useState(getCapital);
  const [riskPct, setRisk] = useState(getRiskPct);
  useEffect(() => {
    const sync = () => { setCap(getCapital()); setRisk(getRiskPct()); };
    window.addEventListener(EVT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(EVT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);
  const setCapital = (v) => {
    localStorage.setItem(CAP_KEY, String(Math.max(0, Number(v) || 0)));
    window.dispatchEvent(new Event(EVT));
  };
  const setRiskPct = (v) => {
    localStorage.setItem(RISK_KEY, String(Number(v) || 1));
    window.dispatchEvent(new Event(EVT));
  };
  return { capital, riskPct, setCapital, setRiskPct };
}

// The professional rule: shares = (capital * risk%) / (entry - stop), i.e. size so a
// stop-out loses only your chosen small slice of capital. Never exceed what your
// capital can buy.
export function positionSize({ capital, riskPct, entry, stop }) {
  if (!capital || !entry || !stop || entry <= stop) return null;
  const riskPerShare = entry - stop;
  const riskBudget = capital * (riskPct / 100);
  const maxByCapital = Math.floor(capital / entry);
  let shares = Math.floor(riskBudget / riskPerShare);
  const cappedByCapital = shares > maxByCapital;
  shares = Math.min(shares, maxByCapital);
  if (shares <= 0) return { shares: 0, riskPerShare, cappedByCapital, tooSmall: true };
  return {
    shares,
    cost: shares * entry,
    maxLoss: shares * riskPerShare,
    riskPerShare,
    cappedByCapital,
    tooSmall: false,
  };
}
