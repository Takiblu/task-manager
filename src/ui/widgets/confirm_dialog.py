"""Confirmation dialogs for destructive process/service actions."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def confirm_end_task(parent: QWidget, app_name: str, pid: int) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle("End Task?")
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText(f"Application: {app_name}\nPID: {pid}")
    box.setInformativeText(
        "Ending this application may cause unsaved data to be lost."
    )
    end_button = box.addButton("End Task", QMessageBox.ButtonRole.DestructiveRole)
    box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(end_button)
    box.exec()
    return box.clickedButton() == end_button


def confirm_force_kill(parent: QWidget, app_name: str, pid: int) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle("Force Kill")
    box.setIcon(QMessageBox.Icon.Critical)
    box.setText(f"Force terminate this process?\n\n{app_name} (PID {pid})")
    box.setInformativeText("This may result in data loss.")
    kill_button = box.addButton("Force Kill", QMessageBox.ButtonRole.DestructiveRole)
    box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(kill_button)
    box.exec()
    return box.clickedButton() == kill_button


def confirm_end_process_tree(parent: QWidget, app_name: str, pid: int, descendant_count: int) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle("End Process Tree?")
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText(f"End {app_name} (PID {pid}) and {descendant_count} related process(es)?")
    box.setInformativeText("This will terminate the entire process tree.")
    end_button = box.addButton("End Tree", QMessageBox.ButtonRole.DestructiveRole)
    box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(end_button)
    box.exec()
    return box.clickedButton() == end_button
