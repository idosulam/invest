"""CongressInvests provider — congressional stock trading disclosures.

Free tier: 100 requests/day, no API key or account needed.
Docs: https://congressinvests.com/
"""

import logging
from datetime import datetime, timezone
from typing import Iterable

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://congressinfor-production.up.railway.app"


class CongressTrade:
    """A single disclosed congressional stock trade."""

    def __init__(
        self,
        symbol: str,
        member_name: str,
        chamber: str,
        trade_type: str,
        amount_range: str,
        transaction_date: datetime,
        disclosed_date: datetime,
        asset_name: str = "",
        source_url: str = "",
    ):
        self.symbol = symbol
        self.member_name = member_name
        self.chamber = chamber
        self.trade_type = trade_type
        self.amount_range = amount_range
        self.transaction_date = transaction_date
        self.disclosed_date = disclosed_date
        self.asset_name = asset_name
        self.source_url = source_url


class CongressTradingProvider:
    """Fetches congressional trade disclosures for a given ticker."""

    def trades_for_symbol(self, symbol: str, limit: int = 50) -> Iterable[CongressTrade]:
        try:
            resp = requests.get(
                f"{BASE_URL}/trades/{symbol.upper()}",
                params={"limit": limit},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("trades", []):
                try:
                    tx_date = datetime.strptime(item.get("tx_date", ""), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    tx_date = datetime.now(timezone.utc)
                try:
                    disclosed_date = datetime.strptime(item.get("disclosed", ""), "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    disclosed_date = tx_date

                yield CongressTrade(
                    symbol=symbol.upper(),
                    member_name=item.get("member", "Unknown"),
                    chamber=item.get("chamber", "Unknown"),
                    trade_type=item.get("trade_type", "unknown").lower(),
                    amount_range=item.get("amount", ""),
                    transaction_date=tx_date,
                    disclosed_date=disclosed_date,
                    asset_name=item.get("asset", ""),
                    source_url=item.get("link", ""),
                )
        except requests.RequestException as e:
            logger.error(f"Error fetching congressional trades for {symbol}: {e}")
        except (ValueError, KeyError) as e:
            logger.error(f"Error parsing congressional trades response for {symbol}: {e}")
