"use client";

interface OverlayToggle {
  id: string;
  label: string;
  color: string;
  active: boolean;
  onToggle: () => void;
}

export function ChartOverlayToggles({ toggles }: { toggles: OverlayToggle[] }) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {toggles.map((t) => (
        <button
          key={t.id}
          onClick={t.onToggle}
          className="px-2 py-0.5 rounded text-[10px] font-medium tracking-wide transition-all duration-150 border"
          style={{
            borderColor: t.active ? t.color : "rgba(255,255,255,0.08)",
            backgroundColor: t.active ? `${t.color}15` : "transparent",
            color: t.active ? t.color : "#64748b",
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
