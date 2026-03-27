/**
 * ICT Session Zone Calculator
 * Computes Asian, London, and New York session boundaries + kill zones
 * from candle timestamps for chart overlay rendering.
 */

export interface SessionZone {
  start: number; // unix timestamp
  end: number;   // unix timestamp
  type: "asian" | "london" | "newyork";
  label: string;
  color: string;
  isKillZone: boolean;
}

// Session times in ET (Eastern Time) — hours in 24h format
const SESSION_DEFS = {
  asian:    { start: 20, end: 1,  color: "rgba(139, 92, 246, 0.06)",  killStart: 20, killEnd: 0,    killColor: "rgba(139, 92, 246, 0.12)" },
  london:   { start: 2,  end: 5,  color: "rgba(59, 130, 246, 0.06)",  killStart: 2,  killEnd: 5,    killColor: "rgba(59, 130, 246, 0.12)" },
  newyork:  { start: 8,  end: 11, color: "rgba(249, 115, 22, 0.06)",  killStart: 9,  killEnd: 11,   killColor: "rgba(249, 115, 22, 0.12)" },
} as const;

// ET offset from UTC (standard = -5, DST = -4)
// Simple DST detection: 2nd Sunday Mar to 1st Sunday Nov
function getETOffsetHours(date: Date): number {
  const year = date.getUTCFullYear();
  const mar = new Date(Date.UTC(year, 2, 1));
  const marDay = mar.getUTCDay();
  const dstStart = new Date(Date.UTC(year, 2, 8 + (7 - marDay) % 7, 7)); // 2nd Sun Mar at 2AM ET = 7AM UTC

  const nov = new Date(Date.UTC(year, 10, 1));
  const novDay = nov.getUTCDay();
  const dstEnd = new Date(Date.UTC(year, 10, 1 + (7 - novDay) % 7, 6)); // 1st Sun Nov at 2AM ET = 6AM UTC

  return (date >= dstStart && date < dstEnd) ? -4 : -5;
}

function utcToET(utcTimestamp: number): { hour: number; date: Date } {
  const date = new Date(utcTimestamp * 1000);
  const etOffset = getETOffsetHours(date);
  const etDate = new Date(date.getTime() + etOffset * 3600 * 1000);
  return { hour: etDate.getUTCHours(), date: etDate };
}

/**
 * Given an array of candle timestamps, compute session zones that overlap
 * with the visible data range.
 */
export function getSessionZones(
  candles: { time: number }[],
  timeframe: string
): SessionZone[] {
  // Skip sessions for timeframes >= 1h (too zoomed out)
  if (timeframe === "1h" || timeframe === "4h" || timeframe === "1d") {
    return [];
  }

  if (!candles.length) return [];

  const firstTime = candles[0].time;
  const lastTime = candles[candles.length - 1].time;
  const zones: SessionZone[] = [];

  // Walk through each day in the candle range and compute session boundaries
  // Expand range by 1 day on each side to catch sessions that span midnight
  const startDate = new Date((firstTime - 86400) * 1000);
  const endDate = new Date((lastTime + 86400) * 1000);

  const current = new Date(Date.UTC(startDate.getUTCFullYear(), startDate.getUTCMonth(), startDate.getUTCDate()));
  const end = new Date(Date.UTC(endDate.getUTCFullYear(), endDate.getUTCMonth(), endDate.getUTCDate()));

  while (current <= end) {
    const etOffset = getETOffsetHours(current);
    const utcOffsetMs = -etOffset * 3600 * 1000; // ET to UTC offset in ms

    for (const [sessionType, def] of Object.entries(SESSION_DEFS)) {
      const type = sessionType as SessionZone["type"];

      // Compute session start/end in UTC timestamps
      let startMs: number;
      let endMs: number;

      if (def.start > def.end) {
        // Crosses midnight (e.g., Asian: 20:00 to 01:00)
        startMs = current.getTime() + def.start * 3600000 + utcOffsetMs;
        endMs = current.getTime() + (24 + def.end) * 3600000 + utcOffsetMs;
      } else {
        startMs = current.getTime() + def.start * 3600000 + utcOffsetMs;
        endMs = current.getTime() + def.end * 3600000 + utcOffsetMs;
      }

      const startSec = Math.floor(startMs / 1000);
      const endSec = Math.floor(endMs / 1000);

      // Only include if it overlaps with candle range
      if (endSec >= firstTime && startSec <= lastTime) {
        zones.push({
          start: Math.max(startSec, firstTime),
          end: Math.min(endSec, lastTime),
          type,
          label: type.charAt(0).toUpperCase() + type.slice(1),
          color: def.color,
          isKillZone: false,
        });

        // Kill zone (subset of session)
        let kStartMs: number;
        let kEndMs: number;

        if (def.killStart > def.killEnd) {
          kStartMs = current.getTime() + def.killStart * 3600000 + utcOffsetMs;
          kEndMs = current.getTime() + (24 + def.killEnd) * 3600000 + utcOffsetMs;
        } else {
          kStartMs = current.getTime() + def.killStart * 3600000 + utcOffsetMs;
          kEndMs = current.getTime() + def.killEnd * 3600000 + utcOffsetMs;
        }

        const kStartSec = Math.floor(kStartMs / 1000);
        const kEndSec = Math.floor(kEndMs / 1000);

        if (kEndSec >= firstTime && kStartSec <= lastTime) {
          zones.push({
            start: Math.max(kStartSec, firstTime),
            end: Math.min(kEndSec, lastTime),
            type,
            label: `${type.charAt(0).toUpperCase() + type.slice(1)} KZ`,
            color: def.killColor,
            isKillZone: true,
          });
        }
      }
    }

    current.setUTCDate(current.getUTCDate() + 1);
  }

  return zones;
}
