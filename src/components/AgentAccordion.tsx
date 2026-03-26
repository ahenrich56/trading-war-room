"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { ChevronDown } from "lucide-react";

interface AgentAccordionProps {
  agentData: Record<string, any>;
  currentStage: string | null;
}

const AGENTS = [
  { key: "FUNDAMENTAL_ANALYST", label: "FUNDAMENTAL", color: "text-slate-300" },
  { key: "SENTIMENT_ANALYST", label: "SENTIMENT", color: "text-slate-300" },
  { key: "NEWS_ANALYST", label: "NEWS", color: "text-slate-300" },
  { key: "TECHNICAL_ANALYST", label: "TECHNICAL", color: "text-slate-300" },
  { key: "BEAR_RESEARCHER", label: "BEAR", color: "text-red-400" },
  { key: "BULL_RESEARCHER", label: "BULL", color: "text-green-400" },
  { key: "TRADER_DECISION", label: "TRADER", color: "text-cyan-400" },
  { key: "RISK_MANAGER", label: "RISK MGR", color: "text-cyan-400" },
];

export function AgentAccordion({ agentData, currentStage }: AgentAccordionProps) {
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  const completedCount = AGENTS.filter(a => agentData[a.key]).length;
  const isRunning = currentStage !== null && completedCount < AGENTS.length;

  return (
    <div className="space-y-1">
      {/* Progress header when running */}
      {isRunning && (
        <div className="flex items-center gap-2 px-2 py-1.5 mb-1">
          <div className="flex gap-1">
            {AGENTS.map(a => (
              <div
                key={a.key}
                className={`w-2 h-2 rounded-full transition-all duration-300 ${
                  agentData[a.key] ? "bg-cyan-400" :
                  currentStage === a.key ? "bg-cyan-400 animate-pulse" :
                  "bg-slate-700"
                }`}
                title={a.label}
              />
            ))}
          </div>
          <span className="text-[10px] text-slate-500">{completedCount}/{AGENTS.length} agents</span>
        </div>
      )}

      {/* Agent rows */}
      {AGENTS.map(agent => {
        const data = agentData[agent.key];
        const isExpanded = expandedAgent === agent.key;
        const isActive = currentStage === agent.key;

        return (
          <div key={agent.key} className="border border-white/5 rounded bg-black/30 overflow-hidden">
            <button
              onClick={() => setExpandedAgent(isExpanded ? null : agent.key)}
              className="w-full flex items-center justify-between px-3 py-2 hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-2">
                <span className={`text-[10px] font-bold tracking-widest ${agent.color}`}>
                  {agent.label}
                </span>
                {isActive && !data && (
                  <div className="flex gap-0.5">
                    <div className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                    <div className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                    <div className="w-1 h-1 bg-cyan-400 rounded-full animate-bounce" />
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                {data && (
                  <Badge variant="outline" className="text-[9px] px-1.5 py-0 text-slate-400 border-white/10 bg-white/5">
                    DONE
                  </Badge>
                )}
                {data && (
                  <ChevronDown className={`h-3 w-3 text-slate-600 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
                )}
              </div>
            </button>
            {isExpanded && data && (
              <div className="px-3 pb-3 text-xs leading-relaxed text-slate-400 border-t border-white/5 pt-2 max-h-[300px] overflow-y-auto animate-in fade-in slide-in-from-top-1 duration-200">
                {data}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
