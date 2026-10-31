"""The standing market trades of the Tracked Empire and how long its stock lasts for them.

The save lists each trade the empire set to repeat monthly in `market.monthly_trades`
(`trade_type` `market_buy` or `market_sell`, the resource, the amount per month). The market's
currency is the resource `trade` (defines `MARKET_RESOURCE`): a sale earns it, a purchase spends it.
A trade runs only while its stock lasts, so the section answers the two questions behind a trade
that stalls (docs/plans/grilling.md topic 3):

- `sell_cover`: the stockpile of the resource sold, divided by the amount sold per month,
  for the sale with the least cover. Under one month the sale does not run in full.
- `buy_cover`: the stockpile of `trade`, divided by the monthly drain on it. The drain is
  what the budget books for the trades: trade spent on purchases minus trade earned by sales.

A cover is left out where there is nothing to divide by (no sale, no drain). `short` counts the
sales and the purchases under one month of cover and is 0 without trades, so an Obstacle can always
check it. The keys are short because the extract is at its size budget. Amounts are as stored; the
formula is the plain division above, not a game rule.
"""

from __future__ import annotations

from typing import Any

from admiralty.extract.context import Context, as_list, block, rounded

CURRENCY = "trade"
_KINDS = {"market_buy": "standing_buys", "market_sell": "standing_sells"}


def market(ctx: Context, country_id: int, country: dict[str, Any]) -> dict[str, Any]:
    stock = block(block(country["modules"].get("standard_economy_module")).get("resources"))
    buys: dict[str, float] = {}
    sells: dict[str, float] = {}
    sold: dict[str, float] = {}  # by resource id, for the stock check
    for trade in as_list(block(ctx.g.get("market")).get("monthly_trades")):
        data = block(trade.get("trade_data")) if isinstance(trade, dict) else {}
        if data.get("country") != country_id or data.get("trade_type") not in _KINDS:
            continue
        resource, amount = data["resource"], trade.get("amount", 0)
        side = buys if data["trade_type"] == "market_buy" else sells
        side[ctx.label(resource)] = side.get(ctx.label(resource), 0) + amount
        if side is sells:
            sold[resource] = sold.get(resource, 0) + amount

    month = block(block(country.get("budget")).get("current_month"))
    earned = block(block(month.get("trade_income")).get("monthly_trades"))
    spent = block(block(month.get("trade_expenses")).get("monthly_trades"))
    drain = spent.get(CURRENCY, 0) - earned.get(CURRENCY, 0)  # trade the trades cost per month

    cover = {
        resource: stock.get(resource, 0) / amount for resource, amount in sold.items() if amount
    }
    buy_cover = stock.get(CURRENCY, 0) / drain if drain > 0 else None
    out: dict[str, Any] = {
        "buys": {name: rounded(amount) for name, amount in buys.items()},
        "sells": {name: rounded(amount) for name, amount in sells.items()},
        "count": len(buys) + len(sells),
        # trades that cannot run in full next month for lack of stock; 0 where none is standing
        "short": sum(1 for months in cover.values() if months < 1)
        + int(bool(buys) and buy_cover is not None and buy_cover < 1),
    }
    if cover:
        out["sell_cover"] = rounded(min(cover.values()), 1)
    if buy_cover is not None:
        out["buy_cover"] = rounded(buy_cover, 1)
    return out
