"use client";

import { getPortfolioLedger } from "@/lib/api";
import { parseApiError } from "@/lib/apiError";
import {
  ALL_MONTHS,
  ALL_YEARS,
  collectTradingPeriods,
  defaultYearFilter,
  dedupeTradeRows,
  filterTradesByPeriod,
  isRobinhoodMcpTrade,
  isTradeRow,
  monthOptionsForYear,
  type MonthFilter,
  type YearFilter,
} from "@/lib/tradingHistory";
import type { LedgerEntry } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { useCallback, useEffect, useMemo, useState } from "react";

export function useTradingHistory(reloadToken = 0) {
  const { t } = useTranslation();
  const [rows, setRows] = useState<LedgerEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [year, setYear] = useState<YearFilter>(ALL_YEARS);
  const [month, setMonth] = useState<MonthFilter>(ALL_MONTHS);

  const load = useCallback(async (opts?: { silent?: boolean }) => {
    if (!opts?.silent) setLoading(true);
    setError(null);
    try {
      const data = await getPortfolioLedger();
      const trades = dedupeTradeRows(
        (data.rows ?? []).filter((row) => isTradeRow(row) && isRobinhoodMcpTrade(row)),
      );
      setRows(trades);
      const { years } = collectTradingPeriods(trades);
      setYear((prev) => (prev === ALL_YEARS ? defaultYearFilter(years) : prev));
    } catch (e) {
      setError(parseApiError(e, t.portfolio.tradingHistoryLoadFailed));
    } finally {
      if (!opts?.silent) setLoading(false);
    }
  }, [t.portfolio.tradingHistoryLoadFailed]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (reloadToken > 0) void load({ silent: true });
  }, [load, reloadToken]);

  const { years, monthsByYear } = useMemo(() => collectTradingPeriods(rows), [rows]);

  const availableMonths = useMemo(
    () => monthOptionsForYear(monthsByYear, year),
    [monthsByYear, year],
  );

  useEffect(() => {
    if (month === ALL_MONTHS) return;
    if (!availableMonths.includes(month)) {
      setMonth(ALL_MONTHS);
    }
  }, [availableMonths, month]);

  const filtered = useMemo(
    () => filterTradesByPeriod(rows, year, month),
    [rows, year, month],
  );

  const setYearFilter = useCallback((next: YearFilter) => {
    setYear(next);
    setMonth(ALL_MONTHS);
  }, []);

  return {
    rows,
    filtered,
    loading,
    error,
    year,
    month,
    years,
    availableMonths,
    setYear: setYearFilter,
    setMonth,
    reload: () => load({ silent: true }),
  };
}
