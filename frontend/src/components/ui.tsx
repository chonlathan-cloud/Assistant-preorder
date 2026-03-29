import { cn } from "@/lib/utils";
import React from "react";

export function Input({ className, type, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-md border border-neutral-800 bg-[#0A0A0A] px-3 py-2 text-sm text-neutral-100 ring-offset-neutral-950 file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-neutral-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 disabled:cursor-not-allowed disabled:opacity-50 transition-colors",
        className
      )}
      {...props}
    />
  );
}

export function Button({
  className,
  variant = "primary",
  size = "default",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { 
  variant?: "primary" | "secondary" | "danger" | "ghost";
  size?: "default" | "sm" | "lg";
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-md font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
        {
          "h-10 px-4 py-2 text-sm": size === "default",
          "h-8 px-3 text-xs": size === "sm",
          "h-12 px-8 text-base": size === "lg",
        },
        {
          "bg-cyan-500 text-black hover:bg-cyan-400 font-bold tracking-wider": variant === "primary",
          "bg-emerald-500 text-black hover:bg-emerald-400 font-bold tracking-wider": variant === "secondary",
          "bg-rose-500 text-white hover:bg-rose-600 font-bold tracking-wider": variant === "danger",
          "bg-transparent text-neutral-300 hover:text-white hover:bg-neutral-800": variant === "ghost",
        },
        className
      )}
      {...props}
    />
  );
}

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-xl border border-neutral-800 bg-[#111] text-neutral-100 shadow-sm", className)}
      {...props}
    />
  );
}
