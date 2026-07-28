export const SIGNAL_LABEL = {
  super_strong_buy: "SUPER STRONG BUY",
  strong_buy: "STRONG BUY",
  buy: "BUY",
  hold: "HOLD",
  sell: "SELL",
  strong_sell: "STRONG SELL",
  super_strong_sell: "SUPER STRONG SELL",
};

// The model emits 7 fine tiers, but its real edge doesn't justify that much
// precision (and you can't easily short EGX, so one "Sell" is enough). Collapse to
// 4 plain, action-mapped tiers for display: Strong Buy / Buy / Hold / Sell.
export const SIGNAL_GROUP = {
  super_strong_buy: "strong_buy",
  strong_buy: "strong_buy",
  buy: "buy",
  hold: "hold",
  sell: "sell",
  strong_sell: "sell",
  super_strong_sell: "sell",
};
export const SIGNAL_GROUP_LABEL = {
  strong_buy: "STRONG BUY",
  buy: "BUY",
  hold: "HOLD",
  sell: "SELL",
};
// group -> badge CSS class (reuses existing badge colors).
export const groupOf = (sig) => SIGNAL_GROUP[sig] || sig;
export const groupLabel = (sig) => SIGNAL_GROUP_LABEL[groupOf(sig)] || sig;

export const money = (x) =>
  x == null ? "—" : Number(x).toLocaleString(undefined, { maximumFractionDigits: 2 });

export const prob = (p) => (p == null ? "—" : `${Math.round(p * 100)}%`);

// Display a ticker without its exchange suffix (COMI.EGX -> COMI, AAPL.US -> AAPL).
export const tickerLabel = (t) => (t || "").replace(/\.[A-Z]+$/, "");

export const signed = (x, digits = 1) => {
  if (x == null) return "—";
  const v = Number(x);
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
};
