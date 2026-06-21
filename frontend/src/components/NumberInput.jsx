// A number field with a clean, theme-matched stepper instead of the browser's
// default spin buttons. `onChange` receives the raw string value (like the
// native input's e.target.value) so it drops into existing form handlers.
export default function NumberInput({
  value, onChange, step = 1, min, max, className = "", style, ...rest
}) {
  const toNum = (v) => {
    const n = parseFloat(v);
    return Number.isFinite(n) ? n : 0;
  };
  const clamp = (n) => {
    if (min != null && n < Number(min)) n = Number(min);
    if (max != null && n > Number(max)) n = Number(max);
    return n;
  };
  const bump = (dir) => {
    const next = clamp(Math.round((toNum(value) + dir * step) * 1e6) / 1e6);
    onChange(String(next));
  };
  return (
    <div className={`numfield ${className}`} style={style}>
      <input
        type="number"
        inputMode="decimal"
        value={value}
        step={step}
        min={min}
        max={max}
        onChange={(e) => onChange(e.target.value)}
        {...rest}
      />
      <div className="numsteps">
        <button type="button" tabIndex={-1} aria-label="Increase" onClick={() => bump(1)}>▲</button>
        <button type="button" tabIndex={-1} aria-label="Decrease" onClick={() => bump(-1)}>▼</button>
      </div>
    </div>
  );
}
