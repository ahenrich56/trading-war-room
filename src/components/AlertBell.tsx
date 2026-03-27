"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Bell, Volume2, VolumeX, X } from "lucide-react";

interface Alert {
  id: number;
  type: string;
  ticker: string;
  data: any;
  read: boolean;
  created_at: string;
}

interface AlertBellProps {
  onTickerSelect?: (ticker: string) => void;
}

// Generate a subtle ping sound via Web Audio API
function playAlertSound() {
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(440, ctx.currentTime + 0.15);
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.3);
    setTimeout(() => ctx.close(), 500);
  } catch (_) {}
}

export function AlertBell({ onTickerSelect }: AlertBellProps) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [soundOn, setSoundOn] = useState(true);
  const prevUnreadRef = useRef(0);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const fetchAlerts = useCallback(async () => {
    try {
      const res = await fetch("/api/alerts");
      const data = await res.json();
      setAlerts(data.alerts || []);
      const newUnread = data.unread || 0;

      // Play sound if new unread alerts appeared
      if (soundOn && newUnread > prevUnreadRef.current && prevUnreadRef.current >= 0) {
        playAlertSound();
      }
      prevUnreadRef.current = newUnread;
      setUnread(newUnread);
    } catch (_) {}
  }, [soundOn]);

  // Poll alerts every 30 seconds
  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 30000);
    return () => clearInterval(interval);
  }, [fetchAlerts]);

  // Close dropdown on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const markRead = async () => {
    try {
      await fetch("/api/alerts", { method: "POST" });
      setUnread(0);
      prevUnreadRef.current = 0;
      setAlerts((prev) => prev.map((a) => ({ ...a, read: true })));
    } catch (_) {}
  };

  const handleAlertClick = (alert: Alert) => {
    if (onTickerSelect) onTickerSelect(alert.ticker);
    setOpen(false);
  };

  const directionColor = (dir: string) =>
    dir === "LONG" ? "text-green-400" : dir === "SHORT" ? "text-red-400" : "text-slate-400";

  const gradeColor = (grade: string) => {
    if (grade.startsWith("A")) return "text-green-400";
    if (grade.startsWith("B")) return "text-cyan-400";
    return "text-slate-400";
  };

  const timeAgo = (ts: string) => {
    const diff = (Date.now() - new Date(ts + "Z").getTime()) / 1000;
    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => { setOpen(!open); if (!open && unread > 0) markRead(); }}
        className="relative p-1.5 rounded-lg hover:bg-white/5 transition-colors"
      >
        <Bell className={`w-4 h-4 ${unread > 0 ? "text-amber-400" : "text-slate-500"}`} />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-[#0d1117] border border-white/10 rounded-xl shadow-2xl z-50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-white/5">
            <span className="text-xs font-bold text-slate-300">Alerts</span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setSoundOn(!soundOn)}
                className="p-1 rounded hover:bg-white/5"
                title={soundOn ? "Mute alerts" : "Unmute alerts"}
              >
                {soundOn
                  ? <Volume2 className="w-3 h-3 text-slate-500" />
                  : <VolumeX className="w-3 h-3 text-red-400" />
                }
              </button>
              <button onClick={() => setOpen(false)} className="p-1 rounded hover:bg-white/5">
                <X className="w-3 h-3 text-slate-500" />
              </button>
            </div>
          </div>

          {/* Alert list */}
          <div className="max-h-72 overflow-y-auto">
            {alerts.length === 0 ? (
              <div className="px-3 py-6 text-center text-slate-600 text-xs">
                No alerts yet. Scanner checks every 5 min.
              </div>
            ) : (
              alerts.slice(0, 20).map((alert) => (
                <button
                  key={alert.id}
                  onClick={() => handleAlertClick(alert)}
                  className={`w-full text-left px-3 py-2 hover:bg-white/5 transition-colors border-b border-white/[0.03] ${
                    !alert.read ? "bg-white/[0.02]" : ""
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {!alert.read && <span className="w-1.5 h-1.5 bg-amber-400 rounded-full flex-shrink-0" />}
                      <span className="text-xs font-bold text-white">{alert.ticker}</span>
                      <span className={`text-[10px] font-bold ${directionColor(alert.data.direction)}`}>
                        {alert.data.direction}
                      </span>
                      <span className={`text-[10px] font-bold ${gradeColor(alert.data.grade)}`}>
                        {alert.data.grade}
                      </span>
                    </div>
                    <span className="text-[9px] text-slate-600">{timeAgo(alert.created_at)}</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5 pl-3.5">
                    Score {alert.data.score}% @ ${alert.data.price}
                    {alert.data.vol_ratio > 1.5 ? ` | Vol ${alert.data.vol_ratio}x` : ""}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
