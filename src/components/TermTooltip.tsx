import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface TermTooltipProps {
  term: string;
  description: string;
  children: React.ReactNode;
}

export function TermTooltip({ term, description, children }: TermTooltipProps) {
  return (
    <TooltipProvider>
      <Tooltip delayDuration={300}>
        <TooltipTrigger asChild>
          <span className="cursor-help underline decoration-dashed decoration-white/30 hover:decoration-cyan-400">
            {children}
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-[250px] bg-slate-900 border-white/20 text-slate-200">
          <p className="font-bold text-cyan-400 text-xs mb-1">{term}</p>
          <p className="text-xs">{description}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
