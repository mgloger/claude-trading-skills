#!/usr/bin/env python3
"""
Market Top Detector - Main Orchestrator

Integrates O'Neil (Distribution Days), Minervini (Leading Stock Deterioration),
and Monty (Defensive Sector Rotation) approaches to detect market top probability.

Usage:
    # With FMP API (recommended):
    python3 market_top_detector.py --api-key YOUR_KEY \\
        --breadth-200dma 62.26 --breadth-50dma 55.0 \\
        --put-call 0.67 --vix-term contango

    # Using environment variable:
    export FMP_API_KEY=YOUR_KEY
    python3 market_top_detector.py --breadth-200dma 62.26

    # Minimal (VIX from API, rest from CLI):
    python3 market_top_detector.py --api-key YOUR_KEY \\
        --breadth-200dma 62.26 --put-call 0.67

Output:
    - JSON: market_top_YYYY-MM-DD_HHMMSS.json
    - Markdown: market_top_YYYY-MM-DD_HHMMSS.md
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from breadth_csv_client import fetch_breadth_200dma
from calculators.breadth_calculator import calculate_breadth_divergence
from calculators.defensive_rotation_calculator import (
    DEFENSIVE_ETFS,
    OFFENSIVE_ETFS,
    calculate_defensive_rotation,
)
from calculators.distribution_day_calculator import calculate_distribution_days
from calculators.index_technical_calculator import calculate_index_technical
from calculators.leading_stock_calculator import (
    CANDIDATE_POOL,
    LEADING_ETFS,
    calculate_leading_stock_health,
    select_dynamic_basket,
)
from calculators.sentiment_calculator import calculate_sentiment
from fmp_client import FMPClient
from yfinance_client import YFinanceClient
from historical_comparator import compare_to_historical
from report_generator import generate_json_report, generate_markdown_report
from scenario_engine import generate_scenarios
from scorer import calculate_composite_score, detect_follow_through_day


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Market Top Detector - O'Neil/Minervini/Monty Integration"
    )

    # API key
    parser.add_argument(
        "--api-key", help="FMP API key (defaults to FMP_API_KEY environment variable)"
    )

    # WebSearch-sourced data (provided by Claude before script execution)
    parser.add_argument(
        "--breadth-200dma",
        type=float,
        default=None,
        help="Percent of S&P 500 stocks above 200DMA (e.g., 62.26)",
    )
    parser.add_argument(
        "--breadth-50dma",
        type=float,
        default=None,
        help="Percent of S&P 500 stocks above 50DMA (e.g., 55.0)",
    )
    parser.add_argument(
        "--put-call", type=float, default=None, help="CBOE equity put/call ratio (e.g., 0.67)"
    )
    parser.add_argument(
        "--vix-term",
        choices=["steep_contango", "contango", "flat", "backwardation"],
        default=None,
        help="VIX term structure state",
    )
    parser.add_argument(
        "--margin-debt-yoy",
        type=float,
        default=None,
        help="Margin debt year-over-year change percent (e.g., 36.0)",
    )

    # Data freshness dates
    parser.add_argument(
        "--breadth-200dma-date", default=None, help="Date of breadth 200DMA data (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--breadth-50dma-date", default=None, help="Date of breadth 50DMA data (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--put-call-date", default=None, help="Date of put/call ratio data (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--margin-debt-date", default=None, help="Date of margin debt data (YYYY-MM-DD)"
    )

    # Additional context (not scored, but included in report)
    parser.add_argument(
        "--context",
        nargs="*",
        default=[],
        help="Additional context items in 'key=value' format (e.g., 'Consumer Confidence=57.3')",
    )

    # Breadth auto-fetch control
    parser.add_argument(
        "--no-auto-breadth",
        action="store_true",
        help="Disable auto-fetch of 200DMA breadth from TraderMonty CSV",
    )

    # Leading stock basket mode
    parser.add_argument(
        "--static-basket",
        action="store_true",
        help="Use static default ETF basket instead of dynamic selection",
    )

    # European mode
    parser.add_argument(
        "--europe",
        action="store_true",
        help=(
            "Analyse European market instead of US. "
            "Uses Euro Stoxx 50 (^STOXX50E), DAX (^GDAXI), VSTOXX (^V2TX) "
            "and European sector ETFs. Disables TraderMonty auto-breadth (US-only)."
        ),
    )

    # Output
    parser.add_argument("--output-dir", default=".", help="Output directory for reports")

    return parser.parse_args()


# ── European ETF baskets ────────────────────────────────────────────────────
# Leading/risk-on European ETFs (proxies for growth leadership)
EUROPEAN_CANDIDATE_POOL = [
    "EXV1.DE",  # iShares STOXX Europe 600 Oil & Gas
    "EXH1.DE",  # iShares STOXX Europe 600 Banks
    "EXH6.DE",  # iShares STOXX Europe 600 Industrials
    "EXH9.DE",  # iShares STOXX Europe 600 Technology
    "EXH7.DE",  # iShares STOXX Europe 600 Basic Resources
    "EZU",      # iShares MSCI Eurozone ETF (broad)
    "EWG",      # iShares MSCI Germany
    "EWU",      # iShares MSCI United Kingdom
    "EWQ",      # iShares MSCI France
    "EUFN",     # iShares MSCI Europe Financials
    "EXH8.DE",  # iShares STOXX Europe 600 Healthcare
    "EXV6.DE",  # iShares STOXX Europe 600 Utilities
]
EUROPEAN_LEADING_ETFS = ["EZU", "EWG", "EWU", "EWQ", "EUFN", "EXH9.DE", "EXH7.DE"]

# Defensive vs offensive European sector ETFs
EUROPEAN_DEFENSIVE_ETFS = ["EXH8.DE", "EXV6.DE", "EXH3.DE"]   # Healthcare, Utilities, Cons.Staples
EUROPEAN_OFFENSIVE_ETFS = ["EXH1.DE", "EXV1.DE", "EXH6.DE", "EXH9.DE"]  # Banks, Oil&Gas, Indust., Tech


def compute_data_freshness(date_args: dict) -> dict:
    """
    Compute data freshness factors for CLI input dates.

    Args:
        date_args: Dict with keys like 'breadth_200dma_date', 'breadth_50dma_date',
                   'put_call_date', 'margin_debt_date' -> YYYY-MM-DD strings.

    Returns:
        Dict with per-input freshness info and overall_confidence (min of all factors).
    """
    from datetime import date as dateclass

    freshness_map = {
        "breadth_200dma_date": "breadth_200dma",
        "breadth_50dma_date": "breadth_50dma",
        "put_call_date": "put_call",
        "margin_debt_date": "margin_debt",
    }

    result = {}
    factors = []
    today = dateclass.today()

    for arg_key, label in freshness_map.items():
        date_str = date_args.get(arg_key)
        if not date_str:
            continue
        try:
            d = dateclass.fromisoformat(date_str)
            age_days = (today - d).days
        except (ValueError, TypeError):
            result[label] = {"date": date_str, "age_days": None, "factor": 0.70}
            factors.append(0.70)
            continue

        if age_days <= 1:
            factor = 1.0
        elif age_days <= 3:
            factor = 0.95
        elif age_days <= 7:
            factor = 0.85
        else:
            factor = 0.70

        result[label] = {"date": date_str, "age_days": age_days, "factor": factor}
        factors.append(factor)

    result["overall_confidence"] = min(factors) if factors else 1.0
    return result


def _load_previous_report(output_dir: str) -> Optional[dict]:
    """
    Load the most recent market_top_*.json from output_dir.

    Files are named market_top_YYYY-MM-DD_HHMMSS.json, so lexicographic
    sorting gives chronological order.
    """
    pattern = os.path.join(output_dir, "market_top_*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        return None
    try:
        with open(files[-1]) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _compute_deltas(current_scores: dict[str, float], previous_report: Optional[dict]) -> dict:
    """
    Compute delta between current and previous component scores.

    Returns:
        Dict with per-component delta info and composite delta.
        If no previous report, direction is 'first_run' for all.
    """
    component_keys = [
        "distribution_days",
        "leading_stocks",
        "defensive_rotation",
        "breadth_divergence",
        "index_technical",
        "sentiment",
    ]
    deltas = {}

    if previous_report is None:
        for key in component_keys:
            deltas[key] = {"delta": 0, "direction": "first_run"}
        return {
            "components": deltas,
            "composite_delta": 0,
            "composite_direction": "first_run",
            "previous_date": None,
        }

    prev_components = previous_report.get("components", {})
    prev_composite = previous_report.get("composite", {}).get("composite_score", 0)

    for key in component_keys:
        prev_score = prev_components.get(key, {}).get("score", 0)
        curr_score = current_scores.get(key, 0)
        delta = curr_score - prev_score
        if abs(delta) <= 3:
            direction = "stable"
        elif delta > 0:
            direction = "worsening"
        else:
            direction = "improving"
        deltas[key] = {"delta": round(delta, 1), "direction": direction, "previous": prev_score}

    prev_date = previous_report.get("metadata", {}).get("generated_at", None)

    return {
        "components": deltas,
        "composite_delta": 0,  # Will be filled after composite calc
        "composite_direction": "first_run",
        "previous_date": prev_date,
        "previous_composite": prev_composite,
    }


def main():
    args = parse_arguments()

    print("=" * 70)
    print("Market Top Detector")
    mode_label = "European Market" if args.europe else "US Market"
    print(f"O'Neil (Distribution) + Minervini (Leadership) + Monty (Rotation) [{mode_label}]")
    print("=" * 70)
    print()

    # ── Mode-specific configuration ──────────────────────────────────────────
    if args.europe:
        primary_symbol   = "^STOXX50E"
        secondary_symbol = "^GDAXI"
        vix_symbol       = "^V2TX"
        primary_label    = "Euro Stoxx 50"
        secondary_label  = "DAX"
        vix_label        = "VSTOXX"
        candidate_pool   = EUROPEAN_CANDIDATE_POOL
        leading_etfs     = EUROPEAN_LEADING_ETFS
        defensive_etfs   = EUROPEAN_DEFENSIVE_ETFS
        offensive_etfs   = EUROPEAN_OFFENSIVE_ETFS
        # TraderMonty breadth CSV is US-only; disable auto-fetch
        if not args.no_auto_breadth:
            args.no_auto_breadth = True
            print("  [INFO] --europe: TraderMonty breadth CSV is US-only — auto-breadth disabled.")
    else:
        primary_symbol   = "^GSPC"
        secondary_symbol = "QQQ"
        vix_symbol       = "^VIX"
        primary_label    = "S&P 500"
        secondary_label  = "NASDAQ (QQQ)"
        vix_label        = "VIX"
        candidate_pool   = CANDIDATE_POOL
        leading_etfs     = LEADING_ETFS
        defensive_etfs   = DEFENSIVE_ETFS
        offensive_etfs   = OFFENSIVE_ETFS

    # Initialize data client: prefer FMP when a key is available, else yfinance
    use_fmp = args.api_key or os.getenv("FMP_API_KEY")
    if use_fmp:
        try:
            client = FMPClient(api_key=args.api_key)
            print("FMP API client initialized")
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        client = YFinanceClient()
        print("yfinance client initialized (no FMP key — using Yahoo Finance)")

    # ========================================================================
    # Step 1: Fetch shared data (indices, ETFs)
    # ========================================================================
    print()
    print("Step 1: Fetching Market Data")
    print("-" * 70)

    # Primary index data
    print(f"  Fetching {primary_label} data...", end=" ", flush=True)
    sp500_quote_list = client.get_quote(primary_symbol)
    sp500_quote = sp500_quote_list[0] if sp500_quote_list else None
    sp500_history_data = client.get_historical_prices(primary_symbol, days=260)
    sp500_history = sp500_history_data.get("historical", []) if sp500_history_data else []
    if sp500_quote and sp500_history:
        print(f"OK (${sp500_quote.get('price', 0):.2f}, {len(sp500_history)} days)")
    else:
        print("FAILED")
        print(f"ERROR: Cannot proceed without {primary_label} data", file=sys.stderr)
        sys.exit(1)

    # Secondary index data
    print(f"  Fetching {secondary_label} data...", end=" ", flush=True)
    qqq_quote_list = client.get_quote(secondary_symbol)
    qqq_quote = qqq_quote_list[0] if qqq_quote_list else None
    qqq_history_data = client.get_historical_prices(secondary_symbol, days=260)
    qqq_history = qqq_history_data.get("historical", []) if qqq_history_data else []
    if qqq_quote and qqq_history:
        print(f"OK (${qqq_quote.get('price', 0):.2f}, {len(qqq_history)} days)")
    else:
        print(f"WARN - {secondary_label} data unavailable, using {primary_label} only")

    # Volatility index
    print(f"  Fetching {vix_label}...", end=" ", flush=True)
    vix_quote_list = client.get_quote(vix_symbol)
    vix_quote = vix_quote_list[0] if vix_quote_list else None
    vix_level = vix_quote.get("price", None) if vix_quote else None
    if vix_level:
        print(f"OK ({vix_level:.2f})")
    else:
        print(f"WARN - {vix_label} unavailable")

    # VIX Term Structure auto-detection
    effective_vix_term = args.vix_term  # CLI override takes priority
    vix_term_auto = None
    if effective_vix_term is None:
        print("  Auto-detecting VIX term structure...", end=" ", flush=True)
        vix_term_auto = client.get_vix_term_structure()
        if vix_term_auto:
            effective_vix_term = vix_term_auto["classification"]
            print(f"OK ({effective_vix_term}, ratio={vix_term_auto['ratio']})")
        else:
            print("WARN - VIX3M unavailable, manual --vix-term needed")

    # Leading ETFs (dynamic or static basket)
    if args.static_basket or args.europe:
        # European mode always uses static basket (no dynamic selection logic)
        selected_basket = list(leading_etfs)
        basket_mode = "static (European)" if args.europe else "static"
        print(f"  Fetching Leading ETFs ({basket_mode})...", end=" ", flush=True)
        leading_quotes = client.get_batch_quotes(selected_basket)
        leading_historical = client.get_batch_historical(selected_basket, days=60)
    else:
        print("  Fetching candidate pool quotes for dynamic basket...", end=" ", flush=True)
        candidate_quotes = client.get_batch_quotes(candidate_pool)
        print(f"OK ({len(candidate_quotes)} candidates)")
        selected_basket = select_dynamic_basket(candidate_quotes)
        print(f"  Selected dynamic basket: {selected_basket}")
        print("  Fetching Leading ETFs (dynamic basket)...", end=" ", flush=True)
        leading_quotes = {s: candidate_quotes[s] for s in selected_basket if s in candidate_quotes}
        leading_historical = client.get_batch_historical(selected_basket, days=60)
    print(f"OK ({len(leading_quotes)} quotes, {len(leading_historical)} histories)")

    # Sector ETFs
    all_sector_etfs = list(set(defensive_etfs + offensive_etfs))
    # Exclude the secondary index if it was already fetched
    sector_etfs_to_fetch = [e for e in all_sector_etfs if e != secondary_symbol]
    print("  Fetching Sector ETFs...", end=" ", flush=True)
    sector_historical = client.get_batch_historical(sector_etfs_to_fetch, days=50)
    # Add secondary index history if available
    if qqq_history:
        sector_historical[secondary_symbol] = qqq_history[:50]
    print(f"OK ({len(sector_historical)} ETFs)")

    print()

    # ========================================================================
    # Step 2: Calculate Components
    # ========================================================================
    print("Step 2: Calculating Components")
    print("-" * 70)

    # Component 1: Distribution Days (25%)
    print("  [1/6] Distribution Day Count...", end=" ", flush=True)
    comp1 = calculate_distribution_days(sp500_history, qqq_history)
    print(f"Score: {comp1['score']} ({comp1['signal']})")

    # Component 2: Leading Stock Health (20%)
    print("  [2/6] Leading Stock Health...", end=" ", flush=True)
    comp2 = calculate_leading_stock_health(
        leading_quotes, leading_historical, etf_list=selected_basket
    )
    print(f"Score: {comp2['score']} ({comp2['signal']})")

    # Component 3: Defensive Rotation (15%)
    print("  [3/6] Defensive Sector Rotation...", end=" ", flush=True)
    comp3 = calculate_defensive_rotation(
        sector_historical,
        defensive_etfs=defensive_etfs,
        offensive_etfs=offensive_etfs,
    )
    print(f"Score: {comp3['score']} ({comp3['signal']})")

    # Auto-fetch 200DMA breadth if not provided via CLI
    effective_breadth_200dma = args.breadth_200dma
    breadth_source = "cli"
    breadth_auto_date = None

    if effective_breadth_200dma is None and not args.no_auto_breadth:
        print("  Fetching 200DMA breadth from TraderMonty CSV...", end=" ", flush=True)
        auto_result = fetch_breadth_200dma()
        if auto_result is not None:
            effective_breadth_200dma = auto_result["value"]
            breadth_source = "auto"
            breadth_auto_date = auto_result["date"]
            fresh_str = (
                "fresh" if auto_result["is_fresh"] else f"STALE ({auto_result['days_old']}d old)"
            )
            print(f"OK ({effective_breadth_200dma}%, {auto_result['date']}, {fresh_str})")
            if not auto_result["is_fresh"]:
                print(f"  WARNING: Breadth data is {auto_result['days_old']} days old")
        else:
            print("FAILED (will use neutral default)")

    # Component 4: Breadth Divergence (15%)
    print("  [4/6] Market Breadth Divergence...", end=" ", flush=True)
    # Calculate index distance from 52-week high
    sp500_year_high = sp500_quote.get("yearHigh", 0)
    sp500_price = sp500_quote.get("price", 0)
    if sp500_year_high > 0:
        index_dist = (sp500_price - sp500_year_high) / sp500_year_high * 100
    else:
        index_dist = 0

    comp4 = calculate_breadth_divergence(
        breadth_200dma=effective_breadth_200dma,
        breadth_50dma=args.breadth_50dma,
        index_distance_from_high_pct=index_dist,
    )
    comp4["breadth_source"] = breadth_source
    if breadth_auto_date:
        comp4["breadth_auto_date"] = breadth_auto_date
    print(f"Score: {comp4['score']} ({comp4['signal']})")

    # Component 5: Index Technical (15%)
    print("  [5/6] Index Technical Condition...", end=" ", flush=True)
    comp5 = calculate_index_technical(
        sp500_history, qqq_history, sp500_quote=sp500_quote, nasdaq_quote=qqq_quote
    )
    print(f"Score: {comp5['score']} ({comp5['signal']})")

    # Component 6: Sentiment (10%)
    print("  [6/6] Sentiment & Speculation...", end=" ", flush=True)
    comp6 = calculate_sentiment(
        vix_level=vix_level,
        put_call_ratio=args.put_call,
        vix_term_structure=effective_vix_term,
        margin_debt_yoy_pct=args.margin_debt_yoy,
    )
    print(f"Score: {comp6['score']} ({comp6['signal']})")

    print()

    # Compute data freshness
    freshness_args = {
        "breadth_200dma_date": breadth_auto_date
        if breadth_source == "auto"
        else args.breadth_200dma_date,
        "breadth_50dma_date": args.breadth_50dma_date,
        "put_call_date": args.put_call_date,
        "margin_debt_date": args.margin_debt_date,
    }
    data_freshness = compute_data_freshness(freshness_args)

    # ========================================================================
    # Step 3: Composite Score
    # ========================================================================
    print("Step 3: Calculating Composite Score")
    print("-" * 70)

    component_scores = {
        "distribution_days": comp1["score"],
        "leading_stocks": comp2["score"],
        "defensive_rotation": comp3["score"],
        "breadth_divergence": comp4["score"],
        "index_technical": comp5["score"],
        "sentiment": comp6["score"],
    }

    data_availability = {
        "distribution_days": True,  # Always available (requires S&P data to run)
        "leading_stocks": comp2.get("data_available", True),
        "defensive_rotation": comp3.get("data_available", True),
        "breadth_divergence": comp4.get("data_available", True),
        "index_technical": comp5.get("data_available", True),
        "sentiment": comp6.get("data_available", True),
    }

    composite = calculate_composite_score(component_scores, data_availability)

    print(f"  Composite Score: {composite['composite_score']}/100")
    print(f"  Risk Zone: {composite['zone']}")
    print(f"  Risk Budget: {composite['risk_budget']}")
    print(
        f"  Strongest Warning: {composite['strongest_warning']['label']} "
        f"({composite['strongest_warning']['score']})"
    )

    # Delta tracking vs previous run
    previous_report = _load_previous_report(args.output_dir)
    delta_info = _compute_deltas(component_scores, previous_report)
    # Update composite delta now that we have the composite score
    if previous_report is not None:
        prev_composite = delta_info.get("previous_composite", 0)
        comp_delta = composite["composite_score"] - prev_composite
        delta_info["composite_delta"] = round(comp_delta, 1)
        if abs(comp_delta) <= 3:
            delta_info["composite_direction"] = "stable"
        elif comp_delta > 0:
            delta_info["composite_direction"] = "worsening"
        else:
            delta_info["composite_direction"] = "improving"
        print(
            f"  vs Previous: {prev_composite} -> {composite['composite_score']} "
            f"({delta_info['composite_delta']:+.1f})"
        )
    else:
        print("  (First run - no comparison available)")
    print()

    # ========================================================================
    # Step 4: Follow-Through Day Check
    # ========================================================================
    ftd = detect_follow_through_day(sp500_history, composite["composite_score"])
    if ftd.get("applicable"):
        print("Step 4: Follow-Through Day Monitor")
        print("-" * 70)
        print(f"  {ftd['reason']}")
        print()

    # ========================================================================
    # Step 5: Historical Comparison & Scenarios
    # ========================================================================
    print("Step 5: Historical Comparison & Scenarios")
    print("-" * 70)

    historical_comparison = compare_to_historical(component_scores)
    print(f"  Closest historical pattern: {historical_comparison['closest_match']}")

    scenarios = generate_scenarios(component_scores, data_availability)
    print(f"  Generated {len(scenarios)} what-if scenarios")
    print()

    # ========================================================================
    # Step 6: Generate Reports
    # ========================================================================
    print("Step 6: Generating Reports")
    print("-" * 70)

    # Parse additional context
    additional_context = {}
    for item in args.context:
        if "=" in item:
            key, value = item.split("=", 1)
            additional_context[key.strip()] = value.strip()

    # Build full analysis
    analysis = {
        "metadata": {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_mode": "FMP API + CLI inputs",
            "api_calls": client.get_api_stats(),
            "cli_inputs": {
                "breadth_200dma": effective_breadth_200dma,
                "breadth_200dma_source": breadth_source,
                "breadth_200dma_auto_date": breadth_auto_date,
                "breadth_50dma": args.breadth_50dma,
                "put_call_ratio": args.put_call,
                "vix_term_structure": args.vix_term,
                "margin_debt_yoy_pct": args.margin_debt_yoy,
            },
            "vix_term_auto": vix_term_auto,
            "index_data": {
                "sp500_price": sp500_price,
                "sp500_year_high": sp500_year_high,
                "sp500_distance_from_high_pct": round(index_dist, 2),
                "qqq_price": qqq_quote.get("price", 0) if qqq_quote else None,
                "vix_level": vix_level,
            },
            "data_freshness": data_freshness,
        },
        "composite": composite,
        "components": {
            "distribution_days": comp1,
            "leading_stocks": comp2,
            "defensive_rotation": comp3,
            "breadth_divergence": comp4,
            "index_technical": comp5,
            "sentiment": comp6,
        },
        "follow_through_day": ftd,
        "historical_comparison": historical_comparison,
        "scenarios": scenarios,
        "delta": delta_info,
        "additional_context": additional_context,
    }

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    json_file = os.path.join(args.output_dir, f"market_top_{timestamp}.json")
    md_file = os.path.join(args.output_dir, f"market_top_{timestamp}.md")

    generate_json_report(analysis, json_file)
    generate_markdown_report(analysis, md_file)

    print()
    print("=" * 70)
    print("Market Top Detection Complete")
    print("=" * 70)
    print(f"  Composite Score: {composite['composite_score']}/100")
    print(f"  Risk Zone: {composite['zone']}")
    print(f"  Risk Budget: {composite['risk_budget']}")
    print(f"  JSON Report: {json_file}")
    print(f"  Markdown Report: {md_file}")
    print()

    stats = client.get_api_stats()
    print("API Usage:")
    print(f"  API calls made: {stats['api_calls_made']}")
    print(f"  Cache entries: {stats['cache_entries']}")
    print()


if __name__ == "__main__":
    main()
