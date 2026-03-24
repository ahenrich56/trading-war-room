import React from 'react';

export const Switch = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement> & { onCheckedChange?: (checked: boolean) => void }>(
  ({ className, onCheckedChange, ...props }, ref) => {
    return (
      <input
        type="checkbox"
        className={`form-checkbox h-5 w-5 text-cyan-600 bg-slate-800 border-slate-700 rounded focus:ring-cyan-500 focus:ring-2 cursor-pointer ${className || ''}`}
        ref={ref}
        onChange={(e) => onCheckedChange?.(e.target.checked)}
        {...props}
      />
    );
  }
);
Switch.displayName = "Switch";
