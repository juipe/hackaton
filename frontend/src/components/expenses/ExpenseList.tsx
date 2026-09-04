import {
  CalendarRange,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Receipt,
  Search,
  SearchX,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { ExpenseCard } from "@/components/expenses/ExpenseCard";
import { ExpenseDetailDialog } from "@/components/expenses/ExpenseDetailDialog";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useExpenses } from "@/hooks/useExpenses";
import { formatDateShort, formatDayHeading, toDateInputValue } from "@/lib/format";
import { formatMoney } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { Category, Expense, ExpenseFilters, Member } from "@/types/api";

export interface ExpenseListProps {
  groupId: string;
  members: Member[];
  categories: Category[];
  currentUserId: string;
}

const PAGE_SIZE = 20;
const ANY = "any";

interface DayGroup {
  key: string;
  date: string;
  totalCents: number;
  currency: string;
  items: Expense[];
}

/**
 * Группировка идёт по уже полученной странице и только по соседним элементам:
 * порядок, в котором расходы пришли с сервера, сохраняется как есть. Если день
 * вдруг встретится дважды, он и покажется дважды — это честнее, чем молча
 * пересортировать список под свою вёрстку.
 */
function groupByDay(items: Expense[]): DayGroup[] {
  const groups: DayGroup[] = [];
  for (const expense of items) {
    const key = toDateInputValue(expense.occurred_at);
    const last = groups[groups.length - 1];
    if (last && last.key === key) {
      last.items.push(expense);
      last.totalCents += expense.amount_cents;
      continue;
    }
    groups.push({
      key,
      date: expense.occurred_at,
      totalCents: expense.amount_cents,
      currency: expense.currency,
      items: [expense],
    });
  }
  return groups;
}

export function ExpenseList({
  groupId,
  members,
  categories,
  currentUserId,
}: ExpenseListProps) {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [categoryId, setCategoryId] = useState(ANY);
  const [payerId, setPayerId] = useState(ANY);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(0);
  const [selectedId, setSelectedId] = useState<string | undefined>(undefined);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  // A filter change makes the current page number meaningless.
  useEffect(() => {
    setPage(0);
  }, [debouncedSearch, categoryId, payerId, dateFrom, dateTo]);

  const filters = useMemo<ExpenseFilters>(
    () => ({
      q: debouncedSearch || undefined,
      category_id: categoryId === ANY ? undefined : categoryId,
      paid_by: payerId === ANY ? undefined : payerId,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    }),
    [debouncedSearch, categoryId, payerId, dateFrom, dateTo, page],
  );

  const expensesQuery = useExpenses(groupId, filters);
  const pageData = expensesQuery.data;
  const items = pageData?.items ?? [];
  const total = pageData?.total ?? 0;

  const days = useMemo(() => groupByDay(items), [items]);

  const periodActive = Boolean(dateFrom) || Boolean(dateTo);
  const filtersActive =
    Boolean(search) ||
    Boolean(debouncedSearch) ||
    categoryId !== ANY ||
    payerId !== ANY ||
    periodActive;

  const clearFilters = () => {
    setSearch("");
    setDebouncedSearch("");
    setCategoryId(ANY);
    setPayerId(ANY);
    setDateFrom("");
    setDateTo("");
    setPage(0);
  };

  const firstShown = total === 0 ? 0 : page * PAGE_SIZE + 1;
  const lastShown = page * PAGE_SIZE + items.length;

  return (
    <div className="flex flex-col gap-4">
      <div className="no-scrollbar flex items-center gap-2 overflow-x-auto py-1 lg:flex-wrap lg:overflow-x-visible">
        <label className="inline-flex h-[46px] w-[220px] shrink-0 items-center gap-2.5 rounded-full bg-card px-[18px] shadow-flat sm:w-[260px]">
          <Search className="size-[18px] shrink-0 text-dim" aria-hidden="true" />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Поиск по расходам"
            aria-label="Поиск по расходам"
            className="h-full w-full min-w-0 border-0 bg-transparent p-0 text-[15px] text-foreground outline-none placeholder:text-dim"
          />
        </label>

        <FilterCapsule
          value={categoryId}
          onValueChange={setCategoryId}
          label="Фильтр по категории"
          clearLabel="Сбросить фильтр по категории"
        >
          <SelectItem value={ANY}>Все категории</SelectItem>
          {categories.map((category) => (
            <SelectItem key={category.id} value={category.id}>
              {category.name}
            </SelectItem>
          ))}
        </FilterCapsule>

        <FilterCapsule
          value={payerId}
          onValueChange={setPayerId}
          label="Фильтр по плательщику"
          clearLabel="Сбросить фильтр по плательщику"
        >
          <SelectItem value={ANY}>Любой плательщик</SelectItem>
          {members.map((member) => (
            <SelectItem key={member.id} value={member.user.id}>
              {member.user.id === currentUserId ? "Вы" : member.user.name}
            </SelectItem>
          ))}
        </FilterCapsule>

        <PeriodCapsule
          dateFrom={dateFrom}
          dateTo={dateTo}
          onDateFromChange={setDateFrom}
          onDateToChange={setDateTo}
        />

        {filtersActive ? (
          <Button
            variant="ghost"
            className="h-[46px] shrink-0 px-4 text-[15px] font-medium text-dim hover:bg-transparent hover:text-foreground [&_svg]:size-[15px]"
            onClick={clearFilters}
          >
            <X strokeWidth={2.2} aria-hidden="true" />
            Сбросить фильтры
          </Button>
        ) : null}
      </div>

      {expensesQuery.isPending ? (
        <div className="flex flex-col gap-2" aria-busy="true">
          {[0, 1, 2, 3].map((row) => (
            <Skeleton key={row} className="h-[74px] w-full rounded-row" />
          ))}
        </div>
      ) : expensesQuery.isError ? (
        <ErrorState
          error={expensesQuery.error}
          onRetry={() => void expensesQuery.refetch()}
        />
      ) : items.length === 0 ? (
        filtersActive ? (
          <EmptyState
            icon={SearchX}
            title="Ничего не нашлось"
            description="Попробуйте изменить период, категорию или поисковый запрос."
            action={
              <Button variant="outline" onClick={clearFilters}>
                Сбросить фильтры
              </Button>
            }
          />
        ) : (
          <EmptyState
            icon={Receipt}
            title="Расходов пока нет"
            description="Добавьте первый — балансы участников обновятся сразу."
          />
        )
      ) : (
        <div className="rounded-card bg-card px-3 pb-[22px] pt-3 shadow-card sm:px-7">
          {days.map((day, index) => (
            <section key={`${day.key}-${index}`}>
              <div
                className={cn(
                  "flex items-center justify-between gap-3 py-2 pt-4",
                  index > 0 && "mt-2 border-t border-border/60 pt-5",
                )}
              >
                <h3 className="text-[13px] font-bold uppercase tracking-[0.08em] text-dim">
                  {formatDayHeading(day.date)}
                </h3>
                <span className="text-sm font-semibold text-dim tabular-nums-money">
                  {formatMoney(day.totalCents, day.currency)}
                </span>
              </div>

              <ul>
                {day.items.map((expense) => (
                  <li key={expense.id}>
                    <ExpenseCard
                      expense={expense}
                      currentUserId={currentUserId}
                      onSelect={(selected) => setSelectedId(selected.id)}
                    />
                  </li>
                ))}
              </ul>
            </section>
          ))}

          {total > PAGE_SIZE ? (
            <div className="mt-2 flex flex-wrap items-center justify-between gap-3 border-t border-border/60 px-1 pb-1 pt-5 sm:px-4">
              <p className="text-sm text-dim">
                Показаны {firstShown}–{lastShown} из {total}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="muted"
                  size="sm"
                  className="disabled:bg-subtle disabled:text-faint disabled:opacity-100 hover:bg-accent hover:text-accent-foreground [&_svg]:size-[15px]"
                  disabled={page === 0}
                  onClick={() => setPage((current) => Math.max(0, current - 1))}
                >
                  <ChevronLeft strokeWidth={2.2} aria-hidden="true" />
                  Назад
                </Button>
                <Button
                  variant="muted"
                  size="sm"
                  className="disabled:bg-subtle disabled:text-faint disabled:opacity-100 hover:bg-accent hover:text-accent-foreground [&_svg]:size-[15px]"
                  disabled={lastShown >= total}
                  onClick={() => setPage((current) => current + 1)}
                >
                  Дальше
                  <ChevronRight strokeWidth={2.2} aria-hidden="true" />
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      )}

      <ExpenseDetailDialog
        expenseId={selectedId}
        groupId={groupId}
        open={Boolean(selectedId)}
        onOpenChange={(next) => {
          if (!next) setSelectedId(undefined);
        }}
      />
    </div>
  );
}

interface PeriodCapsuleProps {
  dateFrom: string;
  dateTo: string;
  onDateFromChange: (value: string) => void;
  onDateToChange: (value: string) => void;
}

/** Подпись капсулы: «Период», пока диапазон пуст, иначе — сам диапазон. */
function periodLabel(dateFrom: string, dateTo: string): string {
  if (dateFrom && dateTo) return `${formatDateShort(dateFrom)} — ${formatDateShort(dateTo)}`;
  if (dateFrom) return `с ${formatDateShort(dateFrom)}`;
  if (dateTo) return `по ${formatDateShort(dateTo)}`;
  return "Период";
}

/**
 * Период — такая же капсула, как остальные фильтры: пока он не задан, это одно
 * слово с шевроном, а два поля дат живут в поповере. Два видимых `input[date]`
 * в строке фильтров занимали втрое больше места и в пустом виде читались как
 * «дд.мм.гггг — дд.мм.гггг».
 */
function PeriodCapsule({
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
}: PeriodCapsuleProps) {
  const active = Boolean(dateFrom) || Boolean(dateTo);

  return (
    <div
      className={cn(
        "inline-flex h-[46px] shrink-0 items-center rounded-full transition-colors",
        active ? "bg-accent text-accent-foreground" : "bg-card text-muted-foreground shadow-flat",
      )}
    >
      <Popover>
        <PopoverTrigger
          className={cn(
            "inline-flex h-[46px] items-center gap-[9px] rounded-full px-[18px] text-[15px] outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
            active
              ? "pr-2 font-semibold text-accent-foreground"
              : "font-medium text-muted-foreground hover:text-foreground",
          )}
          aria-label={
            active ? `Период: ${periodLabel(dateFrom, dateTo)}` : "Фильтр по периоду"
          }
        >
          <CalendarRange
            className={cn("size-4 shrink-0", active ? "text-accent-foreground" : "text-dim")}
            aria-hidden="true"
          />
          <span className={active ? "tabular-nums-money" : undefined}>
            {periodLabel(dateFrom, dateTo)}
          </span>
          {active ? null : (
            <ChevronDown
              className="size-[15px] shrink-0 text-dim"
              strokeWidth={2.2}
              aria-hidden="true"
            />
          )}
        </PopoverTrigger>

        <PopoverContent align="start" className="w-[264px] rounded-field p-4">
          <div className="flex flex-col gap-3">
            <label className="flex flex-col gap-1.5">
              <span className="text-[13px] font-semibold text-muted-foreground">С даты</span>
              <input
                type="date"
                value={dateFrom}
                max={dateTo || undefined}
                onChange={(event) => onDateFromChange(event.target.value)}
                className="h-11 w-full rounded-field border-0 bg-subtle px-3.5 text-[15px] text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring tabular-nums-money"
              />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-[13px] font-semibold text-muted-foreground">По дату</span>
              <input
                type="date"
                value={dateTo}
                min={dateFrom || undefined}
                onChange={(event) => onDateToChange(event.target.value)}
                className="h-11 w-full rounded-field border-0 bg-subtle px-3.5 text-[15px] text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring tabular-nums-money"
              />
            </label>
          </div>
        </PopoverContent>
      </Popover>

      {active ? (
        <button
          type="button"
          onClick={() => {
            onDateFromChange("");
            onDateToChange("");
          }}
          aria-label="Сбросить период"
          className="mr-[14px] flex size-5 shrink-0 items-center justify-center rounded-full text-accent-foreground/70 transition-colors hover:text-accent-foreground"
        >
          <X className="size-[15px]" strokeWidth={2.4} aria-hidden="true" />
        </button>
      ) : null}
    </div>
  );
}

interface FilterCapsuleProps {
  value: string;
  onValueChange: (value: string) => void;
  label: string;
  clearLabel: string;
  children: ReactNode;
}

/**
 * Один фильтр-капсула. Выбранное значение красится в зелёную плашку и получает
 * крестик, пустое — остаётся белой капсулой с шевроном. Крестик живёт рядом с
 * триггером, а не внутри него: кнопка внутри кнопки — сломанная семантика.
 */
function FilterCapsule({
  value,
  onValueChange,
  label,
  clearLabel,
  children,
}: FilterCapsuleProps) {
  const active = value !== ANY;

  return (
    <div
      className={cn(
        "inline-flex h-[46px] shrink-0 items-center rounded-full transition-colors",
        active
          ? "bg-accent text-accent-foreground hover:bg-accent-hover"
          : "bg-card text-muted-foreground shadow-flat",
      )}
    >
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger
          aria-label={label}
          className={cn(
            "h-[46px] w-auto gap-[9px] rounded-full bg-transparent px-[18px] text-[15px]",
            active
              ? "pr-2 font-semibold text-accent-foreground [&>svg]:hidden"
              : "font-medium text-muted-foreground",
          )}
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>{children}</SelectContent>
      </Select>

      {active ? (
        <button
          type="button"
          onClick={() => onValueChange(ANY)}
          aria-label={clearLabel}
          className="mr-[14px] flex size-5 shrink-0 items-center justify-center rounded-full text-accent-foreground/70 transition-colors hover:text-accent-foreground"
        >
          <X className="size-[15px]" strokeWidth={2.4} aria-hidden="true" />
        </button>
      ) : null}
    </div>
  );
}
