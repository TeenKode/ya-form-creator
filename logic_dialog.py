"""Review explainable logic warnings and apply explicitly selected JSON conditions."""
from __future__ import annotations

from copy import deepcopy
import tkinter as tk
from tkinter import messagebox, ttk

import engine
import logic_analyzer


class LogicReviewDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, config: dict):
        super().__init__(parent)
        self.title("Проверка логики между вопросами")
        self.geometry("990x620")
        self.minsize(670, 450)
        self.transient(parent)
        self.working = deepcopy(config)
        self.result: dict | None = None
        self.issues: list[dict] = []

        top = ttk.Frame(self, padding=(14, 12))
        top.pack(fill="x")
        ttk.Label(top, text="Логические связи между вопросами",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(
            top, text=("Проверка распознаёт вероятные противоречия. "
                       "Изменения вносятся только после подтверждения; "
                       "неоднозначные ситуации требуют ручной проверки."),
            wraplength=930, justify="left").pack(anchor="w", pady=(5, 0))

        area = ttk.Frame(self, padding=(14, 0, 14, 8))
        area.pack(fill="both", expand=True)
        area.rowconfigure(0, weight=1)
        area.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(area, columns=("source", "target", "status"),
                                 show="headings", selectmode="browse", height=10)
        for key, title, width in [
            ("source", "Условие / предыдущий вопрос", 290),
            ("target", "Зависимый вопрос", 330),
            ("status", "Решение", 190),
        ]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=110, stretch=(key != "status"))
        scroller = ttk.Scrollbar(area, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroller.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroller.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self.show_selected)

        self.explanation = tk.Text(self, height=7, wrap="word", state="disabled",
                                   font=("Segoe UI", 10))
        self.explanation.pack(fill="x", padx=14, pady=(0, 10))

        controls = ttk.Frame(self, padding=(14, 0, 14, 14))
        controls.pack(fill="x")
        self.count_label = ttk.Label(controls, text="")
        self.count_label.pack(side="left")
        ttk.Button(controls, text="Закрыть", command=self.close).pack(side="right", padx=(8, 0))
        self.apply_all_btn = ttk.Button(controls, text="Применить все предложения",
                                        command=self.apply_all)
        self.apply_all_btn.pack(side="right", padx=(8, 0))
        self.apply_one_btn = ttk.Button(controls, text="Применить выбранное",
                                        command=self.apply_selected)
        self.apply_one_btn.pack(side="right")
        self.refresh()

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.grab_set()
        self.wait_window()

    def refresh(self):
        self.issues = logic_analyzer.analyze_logic(self.working)
        self.tree.delete(*self.tree.get_children())
        for index, issue in enumerate(self.issues):
            status = "Есть предложение" if issue.get("suggestion") else "Проверить вручную"
            self.tree.insert("", "end", iid=str(index), values=(
                issue["source_label"][:85], issue["target_label"][:85], status))
        proposed = sum(bool(i.get("suggestion")) for i in self.issues)
        self.count_label.configure(text=f"Замечаний: {len(self.issues)}  ·  Исправлений: {proposed}")
        self.apply_all_btn.configure(state="normal" if proposed else "disabled")
        self.apply_one_btn.configure(state="disabled")
        if self.issues:
            self.tree.selection_set("0")
            self.show_selected()
        else:
            self._text("Предполагаемых противоречий не найдено. "
                       "Проверка эвристическая: это не гарантия отсутствия всех логических ошибок.")

    def _text(self, value: str):
        self.explanation.configure(state="normal")
        self.explanation.delete("1.0", "end")
        self.explanation.insert("1.0", value)
        self.explanation.configure(state="disabled")

    def show_selected(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            self.apply_one_btn.configure(state="disabled")
            return
        issue = self.issues[int(selection[0])]
        if issue.get("suggestion"):
            details = (f"Вопрос: {issue['source_label']}\n"
                       f"Ответ, при котором не нужен следующий вопрос: "
                       f"{', '.join(issue['negative_answers'])}\n"
                       f"Проверяемый вопрос: {issue['target_label']}\n\n"
                       f"Предлагается показывать зависимый вопрос только при других ответах. "
                       f"Будет добавлено условие в JSON; исходные ответы останутся без изменений.")
        else:
            details = (f"{issue['source_label']} → {issue['target_label']}\n"
                       f"{issue['message']}\n\nИсправьте условия в редакторе вручную.")
        self._text(details)
        self.apply_one_btn.configure(state="normal" if issue.get("suggestion") else "disabled")

    def _apply(self, targets: set[str] | None):
        selected = [i for i in self.issues if i.get("suggestion") and
                    (targets is None or i["target"] in targets)]
        if not selected:
            return
        if not messagebox.askyesno(
            "Добавить условия показа?",
            f"Внести в анкету {len(selected)} условие(я) показа?\n"
            "Изменения будут сохранены только вместе с анкетой.",
            parent=self,
        ):
            return
        try:
            updated = logic_analyzer.apply_suggestions(self.working, selected, targets)
        except (engine.ConfigError, ValueError) as exc:
            messagebox.showerror("Не удалось применить условия", str(exc), parent=self)
            return
        self.working = updated
        self.result = deepcopy(updated)
        self.refresh()
        messagebox.showinfo("Условия добавлены",
                            f"Добавлено условий: {len(selected)}.\n"
                            "Теперь сохраните анкету и проверьте предпросмотр.", parent=self)

    def apply_selected(self):
        selection = self.tree.selection()
        if selection:
            self._apply({self.issues[int(selection[0])]["target"]})

    def apply_all(self):
        self._apply(None)

    def close(self):
        self.destroy()
