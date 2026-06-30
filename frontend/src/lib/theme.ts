export type ThemePreference = "dark" | "light" | "system";

export const THEME_STORAGE_KEY = "pickerquant-theme";

export function resolveTheme(preference: ThemePreference): "dark" | "light" {
  if (preference === "system" && typeof window !== "undefined") {
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  return preference === "light" ? "light" : "dark";
}

export function readStoredTheme(): ThemePreference {
  if (typeof window === "undefined") return "dark";
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "system") return stored;
    if (stored === "dark") return "dark";
  } catch {
    /* ignore */
  }
  return "dark";
}

export function persistTheme(preference: ThemePreference): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    /* ignore */
  }
}

/** Inline script source — must stay in sync with resolveTheme/readStoredTheme. */
export const THEME_INIT_SCRIPT = `(function(){try{var k='pickerquant-theme';var p=localStorage.getItem(k);var d='dark';if(p==='light')d='light';else if(p==='system'&&window.matchMedia('(prefers-color-scheme: light)').matches)d='light';document.documentElement.setAttribute('data-theme',d);}catch(e){document.documentElement.setAttribute('data-theme','dark');}})();`;
