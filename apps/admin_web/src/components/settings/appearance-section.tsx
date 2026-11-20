"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useTheme, type Theme } from "@/lib/theme";
import { cn } from "@/lib/utils";

const OPTIONS: { value: Theme; label: string; hint: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", hint: "Always use the light theme", icon: Sun },
  { value: "dark", label: "Dark", hint: "Always use the dark theme", icon: Moon },
  { value: "system", label: "System", hint: "Match your device setting", icon: Monitor },
];

export function AppearanceSection() {
  const { theme, resolved, setTheme } = useTheme();
  return (
    <Card>
      <CardHeader>
        <CardTitle>Appearance</CardTitle>
        <CardDescription>
          Choose how the admin console looks. Your choice is saved in this browser and applies to every page, including sign-in.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div role="radiogroup" aria-label="Theme" className="grid gap-3 sm:grid-cols-3">
          {OPTIONS.map(({ value, label, hint, icon: Icon }) => {
            const selected = theme === value;
            return (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setTheme(value)}
                className={cn(
                  "flex flex-col items-start gap-2 rounded-lg border p-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
                  selected ? "border-primary bg-primary-tint" : "border-border hover:bg-muted",
                )}
              >
                <Icon className={cn("size-5", selected ? "text-primary" : "text-muted-foreground")} aria-hidden />
                <span className="text-sm font-medium">{label}</span>
                <span className="text-xs text-muted-foreground">{hint}</span>
              </button>
            );
          })}
        </div>
        <p className="mt-4 text-xs text-muted-foreground">Currently showing the {resolved} theme.</p>
      </CardContent>
    </Card>
  );
}
