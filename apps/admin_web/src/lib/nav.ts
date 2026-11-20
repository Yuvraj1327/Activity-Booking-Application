import {
  BarChart3, Bell, CalendarCheck, CreditCard, LayoutDashboard, MapPin, ScrollText, Settings, Store, Users,
  type LucideIcon,
} from "lucide-react";

export type NavItem = { label: string; href: string; icon: LucideIcon };
export type NavGroup = { title: string; items: NavItem[] };

export const navGroups: NavGroup[] = [
  { title: "Overview", items: [
    { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
    { label: "Analytics", href: "/analytics", icon: BarChart3 },
  ] },
  { title: "People", items: [
    { label: "Owners", href: "/owners", icon: Store },
    { label: "Customers", href: "/customers", icon: Users },
  ] },
  { title: "Marketplace", items: [
    { label: "Venues", href: "/venues", icon: MapPin },
    { label: "Bookings", href: "/bookings", icon: CalendarCheck },
    { label: "Payments", href: "/payments", icon: CreditCard },
  ] },
  { title: "Platform", items: [
    { label: "Notifications", href: "/notifications", icon: Bell },
    { label: "Audit log", href: "/audit", icon: ScrollText },
  ] },
];
export const navItems: NavItem[] = navGroups.flatMap((g) => g.items);

/** Pinned to the bottom of the sidebar. */
export const settingsItem: NavItem = { label: "Settings", href: "/settings", icon: Settings };
