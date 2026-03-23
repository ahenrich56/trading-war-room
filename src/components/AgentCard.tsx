"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export function AgentCard({ title, data, accent = "white" }: { title: string, data?: string, accent?: string }) {
  const isComplete = !!data;
  
  return (
    <Card className="bg-black/30 border-white/10 backdrop-blur-md transition-all duration-500 overflow-hidden h-full flex flex-col">
      <CardHeader className="border-b border-white/5 pb-2 bg-gradient-to-b from-white/[0.02] to-transparent">
        <CardTitle className={`text-sm tracking-wider flex justify-between items-center ${accent === "cyan" ? "text-cyan-400" : "text-slate-300"}`}>
          <span>[{title}]</span>
          {isComplete && <Badge variant="secondary" className="bg-white/10 text-white hover:bg-white/20 px-1 py-0 text-[10px] animate-in fade-in">DONE</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-4 text-xs leading-relaxed text-slate-400 flex-grow">
        {data ? (
          <div className="animate-in fade-in slide-in-from-top-2">{data}</div>
        ) : (
          <div className="flex space-x-1 items-center opacity-50">
            <div className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
            <div className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
            <div className="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce"></div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
