"use client";

import React, { useState } from "react";
import { ChevronDown, Check, Brain, BarChart3, Zap, Globe, LineChart, Eye, Crown, TrendingUp, TrendingDown, Shield } from "lucide-react";

interface AgentAccordionProps {
  agentData: Record<string, any>;
  currentStage: string | null;
}

const AGENTS = [
  { key: "ICT_TRADER", label: "ICT / Smart Money", icon: Brain, color: "text-purple-400", accent: "bg-purple-500" },
  { key: "ORDERFLOW_TRADER", label: "Order Flow", icon: BarChart3, color: "text-cyan-400", accent: "bg-cyan-500" },
  { key: "SCALPER", label: "Scalper", icon: Zap, color: "text-green-400", accent: "bg-green-500" },
  { key: "MACRO_TRADER", label: "Macro", icon: Globe, color: "text-amber-400", accent: "bg-amber-500" },
  { key: "STRUCTURE_TRADER", label: "Structure", icon: LineChart, color: "text-blue-400", accent: "bg-blue-500" },
  { key: "WHALE_TRACKER", label: "Whale Tracker", icon: Eye, color: "text-red-400", accent: "bg-red-500" },
  { key: "HEAD_TRADER", label: "Head Trader", icon: Crown, color: "text-yellow-400", accent: "bg-yellow-500" },
  { key: "BULL_ADVOCATE", label: "Bull Advocate", icon: TrendingUp, color: "text-lime-400", accent: "bg-lime-500" },
  { key: "BEAR_ADVOCATE", label: "Bear Advocate", icon: TrendingDown, color: "text-rose-400", accent: "bg-rose-500" },
  { key: "HEAD_TRADER_FINAL", label: "Final Decision", icon: Crown, color: "text-white", accent: "bg-yellow-600" },
  { key: "RISK_MANAGER", label: "Risk Manager", icon: Shield, color: "text-orange-400", accent: "bg-orange-500" },
];

function formatAgentOutput(text: string) {
  if (!text) return null;
  const lines = text.split("\n");
  const elements: React.ReactNode[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    // Section headers (### or lines ending with :)
    if (line.startsWith("###") || line.startsWith("##") || line.startsWith("#")) {
      const headerText = line.replace(/^#+\s*/, "");
      elements.push(
        <h4 key={i} className="text-xs font-semibold text-slate-200 mt-3 mb-1 first:mt-0">{headerText}</h4>
      );
    } else if (line.endsWith(":") && line.length < 60 && !line.startsWith("-") && !line.startsWith("*")) {
      elements.push(
        <h5 key={i} className="text-[11px] font-semibold text-slate-300 mt-2 mb-0.5">{line}</h5>
      );
    }
    // Bullet items
    else if (line.startsWith("- ") || line.startsWith("* ") || line.match(/^\d+\.\s/)) {
      const bulletText = line.replace(/^[-*]\s+/, "").replace(/^\d+\.\s+/, "");
      elements.push(
        <div key={i} className="flex gap-1.5 text-[11px] text-slate-400 leading-relaxed pl-1">
          <span className="text-slate-600 flex-shrink-0">-</span>
          <span>{bulletText}</span>
        </div>
      );
    }
    // Bold text markers
    else if (line.startsWith("**") && line.endsWith("**")) {
      elements.push(
        <div key={i} className="text-[11px] font-semibold text-slate-300 mt-1">{line.replace(/\*\*/g, "")}</div>
      );
    }
    // Regular paragraph
    else {
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
        <div className="flex items-center gap-2.5 px-2 py-1.5 mb-1">
          <div className="flex gap-1">
            {AGENTS.map((a, i) => (
              <div
                key={a.key}
                className={`w-2.5 h-2.5 rounded-full transition-all duration-500 ${
                  allComplete
                    ? "bg-green-400"
                    : agentData[a.key]
                    ? "bg-cyan-400"
                    : currentStage === a.key
                    ? "bg-cyan-400 animate-pulse"
                    : "bg-slate-700"
                }`}
                style={allComplete ? { transitionDelay: `${i * 80}ms` } : {}}
                title={a.label}
              />
            ))}
          </div>
          <span className={`text-[10px] font-medium transition-colors duration-500 ${
            allComplete ? "text-green-400" : "text-slate-500"
          }`}>
            {allComplete ? "All complete" : `${completedCount}/${AGENTS.length} agents`}
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
          <div key={agent.key} className="border border-white/8 rounded-xl bg-white/[0.03] backdrop-blur-md overflow-hidden shadow-sm shadow-black/10">
            <button
              onClick={() => setExpandedAgent(isExpanded ? null : agent.key)}
              className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-2.5">
                <Icon className={`h-3.5 w-3.5 ${data ? agent.color : isActive ? agent.color : "text-slate-600"}`} />
                <span className={`text-xs font-semibold tracking-wide ${
                  data ? "text-slate-200" : isActive ? agent.color : "text-slate-500"
                }`}>
                  {agent.label}
                </span>
                {isActive && !data && (
                  <div className="flex gap-0.5 ml-1">
                    <div className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                    <div className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                    <div className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce" />
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                {data && (
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center ${agent.accent}/20`}>
                    <Check className={`h-3 w-3 ${agent.color}`} strokeWidth={3} />
                  </div>
                )}
                {data && (
                  <ChevronDown className={`h-3 w-3 text-slate-600 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                )}
              </div>
            </button>
            {isExpanded && data && (
              <div className="px-3 pb-3 border-t border-white/5 pt-2 max-h-[300px] overflow-y-auto animate-in fade-in slide-in-from-top-1 duration-200 space-y-0.5">
                {formatAgentOutput(data)}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
