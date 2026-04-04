"use client";

import React, { useState } from "react";
import { ChevronDown, Check, Brain, BarChart3, Zap, Globe, LineChart, Eye, Crown, TrendingUp, TrendingDown, Shield } from "lucide-react";

interface AgentAccordionProps {
  agentData: Record<string, any>;
  currentStage: string | null;
}

const AGENTS = [
  { key: "ICT_TRADER", label: "ICT / Smart Money", icon: Brain, color: "text-purple-400", accent: "purple" },
  { key: "ORDERFLOW_TRADER", label: "Order Flow", icon: BarChart3, color: "text-cyan-400", accent: "cyan" },
  { key: "SCALPER", label: "Scalper", icon: Zap, color: "text-green-400", accent: "green" },
  { key: "MACRO_TRADER", label: "Macro", icon: Globe, color: "text-amber-400", accent: "amber" },
  { key: "STRUCTURE_TRADER", label: "Structure", icon: LineChart, color: "text-blue-400", accent: "blue" },
  { key: "WHALE_TRACKER", label: "Whale Tracker", icon: Eye, color: "text-red-400", accent: "red" },
  { key: "HEAD_TRADER", label: "Head Trader", icon: Crown, color: "text-yellow-400", accent: "yellow" },
  { key: "BULL_ADVOCATE", label: "Bull Advocate", icon: TrendingUp, color: "text-lime-400", accent: "lime" },
  { key: "BEAR_ADVOCATE", label: "Bear Advocate", icon: TrendingDown, color: "text-rose-400", accent: "rose" },
  { key: "HEAD_TRADER_FINAL", label: "Final Decision", icon: Crown, color: "text-white", accent: "yellow" },
  { key: "RISK_MANAGER", label: "Risk Manager", icon: Shield, color: "text-orange-400", accent: "orange" },
];

function formatAgentOutput(text: string) {
  if (!text) return null;
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    if (line.startsWith("###") || line.startsWith("##") || line.startsWith("#")) {
      const headerText = line.replace(/^#+\s*/, "");
      elements.push(
        <h4 key={i} className="text-xs font-semibold text-slate-200 mt-3 mb-1 first:mt-0">{headerText}</h4>
      );
    } else if (line.endsWith(":") && line.length < 60 && !line.startsWith("-") && !line.startsWith("*")) {
      elements.push(
        <h5 key={i} className="text-[11px] font-semibold text-slate-300 mt-2 mb-0.5">{line}</h5>
      );
    } else if (line.startsWith("- ") || line.startsWith("* ") || line.match(/^\d+\.\s/)) {
      const bulletText = line.replace(/^[-*]\s+/, "").replace(/^\d+\.\s+/, "");
      elements.push(
        <div key={i} className="flex gap-1.5 text-[11px] text-slate-400 leading-relaxed pl-1">
          <span className="text-slate-600 flex-shrink-0">-</span>
          <span>{bulletText}</span>
        </div>
      );
    } else if (line.startsWith("**") && line.endsWith("**")) {
      elements.push(
        <div key={i} className="text-[11px] font-semibold text-slate-300 mt-1">{line.replace(/\*\*/g, "")}</div>
      );
    } else {
      elements.push(
        <p key={i} className="text-[11px] text-slate-400 leading-relaxed">{line}</p>
      );
    }
  }

  return elements;
}

export function AgentAccordion({ agentData, currentStage }: AgentAccordionProps) {
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  const completedCount = AGENTS.filter(a => agentData[a.key]).length;
  const isRunning = currentStage !== null && completedCount < AGENTS.length;
  const allComplete = completedCount === AGENTS.length && Object.keys(agentData).length > 0;

  return (
    <div className="space-y-1.5">
      {/* Progress header */}
      {(isRunning || allComplete) && (
        <div className="flex items-center gap-3 px-3 py-2 mb-2 rounded-xl bg-white/[0.02] border border-white/[0.04]">
          <div className="flex gap-[3px]">
            {AGENTS.map((a, i) => (
              <div
                key={a.key}
                className={`h-1.5 rounded-full transition-all duration-500 ${
                  allComplete
                    ? "w-6 bg-green-400"
                    : agentData[a.key]
                    ? "w-6 bg-cyan-400"
                    : currentStage === a.key
                    ? "w-8 bg-cyan-400 animate-pulse"
                    : "w-3 bg-slate-700/50"
                }`}
                style={allComplete ? { transitionDelay: `${i * 80}ms` } : {}}
                title={a.label}
              />
            ))}
          </div>
          <span className={`text-[10px] font-semibold transition-colors duration-500 ${
            allComplete ? "text-green-400" : "text-slate-500"
          }`}>
            {allComplete ? "All agents complete" : `${completedCount}/${AGENTS.length} agents`}
          </span>
        </div>
      )}

      {/* Agent rows */}
      {AGENTS.map(agent => {
        const data = agentData[agent.key];
        const isExpanded = expandedAgent === agent.key;
        const isActive = currentStage === agent.key;
        const Icon = agent.icon;

        return (
          <div
            key={agent.key}
            className={`rounded-xl overflow-hidden transition-all duration-300 ${
              isActive && !data
                ? "bg-white/[0.04] border border-cyan-500/15 shadow-[0_0_15px_rgba(6,182,212,0.06)]"
                : data
                ? "bg-white/[0.03] border border-white/[0.06] hover:border-white/[0.1]"
                : "bg-white/[0.015] border border-white/[0.04]"
            }`}
            style={{ backdropFilter: "blur(8px)" }}
          >
            <button
              onClick={() => data && setExpandedAgent(isExpanded ? null : agent.key)}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 transition-colors ${data ? "hover:bg-white/[0.03] cursor-pointer" : ""}`}
            >
              <div className="flex items-center gap-3">
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center transition-all ${
                  isActive && !data ? `bg-${agent.accent}-500/15` :
                  data ? `bg-${agent.accent}-500/10` :
                  "bg-white/[0.03]"
                }`}>
                  <Icon className={`h-3.5 w-3.5 ${data ? agent.color : isActive ? agent.color : "text-slate-600"}`} />
                </div>
                <span className={`text-xs font-semibold tracking-wide ${
                  data ? "text-slate-200" : isActive ? agent.color : "text-slate-500"
                }`}>
                  {agent.label}
                </span>
                {isActive && !data && (
                  <div className="flex gap-1 ml-1">
                    <div className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                    <div className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                    <div className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce" />
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                {data && (
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center bg-${agent.accent}-500/15`}>
                    <Check className={`h-3 w-3 ${agent.color}`} strokeWidth={3} />
                  </div>
                )}
                {data && (
                  <ChevronDown className={`h-3.5 w-3.5 text-slate-600 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`} />
                )}
              </div>
            </button>
            {isExpanded && data && (
              <div className="px-4 pb-3.5 border-t border-white/[0.04] pt-2.5 max-h-[300px] overflow-y-auto animate-in fade-in slide-in-from-top-1 duration-200 space-y-0.5 scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
                {formatAgentOutput(data)}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
