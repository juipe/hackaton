import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { GroupSummaryHeader } from "@/components/groups/GroupSummaryHeader";
import { makeGroup } from "@/test/factories";
import type { Group } from "@/types/api";

function renderHeader(group: Group) {
  return render(
    <MemoryRouter>
      <GroupSummaryHeader group={group} />
    </MemoryRouter>,
  );
}

describe("GroupSummaryHeader", () => {
  it("даёт владельцу вход в настройки группы", () => {
    const group = makeGroup({ id: "g-flat", my_role: "owner" });
    renderHeader(group);

    expect(screen.getByRole("link", { name: "Настройки группы" })).toHaveAttribute(
      "href",
      "/groups/g-flat/settings",
    );
    expect(screen.getByText("Владелец")).toBeInTheDocument();
  });

  /**
   * Страница настроек — единственный путь рядового участника к составу группы и
   * к кнопке «Выйти из группы», поэтому ссылка есть у всех; владельцу меняется
   * только подпись и бейдж.
   */
  it("оставляет участнику ту же ссылку — на состав группы", () => {
    const group = makeGroup({ id: "g-flat", my_role: "member" });
    renderHeader(group);

    expect(screen.getByRole("link", { name: "Участники группы" })).toHaveAttribute(
      "href",
      "/groups/g-flat/settings",
    );
    expect(screen.queryByText("Владелец")).not.toBeInTheDocument();
  });
});
