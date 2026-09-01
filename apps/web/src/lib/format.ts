/* ── Formatting utilities ── */

export const format = {
  /** Short date: "Jan 15" or "Jan 15, 2024" if different year */
  shortDate: (d: Date): string => {
    const now = new Date();
    const opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
    if (d.getFullYear() !== now.getFullYear()) {
      opts.year = "numeric";
    }
    return d.toLocaleDateString("en-US", opts);
  },

  /** Full date: "Jan 15, 2024 14:30" */
  fullDate: (d: Date): string =>
    d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }),

  /** Compact number: 1.2M, 3.5K, etc. */
  compact: (n: number): string => {
    if (Math.abs(n) >= 1e9) return (n / 1e9).toFixed(1) + "B";
    if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + "K";
    return n.toFixed(0);
  },

  /** Currency: $1,234.56 */
  currency: (n: number, currency = "USD"): string =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(n),

  /** Percentage: +2.35% or -1.12% */
  pct: (n: number, decimals = 2): string => {
    const sign = n > 0 ? "+" : "";
    return `${sign}${n.toFixed(decimals)}%`;
  },

  /** Color class for positive/negative values */
  changeColor: (n: number): string => {
    if (n > 0) return "text-success-500";
    if (n < 0) return "text-danger-500";
    return "text-surface-700";
  },
};
