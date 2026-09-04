import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { AlertCircle, Check, KeyRound, Loader2, LogOut } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { UserAvatar } from "@/components/common/UserAvatar";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/useAuth";
import { api, errorMessage } from "@/lib/api";
import type { UserPublic } from "@/types/api";

const profileSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Имя не может быть пустым")
    .max(120, "Такое имя чуть длиннее, чем нужно"),
  email: z
    .string()
    .min(1, "Введите адрес электронной почты")
    .email("Похоже, это не адрес электронной почты"),
});

type ProfileValues = z.infer<typeof profileSchema>;

const passwordSchema = z
  .object({
    currentPassword: z.string().min(1, "Введите текущий пароль"),
    newPassword: z
      .string()
      .min(8, "Не меньше 8 символов")
      .max(72, "Пароль не длиннее 72 символов"),
    confirmPassword: z.string().min(1, "Повторите новый пароль"),
  })
  .refine((values) => values.newPassword === values.confirmPassword, {
    message: "Пароли не совпадают",
    path: ["confirmPassword"],
  });

type PasswordValues = z.infer<typeof passwordSchema>;

export default function ProfilePage() {
  const { user, logout, refresh } = useAuth();
  const navigate = useNavigate();
  const [showPasswords, setShowPasswords] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);

  const profileForm = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: { name: user?.name ?? "", email: user?.email ?? "" },
  });
  const passwordForm = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { currentPassword: "", newPassword: "", confirmPassword: "" },
  });

  const { reset: resetProfileForm } = profileForm;
  const profileName = user?.name;
  const profileEmail = user?.email;

  // The server is the authority on the saved values, so re-seed the form from the
  // refreshed session rather than from what was typed.
  useEffect(() => {
    if (profileName === undefined || profileEmail === undefined) return;
    resetProfileForm({ name: profileName, email: profileEmail });
  }, [profileName, profileEmail, resetProfileForm]);

  const updateProfile = useMutation({
    mutationFn: (values: ProfileValues) =>
      api.patch<UserPublic>("/auth/me", {
        name: values.name,
        email: values.email.trim().toLowerCase(),
      }),
  });

  const changePassword = useMutation({
    mutationFn: (values: PasswordValues) =>
      api.post<void>("/auth/change-password", {
        current_password: values.currentPassword,
        new_password: values.newPassword,
      }),
  });

  const onSaveProfile = profileForm.handleSubmit(async (values) => {
    try {
      await updateProfile.mutateAsync(values);
      await refresh();
      toast.success("Профиль обновлён");
    } catch (error) {
      const message = errorMessage(error);
      profileForm.setError("root", { message });
      toast.error(message);
    }
  });

  const onChangePassword = passwordForm.handleSubmit(async (values) => {
    try {
      await changePassword.mutateAsync(values);
      passwordForm.reset({ currentPassword: "", newPassword: "", confirmPassword: "" });
      setShowPasswords(false);
      toast.success("Пароль изменён");
    } catch (error) {
      const message = errorMessage(error);
      passwordForm.setError("root", { message });
      toast.error(message);
    }
  });

  async function handleSignOut() {
    setIsSigningOut(true);
    try {
      await logout();
      navigate("/login", { replace: true });
    } finally {
      setIsSigningOut(false);
    }
  }

  const profileErrors = profileForm.formState.errors;
  const passwordErrors = passwordForm.formState.errors;
  const profileDirty = profileForm.formState.isDirty;

  // Signing out clears the session; RequireAuth takes over the redirect.
  if (!user) return null;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Профиль"
        description="Данные аккаунта, пароль и сессия на этом устройстве."
      />

      <div className="grid gap-5 lg:grid-cols-2 lg:items-start">
        <SectionCard
          title="Данные аккаунта"
          description="Ваше имя видят все участники групп рядом с каждым расходом."
        >
          <div className="flex items-center gap-3.5 rounded-row bg-subtle px-[18px] py-3.5">
            <UserAvatar user={user} size="xl" />
            <div className="min-w-0">
              <p className="truncate text-base font-semibold">{user.name}</p>
              <p className="truncate text-[13px] text-dim">{user.email}</p>
            </div>
          </div>

          <form onSubmit={onSaveProfile} noValidate className="mt-5 flex flex-col gap-[18px]">
            {profileErrors.root?.message ? (
              <Alert variant="destructive">
                <AlertCircle aria-hidden="true" />
                <AlertDescription>{profileErrors.root.message}</AlertDescription>
              </Alert>
            ) : null}

            <div className="flex flex-col gap-2">
              <Label htmlFor="profile-name">Имя</Label>
              <Input
                id="profile-name"
                type="text"
                autoComplete="name"
                aria-invalid={profileErrors.name ? true : undefined}
                aria-describedby={profileErrors.name ? "profile-name-error" : undefined}
                {...profileForm.register("name")}
              />
              {profileErrors.name ? (
                <p id="profile-name-error" className="text-[13px] text-destructive">
                  {profileErrors.name.message}
                </p>
              ) : null}
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="profile-email">Электронная почта</Label>
              <Input
                id="profile-email"
                type="email"
                autoComplete="email"
                aria-invalid={profileErrors.email ? true : undefined}
                aria-describedby={
                  profileErrors.email ? "profile-email-error" : "profile-email-hint"
                }
                {...profileForm.register("email")}
              />
              {profileErrors.email ? (
                <p id="profile-email-error" className="text-[13px] text-destructive">
                  {profileErrors.email.message}
                </p>
              ) : (
                <p id="profile-email-hint" className="text-[13px] leading-relaxed text-dim">
                  С этим адресом вы входите, и к нему же привязываются приглашения в группы.
                </p>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="submit"
                disabled={updateProfile.isPending || !profileDirty}
                className="min-w-[9rem]"
              >
                {updateProfile.isPending ? (
                  <Loader2 className="animate-spin" aria-hidden="true" />
                ) : (
                  <Check aria-hidden="true" />
                )}
                {updateProfile.isPending ? "Сохраняем…" : "Сохранить"}
              </Button>
              {profileDirty && !updateProfile.isPending ? (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => resetProfileForm({ name: user.name, email: user.email })}
                >
                  Отменить
                </Button>
              ) : null}
            </div>
          </form>
        </SectionCard>

        <SectionCard
          title="Смена пароля"
          description="После смены пароля вы останетесь в системе на этом устройстве."
        >
          <form onSubmit={onChangePassword} noValidate className="flex flex-col gap-[18px]">
            {passwordErrors.root?.message ? (
              <Alert variant="destructive">
                <AlertCircle aria-hidden="true" />
                <AlertDescription>{passwordErrors.root.message}</AlertDescription>
              </Alert>
            ) : null}

            <div className="flex flex-col gap-2">
              <Label htmlFor="current-password">Текущий пароль</Label>
              <Input
                id="current-password"
                type={showPasswords ? "text" : "password"}
                autoComplete="current-password"
                aria-invalid={passwordErrors.currentPassword ? true : undefined}
                aria-describedby={
                  passwordErrors.currentPassword ? "current-password-error" : undefined
                }
                {...passwordForm.register("currentPassword")}
              />
              {passwordErrors.currentPassword ? (
                <p id="current-password-error" className="text-[13px] text-destructive">
                  {passwordErrors.currentPassword.message}
                </p>
              ) : null}
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="new-password">Новый пароль</Label>
              <Input
                id="new-password"
                type={showPasswords ? "text" : "password"}
                autoComplete="new-password"
                aria-invalid={passwordErrors.newPassword ? true : undefined}
                aria-describedby={
                  passwordErrors.newPassword ? "new-password-error" : "new-password-hint"
                }
                {...passwordForm.register("newPassword")}
              />
              {passwordErrors.newPassword ? (
                <p id="new-password-error" className="text-[13px] text-destructive">
                  {passwordErrors.newPassword.message}
                </p>
              ) : (
                <p id="new-password-hint" className="text-[13px] text-dim">
                  Не меньше 8 символов.
                </p>
              )}
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="confirm-password">Повторите новый пароль</Label>
              <Input
                id="confirm-password"
                type={showPasswords ? "text" : "password"}
                autoComplete="new-password"
                aria-invalid={passwordErrors.confirmPassword ? true : undefined}
                aria-describedby={
                  passwordErrors.confirmPassword ? "confirm-password-error" : undefined
                }
                {...passwordForm.register("confirmPassword")}
              />
              {passwordErrors.confirmPassword ? (
                <p id="confirm-password-error" className="text-[13px] text-destructive">
                  {passwordErrors.confirmPassword.message}
                </p>
              ) : null}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button type="submit" disabled={changePassword.isPending} className="min-w-[11rem]">
                {changePassword.isPending ? (
                  <Loader2 className="animate-spin" aria-hidden="true" />
                ) : (
                  <KeyRound aria-hidden="true" />
                )}
                {changePassword.isPending ? "Обновляем…" : "Обновить пароль"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setShowPasswords((visible) => !visible)}
              >
                {showPasswords ? "Скрыть пароли" : "Показать пароли"}
              </Button>
            </div>
          </form>
        </SectionCard>
      </div>

      <SectionCard
        title="Сессия"
        description="Выход завершает только эту сессию — группы, расходы и балансы останутся ровно такими же."
      >
        <Button
          variant="secondary"
          className="bg-negative-surface text-negative hover:bg-negative-surface-hover hover:text-negative"
          onClick={handleSignOut}
          disabled={isSigningOut}
        >
          {isSigningOut ? (
            <Loader2 className="animate-spin" aria-hidden="true" />
          ) : (
            <LogOut aria-hidden="true" />
          )}
          {isSigningOut ? "Выходим…" : "Выйти"}
        </Button>
      </SectionCard>
    </div>
  );
}
