from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .converter import ConversionError, ConversionOptions, available_backends, convert_pdf


class ConverterApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PDF to Word Local")
        self.geometry("820x600")
        self.minsize(680, 520)
        self.files: list[Path] = []
        self.output_dir = tk.StringVar(value=str(Path.home() / "Documents"))
        self.overwrite = tk.BooleanVar(value=False)
        self.formula_ocr = tk.BooleanVar(value=False)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self._build_ui()
        self.after(100, self._read_events)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        root = ttk.Frame(self, padding=20)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)
        ttk.Label(root, text="PDF to Word Local", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        engines = ", ".join(available_backends()) or "none"
        ttk.Label(root, text=f"Files stay on this computer. Engine: {engines}").grid(
            row=1, column=0, sticky="w", pady=(2, 14)
        )
        self.table = ttk.Treeview(root, columns=("status",), show="tree headings", height=12)
        self.table.heading("#0", text="PDF file")
        self.table.heading("status", text="Status")
        self.table.column("#0", width=520, minwidth=260)
        self.table.column("status", width=210, minwidth=140, anchor="w")
        self.table.grid(row=2, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.table.yview)
        scrollbar.grid(row=2, column=1, sticky="ns")
        self.table.configure(yscrollcommand=scrollbar.set)
        actions = ttk.Frame(root)
        actions.grid(row=3, column=0, sticky="w", pady=(10, 16))
        ttk.Button(actions, text="Add PDFs", command=self._add_files).pack(side="left")
        ttk.Button(actions, text="Remove selected", command=self._remove_selected).pack(
            side="left", padx=8
        )
        ttk.Button(actions, text="Clear", command=self._clear).pack(side="left")
        output = ttk.Frame(root)
        output.grid(row=4, column=0, sticky="ew")
        output.columnconfigure(1, weight=1)
        ttk.Label(output, text="Output folder").grid(row=0, column=0, padx=(0, 10))
        ttk.Entry(output, textvariable=self.output_dir).grid(row=0, column=1, sticky="ew")
        ttk.Button(output, text="Browse", command=self._choose_output).grid(
            row=0, column=2, padx=(8, 0)
        )
        options = ttk.Frame(root)
        options.grid(row=5, column=0, sticky="w", pady=(14, 0))
        ttk.Checkbutton(
            options,
            text="Recognize formula images (experimental)",
            variable=self.formula_ocr,
        ).pack(side="left")
        ttk.Checkbutton(
            options,
            text="Replace existing files",
            variable=self.overwrite,
        ).pack(side="left", padx=(20, 0))
        footer = ttk.Frame(root)
        footer.grid(row=6, column=0, sticky="ew", pady=(16, 0))
        footer.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(footer, mode="determinate", length=180)
        self.progress.grid(row=0, column=0, padx=(0, 16), sticky="e")
        self.convert_button = ttk.Button(footer, text="Convert", command=self._start)
        self.convert_button.grid(row=0, column=1)
        self.status = ttk.Label(root, text="Ready")
        self.status.grid(row=7, column=0, sticky="w", pady=(12, 0))

    def _add_files(self) -> None:
        selected = filedialog.askopenfilenames(
            title="Choose PDF files", filetypes=[("PDF files", "*.pdf")]
        )
        existing = {path.resolve() for path in self.files}
        for item in selected:
            path = Path(item).resolve()
            if path not in existing:
                self.files.append(path)
                self.table.insert("", "end", iid=str(path), text=path.name, values=("Waiting",))
                existing.add(path)

    def _remove_selected(self) -> None:
        selected = set(self.table.selection())
        self.files = [path for path in self.files if str(path) not in selected]
        for item in selected:
            self.table.delete(item)

    def _clear(self) -> None:
        self.files.clear()
        for item in self.table.get_children():
            self.table.delete(item)

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(title="Choose output folder")
        if selected:
            self.output_dir.set(selected)

    def _start(self) -> None:
        if not self.files:
            messagebox.showinfo("No files", "Add at least one PDF file first.")
            return
        output_dir = Path(self.output_dir.get()).expanduser()
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Output folder", str(exc))
            return
        self.convert_button.configure(state="disabled")
        self.progress.configure(maximum=len(self.files), value=0)
        self.status.configure(text="Converting...")
        threading.Thread(
            target=self._convert_all,
            args=(
                list(self.files),
                output_dir.resolve(),
                self.overwrite.get(),
                self.formula_ocr.get(),
            ),
            daemon=True,
        ).start()

    def _convert_all(
        self,
        files: list[Path],
        output_dir: Path,
        overwrite: bool,
        formula_ocr: bool,
    ) -> None:
        completed = 0
        failed = 0
        for index, source in enumerate(files, start=1):
            self.events.put(("status", (source, "Converting")))
            try:
                report = convert_pdf(
                    source,
                    output_dir / f"{source.stem}.docx",
                    options=ConversionOptions(
                        overwrite=overwrite,
                        recognize_formulas=formula_ocr,
                    ),
                )
                if report.formula_recognition and report.formula_recognition.recognized_count:
                    count = report.formula_recognition.recognized_count
                    state = f"Done ({count} formulae)"
                else:
                    state = "Done" if not report.warnings else "Done with warning"
                completed += 1
                self.events.put(("status", (source, state)))
            except ConversionError as exc:
                failed += 1
                self.events.put(("status", (source, f"Failed: {exc}")))
            self.events.put(("progress", index))
        self.events.put(("done", (completed, failed, output_dir)))

    def _read_events(self) -> None:
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "status":
                    source, state = payload
                    if self.table.exists(str(source)):
                        self.table.set(str(source), "status", state)
                elif event == "progress":
                    self.progress.configure(value=payload)
                elif event == "done":
                    completed, failed, output_dir = payload
                    self.convert_button.configure(state="normal")
                    self.status.configure(text=f"Completed: {completed} | Failed: {failed}")
                    if completed and messagebox.askyesno(
                        "Conversion finished",
                        f"Completed: {completed}\nFailed: {failed}\n\nOpen the output folder?",
                    ):
                        _open_folder(output_dir)
        except queue.Empty:
            pass
        self.after(100, self._read_events)


def _open_folder(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def main() -> None:
    ConverterApp().mainloop()


if __name__ == "__main__":
    main()
