import { useState } from "react";
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import Modal from "./Modal";

/** A page with an inline onClose, like InterviewsPage's Schedule Interview. */
function FormInModal() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open
      </button>
      <Modal open={open} title="Schedule Interview" onClose={() => setOpen(false)}>
        <input aria-label="Interviewer" value={name} onChange={(e) => setName(e.target.value)} />
      </Modal>
    </>
  );
}

function openModal() {
  const opener = screen.getByRole("button", { name: "Open" });
  opener.focus();
  fireEvent.click(opener);
  return opener;
}

describe("Modal", () => {
  it("keeps focus in an input while typing, even with an inline onClose", () => {
    render(<FormInModal />);
    openModal();
    const input = screen.getByLabelText("Interviewer") as HTMLInputElement;
    input.focus();

    let typed = "";
    for (const char of "John Doe") {
      typed += char;
      fireEvent.change(input, { target: { value: typed } });
      expect(document.activeElement).toBe(input);
    }
    expect(input.value).toBe("John Doe");
    expect(screen.getByLabelText("Interviewer")).toBe(input); // same DOM node
  });

  it("still closes on Escape after re-renders and returns focus to the opener", () => {
    render(<FormInModal />);
    const opener = openModal();
    const input = screen.getByLabelText("Interviewer");
    fireEvent.change(input, { target: { value: "Ann" } });

    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);
  });
});
