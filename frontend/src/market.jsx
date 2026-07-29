import { createContext, useContext, useEffect, useState } from "react";
import { MARKET_KEY } from "./storage.js";

// The markets the app can switch between. `code` matches the `exchange` column
// in the backend (assets.exchange) and the ticker suffix (COMI.EGX, AAPL.US).
export const MARKETS = [
  { code: "EGX", label: "EGX", flag: "🇪🇬", name: "Egyptian Exchange", currency: "EGP" },
  { code: "US", label: "US", flag: "🇺🇸", name: "US Stocks", currency: "$" },
];

export const DEFAULT_MARKET = "EGX";

export function marketByCode(code) {
  return MARKETS.find((m) => m.code === code) || MARKETS[0];
}

// Currency symbol for a namespaced ticker (COMI.EGX -> EGP, AAPL.US -> $).
export function currencyForTicker(ticker) {
  const suffix = (ticker || "").split(".").pop();
  return (MARKETS.find((m) => m.code === suffix) || {}).currency || "";
}

const MarketCtx = createContext(null);
const STORAGE_KEY = MARKET_KEY;

export function MarketProvider({ children }) {
  const [market, setMarketState] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved && MARKETS.some((m) => m.code === saved) ? saved : DEFAULT_MARKET;
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, market);
  }, [market]);

  const setMarket = (code) => {
    if (MARKETS.some((m) => m.code === code)) setMarketState(code);
  };

  return (
    <MarketCtx.Provider value={{ market, setMarket, markets: MARKETS, current: marketByCode(market) }}>
      {children}
    </MarketCtx.Provider>
  );
}

export const useMarket = () => useContext(MarketCtx);
