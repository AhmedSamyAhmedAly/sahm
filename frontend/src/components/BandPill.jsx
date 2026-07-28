import { prob } from "../format.js";

// One scenario pill: a +X% target with its success % and how much it beats luck.
// Colour encodes the edge over random (the honest signal of skill, not the raw %).
export default function BandPill({ band, baseRate }) {
  const pct = Math.round((band.target_pct || 0) * 100);
  const days = band.horizon_days;
  const p = band.prob;
  const lift = p != null && baseRate ? p / baseRate : null;
  const cls =
    lift == null ? "edge-unknown" : lift >= 1.25 ? "edge-strong" : lift >= 1.08 ? "edge-mild" : "edge-none";
  const edgeTxt =
    lift == null ? "" : lift < 1.08 ? " · barely beats luck" : ` · ${lift.toFixed(1)}× luck`;
  const tip =
    p == null
      ? `+${pct}% target`
      : `${prob(p)} hit +${pct}% within ~${days}d${baseRate ? ` · luck alone ${Math.round(baseRate * 100)}%` : ""}${edgeTxt}${band.n ? ` · n=${band.n}` : ""}`;
  return (
    <span className={`band-pill ${cls}`} title={tip}>
      +{pct}% <b>{prob(p)}</b>
    </span>
  );
}

// Base hit-rate ("luck") per band from the track-record model metrics — for colouring.
export function baseRateMap(track) {
  const m = {};
  for (const mm of track?.models || []) {
    m[`${Math.round(mm.target_pct * 100)}_${mm.horizon_days}`] = mm.base_rate;
  }
  return m;
}
export const baseRateFor = (map, band) =>
  map[`${Math.round((band.target_pct || 0) * 100)}_${band.horizon_days}`];
