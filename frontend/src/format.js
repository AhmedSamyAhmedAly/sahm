export const SIGNAL_LABEL = {
  strong_buy: "STRONG BUY",
  buy: "BUY",
  hold: "HOLD",
  sell: "SELL",
  strong_sell: "STRONG SELL",
};

export const money = (x) =>
  x == null ? "—" : Number(x).toLocaleString(undefined, { maximumFractionDigits: 2 });

export const pct = (x, digits = 1) =>
  x == null ? "—" : `${Number(x).toFixed(digits)}%`;

export const prob = (p) => (p == null ? "—" : `${Math.round(p * 100)}%`);

export const signed = (x, digits = 1) => {
  if (x == null) return "—";
  const v = Number(x);
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
};
