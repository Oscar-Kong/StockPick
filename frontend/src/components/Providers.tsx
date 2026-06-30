"use client";

import { LocaleProvider } from "@/lib/i18n";
import { ThemeProvider } from "@/components/ThemeProvider";
import type { ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <LocaleProvider>{children}</LocaleProvider>
    </ThemeProvider>
  );
}
