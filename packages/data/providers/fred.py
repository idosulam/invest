"""FRED (Federal Reserve Economic Data) macro data provider.

Fetches macroeconomic time series — policy rates, Treasury yields,
inflation, labor, growth — from the St. Louis Fed's free API.

Free API key: https://fred.stlouisfed.org/docs/api/api_key.html

Series are referenced by friendly aliases (e.g. "cpi", "unemployment",
"10y_treasury") or raw FRED series IDs (e.g. "CPIAUCSL", "DGS10").
"""

import logging
import os
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

FRED_API_BASE = "https://api.stlouisfed.org/fred"
REQUEST_TIMEOUT = 30
DEFAULT_LOOKBACK_DAYS = 365
MAX_ROWS = 40

# Friendly aliases → FRED series IDs
MACRO_SERIES = {
    # Policy rate & Treasury yields
    "fed_funds_rate": "FEDFUNDS",
    "federal_funds_rate": "FEDFUNDS",
    "fed_funds": "FEDFUNDS",
    "2y_treasury": "DGS2",
    "10y_treasury": "DGS10",
    "30y_treasury": "DGS30",
    "10y_2y_spread": "T10Y2Y",
    "yield_curve": "T10Y2Y",
    # Inflation
    "cpi": "CPIAUCSL",
    "core_cpi": "CPILFESL",
    "pce": "PCEPI",
    "core_pce": "PCEPILFE",
    "inflation_expectations": "T10YIE",
    # Growth & output
    "real_gdp": "GDPC1",
    "gdp": "GDP",
    "industrial_production": "INDPRO",
    # Labor
    "unemployment_rate": "UNRATE",
    "unemployment": "UNRATE",
    "nonfarm_payrolls": "PAYEMS",
    "payrolls": "PAYEMS",
    "initial_claims": "ICSA",
    # Money & markets
    "m2": "M2SL",
    "money_supply": "M2SL",
    "vix": "VIXCLS",
    "dollar_index": "DTWEXBGS",
    # Sentiment & housing
    "consumer_sentiment": "UMCSENT",
    "housing_starts": "HOUST",
    "retail_sales": "RSAFS",
}

# Key macro indicators for the default evidence block
DEFAULT_MACRO_INDICATORS = [
    "fed_funds_rate",
    "10y_treasury",
    "10y_2y_spread",
    "cpi",
    "unemployment_rate",
    "vix",
]


def get_api_key() -> str | None:
    """Get FRED API key from environment. Returns None if not set."""
    return os.getenv("FRED_API_KEY")


def _resolve_series_id(indicator: str) -> str:
    """Map a friendly alias to a FRED series ID."""
    key = indicator.strip().lower().replace(" ", "_").replace("-", "_")
    if key in MACRO_SERIES:
        return MACRO_SERIES[key]
    candidate = indicator.strip().upper()
    if not candidate or len(candidate) > 30 or any(c.isspace() for c in candidate):
        raise ValueError(
            f"'{indicator}' is not a known macro alias or valid FRED series ID. "
            f"Use an alias (e.g. 'cpi', 'unemployment') or a raw FRED series ID."
        )
    return candidate


def _fred_request(path: str, params: dict, api_key: str) -> dict:
    """Make a request to the FRED API."""
    api_params = {**params, "api_key": api_key, "file_type": "json"}
    response = requests.get(
        f"{FRED_API_BASE}/{path}", params=api_params, timeout=REQUEST_TIMEOUT,
    )
    if response.status_code == 400:
        try:
            message = response.json().get("error_message", response.text)
        except ValueError:
            message = response.text
        raise ValueError(f"FRED request failed: {message}")
    response.raise_for_status()
    return response.json()


def get_macro_series(
    indicator: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    api_key: str | None = None,
) -> dict | None:
    """Fetch a single FRED series.

    Returns dict with keys: series_id, title, units, frequency,
    latest_value, latest_date, change, change_pct, observations.
    Returns None if FRED is not configured or the series is unavailable.
    """
    api_key = api_key or get_api_key()
    if not api_key:
        return None

    try:
        series_id = _resolve_series_id(indicator)
    except ValueError as e:
        logger.warning(f"FRED: {e}")
        return None

    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    try:
        meta = _fred_request("series", {"series_id": series_id}, api_key)
        info = (meta.get("seriess") or [{}])[0]

        observations = _fred_request(
            "series/observations",
            {
                "series_id": series_id,
                "observation_start": start_date,
                "observation_end": end_date,
                "sort_order": "asc",
            },
            api_key,
        ).get("observations", [])

        points = [
            (o["date"], o["value"])
            for o in observations
            if o.get("value") not in (".", None, "")
        ]

        if not points:
            return None

        first_date, first_val = points[0]
        last_date, last_val = points[-1]

        try:
            delta = float(last_val) - float(first_val)
            base = float(first_val)
            pct = (delta / base * 100) if base != 0 else 0.0
        except (ValueError, ZeroDivisionError):
            delta = 0.0
            pct = 0.0

        return {
            "series_id": series_id,
            "title": info.get("title", series_id),
            "units": info.get("units_short") or info.get("units", ""),
            "frequency": info.get("frequency", ""),
            "latest_value": last_val,
            "latest_date": last_date,
            "first_value": first_val,
            "first_date": first_date,
            "change": delta,
            "change_pct": pct,
            "observations": points[-MAX_ROWS:],  # recent only
        }

    except Exception as e:
        logger.warning(f"FRED fetch failed for {indicator}: {e}")
        return None


def get_macro_evidence_block(
    indicators: list[str] | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> str:
    """Build a formatted macro evidence block for agent prompts.

    Fetches multiple indicators and renders them as a markdown block
    suitable for injection into debate/analysis prompts.
    """
    api_key = get_api_key()
    if not api_key:
        return "MACRO DATA: FRED API key not configured. Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"

    indicators = indicators or DEFAULT_MACRO_INDICATORS
    lines = ["MACRO DATA (Federal Reserve Economic Data):"]

    for indicator in indicators:
        data = get_macro_series(indicator, lookback_days=lookback_days, api_key=api_key)
        if data is None:
            continue

        change_sign = "+" if data["change"] >= 0 else ""
        lines.append(
            f"- {data['title']}: {data['latest_value']} {data['units']} "
            f"({data['latest_date']}, {change_sign}{data['change']:.2f} / "
            f"{change_sign}{data['change_pct']:.1f}% over {lookback_days}d)"
        )

    if len(lines) == 1:
        lines.append("No macro data available.")

    return "\n".join(lines)
