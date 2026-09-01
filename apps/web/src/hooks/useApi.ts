"use client";

import useSWR from "swr";
import { instruments, charts, watchlists } from "@/lib/api";

/* ── Instruments ── */

export function useInstruments(params?: {
  page?: number;
  page_size?: number;
  type?: string;
  search?: string;
}) {
  const key = ["instruments", params];
  return useSWR(key, () => instruments.list(params), {
    revalidateOnFocus: false,
  });
}

export function useInstrument(id: string | null) {
  return useSWR(id ? ["instrument", id] : null, () => instruments.get(id!), {
    revalidateOnFocus: false,
  });
}

/* ── Charts ── */

export function useChartData(
  instrumentId: string | null,
  params?: {
    timeframe?: string;
    indicators?: string;
    limit?: number;
  }
) {
  const key = instrumentId ? ["chart", instrumentId, params] : null;
  return useSWR(key, () => charts.getData(instrumentId!, params), {
    revalidateOnFocus: false,
  });
}

/* ── Watchlists ── */

export function useWatchlists() {
  return useSWR("watchlists", () => watchlists.list(), {
    revalidateOnFocus: false,
  });
}

export function useWatchlist(id: string | null) {
  return useSWR(id ? ["watchlist", id] : null, () => watchlists.get(id!), {
    revalidateOnFocus: false,
  });
}
