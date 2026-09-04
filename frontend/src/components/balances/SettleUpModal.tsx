import { useMemo, useState, type FormEvent } from "react";
import { ArrowLeftRight, Info } from "lucide-react";
import { toast } from "sonner";

import { AvatarStack } from "@/components/common/AvatarStack";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCurrentUser } from "@/hooks/useAuth";
import { useCreatePayment } from "@/hooks/usePayments";
import { errorMessage } from "@/lib/api";
import {
  centsToInput,
  currencySymbol,
  formatMoney,
  parseAmountToCents,
} from "@/lib/money";
import { cn } from "@/lib/utils";
import type { Group, GroupBalances, Member, Transfer, Uuid } from "@/types/api";

export interface SettleUpPrefill {
  fromUserId?: Uuid;
  toUserId?: Uuid;
  amountCents?: number;
}

export interface SettleUpModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  group: Group;
  members: Member[];
  balances?: GroupBalances;
  prefill?: SettleUpPrefill;
}

export function SettleUpModal({
  open,
  onOpenChange,
  group,
  members,
  balances,
  prefill,
}: SettleUpModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle>Погасить долг</DialogTitle>
          <DialogDescription>
            «Складчина» не переводит деньги. Запишите здесь перевод, который уже
            состоялся на самом деле, — наличными, картой, как договорились.
          </DialogDescription>
        </DialogHeader>

        {/* Remounted on every open, so the defaults are recalculated from the
            balances as they are right now rather than as they were last time. */}
        <SettleUpForm
          group={group}
          members={members}
          balances={balances}
          prefill={prefill}
          onDone={() => onOpenChange(false)}
        />
      </DialogContent>
    </Dialog>
  );
}

interface SettleUpFormProps {
  group: Group;
  members: Member[];
  balances?: GroupBalances;
  prefill?: SettleUpPrefill;
  onDone: () => void;
}

function pickDefaults(
  members: Member[],
  balances: GroupBalances | undefined,
  currentUserId: Uuid,
  prefill: SettleUpPrefill | undefined,
): { fromUserId: string; toUserId: string; amount: string } {
  const pairwise = balances?.pairwise ?? [];
  const byAmountDesc = (a: Transfer, b: Transfer) => b.amount_cents - a.amount_cents;

  const myDebts: Transfer[] = pairwise.filter((t) => t.from_user_id === currentUserId);
  const owedToMe: Transfer[] = pairwise.filter((t) => t.to_user_id === currentUserId);
  // What the user almost always wants is to clear their own biggest debt; being
  // paid back is the second-best guess.
  const anchor: Transfer | undefined =
    myDebts.sort(byAmountDesc)[0] ?? owedToMe.sort(byAmountDesc)[0];

  const fromUserId = prefill?.fromUserId ?? anchor?.from_user_id ?? currentUserId;
  const anchorFits = anchor !== undefined && anchor.from_user_id === fromUserId;
  const fallbackTo = members.find((member) => member.user.id !== fromUserId)?.user.id ?? "";
  const toUserId = prefill?.toUserId ?? (anchorFits ? anchor.to_user_id : fallbackTo);
  const amountCents = prefill?.amountCents ?? (anchorFits ? anchor.amount_cents : null);

  return {
    fromUserId,
    toUserId,
    amount: amountCents === null ? "" : centsToInput(amountCents),
  };
}

function SettleUpForm({ group, members, balances, prefill, onDone }: SettleUpFormProps) {
  const currentUser = useCurrentUser();
  const createPayment = useCreatePayment(group.id);

  const [defaults] = useState(() =>
    pickDefaults(members, balances, currentUser.id, prefill),
  );
  const [fromUserId, setFromUserId] = useState(defaults.fromUserId);
  const [toUserId, setToUserId] = useState(defaults.toUserId);
  const [amount, setAmount] = useState(defaults.amount);
  const [note, setNote] = useState("");
  const [attempted, setAttempted] = useState(false);

  const userOf = (userId: string) =>
    members.find((member) => member.user.id === userId)?.user;
  const nameOf = (userId: string) => userOf(userId)?.name ?? "кто-то";

  const outstandingCents = useMemo(() => {
    const match = (balances?.pairwise ?? []).find(
      (transfer) =>
        transfer.from_user_id === fromUserId && transfer.to_user_id === toUserId,
    );
    return match?.amount_cents ?? 0;
  }, [balances, fromUserId, toUserId]);

  if (members.length < 2) {
    return (
      <div className="mt-[26px] flex flex-col gap-5">
        <p className="text-[15px] leading-relaxed text-muted-foreground">
          Для перевода нужны двое. Сначала пригласите кого-нибудь в группу
          «{group.name}», а потом возвращайтесь и запишите расчёт.
        </p>
        <DialogFooter className="mt-0">
          <DialogClose asChild>
            <Button type="button" variant="secondary">
              Закрыть
            </Button>
          </DialogClose>
        </DialogFooter>
      </div>
    );
  }

  const parsed = parseAmountToCents(amount);
  const amountCents = parsed ?? 0;
  const samePerson = fromUserId === toUserId;
  // Exactly the wording the API answers with, so the message never changes shape
  // between the guard here and a rejection from the server.
  const validationError = samePerson
    ? "Перевод возможен только между разными людьми"
    : amountCents <= 0
      ? "Сумма должна быть больше нуля"
      : null;

  const fromName = nameOf(fromUserId);
  const toName = nameOf(toUserId);
  const money = formatMoney(amountCents, group.currency);
  // Same arrow scheme as the debt list: both people stay in the nominative, so
  // nothing here depends on inflecting a name the user typed in.
  const fromLabel = fromUserId === currentUser.id ? "Вы" : fromName;
  const toLabel = toUserId === currentUser.id ? "вы" : toName;
  const direction = `${fromLabel} → ${toLabel}`;

  // Знак долга — со стороны читателя: платит он — красный, получает — зелёный,
  // чужая пара остаётся нейтральной.
  const outstandingTone =
    toUserId === currentUser.id
      ? "text-positive"
      : fromUserId === currentUser.id
        ? "text-negative"
        : "text-foreground";

  const pair = [userOf(fromUserId), userOf(toUserId)].filter(
    (user): user is NonNullable<typeof user> => Boolean(user),
  );

  const statement = (() => {
    if (samePerson) return "Перевод возможен только между разными людьми";
    if (amount.trim() === "") return "Укажите сумму перевода.";
    if (amountCents <= 0) return "Сумма должна быть больше нуля";
    return `Будет записан перевод: ${direction}, ${money}.`;
  })();

  function swapDirection() {
    setFromUserId(toUserId);
    setToUserId(fromUserId);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAttempted(true);
    if (validationError) {
      toast.error(validationError);
      return;
    }

    createPayment.mutate(
      {
        from_user_id: fromUserId,
        to_user_id: toUserId,
        amount_cents: amountCents,
        note: note.trim() ? note.trim() : null,
      },
      {
        onSuccess: () => {
          toast.success(`Перевод записан: ${direction}, ${money}.`);
          onDone();
        },
        onError: (error) => toast.error(errorMessage(error)),
      },
    );
  }

  return (
    <form onSubmit={handleSubmit} className="mt-[26px] flex flex-col gap-[18px]">
      {/* Строка долга — та же, что в списке «Кто кому должен»: человек узнаёт
          её и понимает, какую именно строку он сейчас закрывает. */}
      {samePerson ? null : (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-row bg-subtle px-[18px] py-3.5">
          {pair.length === 2 ? (
            <AvatarStack
              users={pair}
              size="md"
              max={2}
              ringClassName="shadow-[0_0_0_3px_hsl(var(--subtle))]"
            />
          ) : null}
          <p className="min-w-0 flex-1 basis-32 text-base font-semibold tracking-[-0.01em] text-foreground">
            {fromLabel} <span className="font-medium text-dim">→</span> {toLabel}
          </p>
          {outstandingCents > 0 ? (
            <>
              <p
                className={cn(
                  "shrink-0 text-[19px] font-bold tracking-[-0.02em] tabular-nums-money",
                  outstandingTone,
                )}
              >
                {formatMoney(outstandingCents, group.currency)}
              </p>
              <Button
                type="button"
                variant="soft"
                size="sm"
                className="shrink-0 font-bold"
                onClick={() => setAmount(centsToInput(outstandingCents))}
              >
                Весь долг
              </Button>
            </>
          ) : (
            <p className="basis-full text-[13px] text-dim sm:basis-auto sm:text-right">
              Между этими участниками долга нет — укажите сумму, которая перешла из рук
              в руки.
            </p>
          )}
        </div>
      )}

      <div className="grid gap-3.5 sm:grid-cols-[1fr_auto_1fr] sm:items-end">
        <div className="space-y-2">
          <Label htmlFor="settle-from">Отправитель</Label>
          <Select value={fromUserId} onValueChange={setFromUserId}>
            <SelectTrigger id="settle-from">
              <SelectValue placeholder="Выберите человека" />
            </SelectTrigger>
            <SelectContent>
              {members.map((member) => (
                <SelectItem key={member.user.id} value={member.user.id}>
                  {member.user.id === currentUser.id
                    ? `${member.user.name} (вы)`
                    : member.user.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Button
          type="button"
          variant="muted"
          onClick={swapDirection}
          aria-label="Поменять отправителя и получателя местами"
          className="h-[46px] justify-self-start sm:size-[52px] sm:justify-self-center sm:px-0"
        >
          <ArrowLeftRight aria-hidden="true" />
          <span className="sm:sr-only">Поменять</span>
        </Button>

        <div className="space-y-2">
          <Label htmlFor="settle-to">Получатель</Label>
          <Select value={toUserId} onValueChange={setToUserId}>
            <SelectTrigger id="settle-to">
              <SelectValue placeholder="Выберите человека" />
            </SelectTrigger>
            <SelectContent>
              {members.map((member) => (
                <SelectItem key={member.user.id} value={member.user.id}>
                  {member.user.id === currentUser.id
                    ? `${member.user.name} (вы)`
                    : member.user.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="settle-amount">Сумма</Label>
        <div className="relative">
          <Input
            id="settle-amount"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            inputMode="decimal"
            autoComplete="off"
            placeholder="0,00"
            className="pr-12 font-semibold tabular-nums-money"
          />
          <span className="pointer-events-none absolute inset-y-0 right-[18px] flex items-center text-base font-semibold text-dim">
            {currencySymbol(group.currency)}
          </span>
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="settle-note">Комментарий (необязательно)</Label>
        <Textarea
          id="settle-note"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          rows={2}
          maxLength={280}
          placeholder="Перевод на карту, наличные за ужин, …"
          className="min-h-[72px]"
        />
      </div>

      <div
        className={cn(
          "flex items-start gap-3 rounded-row p-4",
          attempted && validationError ? "bg-negative-surface" : "bg-subtle",
        )}
      >
        <Info
          className={cn(
            "mt-0.5 size-[17px] shrink-0",
            attempted && validationError ? "text-negative" : "text-dim",
          )}
          aria-hidden="true"
        />
        <p
          className={cn(
            "text-[15px] leading-relaxed",
            attempted && validationError
              ? "text-negative"
              : validationError
                ? "text-muted-foreground"
                : "text-foreground",
          )}
        >
          {statement}
        </p>
      </div>

      <DialogFooter className="mt-2">
        <DialogClose asChild>
          <Button type="button" variant="secondary" size="lg">
            Отмена
          </Button>
        </DialogClose>
        <Button type="submit" size="lg" disabled={createPayment.isPending}>
          {createPayment.isPending ? "Записываем…" : "Записать перевод"}
        </Button>
      </DialogFooter>
    </form>
  );
}
