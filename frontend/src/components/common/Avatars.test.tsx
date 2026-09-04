import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AvatarStack } from "@/components/common/AvatarStack";
import { GroupAvatar, groupInitials } from "@/components/common/GroupAvatar";

const TEAM = [
  { id: "user-1", name: "Оля" },
  { id: "user-2", name: "Саша" },
  { id: "user-3", name: "Костя" },
  { id: "user-4", name: "Максим" },
  { id: "user-5", name: "Жора" },
];

describe("groupInitials", () => {
  it("берёт первые буквы значимых слов, пропуская предлоги", () => {
    expect(groupInitials("Квартира на Вайнера")).toBe("КВ");
    expect(groupInitials("Сплав по Чусовой")).toBe("СЧ");
  });

  it("берёт два первых слова, когда предлогов нет", () => {
    expect(groupInitials("Хакатон Сбера")).toBe("ХС");
  });

  it("не спотыкается об односложные и пустые названия", () => {
    expect(groupInitials("Дом")).toBe("Д");
    expect(groupInitials("я и ты")).toBe("ЯИ");
    expect(groupInitials("   ")).toBe("?");
  });
});

describe("GroupAvatar", () => {
  it("подписан названием группы для скринридера", () => {
    render(<GroupAvatar group={{ id: "group-1", name: "Хакатон Сбера" }} />);

    expect(screen.getByRole("img", { name: "Хакатон Сбера" })).toHaveTextContent("ХС");
  });
});

describe("AvatarStack", () => {
  it("показывает max аватаров и остаток кружком «+N»", () => {
    render(<AvatarStack users={TEAM} max={3} />);

    expect(screen.getByText("+2")).toBeInTheDocument();
    expect(screen.getByText("Оля")).toBeInTheDocument();
    expect(screen.queryByText("Максим")).not.toBeInTheDocument();
  });

  it("обходится без «+N», когда все помещаются", () => {
    render(<AvatarStack users={TEAM.slice(0, 2)} max={3} />);

    expect(screen.queryByText(/^\+/)).not.toBeInTheDocument();
  });

  it("перечисляет всех участников в подписи стопки", () => {
    render(<AvatarStack users={TEAM.slice(0, 3)} max={2} />);

    expect(
      screen.getByRole("img", { name: "Оля, Саша и Костя" }),
    ).toBeInTheDocument();
  });

  it("ничего не рисует для пустого списка", () => {
    const { container } = render(<AvatarStack users={[]} />);

    expect(container).toBeEmptyDOMElement();
  });
});
