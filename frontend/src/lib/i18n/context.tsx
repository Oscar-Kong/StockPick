"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { en, type Messages } from "./messages/en";
import { zh } from "./messages/zh";

export type Locale = "en" | "zh";

const STORAGE_KEY = "picker-locale";

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: Messages;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

function readStoredLocale(): Locale {
  if (typeof window === "undefined") return "en";
  const raw = localStorage.getItem(STORAGE_KEY);
  return raw === "zh" ? "zh" : "en";
}

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setLocaleState(readStoredLocale());
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    document.documentElement.lang = locale === "zh" ? "zh-Hans" : "en";
    localStorage.setItem(STORAGE_KEY, locale);
    window.dispatchEvent(new CustomEvent("locale-changed", { detail: locale }));
  }, [locale, ready]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
  }, []);

  // `en` / `zh` are module singletons — switching locale re-renders UI only.
  // Do not put `t` in useEffect deps; use useTRef() for error strings in fetch handlers.
  const t = locale === "zh" ? zh : en;

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider");
  return ctx;
}

export function useTranslation() {
  return useLocale();
}
