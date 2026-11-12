import { LayoutDashboard, type LucideIcon } from "lucide-react";

export type NavItem = { label: string; href: string; icon: LucideIcon };

// Navigation foundation. Admin modules (venues, users, bookings, ...) are added in Stage 8.
export const navItems: NavItem[] = [{ label: "Dashboard", href: "/dashboard", icon: LayoutDashboard }];
