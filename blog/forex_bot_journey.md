# From $297 to a Rust rewrite: what a year of building forex bots actually taught me

*Posted April 2026 · Chris Thrasher · [thrasherapps.com](https://thrasherapps.com)*

---

**TL;DR** — A friend of mine turned a small deposit into roughly $300,000 on OANDA. I wanted to automate a version of what he was doing on my own laptop. Fifteen production bugs, three rewrites, and one honest live-performance audit later, this is what I've learned. I'm now publishing every trade the bot takes at [thrasherapps.com/signals.html](https://thrasherapps.com/signals.html).

---

## 1. Why I started

My friend made real money trading forex the old-fashioned way — charts, patience, and a strict rule set. A few hundred thousand dollars' worth, over a few years, on an OANDA live account. Not a scam. Not an influencer. Just somebody who built a process and stuck with it.

That got me asking: could I automate what a disciplined person actually does? Not the YouTube "holy grail indicator" version — the patient, boring, risk-first version. A program that reads the tape, takes the obvious trades, sizes them small, and walks away. No VPS, no prop firm, no $97/month signal service. Just my laptop.

This post is the honest version of that year. I'll warn you now: there's a lot of losing in here. There's also a lot that finally worked.

## 2. V1 — a script on a $297 live account

The first version was about 4,200 lines of Python. It hooked into OANDA's v20 REST API, pulled M15 candles for seven major forex pairs, computed a handful of indicators (EMA crossover, RSI, Bollinger Bands), and ran a simple rule:

> If the 12-period EMA crosses above the 26-period EMA **and** RSI is reset from its last extreme, take a long. Mirror for shorts. Risk 1% on a stop set at 1× ATR.

I funded a micro-account with **$297**. Real money — small enough to lose without disaster, big enough to teach me what paper trading never could. The script ran 24×5 on a plugged-in MacBook, with a PyQt GUI showing open positions.

What V1 taught me:

- **Spreads at Sunday open are brutal.** 5-pip spreads on EUR/USD during the first hour of Sydney will destroy a 7-pip stop-loss strategy.
- **Session matters more than you think.** The same pair behaves like three different instruments across Asian, London, and New York sessions. A strategy that prints money during London overlap loses steadily during Asian chop.
- **Practice and live differ.** OANDA's practice account and their live account are not the same market — practice shows slightly better fills and wider order books. Backtesting against practice is closer to fantasy than reality.

V1 finished around breakeven. I'd call it tuition.

## 3. V2 — more knobs, more bugs, more of the same problem

V2 was a larger codebase (~4,200 lines of the bot plus supporting analysis scripts). I added:

- A backtester that replayed historical candles with the same entry logic.
- Regime detection (ADX-based trending vs ranging).
- A second strategy that ran alongside the trend-following one.
- A walk-forward optimizer to pick strategy parameters.
- Telegram alerts so I knew what the bot was doing while I slept.

The backtest looked genuinely good — profit factor around 1.40, max drawdown under 6%. I spent weeks re-running it on different windows, different parameter grids, different pair sets. Every time, 1.3 to 1.5 PF.

The live account? **PF ~0.9.** Losing slowly.

The gap between backtest and live was the thing I didn't understand yet.

## 4. V3 — the big rebuild on an $85K demo account

I opened an OANDA practice account with enough headroom ($85,000 demo balance) to test everything V1 and V2 couldn't. V3 is a ~7,200-line Python project with:

- Six strategies across trend, range, and multi-timeframe variants (mechanics private &mdash; we don't publish current edge).
- Session-aware filters and per-pair blocks.
- A full PyQt desktop GUI with live performance dashboards.
- An ML entry filter (XGBoost + CatBoost + LightGBM ensemble) trained on its own historical signals.
- Optuna hyperparameter sweeps.
- SHAP analysis to understand which features mattered.

I was proud of it. It backtested beautifully. Out-of-sample walk-forward showed a PF of about **1.45**.

We went live on the demo in early March.

By April 10 — 17 days in — the bot had taken **45 live trades**. The verdict:

- **Profit factor: 0.54**
- **Win rate: 62%** (yes, winning more than half the time — and still losing money)
- **P&L: –40.6 pips**
- **30-day projection (on the $297 live balance): –11.1%**

Winning more than half your trades and still losing money is a very specific kind of bad. It means you're cutting winners short and letting losers run — or, put another way, your exit logic is broken in a way your entry logic can't fix.

## 5. The audit that changed everything

I paused the bot and did something I should have done two months earlier.

I took every one of those 45 live trades — **exact entry price, exact entry time, exact signal** — and replayed them through a simulator with a different exit rule. Just the exit. Nothing else.

The new exit had three phases:

1. **Phase A** — Wide stop at 2× ATR. Let the noise happen.
2. **Phase B** — Once the trade gains +10 pips, move the stop to entry + 3. Small win locked in, upside open.
3. **Phase C** — Fixed take-profit at 2.75R (2.75 × the wide stop distance). No trailing stop.

Same 45 entries, different exit.

- **Profit factor: 1.60**
- **Win rate: 60%**
- **P&L: +152.5 pips**

Same signals, same account, same 17 days. The edge was always there. The exit was giving it all back.

That is the moment I realized the mistake. I had spent months optimizing the wrong thing. Entries are **50% of the equation at best**. Exits — when to cut a loser, when to take a winner, whether to trail at all — were the leverage I was leaving on the table.

## 6. Fifteen bugs between "config saved" and "bot takes trades"

I updated the config. The backtest showed the new numbers. I pushed the config to the live bot.

The live bot ignored it.

Not literally — the values loaded. But what the live bot actually *did* with each trade was subtly different from what the simulator did. Spotting where, and why, took **fifteen separate bug fixes**. Every single one was the difference between a winning config and a losing one. Some highlights:

1. **Legacy breakeven racing the shield.** Old code moved the stop to entry at +3 pips; the new config wanted it at +10. Both were firing.
2. **Partial TP still half-closing.** An "old" rule was closing 60% of the position at 60% of the TP, before the new fixed TP could fire.
3. **MFE override flipping exits.** A favorable-excursion rule was swapping the new fixed-TP exit back to the old trailing one on winning trades. Only. So winners shrank, losers didn't.
4. **`max_sl_pips` cap.** The wide 10-pip stop was being clamped back to 7 by a safety cap that didn't know about the new wider regime.
5. **Dynamic risk scaling.** Kelly-VAPS, ML confidence, MTF conviction, regime, streak — all multiplied on top of the flat 1% risk. On a losing streak, 1% risk became 0.47%. So the trade that finally won was half-sized.
6. **The empty-dict `_deep_merge` trap.** Setting a config override to `{}` was a no-op because my merge function iterated over the override's items. A stale default (a 1.5% pair risk override for USD_CAD) kept leaking through.
7. **The 500K unit cap.** A safety cap at 500,000 units silently halved every trade's real risk on an $85K account. Would have halved expected return.

…and eight more like them. The complete list is in the project's [MEMORY.md](https://github.com/Cbthrasher/forex_currencybotV3Mac).

Every one of those bugs was a place where the simulator and the live engine had diverged. They weren't obvious — none of them broke anything, no exceptions were thrown, the bot kept running "normally." It just traded a slightly different strategy than the one I thought I'd shipped.

**This is the single biggest lesson from the whole project.** Code paths diverge. Always verify your simulator is running the exact same logic as your live engine, at the `execute_trade` call, not just at the signal.

## 7. V4 — a Rust rewrite for the data plane

V3's weakness at this point isn't the strategy — it's the Python GIL and the ~30ms between a tick arriving and a decision being made. That's fine at M15, where a 30ms delay is invisible, but it rules out faster timeframes entirely.

V4 is Rust for the data plane (OANDA streaming, indicators, decisions, exits) with the **same PyQt GUI** as V3 reading shared state via JSON files and SQLite. The Rust side is about 5,000 lines — async, zero-copy price updates, sub-millisecond decide() latency.

The key design decision: **V4 runs in shadow mode first.** Every signal it would have traded is logged, but no order is submitted. This lets us validate its signal generation, exits, and risk math against live OANDA prices for seven full days before we flip `execute_trades = true`. Phase 1a just shipped on April 18; Phase 1b (live execution on a fresh micro-account) is two to three weeks out.

Cross-version collisions were a real concern — V3 and V4 share the same OANDA demo account during the shadow period. Every V4 order (when we flip to live) will be tagged with a ULID (`v4-fusion-<ULID>`), and the runtime checks for foreign positions on the pair before entering. Other-tagged positions count as external and block the entry.

## 8. Why I'm publishing the trade journal instead of selling signals

In March, before the audit, I'd built a landing page on this site advertising a paid signal subscription: $29/month for real-time alerts, $79/month for strategy breakdowns. I was 24-48 hours from launching it.

Then the audit happened. Profit factor 0.54 on a live account is not something you charge people for. So I pulled the pricing tiers and took the whole page offline for a while.

What I replaced it with is the [Bot Journal page](https://thrasherapps.com/signals.html). Every closed trade the bot takes gets parsed out of the live log and posted there, updated every thirty minutes. The all-time profit factor is still below 1.0 — the early losing strategies are still in the ledger. The 7-day window, measuring only post-April-11 trades, is now the page's real story.

If the fix holds for 30 days, the headline number will earn itself. If it doesn't, you'll see that too.

No signal subscriptions. No Telegram channel. No "limited time offer." Just the trades, live.

## 9. What I'd tell past-me

- **Exits are the leverage.** Entries are easier to tune and less important. The difference between a winning bot and a losing one is almost always what happens after the fill.
- **A backtest is a hypothesis, not a result.** Your backtest and your live bot are probably not running the same code. They diverged somewhere. Find where, then close the gap.
- **Flat 1% risk beats clever risk.** Every dynamic-sizing rule you add compounds with the others and halves your real exposure in a losing streak. Boring is profitable.
- **Block pairs, don't retune them.** EUR/GBP lost 6 straight on my account. Blocking it for all sessions was a 30-second change that paid for itself inside a week. Re-tuning it would have cost weeks and probably produced no edge.
- **Write the journal.** If you can't stomach publishing your results in real time, your strategy probably isn't ready.

## 10. What's next

- **30 days of the winning config** on the V3 demo. If the numbers hold, the V2 live account ($297) gets the same config ported over.
- **V4 Phase 1a** — seven days of shadow-mode observation, confirming the Rust bot's signals and exits match a Python re-implementation that runs alongside it.
- **V4 Phase 1b** — flip to live execution on a fresh OANDA practice account (separate from V3's) with micro position sizes. Tag-aware collision checks let V3 and V4 coexist on shared balance later.
- **Dashboard** — I put up a free [market dashboard](https://thrasherapps.com/dashboard.html) with weekly CFTC Commitments of Traders positioning and US rate tape. Free, no-login, no-email. Rebuilt every Sunday via GitHub Actions.

If you're building your own bot, or if you just like watching someone else's trade account, the [journal](https://thrasherapps.com/signals.html) is the place. No signup required.

And if you've made it this far — thanks for reading. It's been a long year of losing before winning. I'm glad the winning part is finally starting to show up in the ledger.

---

*Chris Thrasher is an independent developer in Georgia. He builds [iOS apps](https://thrasherapps.com/apps.html) and [AI solutions](https://thrasherapps.com/ai.html), and now this.*

*Nothing in this post is investment advice. Trading forex involves risk. Past performance doesn't predict future results. Seriously.*
