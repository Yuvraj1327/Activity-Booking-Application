import * as React from "react";
import { cn } from "@/lib/utils";

export function Alert({
  className,
  variant = "error",
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { variant?: "error" | "info" }) {
  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      className={cn(
        "rounded-md border px-3 py-2 text-sm",
        variant === "error" ? "border-destructive/40 bg-destructive/5" : "border-border bg-muted",
        className,
      )}
      {...props}
    />
  );
}
