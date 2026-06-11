"use client";

import { useEffect, useRef } from "react";
import type { Messages } from "./messages/en";
import { useTranslation } from "./context";

/**
 * Stable ref to the current message catalog. Use inside fetch callbacks / effects
 * instead of putting `t` in dependency arrays — locale changes should re-render
 * labels only, not re-run API calls.
 */
export function useTRef(): React.MutableRefObject<Messages> {
  const { t } = useTranslation();
  const ref = useRef(t);
  useEffect(() => {
    ref.current = t;
  }, [t]);
  return ref;
}
