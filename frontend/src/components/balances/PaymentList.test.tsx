import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PaymentList } from "@/components/balances/PaymentList";
import { makePayment, makeUser } from "@/test/factories";

/** Разряды разделяет неразрывный пробел, копейки — запятая, «₽» стоит после. */
const NBSP = " ";

const ME = makeUser({ id: "user-1", name: "Саша" });
const OLYA = makeUser({ id: "user-2", name: "Оля" });
const KOSTYA = makeUser({ id: "user-3", name: "Костя" });

function rows(): string[] {
  return screen.getAllByRole("listitem").map((item) => item.textContent ?? "");
}

describe("PaymentList", () => {
  it("ставит читателя первым, когда платил он", () => {
    render(
      <PaymentList
        payments={[makePayment(ME, OLYA, 4000)]}
        currency="RUB"
        currentUserId={ME.id}
      />,
    );

    expect(rows()[0]).toContain("Вы → Оля");
    expect(rows()[0]).toContain(`40,00${NBSP}₽`);
  });

  it("ставит читателя вторым, когда платили ему", () => {
    render(
      <PaymentList
        payments={[makePayment(OLYA, ME, 4000)]}
        currency="RUB"
        currentUserId={ME.id}
      />,
    );

    expect(rows()[0]).toContain("Оля → вы");
  });

  it("показывает заметку рядом с датой перевода", () => {
    render(
      <PaymentList
        payments={[makePayment(OLYA, KOSTYA, 150000, { note: "за такси" })]}
        currency="RUB"
        currentUserId={ME.id}
      />,
    );

    expect(rows()[0]).toContain("за такси");
  });

  it("объясняет пустой список, а не оставляет дыру", () => {
    render(<PaymentList payments={[]} currency="RUB" currentUserId={ME.id} />);

    expect(screen.getByText("Переводов пока не было")).toBeInTheDocument();
  });
});
