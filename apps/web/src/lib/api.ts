/* ── API client for the FastAPI backend ── */

const API_BASE = "/api/v1";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

/* ── Auth ── */

export const auth = {
  login: (username: string, password: string) =>
    request<{ access_token: string; token_type: string; expires_in: number }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ username, password }) },
    ),
  register: (email: string, username: string, password: string) =>
    request<any>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, username, password }),
    }),
  me: () => request<any>("/auth/me"),
};

/* ── Instruments ── */

export const instruments = {
  list: (params?: {
    page?: number;
    page_size?: number;
    type?: string;
    status?: string;
    search?: string;
  }) => {
    const qs = new URLSearchParams();
    if (params?.page) qs.set("page", String(params.page));
    if (params?.page_size) qs.set("page_size", String(params.page_size));
    if (params?.type) qs.set("type", params.type);
    if (params?.status) qs.set("status", params.status);
    if (params?.search) qs.set("search", params.search);

    return request<any>(`/instruments?${qs}`);
  },
  get: (id: string) => request<any>(`/instruments/${id}`),
  create: (data: any) =>
    request<any>("/instruments", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  remove: (id: string) =>
    request<any>(`/instruments/${id}`, { method: "DELETE" }),
};

/* ── Charts ── */

export const charts = {
  getData: (
    instrumentId: string,
    params?: {
      timeframe?: string;
      start?: string;
      end?: string;
      indicators?: string;
      limit?: number;
    },
  ) => {
    const qs = new URLSearchParams();
    if (params?.timeframe) qs.set("timeframe", params.timeframe);
    if (params?.start) qs.set("start", params.start);
    if (params?.end) qs.set("end", params.end);
    if (params?.indicators) qs.set("indicators", params.indicators);
    if (params?.limit) qs.set("limit", String(params.limit));
    return request<any>(`/charts/${instrumentId}?${qs}`);
  },
  listIndicators: () => request<string[]>("/charts/indicators"),
};

/* ── Assistant ── */

export const assistant = {
  query: (question: string, instrumentId: string, contextType = "signal") =>
    request<any>("/assistant/query", {
      method: "POST",
      body: JSON.stringify({
        question,
        instrument_id: instrumentId,
        context_type: contextType,
      }),
    }),
  history: (limit = 20) => request<any[]>(`/assistant/history?limit=${limit}`),
};

/* ── Scanner ── */

export const signals = {
  debate: (instrumentId: string) =>
    request<any>(`/signals/debate/${instrumentId}`, { method: "POST" }),
  consolidated: (instrumentId: string) =>
    request<any>(`/signals/consolidated/${instrumentId}`, { method: "POST" }),
};

/* ── Strategies ── */

export const strategies = {
  list: (horizon?: string) => {
    const qs = horizon ? `?horizon=${horizon}` : "";
    return request<any[]>(`/signals/strategies${qs}`);
  },
};

/* ── Strategy Performance ── */

export const strategyPerformance = {
  list: (params?: { strategy?: string; instrument_id?: string }) => {
    const qs = new URLSearchParams();
    if (params?.strategy) qs.set("strategy", params.strategy);
    if (params?.instrument_id) qs.set("instrument_id", params.instrument_id);
    return request<any>(`/backtests/performance?${qs}`);
  },
  get: (strategy: string, instrumentId: string) =>
    request<any>(`/backtests/performance/${strategy}/${instrumentId}`),
};

export const scanner = {
  run: (
    filters: Record<string, any>,
    sortBy = "symbol",
    sortDir = "asc",
    limit = 200,
  ) =>
    request<any>(
      `/scanner/run?sort_by=${sortBy}&sort_dir=${sortDir}&limit=${limit}`,
      {
        method: "POST",
        body: JSON.stringify(filters),
      },
    ),
  discover: (screenerName = "most_active", limit = 25) =>
    request<any>(`/scanner/discover?screener=${screenerName}&limit=${limit}`),
};

/* ── Watchlists ── */

export const watchlists = {
  list: () => request<any>("/watchlists"),
  get: (id: string) => request<any>(`/watchlists/${id}`),
  create: (name: string) =>
    request<any>("/watchlists", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  update: (id: string, data: { name?: string }) =>
    request<any>(`/watchlists/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  delete: (id: string) =>
    request<void>(`/watchlists/${id}`, { method: "DELETE" }),
  addInstrument: (id: string, instrumentId: string) =>
    request<any>(`/watchlists/${id}/instruments`, {
      method: "POST",
      body: JSON.stringify({ instrument_id: instrumentId }),
    }),
  removeInstrument: (id: string, instrumentId: string) =>
    request<any>(`/watchlists/${id}/instruments/${instrumentId}`, {
      method: "DELETE",
    }),
};
