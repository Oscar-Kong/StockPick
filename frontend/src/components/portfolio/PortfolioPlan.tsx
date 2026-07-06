"use client";

import type { DailyDashboardResponse } from "@/lib/types";
import { DailyTradingPlanCard } from "@/components/dashboard/daily-decision/DailyTradingPlanCard";

export interface PortfolioPlanProps {
  data: DailyDashboardResponse;
}

export function PortfolioPlan({ data }: PortfolioPlanProps) {
  return (
    <div className="portfolio-plan portfolio-plan--modern">
      <DailyTradingPlanCard data={data} />
    </div>
  );
}
