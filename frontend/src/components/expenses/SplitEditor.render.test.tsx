/** What the split maths looks like to somebody actually typing into the form. */

import { useState } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { SplitEditor } from "@/components/expenses/SplitEditor";
import { makeMembers } from "@/test/factories";
import type { SplitMode } from "@/types/api";

const MEMBERS = makeMembers(["Оля", "Саша", "Костя"]);
const PARTICIPANT_IDS = MEMBERS.map((member) => member.user.id);

/** The editor is controlled, so the test owns the row state the way the form does. */
function Harness({
  mode,
  amountCents = 20_000,
  initialRows = {},
}: {
  mode: SplitMode;
  amountCents?: number;
  initialRows?: Record<string, string>;
}) {
  const [rows, setRows] = useState<Record<string, string>>(initialRows);
  return (
    <SplitEditor
      mode={mode}
      amountCents={amountCents}
      currency="RUB"
      members={MEMBERS}
      participantIds={PARTICIPANT_IDS}
      rows={rows}
      onRowsChange={setRows}
      payerId={PARTICIPANT_IDS[0]}
    />
  );
}

/**
 * A member's name appears twice per row — once in the avatar's screen-reader
 * label and once as the visible name — so the row is found from the first match
 * rather than by asserting on a unique name node.
 */
function row(name: string): HTMLElement {
  const item = screen.getAllByText(name)[0]?.closest("li");
  if (!item) throw new Error(`No row rendered for ${name}`);
  return item;
}

describe("SplitEditor — percentage mode", () => {
  it("shows what each percentage is worth as it is typed", async () => {
    const user = userEvent.setup();
    render(<Harness mode="percentage" />);

    await user.type(screen.getByLabelText("Процент: Оля"), "50");
    await user.type(screen.getByLabelText("Процент: Саша"), "30");
    await user.type(screen.getByLabelText("Процент: Костя"), "20");

    expect(within(row("Оля")).getByText("100,00 ₽")).toBeInTheDocument();
    expect(within(row("Саша")).getByText("60,00 ₽")).toBeInTheDocument();
    expect(within(row("Костя")).getByText("40,00 ₽")).toBeInTheDocument();
  });

  it("confirms the split adds up once the percentages total 100", async () => {
    const user = userEvent.setup();
    render(<Harness mode="percentage" />);

    await user.type(screen.getByLabelText("Процент: Оля"), "50");
    await user.type(screen.getByLabelText("Процент: Саша"), "30");
    await user.type(screen.getByLabelText("Процент: Костя"), "20");

    expect(
      screen.getByText(/Сумма сходится: 200,00 ₽, в делении 3 человека/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Сумма процентов/)).not.toBeInTheDocument();
  });

  it("says the percentages must total 100% when they do not", async () => {
    const user = userEvent.setup();
    render(<Harness mode="percentage" />);

    await user.type(screen.getByLabelText("Процент: Оля"), "50");
    await user.type(screen.getByLabelText("Процент: Саша"), "30");
    await user.type(screen.getByLabelText("Процент: Костя"), "10");

    expect(screen.getByText(/Сумма процентов должна быть 100%/)).toBeInTheDocument();
    // Every row still shows its worth, so the wrong one is easy to find.
    expect(within(row("Костя")).getByText("20,00 ₽")).toBeInTheDocument();
  });

  it("reports the running total so the user can see how far off they are", async () => {
    const user = userEvent.setup();
    render(<Harness mode="percentage" />);

    await user.type(screen.getByLabelText("Процент: Оля"), "50");
    await user.type(screen.getByLabelText("Процент: Саша"), "30");
    await user.type(screen.getByLabelText("Процент: Костя"), "10");

    expect(screen.getByText(/сейчас 90%/)).toBeInTheDocument();
    expect(screen.getByText(/180,00 ₽/)).toBeInTheDocument();
  });
});

describe("SplitEditor — other modes", () => {
  it("splits equally with no inputs to fill in", () => {
    render(<Harness mode="equal" amountCents={1000} />);

    expect(within(row("Оля")).getByText("3,34 ₽")).toBeInTheDocument();
    expect(within(row("Саша")).getByText("3,33 ₽")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Процент:/)).not.toBeInTheDocument();
  });

  it("marks who paid", () => {
    render(<Harness mode="equal" amountCents={1000} />);

    expect(within(row("Оля")).getByText("Плательщик")).toBeInTheDocument();
    expect(within(row("Саша")).queryByText("Плательщик")).not.toBeInTheDocument();
  });

  it("tells the user how much of an exact split is still unassigned", async () => {
    const user = userEvent.setup();
    render(<Harness mode="exact" amountCents={12_000} />);

    await user.type(screen.getByLabelText("Точная сумма: Оля"), "80");

    expect(
      screen.getByText(/Сумма частей должна совпадать с общей суммой/),
    ).toBeInTheDocument();
    expect(screen.getByText(/осталось распределить 40,00 ₽/)).toBeInTheDocument();
  });

  it("accepts a comma as the decimal separator in an exact amount", async () => {
    const user = userEvent.setup();
    render(<Harness mode="exact" amountCents={1000} />);

    await user.type(screen.getByLabelText("Точная сумма: Оля"), "3,34");
    await user.type(screen.getByLabelText("Точная сумма: Саша"), "3,33");
    await user.type(screen.getByLabelText("Точная сумма: Костя"), "3,33");

    expect(
      screen.getByText(/Сумма сходится: 10,00 ₽, в делении 3 человека/),
    ).toBeInTheDocument();
  });

  it("steps share counts with the plus and minus buttons", async () => {
    const user = userEvent.setup();
    render(
      <Harness
        mode="shares"
        amountCents={1000}
        initialRows={{ "user-1": "1", "user-2": "1", "user-3": "1" }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Добавить долю: Оля" }));

    expect(screen.getByLabelText("Доли: Оля")).toHaveValue("2");
    expect(within(row("Оля")).getByText("5,00 ₽")).toBeInTheDocument();
    expect(within(row("Саша")).getByText("2,50 ₽")).toBeInTheDocument();
  });

  it("never lets a share count go below zero", async () => {
    const user = userEvent.setup();
    render(
      <Harness
        mode="shares"
        amountCents={1000}
        initialRows={{ "user-1": "1", "user-2": "1", "user-3": "1" }}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Убрать долю: Оля" }));
    await user.click(screen.getByRole("button", { name: "Убрать долю: Оля" }));

    expect(screen.getByLabelText("Доли: Оля")).toHaveValue("0");
  });

  it("подводит итог: сколько распределено из общей суммы", () => {
    render(<Harness mode="equal" amountCents={20_000} />);

    expect(screen.getByText("Распределено")).toBeInTheDocument();
    expect(screen.getByText(/из 200,00 ₽/)).toBeInTheDocument();
  });

  it("asks for an amount before promising any shares", () => {
    render(<Harness mode="equal" amountCents={0} />);

    expect(
      screen.getByText("Укажите сумму выше — и появятся доли каждого."),
    ).toBeInTheDocument();
  });
});
