import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";

// Ad configuration is served by the API (so you can switch networks without a
// redeploy) and cached for the session.
let _cache = null;
let _inflight = null;
function loadAdsConfig() {
  if (_cache) return Promise.resolve(_cache);
  if (!_inflight) {
    _inflight = api.adsConfig()
      .then((c) => { _cache = c; return c; })
      .catch(() => { _cache = { enabled: false }; return _cache; });
  }
  return _inflight;
}

// Inject the network's <script> once per page load.
let _headDone = false;
function injectHead(snippet) {
  if (_headDone || !snippet) return;
  _headDone = true;
  const holder = document.createElement("div");
  holder.innerHTML = snippet;
  // Cloned <script> tags from innerHTML don't execute — recreate them so they do.
  for (const old of Array.from(holder.querySelectorAll("script"))) {
    const s = document.createElement("script");
    for (const a of Array.from(old.attributes)) s.setAttribute(a.name, a.value);
    s.text = old.textContent || "";
    document.head.appendChild(s);
  }
  for (const node of Array.from(holder.children)) {
    if (node.tagName !== "SCRIPT") document.head.appendChild(node);
  }
}

/**
 * A placement. `slot` is passed to your network's markup as {slot}.
 * Renders nothing at all when ads are off or the viewer is a paying subscriber
 * (never show ads to someone who just paid you).
 */
export default function AdSlot({ slot = "default", inline = false }) {
  const { user } = useAuth();
  const [cfg, setCfg] = useState(_cache);
  const ref = useRef(null);

  useEffect(() => { loadAdsConfig().then(setCfg); }, []);

  useEffect(() => {
    if (!cfg?.enabled || !ref.current) return;
    injectHead(cfg.head_snippet);
    const html = (cfg.slot_html || "").replaceAll("{slot}", slot);
    if (!html) return;
    ref.current.innerHTML = html;
    // Re-run any inline scripts the slot markup carries (AdSense's push call).
    for (const old of Array.from(ref.current.querySelectorAll("script"))) {
      const s = document.createElement("script");
      for (const a of Array.from(old.attributes)) s.setAttribute(a.name, a.value);
      s.text = old.textContent || "";
      old.replaceWith(s);
    }
  }, [cfg, slot]);

  const hideForSubscribers = cfg?.hide_for_subscribers !== false;
  const isPaying = !!user && !user.needsPayment;
  if (!cfg?.enabled || (hideForSubscribers && isPaying)) return null;

  return (
    <div className={`ad-slot${inline ? " ad-inline" : ""}`}>
      <span className="ad-label">Advertisement</span>
      <div ref={ref} style={{ width: "100%" }} />
    </div>
  );
}
