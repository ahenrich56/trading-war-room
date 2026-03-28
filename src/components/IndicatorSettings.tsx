"use client";

import { useState, useRef, useEffect } from "react";
import { Settings, X } from "lucide-react";

interface SettingDef {
  key: string;
  label: string;
  type: "toggle" | "range" | "select";
  value: any;
  options?: { label: string; value: any }[];
  min?: number;
  max?: number;
  step?: number;
}

interface IndicatorSettingsProps {
  indicator: string;
  color: string;
  settings: SettingDef[];
  onChange: (key: string, value: any) => void;
}

export function IndicatorSettings({ indicator, color, settings, onChange }: IndicatorSettingsProps) {
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div className="relative inline-block">
      <button
        onClick={() => setOpen(o => !o)}
        className="p-0.5 rounded hover:bg-white/10 transition-colors"
        style={{ color }}
      >
        <Settings className="h-3 w-3" />
      </button>

      {open && (
        <div
          ref={panelRef}
          className="absolute top-6 right-0 z-[60] w-56 bg-[#0A0A15] border border-white/10 rounded-lg shadow-2xl p-3 space-y-3"
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold tracking-[0.15em] uppercase" style={{ color }}>
              {indicator}
            </span>
            <button onClick={() => setOpen(false)} className="text-slate-500 hover:text-white">
              <X className="h-3 w-3" />
            </button>
          </div>

          {settings.map((s) => (
            <div key={s.key} className="space-y-1">
              <label className="text-[9px] text-slate-400 tracking-wider uppercase block">{s.label}</label>

              {s.type === "toggle" && (
                <button
                  onClick={() => onChange(s.key, !s.value)}
                  className="w-8 h-4 rounded-full transition-colors relative"
                  style={{ backgroundColor: s.value ? color : "#1e293b" }}
                >
                  <div
                    className="w-3 h-3 rounded-full bg-white absolute top-0.5 transition-transform"
                    style={{ transform: s.value ? "translateX(16px)" : "translateX(2px)" }}
                  />
                </button>
              )}

              {s.type === "range" && (
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={s.min || 0}
                    max={s.max || 100}
                    step={s.step || 1}
                    value={s.value}
                    onChange={(e) => onChange(s.key, Number(e.target.value))}
                    className="flex-1 h-1 accent-cyan-500"
                  />
                  <span className="text-[9px] text-slate-400 tabular-nums w-6 text-right">{s.value}</span>
                </div>
              )}

              {s.type === "select" && (
                <select
                  value={s.value}
                  onChange={(e) => onChange(s.key, e.target.value)}
                  className="w-full bg-slate-800 border border-white/10 rounded text-[10px] text-slate-300 px-2 py-1"
                >
                  {s.options?.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
