// Shared trade settings (your capital + how much you'll risk per trade) and the
// position-size math. Kept IN MEMORY only — they follow you while you browse the
// app, but a refresh or closing the tab clears them (nothing is stored).
import { useEffect, useState } from "react";

const EVT = "saeed-trade-settings";
let _capital = 0;
let _riskPct = 1; // default: risk 1% of capital per trade

// Clean up values saved by the old persisted version.
try { localStorage.removeItem("sahm_capital"); localStorage.removeItem("sahm_risk_pct"); localStorage.removeItem("saeed_capital"); localStorage.removeItem("saeed_risk_pct"); } catch { /* ignore */ }

export const getCapital = () => _capital;
export const getRiskPct = () => _riskPct;

export function useTradeSettings() {
  const [capital, setCap] = useState(getCapital);
  const [riskPct, setRisk] = useState(getRiskPct);
  useEffect(() => {
    const sync = () => { setCap(getCapital()); setRisk(getRiskPct()); };
    window.addEventListener(EVT, sync);
    return () => window.removeEventListener(EVT, sync);
  }, []);
  const setCapital = (v) => {
    _capital = Math.max(0, Number(v) || 0);
    window.dispatchEvent(new Event(EVT));
  };
  const setRiskPct = (v) => {
    _riskPct = Number(v) || 1;
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
