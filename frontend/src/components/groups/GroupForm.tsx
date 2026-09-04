import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useId } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateGroup, useUpdateGroup } from "@/hooks/useGroups";
import { errorMessage } from "@/lib/api";
import { DEFAULT_CURRENCY } from "@/lib/constants";
import { cn } from "@/lib/utils";
import type { Group, GroupUpdateInput } from "@/types/api";

const groupSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Введите название группы")
    .max(120, "Название — не длиннее 120 символов"),
  description: z.string().trim().max(500, "Описание — не длиннее 500 символов"),
});

type GroupFormValues = z.infer<typeof groupSchema>;

/**
 * У полей нет обводки, поэтому ошибку показывает кольцо цвета долга: рамка
 * появилась бы только у сломанного поля и ломала бы ритм формы.
 */
const INVALID = "ring-2 ring-negative";

function toFormValues(group: Group | undefined): GroupFormValues {
  return {
    name: group?.name ?? "",
    description: group?.description ?? "",
  };
}

export interface GroupFormProps {
  group?: Group;
  onSaved?: (group: Group) => void;
}

export function GroupForm({ group, onSaved }: GroupFormProps) {
  const navigate = useNavigate();
  const fieldId = useId();
  const nameId = `${fieldId}-name`;
  const descriptionId = `${fieldId}-description`;

  const createGroup = useCreateGroup();
  // Hooks cannot be conditional, so the update mutation is always constructed; in
  // create mode the id is never used because the mutation is never fired.
  const updateGroup = useUpdateGroup(group?.id ?? "");

  const {
    formState: { errors, isDirty, isSubmitting },
    handleSubmit,
    register,
    reset,
  } = useForm<GroupFormValues>({
    resolver: zodResolver(groupSchema),
    defaultValues: toFormValues(group),
  });

  async function onSubmit(values: GroupFormValues) {
    const description = values.description ? values.description : null;

    try {
      if (group) {
        // PATCH means "change exactly these fields", so only genuinely changed ones
        // are sent — an untouched description is never overwritten with itself.
        const patch: GroupUpdateInput = {};
        if (values.name !== group.name) patch.name = values.name;
        if (description !== (group.description ?? null)) patch.description = description;

        if (Object.keys(patch).length === 0) {
          reset(toFormValues(group));
          toast.info("Изменений нет");
          return;
        }

        const saved = await updateGroup.mutateAsync(patch);
        reset(toFormValues(saved));
        toast.success("Группа обновлена");
        onSaved?.(saved);
        return;
      }

      const created = await createGroup.mutateAsync({
        name: values.name,
        description,
        // The product knows exactly one currency; the server defaults to it too.
        currency: DEFAULT_CURRENCY,
      });
      toast.success(`Группа «${created.name}» создана`);
      if (onSaved) {
        onSaved(created);
        return;
      }
      navigate(`/groups/${created.id}`);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  return (
    <form
      className="flex flex-col gap-[18px]"
      onSubmit={handleSubmit(onSubmit)}
      noValidate
    >
      <div className="space-y-2">
        <Label htmlFor={nameId}>Название группы</Label>
        <Input
          id={nameId}
          placeholder="Квартира на Вайнера, хакатон, сплав по Чусовой…"
          autoComplete="off"
          className={cn(errors.name && INVALID)}
          aria-invalid={errors.name ? true : undefined}
          aria-describedby={errors.name ? `${nameId}-error` : undefined}
          {...register("name")}
        />
        {errors.name ? (
          <p id={`${nameId}-error`} className="text-[13px] font-medium text-negative">
            {errors.name.message}
          </p>
        ) : null}
      </div>

      <div className="space-y-2">
        <Label htmlFor={descriptionId}>
          Описание <span className="font-normal text-dim">(необязательно)</span>
        </Label>
        <Textarea
          id={descriptionId}
          rows={3}
          placeholder="Какие расходы попадают в эту группу?"
          className={cn(errors.description && INVALID)}
          aria-invalid={errors.description ? true : undefined}
          aria-describedby={errors.description ? `${descriptionId}-error` : undefined}
          {...register("description")}
        />
        {errors.description ? (
          <p
            id={`${descriptionId}-error`}
            className="text-[13px] font-medium text-negative"
          >
            {errors.description.message}
          </p>
        ) : null}
      </div>

      <p className="text-[13px] text-dim">Все расходы в группе — в рублях.</p>

      <div className="flex flex-col-reverse gap-2.5 border-t border-border/60 pt-6 sm:flex-row sm:justify-end">
        {group ? (
          <Button
            type="button"
            variant="secondary"
            disabled={!isDirty || isSubmitting}
            onClick={() => reset(toFormValues(group))}
          >
            Отменить изменения
          </Button>
        ) : (
          <Button asChild type="button" variant="secondary">
            <Link to="/groups">Отмена</Link>
          </Button>
        )}
        <Button type="submit" disabled={isSubmitting || (Boolean(group) && !isDirty)}>
          {isSubmitting ? <Loader2 className="animate-spin" aria-hidden="true" /> : null}
          {group ? "Сохранить" : "Создать группу"}
        </Button>
      </div>
    </form>
  );
}
