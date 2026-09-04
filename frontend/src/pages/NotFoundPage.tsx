import { ArrowLeft, LayoutDashboard } from "lucide-react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { Wordmark } from "@/components/layout/Wordmark";
import { Button } from "@/components/ui/button";

export default function NotFoundPage() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-app px-4 py-12">
      <Wordmark />

      <div className="mt-8 w-full max-w-[520px] rounded-card bg-card p-5 text-center shadow-card sm:p-8">
        <p className="text-[13px] font-bold uppercase tracking-[0.08em] text-dim">
          Ошибка 404
        </p>
        <p className="mt-2 text-[72px] font-bold leading-none tracking-[-0.035em] tabular-nums sm:text-[96px]">
          404
        </p>
        <h1 className="mt-5 text-[22px] font-bold tracking-[-0.02em]">Такой страницы нет</h1>
        <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">
          По адресу{" "}
          <span className="break-all font-semibold text-foreground">{location.pathname}</span>{" "}
          ничего не найдено. Возможно, ссылка устарела или группа, на которую она вела,
          удалена.
        </p>
        <div className="mt-7 flex flex-col gap-2.5 sm:flex-row sm:justify-center">
          <Button asChild size="lg">
            <Link to="/">
              <LayoutDashboard aria-hidden="true" />
              На главную
            </Link>
          </Button>
          <Button variant="secondary" size="lg" onClick={() => navigate(-1)}>
            <ArrowLeft aria-hidden="true" />
            Назад
          </Button>
        </div>
      </div>
    </div>
  );
}
