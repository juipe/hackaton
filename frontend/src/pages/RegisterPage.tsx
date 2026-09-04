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
import { useMemo, useState } from "react";
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
import { APP_TAGLINE } from "@/lib/constants";

const registerSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Укажите, как к вам обращаться")
    .max(120, "Такое имя чуть длиннее, чем нужно"),
  email: z
    .string()
    .min(1, "Введите адрес электронной почты")
    .email("Похоже, это не адрес электронной почты"),
  // 72 is the bcrypt input limit the API enforces, so cap it here rather than
  // letting the server reject a password the user has already committed to.
  password: z
    .string()
    .min(8, "Не меньше 8 символов")
    .max(72, "Пароль не длиннее 72 символов"),
});

type RegisterValues = z.infer<typeof registerSchema>;

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

export default function RegisterPage() {
  const { user, isLoading, register: registerAccount } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);

  const nextPath = useMemo(() => resolveNextPath(location.search), [location.search]);
  const loginHref = nextPath === "/" ? "/login" : `/login?next=${encodeURIComponent(nextPath)}`;

  const form = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { name: "", email: "", password: "" },
  });
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = form;

  const onSubmit = handleSubmit(async (values) => {
    try {
      const created = await registerAccount({
        name: values.name,
        email: values.email.trim(),
        password: values.password,
      });
      toast.success(`Добро пожаловать в Складчину, ${created.name}`);
      navigate(nextPath, { replace: true });
    } catch (error) {
      const message = errorMessage(error);
      form.setError("root", { message });
      toast.error(message);
    }
  });

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
            <h1 className="text-[26px] font-bold tracking-[-0.02em]">Создать аккаунт</h1>
            <p className="mt-1.5 text-[15px] text-muted-foreground">
              Соберите группу, добавьте первый расход — остальное посчитается само.
            </p>

            <form onSubmit={onSubmit} noValidate className="mt-6 flex flex-col gap-[18px]">
              {errors.root?.message ? (
                <Alert variant="destructive">
                  <AlertCircle aria-hidden="true" />
                  <AlertDescription>{errors.root.message}</AlertDescription>
                </Alert>
              ) : null}

              <div className="flex flex-col gap-2">
                <Label htmlFor="name">Имя</Label>
                <Input
                  id="name"
                  type="text"
                  autoComplete="name"
                  placeholder="Мария Иванова"
                  aria-invalid={errors.name ? true : undefined}
                  aria-describedby={errors.name ? "name-error" : "name-hint"}
                  {...register("name")}
                />
                {errors.name ? (
                  <p id="name-error" className="text-[13px] text-destructive">
                    {errors.name.message}
                  </p>
                ) : (
                  <p id="name-hint" className="text-[13px] text-dim">
                    Это имя увидят участники ваших групп.
                  </p>
                )}
              </div>

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
                    autoComplete="new-password"
                    className="pr-[52px]"
                    aria-invalid={errors.password ? true : undefined}
                    aria-describedby={errors.password ? "password-error" : "password-hint"}
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
                ) : (
                  <p id="password-hint" className="text-[13px] text-dim">
                    Не меньше 8 символов.
                  </p>
                )}
              </div>

              <Button type="submit" size="lg" className="mt-1 w-full" disabled={isSubmitting}>
                {isSubmitting ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
                {isSubmitting ? "Создаём аккаунт…" : "Создать аккаунт"}
              </Button>
            </form>

            <p className="mt-5 text-center text-sm text-muted-foreground">
              Уже есть аккаунт?{" "}
              <Link
                to={loginHref}
                className="font-semibold text-accent-foreground hover:underline"
              >
                Войти
              </Link>
            </p>
          </div>
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
