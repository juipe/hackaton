import { zodResolver } from "@hookform/resolvers/zod";
import {
  AlertCircle,
  ArrowLeftRight,
  Eye,
  EyeOff,
  Loader2,
  PieChart,
  Receipt,
  Wallet,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { Wordmark } from "@/components/layout/Wordmark";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/useAuth";
import { errorMessage } from "@/lib/api";
import { APP_TAGLINE, DEMO_ACCOUNTS, DEMO_PASSWORD } from "@/lib/constants";
import { avatarTone, cn, initials } from "@/lib/utils";

const loginSchema = z.object({
  email: z
    .string()
    .min(1, "Введите адрес электронной почты")
    .email("Похоже, это не адрес электронной почты"),
  password: z.string().min(8, "В пароле не меньше 8 символов"),
});

type LoginValues = z.infer<typeof loginSchema>;

/**
 * `?next=` comes from the URL, so it is attacker-controlled. Only a plain
 * same-origin path is safe to navigate to — `//host` and `/\host` are both read
 * as protocol-relative URLs by browsers and would turn this into an open redirect.
 */
function resolveNextPath(search: string): string {
  const raw = new URLSearchParams(search).get("next");
  if (!raw) return "/";
  if (!raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return "/";
  return raw;
}

const FEATURES = [
  {
    icon: Receipt,
    title: "Четыре способа поделить расход",
    body: "Поровну, точными суммами, процентами или долями — копейки всегда сходятся с общей суммой.",
  },
  {
    icon: ArrowLeftRight,
    title: "Видно, кто кому должен",
    body: "Каждая пара участников сводится к одной строке, и пересчитывать вручную не нужно.",
  },
  {
    icon: Wallet,
    title: "Рассчитаться — одно действие",
    body: "Запишите перевод, и балансы сойдутся. Упрощение долгов превращает четыре перевода в два, ничей итог при этом не меняется.",
  },
  {
    icon: PieChart,
    title: "Понятно, куда ушли деньги",
    body: "Расходы по категориям и по месяцам — в одной группе или сразу во всех.",
  },
];

export default function LoginPage() {
  const { user, isLoading, login } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const submitRef = useRef<HTMLButtonElement>(null);

  const nextPath = useMemo(() => resolveNextPath(location.search), [location.search]);
  const registerHref =
    nextPath === "/" ? "/register" : `/register?next=${encodeURIComponent(nextPath)}`;

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });
  const {
    register,
    handleSubmit,
    setValue,
    clearErrors,
    formState: { errors, isSubmitting },
  } = form;

  const onSubmit = handleSubmit(async (values) => {
    try {
      const signedIn = await login({ email: values.email.trim(), password: values.password });
      toast.success(`С возвращением, ${signedIn.name}`);
      navigate(nextPath, { replace: true });
    } catch (error) {
      const message = errorMessage(error);
      form.setError("root", { message });
      toast.error(message);
    }
  });

  // The demo panel sits below the form, so move focus to the submit button:
  // it scrolls the filled fields back into view and Enter then signs in.
  function fillDemoAccount(email: string) {
    setValue("email", email, { shouldValidate: true, shouldDirty: true });
    setValue("password", DEMO_PASSWORD, { shouldValidate: true, shouldDirty: true });
    clearErrors("root");
    submitRef.current?.focus();
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-app">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
        <span className="sr-only">Проверяем вашу сессию</span>
      </div>
    );
  }

  if (user) return <Navigate to={nextPath} replace />;

  return (
    <div className="min-h-screen bg-app">
      <main className="mx-auto flex w-full max-w-[1120px] flex-col items-center gap-10 px-4 py-8 sm:px-6 sm:py-12 lg:min-h-screen lg:flex-row lg:items-center lg:justify-center lg:gap-16 lg:py-16">
        <div className="flex w-full max-w-[440px] shrink-0 flex-col gap-4">
          <div className="flex flex-col gap-2 lg:hidden">
            <Wordmark />
            <p className="text-[15px] text-muted-foreground">{APP_TAGLINE}</p>
          </div>

          <div className="rounded-card bg-card p-5 shadow-card sm:p-8">
            <h1 className="text-[26px] font-bold tracking-[-0.02em]">Вход</h1>
            <p className="mt-1.5 text-[15px] text-muted-foreground">
              Продолжайте с того места, где остановились.
            </p>

            <form onSubmit={onSubmit} noValidate className="mt-6 flex flex-col gap-[18px]">
              {errors.root?.message ? (
                <Alert variant="destructive">
                  <AlertCircle aria-hidden="true" />
                  <AlertDescription>{errors.root.message}</AlertDescription>
                </Alert>
              ) : null}

              <div className="flex flex-col gap-2">
                <Label htmlFor="email">Электронная почта</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="pochta@example.ru"
                  aria-invalid={errors.email ? true : undefined}
                  aria-describedby={errors.email ? "email-error" : undefined}
                  {...register("email")}
                />
                {errors.email ? (
                  <p id="email-error" className="text-[13px] text-destructive">
                    {errors.email.message}
                  </p>
                ) : null}
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="password">Пароль</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    className="pr-[52px]"
                    aria-invalid={errors.password ? true : undefined}
                    aria-describedby={errors.password ? "password-error" : undefined}
                    {...register("password")}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((visible) => !visible)}
                    className="absolute inset-y-0 right-0 flex w-[52px] items-center justify-center rounded-r-field text-dim transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card"
                  >
                    {showPassword ? (
                      <EyeOff className="size-[18px]" aria-hidden="true" />
                    ) : (
                      <Eye className="size-[18px]" aria-hidden="true" />
                    )}
                    <span className="sr-only">
                      {showPassword ? "Скрыть пароль" : "Показать пароль"}
                    </span>
                  </button>
                </div>
                {errors.password ? (
                  <p id="password-error" className="text-[13px] text-destructive">
                    {errors.password.message}
                  </p>
                ) : null}
              </div>

              <Button
                ref={submitRef}
                type="submit"
                size="lg"
                className="mt-1 w-full"
                disabled={isSubmitting}
              >
                {isSubmitting ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
                {isSubmitting ? "Входим…" : "Войти"}
              </Button>
            </form>

            <p className="mt-5 text-center text-sm text-muted-foreground">
              Впервые в Складчине?{" "}
              <Link
                to={registerHref}
                className="font-semibold text-accent-foreground hover:underline"
              >
                Создать аккаунт
              </Link>
            </p>
          </div>

          <section
            aria-labelledby="demo-accounts-title"
            className="rounded-card bg-card p-5 shadow-card sm:p-7"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <h2 id="demo-accounts-title" className="text-[17px] font-bold tracking-[-0.01em]">
                Демо-доступ: команда хакатона
              </h2>
              <p className="text-[13px] text-dim">
                Общий пароль{" "}
                <span className="rounded-full bg-subtle px-2 py-0.5 font-mono text-[13px] font-semibold text-foreground">
                  {DEMO_PASSWORD}
                </span>
              </p>
            </div>
            <p className="mt-2 text-[13px] leading-relaxed text-muted-foreground">
              Выберите, за кого войти, — почта и пароль подставятся сами. У каждого своя
              картина: Саша состоит во всех трёх группах, Жора — только в сплаве.
            </p>
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {DEMO_ACCOUNTS.map((account, index) => (
                <button
                  key={account.email}
                  type="button"
                  onClick={() => fillDemoAccount(account.email)}
                  aria-label={`Войти как ${account.name}`}
                  className={cn(
                    "flex min-h-[52px] w-full items-center gap-2.5 rounded-full bg-subtle py-2 pl-2 pr-4 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card",
                    // Пятая учётка одна в ряду — растягиваем, чтобы сетка не обрывалась.
                    index === DEMO_ACCOUNTS.length - 1 &&
                      DEMO_ACCOUNTS.length % 2 === 1 &&
                      "sm:col-span-2",
                  )}
                >
                  <span
                    className={cn(
                      "flex size-[34px] shrink-0 items-center justify-center rounded-full text-[13px] font-bold",
                      avatarTone(account.email),
                    )}
                    aria-hidden="true"
                  >
                    {initials(account.name)}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold leading-tight">
                      {account.name}
                    </span>
                    <span className="block truncate text-[12px] text-dim">
                      {account.email}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </section>
        </div>

        <aside className="hidden min-w-0 lg:block lg:flex-1">
          <Wordmark />
          <p className="mt-6 text-[28px] font-bold leading-[1.15] tracking-[-0.025em]">
            {APP_TAGLINE}
          </p>
          <p className="mt-3 max-w-[46ch] text-base text-muted-foreground">
            Складчина ведёт общий счёт компании: кто за что заплатил, кто кому сколько
            должен и каким одним переводом это закрыть.
          </p>

          <h2 className="mt-9 text-[13px] font-bold uppercase tracking-[0.08em] text-dim">
            Создано для самого неловкого разговора — о деньгах
          </h2>
          <ul className="mt-5 flex flex-col gap-5">
            {FEATURES.map((feature) => (
              <li key={feature.title} className="flex gap-3.5">
                <span className="mt-0.5 flex size-11 shrink-0 items-center justify-center rounded-tile bg-accent text-accent-foreground">
                  <feature.icon className="size-5" aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <p className="text-base font-semibold">{feature.title}</p>
                  <p className="mt-1 max-w-[52ch] text-sm leading-relaxed text-muted-foreground">
                    {feature.body}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </aside>
      </main>
    </div>
  );
}
