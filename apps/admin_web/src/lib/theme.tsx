"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore } from "react";
import { THEME_KEY } from "@/lib/theme-script";

export type Theme = "light" | "dark" | "system";

type Ctx = { theme: Theme; resolved: "light" | "dark"; setTheme: (t: Theme) => void };
const ThemeContext = createContext<Ctx | null>(null);

const CHANGE_EVENT = "zuruv-theme-change";
const MQ = "(prefers-color-scheme: dark)";

function readStored(): Theme {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" || v === "system" ? v : "light"; // light is the default
  } catch {
    return "light";
  }
}

// External store: the saved choice (localStorage, shared across tabs) and the OS preference.
function subscribe(cb: () => void) {
  const mq = window.matchMedia(MQ);
  window.addEventListener("storage", cb);
  window.addEventListener(CHANGE_EVENT, cb);
  mq.addEventListener("change", cb);
  return () => {
    window.removeEventListener("storage", cb);
    window.removeEventListener(CHANGE_EVENT, cb);
    mq.removeEventListener("change", cb);
  };
}
const snapshot = () => `${readStored()}|${window.matchMedia(MQ).matches ? "dark" : "light"}`;
const serverSnapshot = () => "light|light";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, os] = useSyncExternalStore(subscribe, snapshot, serverSnapshot).split("|") as [Theme, "light" | "dark"];
  const resolved = theme === "system" ? os : theme;

  // Keep the <html> class in step (the inline script handles first paint).
  useEffect(() => {
    document.documentElement.classList.toggle("dark", resolved === "dark");
  }, [resolved]);

  const setTheme = useCallback((t: Theme) => {
    try {
      localStorage.setItem(THEME_KEY, t);
    } catch {
      // Storage blocked: nothing to persist.
    }
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }, []);

  const value = useMemo(() => ({ theme, resolved, setTheme }), [theme, resolved, setTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): Ctx {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used inside ThemeProvider");
  return ctx;
}
