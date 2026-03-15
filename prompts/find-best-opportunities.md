# Investment Opportunity Scanner — Master Prompt

Paste this prompt into a Claude Code session to run a full top-down investment research workflow.
All steps use skills from this repository. Run them in the order shown — each layer informs the next.

---

## THE PROMPT

```
I want to find the best current investment opportunities using a structured, data-driven process.
Work through the following layers in order. At each layer, record key findings before moving on.
At the end, produce a ranked shortlist of 5-10 actionable ideas with conviction scores.

---

### LAYER 1 — MARKET REGIME: Should I be investing aggressively or defensively?

Run these skills and answer: (a) What is the current macro regime? (b) Is the market healthy or topping?
(c) Are we recovering from a bottom or extended from a prior run?

1. /macro-regime-detector
   → Identify the structural regime (Concentration / Broadening / Contraction / Inflection).
     Note: which asset classes and factors are leading?

2. /market-top-detector
   → Composite score 0-100. Note: distribution day count, leading stock deterioration,
     defensive rotation score. Is risk HIGH / MEDIUM / LOW?

3. /market-breadth-analyzer
   → Composite breadth score 0-100. Note: advance-decline health, % stocks above key MAs.

4. /uptrend-analyzer
   → Uptrend ratio score 0-100. Note: sector participation and momentum readings.

5. /ftd-detector
   → Are we in a confirmed uptrend, rally attempt, or downtrend?
     Note: follow-through day status for S&P 500 and Nasdaq.

LAYER 1 DECISION:
- If market-top score > 70 AND breadth < 40: reduce position sizes by 50%, focus on defensive sectors only.
- If ftd-detector shows no confirmed uptrend: wait for confirmation before new entries.
- If all three (breadth, uptrend, FTD) are positive: full risk-on, proceed aggressively.
Record: RISK MODE = [FULL / REDUCED / DEFENSIVE]

---

### LAYER 2 — MACRO & NEWS CONTEXT: What forces are driving markets this week?

6. /market-news-analyst
   → Identify the 3-5 most market-moving events from the past 10 days.
     Note: which sectors/assets were most impacted and in which direction.

7. /economic-calendar-fetcher
   → List all HIGH-impact events in the next 14 days (Fed decisions, CPI, jobs, GDP).
     Flag any events that could disrupt current setups.

8. /earnings-calendar
   → List major earnings reports due in the next 10 days.
     Highlight any names that appear in later screening steps — avoid holding through earnings
     unless that is intentional.

---

### LAYER 3 — SECTOR & THEME ROTATION: Where is money flowing?

9. /theme-detector
   → Identify the top 3 HOT themes (high conviction, early-to-mid lifecycle preferred).
     Note the top 5 stocks associated with each theme.

10. /sector-analyst
    → Which sectors are in confirmed uptrends vs. weakening?
      Rank sectors: LEADING / IMPROVING / LAGGING / BREAKING DOWN.

LAYER 3 DECISION:
Focus the screening in Layer 4 on stocks in LEADING or IMPROVING sectors that overlap
with HOT themes. Deprioritize stocks in LAGGING or BREAKING DOWN sectors.
Record: FOCUS SECTORS = [...], FOCUS THEMES = [...]

---

### LAYER 4 — STOCK SCREENING: Who are the specific candidates?

Run all four screeners. Collect results into a combined candidate pool.

11. /vcp-screener
    → Run with --mode prebreakout to find stocks near a buyable pivot.
      Note: top 10 by composite score, their sectors, and distance from pivot.

12. /canslim-screener
    → Note: top 10 by score. Focus on stocks with A/B earnings grades and strong RS.

13. /earnings-trade-analyzer
    → Note: top 10 post-earnings momentum stocks (grade A or B only).
      These are candidates for PEAD follow-through.

14. /institutional-flow-tracker
    → Which stocks show the strongest smart-money accumulation in recent 13F filings?
      Note: top 10 by net institutional buying change.

LAYER 4 SYNTHESIS:
Build a master candidate table. Give each stock a MULTI-SCREEN SCORE:
- +1 point for each screener it appears in (max 4)
- +1 point if its sector is in your FOCUS SECTORS list
- +1 point if it belongs to a FOCUS THEME
- -1 point if it has an earnings report within 7 days (unless playing earnings)

Sort descending. Keep the top 15 stocks for deep-dive in Layer 5.

---

### LAYER 5 — DEEP DIVE: Are these actually good setups?

For each of your top 5-7 candidates from Layer 4:

15. /us-stock-analysis [TICKER]
    → Check: EPS growth trend, revenue growth, profit margins, valuation vs. peers.
      Red flags: declining margins, heavy debt, recent earnings miss.

16. /technical-analyst [provide chart image if available]
    → Confirm: stage 2 uptrend, base pattern quality, volume characteristics.
      Identify: exact pivot/entry price, stop-loss level, first price target.

LAYER 5 OUTPUT per stock:
- Fundamental grade: A / B / C / D
- Technical setup: READY / FORMING / EXTENDED / BROKEN
- Entry price, stop-loss price, target price
- Risk/reward ratio

---

### LAYER 6 — SYNTHESIS & SIZING: How much to buy?

17. /stanley-druckenmiller-investment
    → Feed in findings from Layers 1-5. Get a unified conviction score (0-100)
      and allocation recommendation. Note the pattern classification.

18. /position-sizer [for each final candidate]
    → Inputs: account size, entry price, stop-loss price, risk per trade (1-2% of account).
      Output: exact share count and dollar amount per position.

---

### FINAL OUTPUT

**Part 1 — Ranked Investment Shortlist**

Produce a ranked table in this format:

| Rank | Ticker | Theme/Sector | Multi-Screen Score | Conviction (0-100) | Entry | Stop | Target | R:R | Shares | $ Risk |
|------|--------|-------------|-------------------|-------------------|-------|------|--------|-----|--------|--------|
| 1    | ...    | ...         | ...               | ...               | ...   | ...  | ...    | ... | ...    | ...    |

---

**Part 2 — Full Situation Report (required, no bullet points)**

Write a detailed, plain-English explanation covering the following four sections. Each section must be written in full paragraphs — not bullet points, not headers-only. Assume the reader understands basic investing but has not seen the raw data. Explain the *why* behind every conclusion.

**Section A — What is the market doing right now, and why does it matter?**
Describe the current market environment in concrete terms. What do the breadth score, distribution day count, and sector trends actually mean for someone with money invested? Is this a healthy bull market, a topping market, a correction, or a bear market? How serious is the current weakness — is this a routine pullback or something more concerning? Reference the specific numbers (breadth score, distribution days, VIX level, % stocks above key moving averages) and explain what each one tells us about the behaviour of institutional investors.

**Section B — What should I actually do with my portfolio right now?**
Give concrete, specific guidance. Should the reader be fully invested, partially in cash, or mostly defensive? What actions should they take this week — hold, trim, buy, wait? If they currently hold positions, what does the current environment suggest about stop-loss management and position sizing? If they have cash to deploy, what conditions must be met before using it? Explain the reasoning behind each recommendation — not just what to do, but why this is the right response to what the data is showing.

**Section C — Where are the best opportunities if/when the market recovers?**
Explain which stocks and themes showed up as the strongest candidates from the screening, and why they stand out. For the top 1-3 picks, describe what makes their fundamentals strong (earnings growth rate, revenue trends, profit margins) and what the technical setup looks like. Explain what you are waiting for before entering — what specific signal or price level would trigger a buy. Also explain why certain themes (Gold, defensive sectors, etc.) may be relevant even in the current weak environment, and what the risk is if you act on them too early.

**Section D — What are the key risks and triggers to watch?**
Identify the 2-3 most important things to monitor in the coming days and weeks. What economic events, earnings reports, or technical signals could change the picture — either for the better (triggering a buy) or for the worse (requiring further defensive action)? Explain what a Follow-Through Day is and exactly what to look for. Explain what would cause you to abandon a setup entirely. Be specific about price levels, dates, and conditions.

---

Flag any positions that should be AVOIDED or SIZED SMALL due to upcoming earnings,
sector weakness, or market-top risk. Explain in 1-2 sentences why each flagged name
is dangerous right now — not just that it should be avoided, but what specific risk makes it so.
```

---

## QUICK VERSION — US MARKET (15 minutes)

If you want a faster scan without the full deep-dive, use this condensed version:

```
Run a quick investment opportunity scan (US market):

1. /market-breadth-analyzer — is the market healthy enough to buy?
2. /market-top-detector — any warning signs?
3. /theme-detector — what themes are leading?
4. /vcp-screener --mode prebreakout — who is near a buyable pivot?
5. /canslim-screener — who has the best earnings + price momentum?

Cross-reference: list stocks that appear in BOTH vcp-screener and canslim-screener results
AND belong to a leading theme. Rank by composite VCP score. Show top 5 with entry,
stop, and target levels. Use /position-sizer for sizing on the top 2 picks.

Then write a plain-English summary covering:
1. What the market environment means right now (healthy/topping/recovering?) and why, using the actual scores as evidence.
2. What to do with your portfolio this week — specific actions, not vague guidance. Explain the reasoning.
3. Why the top 1-2 picks stand out, what you are waiting for before buying, and what risk you are taking if you act early.
4. What specific signal (e.g. Follow-Through Day, price level, earnings result) would change your stance.

Write in full paragraphs. No bullet points in this section.
```

---

## QUICK VERSION — EUROPEAN MARKET (15 minutes)

Same structure as the US quick scan, using the `--europe` flag where supported.
Tracks Euro Stoxx 50 + DAX instead of S&P 500 + Nasdaq. Uses the European stock universe
(`universes/europe.txt`). No FMP API key required — all skills fall back to yfinance.

```
Run a quick investment opportunity scan (European market):

1. /market-top-detector --europe
   → Composite top risk score using Euro Stoxx 50 + DAX. Note distribution day count,
     defensive rotation, and index technical condition.

2. /ftd-detector --europe
   → Are Euro Stoxx 50 and DAX in confirmed uptrend, rally attempt, or correction?
     Note: follow-through day status for both indices.

3. /theme-detector
   → What themes are currently leading? (theme-detector covers global themes —
     note which hot themes have strong European exposure, e.g. Defence, Financials, Energy.)

4. /vcp-screener --europe --mode prebreakout
   → Screen European stocks from universes/europe.txt for VCP setups near buyable pivots.
     Note: top 10 by composite score and their distance from pivot.

5. /canslim-screener --europe
   → Screen European stocks for CANSLIM growth characteristics.
     Note: top 10 by score, focusing on A/B earnings grades and strong relative strength.

Cross-reference: list stocks that appear in BOTH vcp-screener and canslim-screener results.
Rank by composite VCP score. Show top 5 with entry, stop, and target levels.
Use /position-sizer for sizing on the top 2 picks.

Then write a plain-English summary covering:
1. What the European market environment means right now (healthy/topping/recovering?) and why,
   using the market-top score, distribution day count, and FTD state as evidence.
2. What to do with European holdings this week — specific actions, not vague guidance. Explain the reasoning.
3. Why the top 1-2 picks stand out, what you are waiting for before buying, and what risk you
   are taking if you act early.
4. What specific signal (e.g. Follow-Through Day on Euro Stoxx 50 or DAX, price level, macro event)
   would change your stance.

Write in full paragraphs. No bullet points in this section.
```

---

## FULL VERSION — EUROPEAN MARKET LAYERS

For a more thorough European scan, replace the US-specific steps in the main workflow as follows.
Steps without an EU equivalent (macro-regime-detector, market-breadth-analyzer, earnings-calendar)
can still be run for global context; their data is not Europe-specific but remains informative.

**Layer 1 — Replace with European equivalents:**
- `/market-top-detector --europe` instead of `/market-top-detector`
- `/ftd-detector --europe` instead of `/ftd-detector`
- Run `/market-breadth-analyzer` and `/uptrend-analyzer` as-is for global breadth context
  (these use US data; treat as a proxy for risk appetite rather than EU-specific health)

**Layer 3 — Sector & Theme:**
- Run `/theme-detector` as-is — note themes with strong European representation
  (Defence, European Banks, European Energy, Luxury Goods)
- Run `/sector-analyst` for global sector rotation context

**Layer 4 — Screening:**
- `/vcp-screener --europe --mode prebreakout`
- `/canslim-screener --europe`
- Skip `/earnings-trade-analyzer` and `/institutional-flow-tracker` (US-data only)

**Layer 5 — Deep Dive:**
- Use `/us-stock-analysis` for European ADRs if available (e.g. ASML, SAP, NVO)
- For LSE/Xetra/Euronext stocks, provide a chart image to `/technical-analyst` directly

---

## NOTES

- **API keys required** for steps 7 (economic-calendar), 8 (earnings-calendar), 11-14 (screeners): set `FMP_API_KEY`
- **No API key needed for European quick scan** — all four EU skills fall back to yfinance automatically
- **Chart images required** for step 16 (technical-analyst): screenshot from TradingView or similar
- **Full run time**: ~45-60 minutes end to end
- **Quick version run time**: ~10-15 minutes (US or EU)
- **European universe**: defined in `universes/europe.txt` (Yahoo Finance suffixes: .L, .DE, .PA, .AS, .MI, etc.)
- **Skills supporting `--europe` flag**: `vcp-screener`, `canslim-screener`, `market-top-detector`, `ftd-detector`
- Save all reports to `reports/` — the screeners do this automatically
