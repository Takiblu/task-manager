"""
QAbstractTableModel for the Processes table.

Key design point for "live update without flicker / lost selection /
lost scroll position" (section 28): `update_processes()` diffs the
incoming list against what's currently shown by PID and only emits
dataChanged for rows that actually changed values, plus
insertRows/removeRows for processes that appeared/disappeared. It
never calls beginResetModel(), which is what causes Qt views to drop
selection and scroll position.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from src.process.process_model import ProcessInfo

COLUMNS = (
    ("name", "Name"),
    ("pid", "PID"),
    ("username", "User"),
    ("cpu_percent", "CPU %"),
    ("memory_percent", "RAM %"),
    ("memory_rss_bytes", "RAM"),
    ("num_threads", "Threads"),
    ("nice", "Priority"),
    ("status", "Status"),
    ("create_time", "Start Time"),
)

COLUMN_KEYS = [key for key, _ in COLUMNS]


def _format_bytes(num_bytes: float) -> str:
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num_bytes) < step:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= step
    return f"{num_bytes:.1f} TB"


def _format_time(epoch_seconds: float) -> str:
    import datetime

    if not epoch_seconds:
        return "--"
    try:
        return datetime.datetime.fromtimestamp(epoch_seconds).strftime("%H:%M:%S")
    except (OverflowError, OSError, ValueError):
        return "--"


class ProcessTableModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[ProcessInfo] = []
        self._pid_to_row: dict[int, int] = {}

    # -- Qt model interface --------------------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section][1]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None

        process = self._rows[index.row()]
        key = COLUMN_KEYS[index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            if key == "cpu_percent":
                return f"{process.cpu_percent:.1f}"
            if key == "memory_percent":
                return f"{process.memory_percent:.1f}"
            if key == "memory_rss_bytes":
                return _format_bytes(process.memory_rss_bytes)
            if key == "status":
                return process.status.value.replace("-", " ").title()
            if key == "create_time":
                return _format_time(process.create_time)
            return getattr(process, key)

        if role == Qt.ItemDataRole.TextAlignmentRole and key in (
            "pid", "cpu_percent", "memory_percent", "memory_rss_bytes", "num_threads", "nice",
        ):
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        if role == Qt.ItemDataRole.UserRole:
            return process

        return None

    # -- Diff-based update to preserve selection/scroll -----------------

    def process_at_row(self, row: int) -> ProcessInfo | None:
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def row_for_pid(self, pid: int) -> int | None:
        return self._pid_to_row.get(pid)

    def update_processes(self, new_processes: list[ProcessInfo]) -> None:
        new_by_pid = {p.pid: p for p in new_processes}
        old_by_pid = {p.pid: p for p in self._rows}

        removed_pids = set(old_by_pid) - set(new_by_pid)
        added_pids = set(new_by_pid) - set(old_by_pid)

        # Remove rows for processes that vanished (iterate in descending
        # row order so earlier removals don't shift later indices).
        if removed_pids:
            rows_to_remove = sorted(
                (self._pid_to_row[pid] for pid in removed_pids if pid in self._pid_to_row),
                reverse=True,
            )
            for row in rows_to_remove:
                self.beginRemoveRows(QModelIndex(), row, row)
                del self._rows[row]
                self.endRemoveRows()
            self._rebuild_index()

        # Update values in place for processes that still exist.
        last_col = len(COLUMNS) - 1
        for pid, new_info in new_by_pid.items():
            if pid in removed_pids:
                continue
            row = self._pid_to_row.get(pid)
            if row is None:
                continue
            old_info = self._rows[row]
            if old_info != new_info:
                self._rows[row] = new_info
                top_left = self.index(row, 0)
                bottom_right = self.index(row, last_col)
                self.dataChanged.emit(top_left, bottom_right)

        # Append newly appeared processes at the end.
        if added_pids:
            start = len(self._rows)
            new_rows = [new_by_pid[pid] for pid in added_pids]
            self.beginInsertRows(QModelIndex(), start, start + len(new_rows) - 1)
            self._rows.extend(new_rows)
            self.endInsertRows()
            self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._pid_to_row = {p.pid: i for i, p in enumerate(self._rows)}
