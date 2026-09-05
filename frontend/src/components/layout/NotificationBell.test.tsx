import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { NotificationBell } from "@/components/layout/NotificationBell";
import { emptyResponse, errorResponse, jsonResponse, stubFetch } from "@/test/fetch";
import { renderWithProviders } from "@/test/render";
import type { Notification } from "@/types/api";

/** `renderWithProviders` mounts `AuthProvider`, which fires its own `/auth/me` — keep
 * that request answered separately so it never eats into the notifications sequence. */
function withAuthStub(handler: (url: string) => Response | Promise<Response>) {
  return (url: string) => (url === "/api/auth/me" ? errorResponse(401, "Требуется вход") : handler(url));
}

function makeNotification(overrides: Partial<Notification> = {}): Notification {
  return {
    id: "notif-1",
    type: "debt_reminder",
    group_id: "group-1",
    group_name: "Квартира на Вайнера",
    expense_id: "expense-1",
    expense_title: "Ужин",
    payer_name: "Алиса",
    amount_due_cents: 125000,
    currency: "RUB",
    message: "Не забудьте вернуть Алисе 1250 ₽ за «Ужин» в группе «Квартира на Вайнера».",
    is_read: false,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

async function openPanel(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Уведомления" }));
}

// Opening the Radix popover involves its own position/animation-frame
// bookkeeping, which is measurably slower under jsdom than a real browser —
// the bell itself does nothing slow, so every interaction test below gets a
// longer budget rather than the suite's 5s default.
const INTERACTION_TIMEOUT = 20_000;

describe("NotificationBell", () => {
  it("рендерит колокольчик", () => {
    stubFetch(withAuthStub(() => jsonResponse([])));

    renderWithProviders(<NotificationBell />);

    expect(screen.getByRole("button", { name: "Уведомления" })).toBeInTheDocument();
  });

  it("показывает индикатор непрочитанных, когда есть непрочитанные", async () => {
    stubFetch(withAuthStub(() => jsonResponse([makeNotification({ is_read: false })])));

    renderWithProviders(<NotificationBell />);

    await waitFor(() =>
      expect(screen.getByTestId("notification-unread-dot")).toBeInTheDocument(),
    );
  });

  it("скрывает индикатор, когда всё уже прочитано", async () => {
    stubFetch(withAuthStub(() => jsonResponse([makeNotification({ is_read: true })])));

    renderWithProviders(<NotificationBell />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Уведомления" })).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("notification-unread-dot")).not.toBeInTheDocument();
  });

  it(
    "открывает и закрывает панель по клику",
    async () => {
      const user = userEvent.setup();
      stubFetch(withAuthStub(() => jsonResponse([makeNotification()])));

      renderWithProviders(<NotificationBell />);

      expect(screen.queryByText("Уведомления", { selector: "h2" })).not.toBeInTheDocument();

      await openPanel(user);
      expect(await screen.findByText("Уведомления", { selector: "h2" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "Уведомления" }));
      await waitFor(() =>
        expect(screen.queryByText("Уведомления", { selector: "h2" })).not.toBeInTheDocument(),
      );
    },
    INTERACTION_TIMEOUT,
  );

  it(
    "показывает загрузку, затем список уведомлений",
    async () => {
      const user = userEvent.setup();
      let resolveFetch: (response: Response) => void = () => {};
      stubFetch(
        withAuthStub(
          () =>
            new Promise<Response>((resolve) => {
              resolveFetch = resolve;
            }),
        ),
      );

      renderWithProviders(<NotificationBell />);
      await openPanel(user);

      expect(screen.getByTestId("notifications-loading")).toBeInTheDocument();

      resolveFetch(jsonResponse([makeNotification()]));

      await waitFor(() =>
        expect(screen.queryByTestId("notifications-loading")).not.toBeInTheDocument(),
      );
      expect(screen.getByText(/Не забудьте вернуть Алисе/)).toBeInTheDocument();
    },
    INTERACTION_TIMEOUT,
  );

  it(
    "показывает пустое состояние без уведомлений",
    async () => {
      const user = userEvent.setup();
      stubFetch(withAuthStub(() => jsonResponse([])));

      renderWithProviders(<NotificationBell />);
      await openPanel(user);

      expect(await screen.findByText("Пока нет уведомлений")).toBeInTheDocument();
    },
    INTERACTION_TIMEOUT,
  );

  it(
    "показывает состояние ошибки при сбое запроса",
    async () => {
      const user = userEvent.setup();
      stubFetch(withAuthStub(() => errorResponse(500, "Не удалось загрузить уведомления")));

      renderWithProviders(<NotificationBell />);
      await openPanel(user);

      expect(await screen.findByText("Не удалось загрузить уведомления")).toBeInTheDocument();
    },
    INTERACTION_TIMEOUT,
  );

  it(
    "отображает текст напоминания для нескольких уведомлений",
    async () => {
      const user = userEvent.setup();
      stubFetch(
        withAuthStub(() =>
          jsonResponse([
            makeNotification({ id: "notif-1", message: "Напоминание первое" }),
            makeNotification({ id: "notif-2", message: "Напоминание второе" }),
          ]),
        ),
      );

      renderWithProviders(<NotificationBell />);
      await openPanel(user);

      expect(await screen.findByText("Напоминание первое")).toBeInTheDocument();
      expect(screen.getByText("Напоминание второе")).toBeInTheDocument();
    },
    INTERACTION_TIMEOUT,
  );

  it(
    "никогда не показывает больше 10 уведомлений",
    async () => {
      const user = userEvent.setup();
      const many = Array.from({ length: 12 }, (_, index) =>
        makeNotification({ id: `notif-${index}`, message: `Напоминание ${index}` }),
      );
      stubFetch(withAuthStub(() => jsonResponse(many)));

      renderWithProviders(<NotificationBell />);
      await openPanel(user);

      await waitFor(() => expect(screen.getByText("Напоминание 0")).toBeInTheDocument());
      const list = screen.getByRole("list");
      expect(within(list).getAllByRole("listitem")).toHaveLength(10);
    },
    INTERACTION_TIMEOUT,
  );

  it(
    "подтягивает новое уведомление при возврате фокуса на вкладку, без перезагрузки",
    async () => {
      const user = userEvent.setup();
      let requestCount = 0;
      stubFetch(
        withAuthStub((url) => {
          if (url !== "/api/notifications") return jsonResponse([]);
          requestCount += 1;
          return requestCount === 1 ? jsonResponse([]) : jsonResponse([makeNotification()]);
        }),
      );

      renderWithProviders(<NotificationBell />);
      await openPanel(user);
      expect(await screen.findByText("Пока нет уведомлений")).toBeInTheDocument();

      window.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("focus"));

      await waitFor(() =>
        expect(screen.getByTestId("notification-unread-dot")).toBeInTheDocument(),
      );
    },
    INTERACTION_TIMEOUT,
  );

  it(
    "отмечает уведомления прочитанными при открытии панели",
    async () => {
      const user = userEvent.setup();
      const calls: string[] = [];
      stubFetch(
        withAuthStub((url) => {
          calls.push(url);
          if (url === "/api/notifications/read") return emptyResponse();
          return jsonResponse([makeNotification({ is_read: false })]);
        }),
      );

      renderWithProviders(<NotificationBell />);
      await openPanel(user);

      await waitFor(() => expect(calls).toContain("/api/notifications/read"));
    },
    INTERACTION_TIMEOUT,
  );
});
