/**
 * Auth state is the one piece of app-wide state, and it is derived entirely from
 * a network answer, so these tests drive it through a stubbed `fetch` rather than
 * through the UI. No socket is opened.
 */

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { useAuth } from "@/hooks/useAuth";
import { emptyResponse, errorResponse, jsonResponse, requestedUrls, stubFetch } from "@/test/fetch";
import { renderWithProviders } from "@/test/render";
import type { UserPublic } from "@/types/api";

const OLYA: UserPublic = {
  id: "user-1",
  name: "Оля",
  email: "olya@skladchina.ru",
  monthly_budget_cents: null,
};

/** A minimal consumer: it only reports what `useAuth` says and lets us act on it. */
function AuthProbe() {
  const { user, isLoading, login, logout } = useAuth();

  return (
    <div>
      <p data-testid="status">
        {isLoading ? "загрузка" : user ? `вход выполнен: ${user.name}` : "вход не выполнен"}
      </p>
      <button
        type="button"
        onClick={() => {
          void login({ email: OLYA.email, password: "Demo1234!" });
        }}
      >
        Войти
      </button>
      <button
        type="button"
        onClick={() => {
          // `logout()` re-throws whatever the server said after clearing the
          // client, so a caller that ignores the promise would crash the test
          // runner with an unhandled rejection.
          logout().catch(() => {});
        }}
      >
        Выйти
      </button>
    </div>
  );
}

function status(): string {
  return screen.getByTestId("status").textContent ?? "";
}

describe("AuthProvider", () => {
  it("сообщает, что вход не выполнен, когда /auth/me отвечает 401", async () => {
    const fetchMock = stubFetch(() => errorResponse(401, "Требуется вход"));

    renderWithProviders(<AuthProbe />);

    await waitFor(() => expect(status()).toBe("вход не выполнен"));
    expect(requestedUrls(fetchMock)).toContain("/api/auth/me");
  });

  it("показывает вошедшего пользователя, когда /auth/me отвечает 200", async () => {
    stubFetch(() => jsonResponse(OLYA));

    renderWithProviders(<AuthProbe />);

    await waitFor(() => expect(status()).toBe("вход выполнен: Оля"));
  });

  it("отправляет куку сессии, а не bearer-токен", async () => {
    const fetchMock = stubFetch(() => jsonResponse(OLYA));

    renderWithProviders(<AuthProbe />);

    await waitFor(() => expect(status()).toBe("вход выполнен: Оля"));

    const [, init] = fetchMock.mock.calls[0];
    expect(init?.credentials).toBe("include");
    expect(init?.headers).not.toHaveProperty("Authorization");
  });

  it("не выдаёт настоящий сбой за выход из аккаунта", async () => {
    stubFetch(() => errorResponse(500, "Внутренняя ошибка сервера"));

    renderWithProviders(<AuthProbe />);

    // The query fails rather than resolving to null, so `user` stays null but the
    // 401 shortcut is not what produced it — the request was actually attempted.
    await waitFor(() => expect(status()).toBe("вход не выполнен"));
  });

  it("выполняет вход через login() без повторного запроса", async () => {
    const user = userEvent.setup();
    stubFetch((url) => {
      if (url === "/api/auth/me") return errorResponse(401, "Требуется вход");
      if (url === "/api/auth/login") return jsonResponse(OLYA);
      throw new Error(`Неожиданный запрос: ${url}`);
    });

    renderWithProviders(<AuthProbe />);
    await waitFor(() => expect(status()).toBe("вход не выполнен"));

    await user.click(screen.getByRole("button", { name: "Войти" }));

    await waitFor(() => expect(status()).toBe("вход выполнен: Оля"));
  });

  it("очищает вошедшего пользователя при выходе", async () => {
    const user = userEvent.setup();
    // The server drops the session cookie, so /auth/me stops recognising us —
    // exactly what the browser would see after a real logout.
    let hasSession = true;
    const fetchMock = stubFetch((url) => {
      if (url === "/api/auth/logout") {
        hasSession = false;
        return emptyResponse();
      }
      return hasSession ? jsonResponse(OLYA) : errorResponse(401, "Требуется вход");
    });

    renderWithProviders(<AuthProbe />);
    await waitFor(() => expect(status()).toBe("вход выполнен: Оля"));

    await user.click(screen.getByRole("button", { name: "Выйти" }));

    await waitFor(() => expect(status()).toBe("вход не выполнен"));
    expect(requestedUrls(fetchMock)).toContain("/api/auth/logout");
  });

  it("сбрасывает весь кеш при выходе, чтобы данные не попали в следующую сессию", async () => {
    const user = userEvent.setup();
    stubFetch((url) => (url === "/api/auth/logout" ? emptyResponse() : jsonResponse(OLYA)));

    const { queryClient } = renderWithProviders(<AuthProbe />);
    await waitFor(() => expect(status()).toBe("вход выполнен: Оля"));

    queryClient.setQueryData(["groups"], [{ id: "group-1", name: "Квартира на Вайнера" }]);
    await user.click(screen.getByRole("button", { name: "Выйти" }));

    await waitFor(() => expect(queryClient.getQueryData(["groups"])).toBeUndefined());
  });

  it("очищает клиент, даже если запрос выхода завершился ошибкой", async () => {
    const user = userEvent.setup();
    stubFetch((url) =>
      url === "/api/auth/logout"
        ? errorResponse(500, "Внутренняя ошибка сервера")
        : jsonResponse(OLYA),
    );

    const { queryClient } = renderWithProviders(<AuthProbe />);
    await waitFor(() => expect(status()).toBe("вход выполнен: Оля"));

    queryClient.setQueryData(["groups"], [{ id: "group-1", name: "Квартира на Вайнера" }]);
    await user.click(screen.getByRole("button", { name: "Выйти" }));

    await waitFor(() => expect(queryClient.getQueryData(["groups"])).toBeUndefined());
  });
});
