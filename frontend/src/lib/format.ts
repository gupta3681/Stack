/**
 * Display helpers shared across components.
 */

/**
 * Render a minute count as a compact human string.
 *
 *   formatMinutes(0)   → "0m"
 *   formatMinutes(45)  → "45m"
 *   formatMinutes(60)  → "1h"
 *   formatMinutes(90)  → "1h 30m"
 *   formatMinutes(480) → "8h"
 */
export function formatMinutes(minutes: number): string {
  if (!Number.isFinite(minutes) || minutes <= 0) return "0m";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  if (m === 0) return `${h}h`;
  return `${h}h ${m}m`;
}
