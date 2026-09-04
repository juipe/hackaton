import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";

import { ParticipantSelector } from "@/components/expenses/ParticipantSelector";
import { makeMembers } from "@/test/factories";
import { jsonResponse, stubFetch } from "@/test/fetch";
import { renderWithProviders } from "@/test/render";

vi.mock("sonner", () => ({
  toast: { info: vi.fn(), success: vi.fn(), error: vi.fn() },
}));

const MEMBERS = makeMembers(["Оля", "Саша", "Костя"]);
const IDS = MEMBERS.map((member) => member.user.id);
const [OLYA_ID, SASHA_ID, KOSTYA_ID] = IDS;

/** Вошли как Саша; заплатила Оля. */
async function renderSelector(selectedIds: string[], onChange: (ids: string[]) => void) {
  stubFetch(() => jsonResponse(MEMBERS[1].user));

  renderWithProviders(
    <ParticipantSelector
      members={MEMBERS}
      selectedIds={selectedIds}
      onChange={onChange}
      payerId={OLYA_ID}
    />,
  );

  // Wait for the session so the "Вы" label and the "Только я" shortcut exist.
  await waitFor(() =>
    expect(screen.getByRole("button", { name: /Только я/ })).toBeInTheDocument(),
  );
}

/**
 * Chips are found by the member's name, which is always present as the avatar's
 * screen-reader label even when the visible label reads "Вы".
 */
function chip(name: string): HTMLElement {
  for (const node of screen.getAllByText(name)) {
    const button = node.closest("button");
    if (button) return button;
  }
  throw new Error(`No participant chip for ${name}`);
}

describe("ParticipantSelector", () => {
  it("drops a participant and keeps the member order", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    await renderSelector(IDS, onChange);

    await user.click(chip("Саша"));

    expect(onChange).toHaveBeenCalledWith([OLYA_ID, KOSTYA_ID]);
  });

  it("adds a participant back in member order, not click order", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    await renderSelector([OLYA_ID, KOSTYA_ID], onChange);

    await user.click(chip("Саша"));

    expect(onChange).toHaveBeenCalledWith([OLYA_ID, SASHA_ID, KOSTYA_ID]);
  });

  it("refuses to remove the payer, and explains why", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    await renderSelector(IDS, onChange);

    await user.click(chip("Оля"));

    expect(onChange).not.toHaveBeenCalled();
    expect(vi.mocked(toast.info)).toHaveBeenCalledWith(
      expect.stringContaining("смените «Кто заплатил»"),
    );
  });

  it("selects everyone with the shortcut", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    await renderSelector([OLYA_ID], onChange);

    await user.click(screen.getByRole("button", { name: "Все" }));

    expect(onChange).toHaveBeenCalledWith(IDS);
  });

  it("keeps the payer in the split even when the reader picks 'Только я'", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    await renderSelector(IDS, onChange);

    await user.click(screen.getByRole("button", { name: /Только я/ }));

    // Саша alone would be rejected by the API: the payer must be a participant.
    expect(onChange).toHaveBeenCalledWith([OLYA_ID, SASHA_ID]);
  });

  it("says how many people are sharing and why the payer is locked in", async () => {
    await renderSelector(IDS, vi.fn());

    expect(
      screen.getByText(/В делении 3 человека · плательщик Оля всегда участвует/),
    ).toBeInTheDocument();
  });

  it("agrees the numeral with the count", async () => {
    await renderSelector([OLYA_ID], vi.fn());

    expect(screen.getByText(/В делении 1 человек ·/)).toBeInTheDocument();
  });

  it("гасит ярлык «Все», когда уже выбраны все", async () => {
    await renderSelector(IDS, vi.fn());

    expect(screen.getByRole("button", { name: "Все" })).toBeDisabled();
  });

  it("marks the selected chips as pressed", async () => {
    await renderSelector([OLYA_ID, KOSTYA_ID], vi.fn());

    expect(chip("Оля")).toHaveAttribute("aria-pressed", "true");
    expect(chip("Саша")).toHaveAttribute("aria-pressed", "false");
    expect(chip("Костя")).toHaveAttribute("aria-pressed", "true");
  });

  // Видимый лейбл стоит снаружи компонента и ни к чему не привязан, поэтому
  // подпись чипам даёт сама группа — иначе скринридер читает россыпь кнопок.
  it("собирает чипы в подписанную группу", async () => {
    await renderSelector(IDS, vi.fn());

    const group = screen.getByRole("group", { name: "Между кем делим" });
    expect(group).toContainElement(chip("Оля"));
  });
});
