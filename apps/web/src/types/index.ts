/* ── Domain types matching the FastAPI schemas ── */

export interface Instrument {
  id: string;
  symbol: string;
  name: string;
  type: "STOCK" | "ETF" | "BENCHMARK" | "INDEX";
  venue_id: string | null;
  currency: string;
  status: "ACTIVE" | "SUSPENDED" | "DELISTED" | "PENDING";
  isin: string | null;
  cusip: string | null;
  figi: string | null;
  exchange: string | null;
  sector: string | null;
  industry: string | null;
  country: string | null;
  created_at: string;
  updated_at: string;
}

export interface InstrumentListResponse {
  items: Instrument[];
  total: number;
  page: number;
  page_size: number;
}

export interface BarPoint {
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  vwap: number | null;
}

export interface ChartResponse {
  instrument_id: string;
  symbol: string;
  timeframe: string;
  bars: BarPoint[];
  indicators: Record<string, (number | null)[] | Record<string, (number | null)[]>>;
}

export interface Watchlist {
  id: string;
  name: string;
  owner_id: string;
  instrument_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface WatchlistDetail extends Watchlist {
  instruments: {
    id: string;
    symbol: string;
    name: string;
    type: string;
    exchange: string | null;
    currency: string;
    status: string;
  }[];
}

export interface User {
  id: string;
  email: string;
  username: string;
  role: "ADMIN" | "ANALYST" | "VIEWER";
  is_active: boolean;
  created_at: string;
}
