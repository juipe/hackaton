import { screen, waitFor } from "@testing-library/react";
import { Route, Routes, useSearchParams } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { RequireAuth } from "@/components/layout/RequireAuth";
import { errorResponse, jsonResponse, stubFetch } from "@/test/fetch";
import { renderWithProviders } from "@/test/render";
import type { UserPublic } from "@/types/api";

const OLYA: UserPublic = {
  id: "user-1",
  name: "Оля",
  email: "olya@skladchina.ru",
  monthly_budget_cents: null,
};

/** Подменяет экран входа, чтобы можно было проверить адрес возврата. */
function LoginProbe() {
  const [params] = useSearchParams();
  return <p data-testid="login">next={params.get("next")}</p>;
}

function renderGuarded(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginProbe />} />
      <Route
        path="/groups/:groupId"
        element={
          <RequireAuth>
            <p>Расходы группы «Квартира на Вайнера»</p>
          </RequireAuth>
        }
      />
    </Routes>,
    { route },
  );
}

describe("RequireAuth", () => {
  it("отправляет анонимного гостя на вход и запоминает, куда он шёл", async () => {
    stubFetch(() => errorResponse(401, "Требуется вход"));

    renderGuarded("/groups/group-1?tab=expenses");

    await waitFor(() => expect(screen.getByTestId("login")).toBeInTheDocument());
    expect(screen.getByTestId("login")).toHaveTextContent("next=/groups/group-1?tab=expenses");
    expect(
      screen.queryByText("Расходы группы «Квартира на Вайнера»"),
    ).not.toBeInTheDocument();
  });

  it("показывает защищённый экран вошедшему пользователю", async () => {
    stubFetch(() => jsonResponse(OLYA));

    renderGuarded("/groups/group-1");

    await waitFor(() =>
      expect(screen.getByText("Расходы группы «Квартира на Вайнера»")).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("login")).not.toBeInTheDocument();
  });

  it("ждёт ответа о сессии и не мигает редиректом на вход", () => {
    stubFetch(() => jsonResponse(OLYA));

    renderGuarded("/groups/group-1");

    // На этом тике ответ ещё не пришёл: ни один из исходов не должен быть отрисован.
    expect(screen.queryByTestId("login")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Расходы группы «Квартира на Вайнера»"),
    ).not.toBeInTheDocument();
  });
});
