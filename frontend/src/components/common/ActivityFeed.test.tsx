import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ActivityFeed } from "@/components/common/ActivityFeed";
import { ApiError } from "@/lib/api";
import { makeActivity, makeUser } from "@/test/factories";

const OLYA = makeUser({ id: "user-1", name: "Оля" });
const SASHA = makeUser({ id: "user-2", name: "Саша" });
const KOSTYA = makeUser({ id: "user-3", name: "Костя" });

/** U+00A0 — the money formatter never lets the sign wrap away from the number. */
const NBSP = "\u00A0";

function sentences(): string[] {
  return screen.getAllByRole("listitem").map((item) => item.textContent ?? "");
}

describe("ActivityFeed", () => {
  it("описывает событие безлично, без рода глагола", () => {
    render(
      <ActivityFeed
        activities={[
          makeActivity("expense_created", OLYA, {
            title: "Продукты",
            amount_cents: 7400,
          }),
          makeActivity("payment_created", SASHA, {
            from_name: "Саша",
            to_name: "Оля",
            amount_cents: 3500,
          }),
          makeActivity("member_joined", KOSTYA, {}, { group_name: "Квартира на Вайнера" }),
          makeActivity("group_updated", OLYA, {
            name: "Хакатон Сбера",
            changed: ["name", "description"],
          }),
          makeActivity("debt_simplified", OLYA, { before: 6, after: 3 }),
        ]}
      />,
    );

    const [expense, payment, joined, updated, simplified] = sentences();
    expect(expense).toContain(`Добавлен расход «Продукты» — 74,00${NBSP}₽`);
    expect(payment).toContain(`Перевод: Саша → Оля, 35,00${NBSP}₽`);
    expect(joined).toContain("Новый участник: Костя");
    expect(updated).toContain("Изменена группа «Хакатон Сбера» — название и описание");
    expect(simplified).toContain("Долги упрощены: 6 → 3 перевода");
  });

  it("различает уход из группы и исключение", () => {
    render(
      <ActivityFeed
        activities={[
          makeActivity(
            "member_removed",
            KOSTYA,
            { name: "Костя", left: true },
            { group_name: "Сплав по Чусовой" },
          ),
          makeActivity(
            "member_removed",
            OLYA,
            { name: "Жора" },
            { group_name: "Сплав по Чусовой" },
          ),
          makeActivity("group_created", OLYA, { name: "Хакатон Сбера" }),
          makeActivity("invite_created", OLYA, { invited_email: "zhora@skladchina.ru" }),
        ]}
      />,
    );

    const [left, removed, created, invited] = sentences();
    expect(left).toContain("Костя больше не в группе «Сплав по Чусовой»");
    expect(removed).toContain("Участник Жора удалён из группы «Сплав по Чусовой»");
    expect(created).toContain("Создана группа «Хакатон Сбера»");
    expect(invited).toContain("Приглашение отправлено: zhora@skladchina.ru");
  });

  it("уводит автора во вторую строку рядом со временем", () => {
    render(
      <ActivityFeed
        showGroup
        activities={[
          makeActivity(
            "expense_created",
            OLYA,
            { title: "Пицца на команду", amount_cents: 189000 },
            { group_name: "Хакатон Сбера" },
          ),
        ]}
      />,
    );

    const [expense] = sentences();
    expect(expense).toContain("Оля · ");
    expect(expense).toContain("· Хакатон Сбера");
    expect(expense).not.toContain("Оля добавила");
  });

  it("переживает пустую meta вместо того, чтобы печатать undefined", () => {
    render(
      <ActivityFeed
        activities={[
          makeActivity("expense_created", OLYA, {}),
          makeActivity("payment_created", SASHA, {}),
        ]}
      />,
    );

    for (const sentence of sentences()) {
      expect(sentence).not.toMatch(/undefined|null|NaN|\[object/);
    }
    expect(sentences()[0]).toContain("Добавлен расход без названия");
  });

  it("не красит суммы в ленте цветами баланса", () => {
    const { container } = render(
      <ActivityFeed
        activities={[
          makeActivity("expense_created", OLYA, {
            title: "Продукты",
            amount_cents: 7400,
          }),
        ]}
      />,
    );

    expect(container.querySelector(".text-positive")).toBeNull();
    expect(container.querySelector(".text-negative")).toBeNull();
  });

  it("выделяет названия и суммы внутри фразы", () => {
    render(
      <ActivityFeed
        activities={[
          makeActivity("expense_created", OLYA, {
            title: "Пятёрочка",
            amount_cents: 432000,
          }),
        ]}
      />,
    );

    const [row] = screen.getAllByRole("listitem");
    const bold = Array.from(row.querySelectorAll(".font-semibold")).map(
      (node) => node.textContent ?? "",
    );
    expect(bold).toContain("Пятёрочка");
    expect(bold).toContain(`4${NBSP}320,00${NBSP}₽`);
  });

  it("строит строку по новой сетке: плитка, квадратный аватар, приглушённая подпись", () => {
    render(
      <ActivityFeed
        showGroup
        activities={[
          makeActivity(
            "expense_created",
            OLYA,
            { title: "Пятёрочка", amount_cents: 432000 },
            { group_name: "Квартира на Вайнера" },
          ),
        ]}
      />,
    );

    const [row] = screen.getAllByRole("listitem");
    // Плитка с ховером, а не строка с разделителем.
    expect(row.className).toContain("rounded-tile");
    expect(row.className).toContain("hover:bg-subtle");
    expect(row.className).not.toContain("divide-y");

    // Аватар в ленте — скруглённый квадрат 38px, а не круг.
    const avatar = row.querySelector('[class*="rounded-chip"]');
    expect(avatar).not.toBeNull();
    expect(avatar?.className).toContain("size-[38px]");
    // Скругление перебивает круг из примитива, иначе строка вернётся к кружку:
    // `cn` знает нашу шкалу радиусов, поэтому rounded-full до DOM не доезжает.
    expect(avatar?.className).toContain("rounded-chip");
    expect(avatar?.className).not.toContain("rounded-full");

    // Текст 15px, подпись 13px приглушённым цветом.
    const [sentence, meta] = Array.from(row.querySelectorAll("p"));
    expect(sentence.className).toContain("text-[15px]");
    expect(sentence.textContent).toContain("Добавлен расход");
    expect(meta.className).toContain("text-[13px]");
    expect(meta.className).toContain("text-dim");
    expect(meta.textContent).toMatch(/^Оля · .+ · Квартира на Вайнера$/);
  });

  it("показывает скелетон во время загрузки, а не пустое состояние", () => {
    render(<ActivityFeed isLoading />);

    expect(screen.queryByRole("list")).toBeNull();
    expect(screen.queryByText("Пока ничего не происходило")).not.toBeInTheDocument();
  });

  it("показывает текст ошибки, если запрос не удался", () => {
    render(<ActivityFeed error={new ApiError(500, "Лента недоступна")} />);

    expect(screen.getByText("Лента недоступна")).toBeInTheDocument();
  });

  it("показывает переданный текст пустого состояния", () => {
    render(<ActivityFeed activities={[]} emptyLabel="Здесь пока пусто" />);

    expect(screen.getByText("Здесь пока пусто")).toBeInTheDocument();
    expect(
      screen.getByText("Здесь появятся расходы, переводы и новые участники."),
    ).toBeInTheDocument();
  });
});
