// Local-storage keys, namespaced to the app. The rebrand (sahm_* -> saeed_*) would
// otherwise log everyone out and drop their tracked positions, so each key is
// migrated once, in place, the first time the new build runs.
export function migrateKey(oldKey, newKey) {
  try {
    const v = localStorage.getItem(oldKey);
    if (v === null) return;
    if (localStorage.getItem(newKey) === null) localStorage.setItem(newKey, v);
    localStorage.removeItem(oldKey);
  } catch {
    /* storage unavailable — nothing to migrate */
  }
}

export const TOKEN_KEY = "saeed_token";
export const MARKET_KEY = "saeed_market";
export const POSITIONS_KEY = "saeed_positions";

// Run the migrations once at module load (before any reader touches a key).
migrateKey("sahm_token", TOKEN_KEY);
migrateKey("sahm_market", MARKET_KEY);
migrateKey("sahm_positions", POSITIONS_KEY);
