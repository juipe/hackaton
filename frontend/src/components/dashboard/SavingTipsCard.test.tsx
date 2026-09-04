import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { SavingTipsCard } from "@/components/dashboard/SavingTipsCard";
import { errorResponse, jsonResponse, requestedUrls, stubFetch } from "@/test/fetch";
import { renderWithProviders } from "@/test/render";
import type { SavingTipsResponse } from "@/types/api";

const TIPS: SavingTipsResponse = {
  tips: [
    {
      title: "Еда — крупная категория",
      text: "Еда составляет 31% всех расходов.",
      type: "data_driven",
    },
    { title: "Установите лимит", text: "Ограничьте необязательные покупки.", type: "generic" },
  ],
};

/** `renderWithProviders` mounts `AuthProvider`, which fires its own `/auth/me` — keep
 * that request answered separately so it never eats into the saving-tips sequence. */
function withAuthStub(handler: (url: string) => Response | Promise<Response>) {
  return (url: string) => (url === "/api/auth/me" ? errorResponse(401, "Требуется вход") : handler(url));
}

describe("SavingTipsCard", () => {
  it("показывает начальное состояние с кнопкой генерации", () => {
    stubFetch(withAuthStub(() => errorResponse(500, "не должно вызываться")));

    renderWithProviders(<SavingTipsCard params={{ period: "all" }} />);

    expect(screen.getByText("Советы по экономии")).toBeInTheDocument();
    expect(
      screen.getByText("Персональные рекомендации на основе ваших расходов"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Сгенерировать советы/ })).toBeInTheDocument();
  });

  it("показывает загрузку сразу после клика", async () => {
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

    renderWithProviders(<SavingTipsCard params={{ period: "all" }} />);
    await user.click(screen.getByRole("button", { name: /Сгенерировать советы/ }));

    expect(await screen.findByText("Анализируем расходы…")).toBeInTheDocument();

    resolveFetch(jsonResponse(TIPS));
  });

  it("отображает 2–3 совета после успешного ответа", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(
      withAuthStub((url) =>
        url.startsWith("/api/dashboard/saving-tips")
          ? jsonResponse(TIPS)
          : errorResponse(404, "?"),
      ),
    );

    renderWithProviders(<SavingTipsCard params={{ period: "this_month" }} />);
    await user.click(screen.getByRole("button", { name: /Сгенерировать советы/ }));

    expect(await screen.findByText("Еда — крупная категория")).toBeInTheDocument();
    expect(screen.getByText("Установите лимит")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);

    const url = requestedUrls(fetchMock).find((entry) =>
      entry.startsWith("/api/dashboard/saving-tips"),
    );
    expect(url).toContain("period=this_month");
  });

  it("передаёт group_id в запрос при использовании на странице группы", async () => {
    const user = userEvent.setup();
    const fetchMock = stubFetch(
      withAuthStub((url) =>
        url.startsWith("/api/dashboard/saving-tips")
          ? jsonResponse(TIPS)
          : errorResponse(404, "?"),
      ),
    );

    renderWithProviders(
      <SavingTipsCard params={{ period: "all", group_id: "group-42" }} />,
    );
    await user.click(screen.getByRole("button", { name: /Сгенерировать советы/ }));

    await screen.findByText("Еда — крупная категория");

    const url = requestedUrls(fetchMock).find((entry) =>
      entry.startsWith("/api/dashboard/saving-tips"),
    );
    expect(url).toContain("group_id=group-42");
    expect(url).toContain("period=all");
  });

  it("показывает ошибку и позволяет повторить запрос", async () => {
    const user = userEvent.setup();
    let attempt = 0;
    stubFetch(
      withAuthStub(() => {
        attempt += 1;
        return attempt === 1
          ? errorResponse(500, "Внутренняя ошибка сервера")
          : jsonResponse(TIPS);
      }),
    );

    renderWithProviders(<SavingTipsCard params={{ period: "all" }} />);
    await user.click(screen.getByRole("button", { name: /Сгенерировать советы/ }));

    expect(await screen.findByText("Внутренняя ошибка сервера")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Повторить" }));

    await waitFor(() => expect(screen.getByText("Еда — крупная категория")).toBeInTheDocument());
    expect(attempt).toBe(2);
  });
});
