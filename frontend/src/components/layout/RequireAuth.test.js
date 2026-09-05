import { jsxs as _jsxs, jsx as _jsx } from "react/jsx-runtime";
import { screen, waitFor } from "@testing-library/react";
import { Route, Routes, useSearchParams } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { RequireAuth } from "@/components/layout/RequireAuth";
import { errorResponse, jsonResponse, stubFetch } from "@/test/fetch";
import { renderWithProviders } from "@/test/render";
const OLYA = {
    id: "user-1",
    name: "Оля",
    email: "olya@skladchina.ru",
    monthly_budget_cents: null,
};
/** Подменяет экран входа, чтобы можно было проверить адрес возврата. */
function LoginProbe() {
    const [params] = useSearchParams();
    return _jsxs("p", { "data-testid": "login", children: ["next=", params.get("next")] });
}
function renderGuarded(route) {
    return renderWithProviders(_jsxs(Routes, { children: [_jsx(Route, { path: "/login", element: _jsx(LoginProbe, {}) }), _jsx(Route, { path: "/groups/:groupId", element: _jsx(RequireAuth, { children: _jsx("p", { children: "\u0420\u0430\u0441\u0445\u043E\u0434\u044B \u0433\u0440\u0443\u043F\u043F\u044B \u00AB\u041A\u0432\u0430\u0440\u0442\u0438\u0440\u0430 \u043D\u0430 \u0412\u0430\u0439\u043D\u0435\u0440\u0430\u00BB" }) }) })] }), { route });
}
describe("RequireAuth", () => {
    it("отправляет анонимного гостя на вход и запоминает, куда он шёл", async () => {
        stubFetch(() => errorResponse(401, "Требуется вход"));
        renderGuarded("/groups/group-1?tab=expenses");
        await waitFor(() => expect(screen.getByTestId("login")).toBeInTheDocument());
        expect(screen.getByTestId("login")).toHaveTextContent("next=/groups/group-1?tab=expenses");
        expect(screen.queryByText("Расходы группы «Квартира на Вайнера»")).not.toBeInTheDocument();
    });
    it("показывает защищённый экран вошедшему пользователю", async () => {
        stubFetch(() => jsonResponse(OLYA));
        renderGuarded("/groups/group-1");
        await waitFor(() => expect(screen.getByText("Расходы группы «Квартира на Вайнера»")).toBeInTheDocument());
        expect(screen.queryByTestId("login")).not.toBeInTheDocument();
    });
    it("ждёт ответа о сессии и не мигает редиректом на вход", () => {
        stubFetch(() => jsonResponse(OLYA));
        renderGuarded("/groups/group-1");
        // На этом тике ответ ещё не пришёл: ни один из исходов не должен быть отрисован.
        expect(screen.queryByTestId("login")).not.toBeInTheDocument();
        expect(screen.queryByText("Расходы группы «Квартира на Вайнера»")).not.toBeInTheDocument();
    });
});
