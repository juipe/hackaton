import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { DebtTransferList } from "@/components/balances/DebtTransferList";
import { makeTransfer, makeUser } from "@/test/factories";

/**
 * Суммы отображаются по-русски: разряды разделяет неразрывный пробел U+00A0,
 * копейки — запятая, знак «₽» стоит после числа за таким же пробелом. В коде он
 * записан экранированным, иначе его не отличить от обычного.
 */
const NBSP = "\u00A0";

const ME = makeUser({ id: "user-1", name: "Саша" });
const OLYA = makeUser({ id: "user-2", name: "Оля" });
const KOSTYA = makeUser({ id: "user-3", name: "Костя" });

function rows(): string[] {
  return screen.getAllByRole("listitem").map((item) => item.textContent ?? "");
}

describe("DebtTransferList", () => {
  it("ставит читателя первым в схеме, когда должен он", () => {
    render(
      <DebtTransferList
        transfers={[makeTransfer(ME, OLYA, 4000)]}
        currency="RUB"
        currentUserId={ME.id}
      />,
    );

    expect(rows()[0]).toContain("Вы → Оля");
    expect(rows()[0]).toContain(`40,00${NBSP}₽`);
  });

  it("ставит читателя вторым в схеме, когда должны ему", () => {
    render(
      <DebtTransferList
        transfers={[makeTransfer(OLYA, ME, 4000)]}
        currency="RUB"
        currentUserId={ME.id}
      />,
    );

    expect(rows()[0]).toContain("Оля → вы");
  });

  it("называет обоих, когда долг не касается читателя", () => {
    const { container } = render(
      <DebtTransferList
        transfers={[makeTransfer(OLYA, KOSTYA, 4000)]}
        currency="RUB"
        currentUserId={ME.id}
      />,
    );

    expect(rows()[0]).toContain("Оля → Костя");
    // Зелёный и красный закреплены только за собственной стороной читателя.
    expect(container.querySelector(".text-positive")).toBeNull();
    expect(container.querySelector(".text-negative")).toBeNull();
  });

  it("показывает сумму в рублях с русской типографикой", () => {
    render(
      <DebtTransferList
        transfers={[makeTransfer(ME, OLYA, 123_456)]}
        currency="RUB"
        currentUserId={ME.id}
      />,
    );

    expect(rows()[0]).toContain(`1${NBSP}234,56${NBSP}₽`);
  });

  it("предлагает действие только при переданном обработчике и возвращает перевод", async () => {
    const user = userEvent.setup();
    const onSettle = vi.fn();
    const transfer = makeTransfer(ME, OLYA, 4000);

    const { rerender } = render(
      <DebtTransferList transfers={[transfer]} currency="RUB" currentUserId={ME.id} />,
    );
    expect(screen.queryByRole("button")).toBeNull();

    rerender(
      <DebtTransferList
        transfers={[transfer]}
        currency="RUB"
        currentUserId={ME.id}
        onSettle={onSettle}
      />,
    );

    await user.click(screen.getByRole("button", { name: /рассчитаться/i }));
    expect(onSettle).toHaveBeenCalledWith(transfer);
  });

  it("зовёт платить по своему долгу и погашать чужой", () => {
    render(
      <DebtTransferList
        transfers={[
          makeTransfer(ME, OLYA, 4000),
          makeTransfer(OLYA, ME, 2500),
          makeTransfer(OLYA, KOSTYA, 1500),
        ]}
        currency="RUB"
        currentUserId={ME.id}
        onSettle={vi.fn()}
      />,
    );

    const labels = screen
      .getAllByRole("button")
      .map((button) => button.textContent ?? "");
    expect(labels).toEqual(["Рассчитаться", "Погасить", "Погасить"]);
  });

  it("показывает пустое состояние, заголовок которого можно переопределить", () => {
    const { rerender } = render(
      <DebtTransferList transfers={[]} currency="RUB" currentUserId={ME.id} />,
    );
    expect(screen.getByText("Все в расчёте")).toBeInTheDocument();

    rerender(
      <DebtTransferList
        transfers={[]}
        currency="RUB"
        currentUserId={ME.id}
        emptyLabel="Рекомендованных переводов нет"
      />,
    );
    expect(screen.getByText("Рекомендованных переводов нет")).toBeInTheDocument();
  });
});
