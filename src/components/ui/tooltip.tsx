import * as React from "react"
import { cn } from "@/lib/utils"

const TooltipProvider = ({ children }: { children: React.ReactNode }) => {
  return <>{children}</>
}

const Tooltip = ({ children, delayDuration }: { children: React.ReactNode, delayDuration?: number }) => {
  return <div className="group relative inline-block">{children}</div>
}

const TooltipTrigger = React.forwardRef<
  HTMLSpanElement,
  React.HTMLAttributes<HTMLSpanElement> & { asChild?: boolean }
>(({ className, asChild, children, ...props }, ref) => {
  // Mocking the trigger. Since asChild usually means we don't render a wrapper,
  // we'll just render a span here so events pass through nicely.
  return (
    <span ref={ref} className={cn("inline-block cursor-help", className)} {...props}>
      {children}
    </span>
  )
})
TooltipTrigger.displayName = "TooltipTrigger"

const TooltipContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "absolute left-1/2 -translate-x-1/2 bottom-full mb-2 hidden group-hover:block z-50 w-max max-w-xs overflow-hidden rounded-md border border-white/10 bg-slate-900 px-3 py-2 text-sm text-slate-200 shadow-md",
      className
    )}
    {...props}
  >
    {children}
  </div>
))
TooltipContent.displayName = "TooltipContent"

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }
