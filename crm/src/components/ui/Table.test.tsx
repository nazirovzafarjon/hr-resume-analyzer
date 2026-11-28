import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import Table, { type TableColumn } from "./Table";

type Row = { id: number; name: string };

const ROWS: Row[] = [{ id: 1, name: "Ada Lovelace" }];

function columns(header: string): TableColumn<Row>[] {
  return [{ header, render: (row) => <span>{row.name}</span> }];
}

describe("Table", () => {
  it("keeps its cells when the header text changes (translations, language switch)", () => {
    // Headers are translated, and translations load after the first render.
    // Keying cells by header text rebuilt every cell at that moment: a click
    // in between landed on a detached node and focus inside cells was lost.
    const { rerender } = render(<Table columns={columns("admin.sender")} rows={ROWS} rowKey={(r) => r.id} />);
    const before = screen.getByText("Ada Lovelace");

    rerender(<Table columns={columns("Sender")} rows={ROWS} rowKey={(r) => r.id} />);

    const after = screen.getByText("Ada Lovelace");
    expect(after).toBe(before);
    expect(before.isConnected).toBe(true);
    expect(screen.getByRole("columnheader", { name: "Sender" })).toBeTruthy();
  });

  it("prefers an explicit column id, then the sort key", () => {
    const { container, rerender } = render(
      <Table
        columns={[
          { id: "who", header: "A", render: (row) => <i>{row.name}</i> },
          { sortKey: "name", header: "B", render: () => <b>x</b> },
        ]}
        rows={ROWS}
        rowKey={(r) => r.id}
      />,
    );
    const cells = Array.from(container.querySelectorAll("td"));

    rerender(
      <Table
        columns={[
          { id: "who", header: "C", render: (row) => <i>{row.name}</i> },
          { sortKey: "name", header: "D", render: () => <b>x</b> },
        ]}
        rows={ROWS}
        rowKey={(r) => r.id}
      />,
    );
    expect(Array.from(container.querySelectorAll("td"))).toEqual(cells);
  });
});
