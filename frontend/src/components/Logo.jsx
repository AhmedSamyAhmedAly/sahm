// "Saaed" stylized: Sa + a green rising-chart glyph (the middle letter) + ed.
export default function Logo({ size = "1em" }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", letterSpacing: "0.3px" }}>
      Sa
      <svg width="0.95em" height="0.95em" viewBox="0 0 24 24" fill="none"
        style={{ margin: "0 1px", verticalAlign: "middle" }} aria-hidden="true">
        <path d="M3 18 L9 11 L13 15 L21 5" stroke="#2ecc71" strokeWidth="2.6"
          strokeLinecap="round" strokeLinejoin="round" />
        <path d="M21 5 L21 10 M21 5 L16 5" stroke="#2ecc71" strokeWidth="2.6"
          strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      ed
    </span>
  );
}
