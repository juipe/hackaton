import { LayoutDashboard, UserRound, Users, type LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Dashboard lives at "/", so it only matches when the path is exactly "/". */
  end?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Главная", icon: LayoutDashboard, end: true },
  { to: "/groups", label: "Группы", icon: Users },
  { to: "/profile", label: "Профиль", icon: UserRound },
];
