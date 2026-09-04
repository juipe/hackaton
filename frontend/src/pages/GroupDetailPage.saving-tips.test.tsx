/**
 * Saving Tips on the group Analytics tab.
 *
 * Only the group-scoping behaviour is new here — the card itself (states,
 * rendering, retry) is already covered by `SavingTipsCard.test.tsx`. This
 * file only proves the dashboard's `SavingTipsCard` is reused as-is on
 * `GroupDetailPage` and that it's wired to the *right* group.
 */

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { RequireAuth } from "@/components/layout/RequireAuth";
import GroupDetailPage from "@/pages/GroupDetailPage";
import {
  makeCategory,
  makeGroup,
  makeGroupBalances,
  makeMember,
  makeUser,
} from "@/test/factories";
import { errorResponse, jsonResponse, requestedUrls, stubFetch } from "@/test/fetch";
import { renderWithProviders } from "@/test/render";
import type { CategoryBreakdown, ExpensePage, SavingTipsResponse, SpendingOverTime } from "@/types/api";

const ALICE = makeUser({ id: "user-alice", name: "Алиса" });
const FAMILY = makeGroup({ id: "group-family", name: "Семья" });
const OTHER_GROUP_ID = "group-trip";

const TIPS: SavingTipsResponse = {
  tips: [
    { title: "Продукты — крупная категория", text: "Продукты — 100% расходов.", type: "data_driven" },
    { title: "Установите лимит", text: "Ограничьте необязательные покупки.", type: "generic" },
  ],
};

const EMPTY_CATEGORIES: CategoryBreakdown = { total_cents: 0, items: [] };
const EMPTY_OVER_TIME: SpendingOverTime = { currency: "RUB", items: [] };
const EMPTY_EXPENSE_PAGE: ExpensePage = { items: [], total: 0, limit: 1, offset: 0 };

/** Every endpoint `GroupDetailPage` reads on mount, answered with minimal data. */
function stubGroupPage(saving: (url: string) => Response = () => jsonResponse(TIPS)) {
  return stubFetch((url) => {
    if (url === "/api/auth/me") return jsonResponse(ALICE);
    if (url === `/api/groups/${FAMILY.id}`) return jsonResponse(FAMILY);
    if (url === `/api/groups/${FAMILY.id}/members`) return jsonResponse([makeMember({ user: ALICE })]);
    if (url === `/api/groups/${FAMILY.id}/balances`) {
      return jsonResponse(makeGroupBalances({ group_id: FAMILY.id, currency: FAMILY.currency }));
    }
    if (url === "/api/categories") return jsonResponse([makeCategory()]);
    if (url.startsWith(`/api/groups/${FAMILY.id}/activity`)) return jsonResponse([]);
    if (url === `/api/groups/${FAMILY.id}/payments`) return jsonResponse([]);
    if (url.startsWith(`/api/groups/${FAMILY.id}/expenses`)) return jsonResponse(EMPTY_EXPENSE_PAGE);
    if (url.startsWith("/api/dashboard/spending-by-category")) return jsonResponse(EMPTY_CATEGORIES);
    if (url.startsWith("/api/dashboard/spending-over-time")) return jsonResponse(EMPTY_OVER_TIME);
    if (url.startsWith("/api/dashboard/saving-tips")) return saving(url);
    return errorResponse(404, `Неожиданный запрос: ${url}`);
  });
}

function renderAnalyticsTab() {
  return renderWithProviders(
    <RequireAuth>
      <Routes>
        <Route path="/groups/:groupId" element={<GroupDetailPage />} />
      </Routes>
    </RequireAuth>,
    { route: `/groups/${FAMILY.id}?tab=analytics` },
  );
}

describe("GroupDetailPage — Советы по экономии на вкладке «Аналитика»", () => {
  it("показывает карточку советов на вкладке аналитики группы", async () => {
    stubGroupPage();

    renderAnalyticsTab();

    expect(await screen.findByText("Советы по экономии")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Сгенерировать советы/ })).toBeInTheDocument();
  });

  it("генерирует советы с group_id именно этой группы, а не всех расходов", async () => {
    const user = userEvent.setup();
    const fetchMock = stubGroupPage();

    renderAnalyticsTab();
    const button = await screen.findByRole("button", { name: /Сгенерировать советы/ });
    await user.click(button);

    await screen.findByText("Продукты — крупная категория");

    const url = requestedUrls(fetchMock).find((entry) =>
      entry.startsWith("/api/dashboard/saving-tips"),
    );
    expect(url).toContain(`group_id=${FAMILY.id}`);
    expect(url).toContain("period=all");
    expect(url).not.toContain(OTHER_GROUP_ID);
  });

  it("показывает ошибку, если группа недоступна для генерации советов", async () => {
    const user = userEvent.setup();
    stubGroupPage(() => errorResponse(403, "Вы не участник этой группы"));

    renderAnalyticsTab();
    const button = await screen.findByRole("button", { name: /Сгенерировать советы/ });
    await user.click(button);

    await waitFor(() =>
      expect(screen.getByText("Вы не участник этой группы")).toBeInTheDocument(),
    );
  });
});
