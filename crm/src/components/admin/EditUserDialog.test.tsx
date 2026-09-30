import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import EditUserDialog from "./EditUserDialog";
import { updateAdminUser } from "../../services/adminService";
import { ApiError } from "../../utils/apiError";
import { renderWithProviders } from "../../test/utils";

vi.mock("../../services/adminService", () => ({ updateAdminUser: vi.fn() }));

const target = { id: 7, full_name: "Jane Doe", email: "jane@example.com", is_active: true, is_superuser: false };
const update = vi.mocked(updateAdminUser);

function renderDialog({ isSelf = false, onDone = vi.fn() } = {}) {
  renderWithProviders(<EditUserDialog user={target} isSelf={isSelf} onClose={vi.fn()} onDone={onDone} />);
  return onDone;
}

async function saveButton() {
  return (await screen.findByRole("button", { name: /Save changes/ })) as HTMLButtonElement;
}

const nameInput = () => screen.getByRole("textbox") as HTMLInputElement;
const activeBox = () => screen.getByRole("checkbox") as HTMLInputElement;
const adminRadio = () => screen.getByRole("radio", { name: "Administrator" }) as HTMLInputElement;

describe("EditUserDialog", () => {
  beforeEach(() => update.mockReset());

  it("starts from the current values and cannot save them unchanged", async () => {
    renderDialog();
    expect((await saveButton()).disabled).toBe(true);
    expect(nameInput().value).toBe("Jane Doe");
    expect(activeBox().checked).toBe(true);
    expect(adminRadio().checked).toBe(false);
  });

  it("rejects a blank name without calling the API", async () => {
    renderDialog();
    fireEvent.change(nameInput(), { target: { value: "   " } });
    fireEvent.click(await saveButton());
    expect(await screen.findByText("Full name is required.")).toBeTruthy();
    expect(update).not.toHaveBeenCalled();
  });

  it("sends only the trimmed full_name when only the name changed", async () => {
    update.mockResolvedValueOnce({} as never);
    const onDone = renderDialog();
    fireEvent.change(nameInput(), { target: { value: "  Jane Smith " } });
    fireEvent.click(await saveButton());
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(update).toHaveBeenCalledWith(7, { full_name: "Jane Smith" });
  });

  it("explains status and role changes and sends only those flags", async () => {
    update.mockResolvedValueOnce({} as never);
    const onDone = renderDialog();
    await saveButton(); // translations loaded
    fireEvent.click(activeBox());
    fireEvent.click(adminRadio());
    expect(await screen.findByText(/will be signed out immediately/)).toBeTruthy();
    expect(screen.getByText(/full access to the admin panel/)).toBeTruthy();
    fireEvent.click(await saveButton());
    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(update).toHaveBeenCalledWith(7, { is_active: false, is_superuser: true });
  });

  it("locks status and role on the admin's own account", async () => {
    renderDialog({ isSelf: true });
    await saveButton();
    // Disabled through the surrounding fieldset.
    expect(activeBox().matches(":disabled")).toBe(true);
    expect(adminRadio().matches(":disabled")).toBe(true);
    expect(nameInput().disabled).toBe(false);
  });

  it("shows the server's refusal inline and stays open", async () => {
    update.mockRejectedValueOnce(new ApiError(400, "You cannot deactivate your own account"));
    const onDone = renderDialog();
    fireEvent.click(activeBox());
    fireEvent.click(await saveButton());
    expect(await screen.findByText("You cannot deactivate your own account")).toBeTruthy();
    expect(onDone).not.toHaveBeenCalled();
  });
});
