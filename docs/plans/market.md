# Plan: the market domain (increment 14)

Source: `docs/plans/grilling.md` topic 3 ("Markt im Mechanik-Graphen", Julians Ursachen 1 und 3) and
the first entry of `docs/proposals/debrief.md` stays for increment 15.

## What Julian described (2026-10-31, before the Ops test)

1. Clone vats were built on all planets at once: food use was underestimated, high food deficit.
2. Both deficits (food, energy) were covered by standing trades selling minerals and alloys, until
   the stocks were nearly empty. Then a swing: the auto trade stops, resources fall to zero, the
   crisis starts, one month of minerals stays in stock, the next month the trade runs again. Large
   trades also worsen prices and fees.
3. Solution: all trades out (the swing stops), then buy only what is needed.

## What the save and the game files give

- Save: `market.monthly_trades` (`trade_type` market_buy / market_sell, resource, amount per month,
  `trade_data.country` = owner). The budget books the trades under `monthly_trades`. Checked on
  `vulkan` and `zygerrian` (up to five trades). The currency is the resource `trade`: a sale earns
  it, a purchase spends it (budget `trade_income` / `trade_expenses`, defines `MARKET_RESOURCE`).
- Game files: defines `MARKET_TRADE_FEE_BASE` / `_MIN`, `MARKET_FLUCTUATION_*`,
  `MARKET_MONTHLY_TRADE_FRACTION`, `MARKET_MAX_BASE_AMOUNTS`; the fee modifier `country_trade_fee`
  (traditions, Galactic Stock Exchange, Trader Proxy Office, waystation module). The price per
  trade and the fee in force are not in the save (`price` is 0 in every standing trade), so the
  graph says "the fee exists and can be lowered", not "your fee is x".
- A trade that does not run for lack of stock is not a game-file rule; it is Julian's observation
  and the logical consequence of a trade drawing on a stock. The Obstacle checks use cover in
  months (stock divided by monthly amount), which is plain division, not a game formula.

## Build

- `extract/market.py`: section `market` of the extract (`buys`, `sells`, `count`, `short`, and
  `sell_cover` / `buy_cover` in months where there is something to divide). The keys are short
  because the extract is at its 40k budget (the Zygerrian 2363 save has 20 characters left).
- `quantities.py`: quantity `market` (`country_trade_fee`) -> `generated/market.yaml`.
- `graph/market.yaml`: Goal `market.steady_trade` (mark flag), three Causes, four Remedies, five
  Obstacles; metrics registered.
- Clone vats: `food.clone_vats_eat` (Cause under `food.positive`, facts: upkeep and growth bonus),
  Remedy `food.pace_clone_vats`; `pop_growth.growth_buildings` gets the Obstacle
  `pop_growth.food_deficit`.
- Playbook Rule only as a proposal in `docs/proposals/playbook.md`.
