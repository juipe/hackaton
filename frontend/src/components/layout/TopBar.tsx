import { UserMenu } from "@/components/layout/UserMenu";
import { Wordmark } from "@/components/layout/Wordmark";

/** Только для экранов уже `lg`: на десктопе всё живёт в сайдбаре. */
export function TopBar() {
  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 bg-app/90 px-4 backdrop-blur supports-[backdrop-filter]:bg-app/75 lg:hidden">
      <Wordmark size="sm" />
      <UserMenu />
    </header>
  );
}
