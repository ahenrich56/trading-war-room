"use client";

import React from "react";

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  intensity?: "subtle" | "medium" | "strong";
  glow?: "none" | "cyan" | "green" | "red" | "amber";
}

const glowColors = {
  none: "",
  cyan: "shadow-[0_0_30px_rgba(6,182,212,0.08)]",
  green: "shadow-[0_0_30px_rgba(34,197,94,0.08)]",
  red: "shadow-[0_0_30px_rgba(239,68,68,0.08)]",
  amber: "shadow-[0_0_30px_rgba(245,158,11,0.08)]",
};

const intensityMap = {
  subtle: { bg: "rgba(255,255,255,0.03)", blur: "8px", border: "rgba(255,255,255,0.06)" },
  medium: { bg: "rgba(255,255,255,0.05)", blur: "12px", border: "rgba(255,255,255,0.10)" },
  strong: { bg: "rgba(255,255,255,0.08)", blur: "20px", border: "rgba(255,255,255,0.14)" },
};

export const GlassCard: React.FC<GlassCardProps> = ({
  children,
  className = "",
  style = {},
  intensity = "medium",
  glow = "none",
}) => {
  const config = intensityMap[intensity];

  return (
    <div
      className={`relative overflow-hidden rounded-2xl ${glowColors[glow]} ${className}`}
      style={{
        background: config.bg,
        backdropFilter: `blur(${config.blur})`,
        WebkitBackdropFilter: `blur(${config.blur})`,
        border: `1px solid ${config.border}`,
        ...style,
      }}
    >
      {/* Inner highlight — top edge catch light */}
      <div
        className="absolute inset-x-0 top-0 h-px z-10"
        style={{
          background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent)",
        }}
      />
      {/* Content */}
      <div className="relative z-20">{children}</div>
    </div>
  );
};

export const GlassPanel: React.FC<GlassCardProps> = ({
  children,
  className = "",
  style = {},
  intensity = "subtle",
  glow = "none",
}) => {
  const config = intensityMap[intensity];

  return (
    <div
      className={`relative overflow-hidden rounded-xl ${glowColors[glow]} ${className}`}
      style={{
        background: config.bg,
        backdropFilter: `blur(${config.blur})`,
        WebkitBackdropFilter: `blur(${config.blur})`,
        border: `1px solid ${config.border}`,
        ...style,
      }}
    >
      <div className="relative z-20">{children}</div>
    </div>
  );
};

// SVG Filter for advanced glass distortion (optional, mount once in layout)
export const GlassFilter: React.FC = () => (
  <svg style={{ display: "none" }} aria-hidden="true">
    <filter
      id="glass-distortion"
      x="0%"
      y="0%"
      width="100%"
      height="100%"
      filterUnits="objectBoundingBox"
    >
      <feTurbulence
        type="fractalNoise"
        baseFrequency="0.001 0.005"
        numOctaves="1"
        seed="17"
        result="turbulence"
      />
      <feGaussianBlur in="turbulence" stdDeviation="3" result="softMap" />
      <feSpecularLighting
        in="softMap"
        surfaceScale="3"
        specularConstant="0.8"
        specularExponent="80"
        lightingColor="white"
        result="specLight"
      >
        <fePointLight x="-200" y="-200" z="300" />
      </feSpecularLighting>
    </filter>
  </svg>
);
