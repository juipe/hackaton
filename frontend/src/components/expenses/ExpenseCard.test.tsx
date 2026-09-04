import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ExpenseCard } from "@/components/expenses/ExpenseCard";
import { makeCategory, makeExpense, makeUser } from "@/test/factories";

const OLYA = makeUser({ id: "user-1", name: "Оля" });
const SASHA = makeUser({ id: "user-2", name: "Саша" });
const KOSTYA = makeUser({ id: "user-3", name: "Костя" });
const OUTSIDER = makeUser({ id: "user-9", name: "Жора" });

/** 120,00 ₽ заплатила Оля, делят на троих: по 40,00 ₽. */
function groceries(viewerId: string) {
  return makeExpense({
    title: "Пятёрочка",
    amountCents: 12_000,
    payer: OLYA,
    participants: [OLYA, SASHA, KOSTYA],
    viewerId,
  });
}

describe("ExpenseCard", () => {
  it("tells the payer what they are owed", () => {
    render(<ExpenseCard expense={groceries(OLYA.id)} currentUserId={OLYA.id} />);

    expect(screen.getByText("вам должны 80,00 ₽")).toBeInTheDocument();
    expect(screen.getByText(/Плательщик: вы/)).toBeInTheDocument();
  });

  it("tells a participant what they owe", () => {
    render(<ExpenseCard expense={groceries(SASHA.id)} currentUserId={SASHA.id} />);

    expect(screen.getByText("вы должны 40,00 ₽")).toBeInTheDocument();
    expect(screen.getByText(/Плательщик: Оля/)).toBeInTheDocument();
  });

  it("shows the same expense differently to the payer and to a participant", () => {
    const expense = groceries(OLYA.id);

    const { unmount } = render(<ExpenseCard expense={expense} currentUserId={OLYA.id} />);
    expect(screen.getByText("вам должны 80,00 ₽")).toBeInTheDocument();
    expect(screen.queryByText(/вы должны/)).not.toBeInTheDocument();
    unmount();

    // Same object, only the reader changed — the impact line must follow the
    // reader, not the `my_*` fields the payer's request happened to produce.
    render(<ExpenseCard expense={expense} currentUserId={SASHA.id} />);
    expect(screen.getByText("вы должны 40,00 ₽")).toBeInTheDocument();
    expect(screen.queryByText(/вам должны/)).not.toBeInTheDocument();
  });

  it("says so when the reader is not part of the expense", () => {
    render(<ExpenseCard expense={groceries(OUTSIDER.id)} currentUserId={OUTSIDER.id} />);

    expect(screen.getByText("вы не участвуете")).toBeInTheDocument();
  });

  it("says settled when someone paid exactly their own share", () => {
    const soloCoffee = makeExpense({
      title: "Кофе в «Симпл»",
      amountCents: 450,
      payer: OLYA,
      participants: [OLYA],
      viewerId: OLYA.id,
    });

    render(<ExpenseCard expense={soloCoffee} currentUserId={OLYA.id} />);

    expect(screen.getByText("ровно ваша доля")).toBeInTheDocument();
  });

  it("always shows the full amount in roubles, with the reader's own share beside it", () => {
    const dinner = makeExpense({
      title: "Ресторан «Паштет»",
      amountCents: 123_456,
      currency: "RUB",
      payer: SASHA,
      participants: [OLYA, SASHA],
      viewerId: OLYA.id,
    });

    render(<ExpenseCard expense={dinner} currentUserId={OLYA.id} />);

    expect(screen.getByText("1 234,56 ₽")).toBeInTheDocument();
    expect(screen.getByText("вы должны 617,28 ₽")).toBeInTheDocument();
  });

  // Дата ушла в заголовок дня, который рисует список; в самой строке вторая
  // строчка теперь отвечает на «кто платил и за что».
  it("puts the payer and the category on the secondary line", () => {
    const taxi = makeExpense({
      title: "Такси до Сбер-центра",
      amountCents: 52_000,
      payer: KOSTYA,
      participants: [OLYA, KOSTYA],
      viewerId: OLYA.id,
      category: makeCategory({ name: "Транспорт", slug: "transport", icon: "Car" }),
    });

    render(<ExpenseCard expense={taxi} currentUserId={OLYA.id} />);

    expect(screen.getByText("Плательщик: Костя · Транспорт")).toBeInTheDocument();
  });

  it("becomes a labelled button only when it can be opened", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const expense = groceries(OLYA.id);

    const { unmount } = render(<ExpenseCard expense={expense} currentUserId={OLYA.id} />);
    expect(screen.queryByRole("button")).toBeNull();
    unmount();

    render(<ExpenseCard expense={expense} currentUserId={OLYA.id} onSelect={onSelect} />);
    await user.click(screen.getByRole("button", { name: "Открыть расход «Пятёрочка»" }));

    expect(onSelect).toHaveBeenCalledWith(expense);
  });
});
