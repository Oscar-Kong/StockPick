"use client";

import { TradeJournal } from "@/components/TradeJournal";
import { CsvImportFooter, type CsvImportFooterProps } from "./daily-decision/DailyDecisionPanels";

/** Compact trade log + Robinhood CSV import on Home. */
export function HomeJournalPanel({ csvImport }: { csvImport: CsvImportFooterProps }) {
  return (
    <section id="home-journal" className="home-journal data-panel data-panel--padded" aria-labelledby="home-journal-title">
      <TradeJournal compact />
      <CsvImportFooter {...csvImport} />
    </section>
  );
}
