import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const variants = cva("inline-flex items-center justify-center gap-2 rounded-xl text-sm font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] disabled:pointer-events-none disabled:opacity-50", {
  variants: {
    variant: { primary: "bg-[var(--ink)] text-white hover:bg-black", ghost: "hover:bg-black/5", outline: "border border-[var(--line)] bg-white hover:border-[var(--ink)]" },
    size: { default: "h-11 px-5", icon: "size-11", sm: "h-9 px-3" },
  }, defaultVariants: { variant: "primary", size: "default" },
});

export function Button({ className, variant, size, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof variants>) {
  return <button className={cn(variants({ variant, size }), className)} {...props} />;
}
