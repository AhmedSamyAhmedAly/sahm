"""Keep the serving DB's chart history bounded.

The daily scan appends one bar per ticker per day forever. The UI only ever shows
up to a year, so anything older is dead weight. This drops bars past the window,
per market, measured from that market's own latest bar (markets have different
trading calendars).

    MARKET=US DATABASE_URL=<serving db> python scripts/trim_bars.py
    MARKET=ALL ... ACTIVE_DAYS=380 INACTIVE_DAYS=380 python scripts/trim_bars.py
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select, text  # noqa: E402

from app.database import normalize_db_url  # noqa: E402
from app.models import Asset, DailyBar  # noqa: E402

ACTIVE_DAYS = int(os.environ.get("ACTIVE_DAYS", "380"))      # tradeable: ~1Y chart
INACTIVE_DAYS = int(os.environ.get("INACTIVE_DAYS", "380"))  # the rest


def trim(engine, market: str) -> None:
    with engine.connect() as c:
        maxd = c.execute(
            select(func.max(DailyBar.date))
            .where(DailyBar.ticker.in_(select(Asset.ticker).where(Asset.exchange == market)))
        ).scalar()
    if maxd is None:
        print(f"  {market}: no bars — nothing to trim")
        return
    act_floor = maxd - dt.timedelta(days=ACTIVE_DAYS)
    inact_floor = maxd - dt.timedelta(days=INACTIVE_DAYS)
    with engine.begin() as c:
        n1 = c.execute(text(
            "DELETE FROM daily_bars WHERE date < :f AND ticker IN "
            "(SELECT ticker FROM assets WHERE exchange = :ex AND is_active)"),
            {"f": act_floor, "ex": market}).rowcount
        n2 = c.execute(text(
            "DELETE FROM daily_bars WHERE date < :f AND ticker IN "
            "(SELECT ticker FROM assets WHERE exchange = :ex AND NOT is_active)"),
            {"f": inact_floor, "ex": market}).rowcount
    print(f"  {market}: latest={maxd} trimmed {n1 + n2} rows "
          f"(active<{act_floor}, inactive<{inact_floor})")


def main() -> None:
    engine = create_engine(normalize_db_url(os.environ["DATABASE_URL"]), pool_pre_ping=True)
    want = os.environ.get("MARKET", "ALL").upper()
    for m in (["EGX", "US"] if want == "ALL" else [want]):
        trim(engine, m)
    with engine.connect() as c:
        print("daily_bars rows:", c.execute(text("SELECT count(*) FROM daily_bars")).scalar())


if __name__ == "__main__":
    main()
