from __future__ import annotations

"""
Seed script (no direct SQL): create dummy reports that behave like a Jupyter Notebook
using ArkanaReport object APIs only. Idempotent.

What this script does via ArkanaReport:
- Ensures 3 demo reports exist with:
  - arkana_object (arkana_type='report', auth_group=0, modeling_db=0)
  - arkana_dashboard_header (arkana_group=0)
- Replaces ordered cells using ArkBoard.reset_cells() and ArkBoard.append_cell(...)
  to mimic notebook cells (markdown → code → output, etc.).

Notes:
- Uses db = 0 and group = 0.
- Leaves tags empty.
- Re-running the script will REPLACE the cells for these demo dashboards.
"""

from dataclasses import dataclass
from typing import Iterable, TypedDict

from src.mdd_arkana_object.ark_report import ArkanaReport


@dataclass(frozen=True)
class DummyBoardSpec:
    key: str
    description: str


class CreatedBoard(TypedDict):
    arkana_id: int
    object_key: str
    arkana_type: str
    auth_group: int | None
    modeling_db: int
    arkana_group: int | None
    description: str | None


def _build_cells() -> list[tuple[str, dict]]:
    """Return the fixed demo notebook cells as (cell_type, payload) tuples."""
    return [
        (
            "markdown",
            {
                "source": [
                    "# Hello World in Python",
                    "",
                    "Dieses Board demonstriert Zellen wie in einem Jupyter Notebook.",
                ]
            },
        ),
        (
            "code",
            {
                "language": "python",
                "execution_count": 1,
                "source": ["print('Hello, world!')"],
                "metadata": {},
            },
        ),
        (
            "output",
            {
                "output_type": "stream",
                "name": "stdout",
                "text": "Hello, world!\n",
            },
        ),
        (
            "markdown",
            {
                "source": [
                    "## Kleine Rechnung",
                    "Wir berechnen die Quadrate der Zahlen 0..4:",
                ]
            },
        ),
        (
            "code",
            {
                "language": "python",
                "execution_count": 2,
                "source": [
                    "vals = [i*i for i in range(5)]",
                    "print(' '.join(str(v) for v in vals))",
                ],
                "metadata": {},
            },
        ),
        (
            "output",
            {
                "output_type": "stream",
                "name": "stdout",
                "text": "0 1 4 9 16\n",
            },
        ),
        (
            "markdown",
            {
                "source": [
                    "---",
                    "Fertig! Du kannst weitere Zellen hinzufügen und anpassen.",
                ]
            },
        ),
    ]


def _seed_notebook_cells_obj(board: ArkanaReport) -> int:
    """Replace all cells for a report using ArkanaReport API only. Returns inserted count."""
    cells = _build_cells()
    board.reset_cells()
    inserted = 0
    for cell_type, payload in cells:
        board.append_cell(cell_type, payload)
        inserted += 1
    return inserted


def create_boards(specs: Iterable[DummyBoardSpec]) -> list[CreatedBoard]:
    created: list[CreatedBoard] = []

    for spec in specs:
        # Resolve or create report via ArkanaReport API (no raw SQL here)
        board = ArkanaReport(
            arkana_type="report",
            object_key=spec.key,
            description=spec.description,
            auth_group=0,
            modeling_db=0,
            arkana_group=0,
        )

        # Reuse existing by key if any
        existing = board.get_field_by_key(spec.key)
        if existing and existing.get("arkana_id"):
            board.arkana_id = int(existing["arkana_id"])  # reuse

        # Persist base and header/content rows
        board.save()

        # Note: No JSON dashboard persistence. Only header and cells are used.

        # Seed ordered Jupyter-like cells using ArkBoard API (in-memory)
        inserted = _seed_notebook_cells_obj(board)

        # Persist all in-memory cells to DB (arkana_dashboard_cells)
        board.save()

        created.append(
            CreatedBoard(
                arkana_id=int(board.arkana_id or 0),
                object_key=spec.key,
                arkana_type="report",
                auth_group=board.auth_group,
                modeling_db=board.modeling_db,
                arkana_group=board.arkana_group,
                description=board.description,
            )
        )

    return created


def main() -> None:
    specs = [
        DummyBoardSpec(key="hello_world_py_1", description="Hello World in Python - Dashboard 1"),
        DummyBoardSpec(key="hello_world_py_2", description="Hello World in Python - Dashboard 2"),
        DummyBoardSpec(key="hello_world_py_3", description="Hello World in Python - Dashboard 3"),
    ]

    boards = create_boards(specs)
    for data in boards:
        print(
            f"Created ArkanaReport: id={data.get('arkana_id')} key={data.get('object_key')} "
            f"type={data.get('arkana_type')} auth_group={data.get('auth_group')} "
            f"modeling_db={data.get('modeling_db')} arkana_group={data.get('arkana_group')}"
        )


if __name__ == "__main__":
    main()
