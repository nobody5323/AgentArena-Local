from __future__ import annotations

import subprocess
import sys
from pathlib import Path


AGENTS = ["claude", "codex", "gemini", "aider", "manual", "cursor", "cline", "windsurf"]


def launch_gui() -> int:
    try:
        from PySide6.QtCore import QThread, QUrl, Signal
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QFileDialog,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise RuntimeError("PySide6 is required for `agentarena gui`. Install the GUI dependencies first.") from exc

    class CommandWorker(QThread):
        output = Signal(str)
        failed = Signal(str)
        finished_ok = Signal()

        def __init__(self, command: list[str], cwd: Path) -> None:
            super().__init__()
            self.command = command
            self.cwd = cwd

        def run(self) -> None:
            try:
                process = subprocess.Popen(
                    self.command,
                    cwd=self.cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                assert process.stdout is not None
                for line in process.stdout:
                    self.output.emit(line.rstrip())
                code = process.wait()
                if code == 0:
                    self.finished_ok.emit()
                else:
                    self.failed.emit(f"Command exited with code {code}")
            except Exception as exc:  # pragma: no cover - GUI runtime safety
                self.failed.emit(str(exc))

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("AgentArena Local")
            self.resize(980, 720)
            self.worker: CommandWorker | None = None

            self.project_dir = QLineEdit(str(Path.cwd()))
            self.task_file = QLineEdit("")
            self.variants_dir = QLineEdit("")
            self.mode = QComboBox()
            self.mode.addItems(["Normal Benchmark", "AGENTS.md A/B Test"])
            self.agent_boxes = {agent: QCheckBox(agent.title()) for agent in AGENTS}
            self.agent_boxes["manual"].setChecked(True)
            self.log = QTextEdit()
            self.log.setReadOnly(True)
            self.leaderboard = QTextEdit()
            self.leaderboard.setReadOnly(True)

            run_button = QPushButton("Run Benchmark")
            run_button.clicked.connect(self.run_benchmark)
            refresh_button = QPushButton("Refresh Leaderboard")
            refresh_button.clicked.connect(self.refresh_leaderboard)
            report_button = QPushButton("Open HTML Report")
            report_button.clicked.connect(lambda: self.open_file(".agentarena/reports/latest-report.html"))
            dashboard_button = QPushButton("Open Dashboard")
            dashboard_button.clicked.connect(lambda: self.open_file(".agentarena/reports/dashboard.html"))

            layout = QVBoxLayout()
            form = QGridLayout()
            self._path_row(form, 0, "Project", self.project_dir, self.choose_project)
            self._path_row(form, 1, "Task YAML", self.task_file, self.choose_task)
            self._path_row(form, 2, "Variants", self.variants_dir, self.choose_variants)
            form.addWidget(QLabel("Mode"), 3, 0)
            form.addWidget(self.mode, 3, 1)
            layout.addLayout(form)

            agents_row = QHBoxLayout()
            agents_row.addWidget(QLabel("Agents"))
            for checkbox in self.agent_boxes.values():
                agents_row.addWidget(checkbox)
            layout.addLayout(agents_row)

            buttons = QHBoxLayout()
            for button in (run_button, refresh_button, report_button, dashboard_button):
                buttons.addWidget(button)
            layout.addLayout(buttons)
            layout.addWidget(QLabel("Live Log"))
            layout.addWidget(self.log, 2)
            layout.addWidget(QLabel("Leaderboard"))
            layout.addWidget(self.leaderboard, 1)

            root = QWidget()
            root.setLayout(layout)
            self.setCentralWidget(root)

        def _path_row(self, form: QGridLayout, row: int, label: str, edit: QLineEdit, callback) -> None:
            button = QPushButton("Browse")
            button.clicked.connect(callback)
            form.addWidget(QLabel(label), row, 0)
            form.addWidget(edit, row, 1)
            form.addWidget(button, row, 2)

        def choose_project(self) -> None:
            value = QFileDialog.getExistingDirectory(self, "Select Project Directory", self.project_dir.text())
            if value:
                self.project_dir.setText(value)

        def choose_task(self) -> None:
            value, _ = QFileDialog.getOpenFileName(self, "Select task.yaml", self.project_dir.text(), "YAML (*.yaml *.yml)")
            if value:
                self.task_file.setText(value)

        def choose_variants(self) -> None:
            value = QFileDialog.getExistingDirectory(self, "Select variants Directory", self.project_dir.text())
            if value:
                self.variants_dir.setText(value)

        def selected_agents(self) -> str:
            selected = [name for name, checkbox in self.agent_boxes.items() if checkbox.isChecked()]
            return ",".join(selected or ["manual"])

        def run_benchmark(self) -> None:
            project = Path(self.project_dir.text()).expanduser()
            task = self.task_file.text().strip()
            if not project.exists():
                QMessageBox.critical(self, "AgentArena", "Project directory does not exist.")
                return
            if not task:
                QMessageBox.critical(self, "AgentArena", "Please choose a task.yaml file.")
                return
            if self.mode.currentText().startswith("AGENTS"):
                variants = self.variants_dir.text().strip()
                if not variants:
                    QMessageBox.critical(self, "AgentArena", "Please choose a variants directory.")
                    return
                command = [sys.executable, "-m", "agentarena_local", "abtest", "--agents", self.selected_agents(), "--task", task, "--variants", variants]
            else:
                command = [sys.executable, "-m", "agentarena_local", "run", "--agents", self.selected_agents(), "--task", task]
            self.start_worker(command, project)

        def refresh_leaderboard(self) -> None:
            self.start_worker([sys.executable, "-m", "agentarena_local", "leaderboard"], Path(self.project_dir.text()))

        def start_worker(self, command: list[str], cwd: Path) -> None:
            if self.worker and self.worker.isRunning():
                QMessageBox.warning(self, "AgentArena", "A benchmark is already running.")
                return
            self.log.append("> " + " ".join(command))
            self.worker = CommandWorker(command, cwd)
            self.worker.output.connect(self.on_output)
            self.worker.failed.connect(self.on_error)
            self.worker.finished_ok.connect(self.on_done)
            self.worker.start()

        def on_output(self, line: str) -> None:
            self.log.append(line)
            self.leaderboard.append(line)

        def on_error(self, message: str) -> None:
            self.log.append("ERROR: " + message)
            QMessageBox.critical(self, "AgentArena", message)

        def on_done(self) -> None:
            self.log.append("Done.")

        def open_file(self, relative: str) -> None:
            path = Path(self.project_dir.text()) / relative
            if not path.exists():
                QMessageBox.warning(self, "AgentArena", f"File does not exist: {path}")
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
