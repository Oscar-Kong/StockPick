/** Client-side scan job polling — must exceed worst-case backend Stage A+B runtime. */
export const SCAN_POLL_INTERVAL_MS = 1500;
/** 600 × 1.5s = 15 minutes (matches SCAN_STAGE_B_TIME_BUDGET_SECONDS default). */
export const SCAN_POLL_MAX_TICKS = 600;
