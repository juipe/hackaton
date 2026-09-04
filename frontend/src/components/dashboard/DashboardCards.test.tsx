import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { MonthlyMiniChart } from "@/components/dashboard/MonthlyMiniChart";
import { SummaryCards } from "@/components/dashboard/SummaryCards";
import type { DashboardGroupSummary, DashboardSummary, SpendingOverTime } from "@/types/api";

const MONTHS: SpendingOverTime = {
  currency: "RUB",
  items: [
    { month: "2026-05", label: "May 2026", amount_cents: 1_000_00, your_share_cents: 0 },
    { month: "2026-06", label: "Jun 2026", amount_cents: 4_000_00, your_share_cents: 0 },
    { month: "2026-07", label: "Jul 2026", amount_cents: 2_000_00, your_share_cents: 0 },
    { month: "2026-08", label: "Aug 2026", amount_cents: 3_000_00, your_share_cents: 0 },
    { month: "2026-09", label: "Sep 2026", amount_cents: 0, your_share_cents: 0 },
  ],
};

const GROUPS: DashboardGroupSummary[] = [
  {
    group_id: "g-flat",
    name: "Квартира на Вайнера",
    currency: "RUB",
    net_cents: 39_730_00,
    total_spending_cents: 141_400_00,
    your_share_cents: 58_670_00,
    member_count: 3,
  },
  {
    group_id: "g-hack",
    name: "Хакатон Сбера",
    currency: "RUB",
    net_cents: -6_240_00,
    total_spending_cents: 38_900_00,
    your_share_cents: 11_280_00,
    member_count: 4,
  },
  {
    group_id: "g-raft",
    name: "Сплав по Чусовой",
    currency: "RUB",
    net_cents: -1_000_00,
    total_spending_cents: 34_480_00,
    your_share_cents: 7_240_00,
    member_count: 5,
  },
];

function makeSummary(overrides: Partial<DashboardSummary> = {}): DashboardSummary {
  return {
    you_owe_cents: 7_240_00,
    owed_to_you_cents: 45_620_00,
    net_cents: 38_380_00,
    total_spending_cents: 214_780_00,
    your_paid_cents: 0,
    your_share_cents: 0,
    group_count: 3,
    expense_count: 63,
    currency: "RUB",
    groups: GROUPS,
    ...overrides,
  };
}

function renderSummary(summary: DashboardSummary) {
  return render(
    <MemoryRouter>
      <SummaryCards summary={summary} periodLabel="за всё время" monthly={MONTHS} />
    </MemoryRouter>,
  );
}

describe("MonthlyMiniChart", () => {
  it("подписывает месяцы по-русски и объявляет суммы скринридеру", () => {
    const { container } = render(<MonthlyMiniChart data={MONTHS} />);

    const chart = screen.getByRole("img");
    expect(chart).toHaveAccessibleName(/май —/);
    expect(chart).toHaveAccessibleName(/сент —/);
    expect(container.textContent).toContain("июнь");
    // Локаль добавляет точку к сокращённому месяцу, в макете её нет.
    expect(container.textContent).not.toContain("авг.");
  });

  it("красит самый дорогой месяц брендовым зелёным, остальные — приглушённым", () => {
    const { container } = render(<MonthlyMiniChart data={MONTHS} />);

    const bars = Array.from(container.querySelectorAll("div[style]"));
    expect(bars).toHaveLength(5);
    expect(bars.filter((bar) => bar.className.includes("bg-primary"))).toHaveLength(1);
    expect(bars[1].className).toContain("bg-primary");
    // Месяц без расходов остаётся видимой полоской, а не исчезает.
    expect(bars[4].getAttribute("style")).toContain("height: 6%");
  });

  it("ничего не рисует, пока данных нет", () => {
    const { container } = render(<MonthlyMiniChart data={{ currency: "RUB", items: [] }} />);

    expect(container).toBeEmptyDOMElement();
  });
});

describe("SummaryCards", () => {
  it("склоняет пояснение под итоговым балансом", () => {
    renderSummary(makeSummary());

    expect(screen.getByText("В целом вам должны — по 3 группам сразу.")).toBeInTheDocument();
  });

  it("сообщает, что расчёты закрыты, когда баланс нулевой", () => {
    renderSummary(makeSummary({ net_cents: 0, you_owe_cents: 0, owed_to_you_cents: 0 }));

    expect(screen.getByText("Все расчёты закрыты.")).toBeInTheDocument();
  });

  it("ведёт «Погасить долги» в группу с самым большим долгом", () => {
    renderSummary(makeSummary());

    expect(screen.getByRole("link", { name: "Погасить долги" })).toHaveAttribute(
      "href",
      "/groups/g-hack",
    );
  });

  it("ведёт «Упростить» в самую многолюдную группу", () => {
    renderSummary(makeSummary());

    expect(screen.getByRole("link", { name: "Упростить" })).toHaveAttribute(
      "href",
      "/groups/g-raft",
    );
  });

  it("считает расходы за период вместе с их количеством", () => {
    renderSummary(makeSummary());

    expect(screen.getByText("63 расхода · за всё время")).toBeInTheDocument();
  });

  // Упавший запрос по месяцам раньше просто убирал график из карточки: человек
  // видел обрезанный низ и не знал, что данных не хватает.
  it("говорит вслух, что график по месяцам не загрузился", () => {
    render(
      <MemoryRouter>
        <SummaryCards summary={makeSummary()} periodLabel="за всё время" isMonthlyError />
      </MemoryRouter>,
    );

    expect(screen.getByText("Не удалось загрузить график по месяцам")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /Расходы по месяцам/ })).not.toBeInTheDocument();
  });
});
