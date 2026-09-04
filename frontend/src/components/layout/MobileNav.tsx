import { NavLink } from "react-router-dom";

import { NAV_ITEMS } from "@/components/layout/NavItems";
import { cn } from "@/lib/utils";

export function MobileNav() {
  return (
    <nav
      aria-label="Основная навигация"
      className="fixed inset-x-0 bottom-0 z-40 bg-card pb-[env(safe-area-inset-bottom)] shadow-nav lg:hidden"
    >
      <ul className="mx-auto flex max-w-md items-stretch">
        {NAV_ITEMS.map((item) => (
          <li key={item.to} className="flex-1">
            <NavLink
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex h-16 flex-col items-center justify-center gap-1 px-2 text-[11px] transition-colors",
                  isActive
                    ? "font-semibold text-primary"
                    : "font-medium text-muted-foreground hover:text-foreground",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon
                    className={cn("size-[22px]", isActive && "stroke-[2.25]")}
                    aria-hidden
                  />
                  {item.label}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
