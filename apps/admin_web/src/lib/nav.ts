import {
  Activity, BadgeCheck, BarChart3, Bell, BookOpen, CalendarCheck, CreditCard, Flag, Gavel, Banknote, KeyRound,
  Landmark, LayoutDashboard, LifeBuoy, MapPin, Scale, ScrollText, Settings, Store, Tags, Ticket, ToggleRight, Undo2, Users,
  type LucideIcon,
} from "lucide-react";

/** `perm`: the backend permission that unlocks the page. Items the admin cannot use are hidden (the API enforces it anyway). */
export type NavItem = { label: string; href: string; icon: LucideIcon; perm?: string };
export type NavGroup = { title: string; items: NavItem[] };

export const navGroups: NavGroup[] = [
  { title: "Overview", items: [
    { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard, perm: "dashboard.view" },
    { label: "Analytics", href: "/analytics", icon: BarChart3, perm: "analytics.view" },
  ] },
  { title: "People", items: [
    { label: "Owners", href: "/owners", icon: Store, perm: "owners.view" },
    { label: "Owner KYC", href: "/kyc", icon: BadgeCheck, perm: "kyc.review" },
    { label: "Customers", href: "/customers", icon: Users, perm: "customers.view" },
  ] },
  { title: "Marketplace", items: [
    { label: "Venues", href: "/venues", icon: MapPin, perm: "venues.view" },
    { label: "Venue reports", href: "/venue-reports", icon: Flag, perm: "venues.view" },
    { label: "Bookings", href: "/bookings", icon: CalendarCheck, perm: "bookings.view" },
    { label: "Disputes", href: "/disputes", icon: Gavel, perm: "disputes.manage" },
  ] },
  { title: "Finance", items: [
    { label: "Payments", href: "/payments", icon: CreditCard, perm: "payments.view" },
    { label: "Refunds", href: "/refunds", icon: Undo2, perm: "payments.view" },
    { label: "Finance", href: "/finance", icon: Landmark, perm: "finance.view" },
    { label: "Owner payouts", href: "/payouts", icon: Banknote, perm: "finance.view" },
    { label: "Reconciliation", href: "/finance/reconciliation", icon: Scale, perm: "finance.view" },
  ] },
  { title: "Support & content", items: [
    { label: "Support tickets", href: "/support", icon: LifeBuoy, perm: "support.manage" },
    { label: "Sports", href: "/categories", icon: Tags, perm: "categories.manage" },
    { label: "Coupons", href: "/coupons", icon: Ticket, perm: "coupons.manage" },
    { label: "Content (CMS)", href: "/cms", icon: BookOpen, perm: "cms.manage" },
  ] },
  { title: "Platform", items: [
    { label: "Notifications", href: "/notifications", icon: Bell },
    { label: "Audit log", href: "/audit", icon: ScrollText, perm: "audit.view" },
    { label: "Admin roles", href: "/roles", icon: KeyRound, perm: "roles.manage" },
    { label: "Platform switches", href: "/platform", icon: ToggleRight, perm: "settings.manage" },
    { label: "System monitoring", href: "/monitoring", icon: Activity, perm: "monitoring.view" },
  ] },
];
export const navItems: NavItem[] = navGroups.flatMap((g) => g.items);

/** Groups with only the entries this admin may open (empty groups disappear). */
export function visibleGroups(permissions: string[]): NavGroup[] {
  if (permissions.length === 0) return []; // no role / empty role: nothing is offered
  return navGroups
    .map((g) => ({ ...g, items: g.items.filter((i) => !i.perm || permissions.includes(i.perm)) }))
    .filter((g) => g.items.length > 0);
}

/** Pinned to the bottom of the sidebar. */
export const settingsItem: NavItem = { label: "Settings", href: "/settings", icon: Settings };
