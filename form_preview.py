"""Interactive, local-only preview of YaFormCreator questionnaires.

This module never submits answers or accesses the Yandex API. The form renderer
uses native Tk controls, while pure functions remain testable without a display.
"""
from __future__ import annotations

from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Mapping

import engine


def option_labels(item: Mapping[str, Any]) -> list[str]:
    return [v if isinstance(v, str) else v["label"] for v in item.get("options", [])]


def is_visible(slug: str, conditions: list[dict], answers: Mapping[str, Any],
               visible: set[str]) -> bool:
    """Evaluate the locally modelled conditions for a particular target.

    Separate rules on a target are treated as AND; the Yandex server owns the
    definitive condition semantics. An unanswered or hidden source never shows
    a dependent question, including when a rule uses `neq`.
    """
    rules = [r for r in conditions if r["target"] == slug]
    for rule in rules:
        source = rule["source"]
        if source not in visible:
            return False
        selection = answers.get(source, "")
        chosen = set(selection) if isinstance(selection, (set, list, tuple)) else ({selection} if selection else set())
        if not chosen:
            return False
        expected = rule["answers"]
        comparisons = [(value in chosen) == (rule.get("condition", "eq") == "eq")
                       for value in expected]
        passed = (all(comparisons) if rule.get("operator", "and") == "and"
                  else any(comparisons))
        if not passed:
            return False
    return True


def visible_slugs(config: dict, answers: Mapping[str, Any]) -> set[str]:
    """Compute visible questions in display order (including generated 'other')."""
    conditions = list(config.get("conditions", []))
    for q in config["questions"]:
        if q.get("other"):
            other = q["other"]
            conditions.append({"source": q["slug"],
                               "target": other.get("slug", q["slug"] + "_other"),
                               "answers": [other.get("option", "Другое")],
                               "operator": "and"})
    visible: set[str] = set()
    for q in config["questions"]:
        if q.get("type") in {"section", "comment"} or q.get("hidden"):
            continue
        slug = q["slug"]
        if is_visible(slug, conditions, answers, visible):
            visible.add(slug)
        if q.get("other"):
            other_slug = q["other"].get("slug", slug + "_other")
            if slug in visible and is_visible(other_slug, conditions, answers, visible):
                visible.add(other_slug)
    return visible


def check_answers(config: dict, answers: Mapping[str, Any]) -> list[str]:
    """Advisory local checks, not a substitute for Yandex Forms validators."""
    visible = visible_slugs(config, answers)
    errors = []
    for q in config["questions"]:
        qtype = q["type"]
        if qtype in {"section", "comment"} or q["slug"] not in visible:
            continue
        value = answers.get(q["slug"])
        if qtype == "checkbox":
            value = list(value or [])
            if q.get("required") and not value:
                errors.append(f"{q['label']}: выберите хотя бы один вариант.")
            if len(value) < q.get("min_choices", 0):
                errors.append(f"{q['label']}: выберите не менее {q['min_choices']} вариантов.")
            if len(value) > q.get("max_choices", float('inf')):
                errors.append(f"{q['label']}: выберите не более {q['max_choices']} вариантов.")
        elif qtype == "matrix":
            if q.get("required") and (not isinstance(value, dict) or
                    any(not value.get(row if isinstance(row, str) else row["label"])
                        for row in q["rows"])):
                errors.append(f"{q['label']}: ответьте на каждую строку матрицы.")
        elif qtype == "api":
            # A raw API field may need its own custom frontend. Do not
            # incorrectly report it as an unanswered native text control.
            continue
        else:
            raw = "" if value is None else str(value).strip()
            if q.get("required") and not raw:
                errors.append(f"{q['label']}: ответ обязателен.")
            if raw and qtype == "text":
                if len(raw) < q.get("min_length", 0):
                    errors.append(f"{q['label']}: слишком короткий ответ.")
                if len(raw) > q.get("max_length", float('inf')):
                    errors.append(f"{q['label']}: слишком длинный ответ.")
            if raw and qtype == "integer":
                try:
                    num = int(raw)
                except ValueError:
                    errors.append(f"{q['label']}: укажите целое число.")
                else:
                    if num < q.get("min", -float('inf')) or num > q.get("max", float('inf')):
                        errors.append(f"{q['label']}: значение вне допустимого диапазона.")
            if raw and qtype == "date":
                try:
                    value_date = date.fromisoformat(raw)
                except ValueError:
                    errors.append(f"{q['label']}: дата должна быть в формате YYYY-MM-DD.")
                else:
                    if ("min" in q and value_date < date.fromisoformat(q["min"])) or (
                        "max" in q and value_date > date.fromisoformat(q["max"])):
                        errors.append(f"{q['label']}: дата вне допустимого диапазона.")
        if q.get("other"):
            other = q["other"]
            other_slug = other.get("slug", q["slug"] + "_other")
            if (other_slug in visible and other.get("required", True) and
                    not str(answers.get(other_slug, "")).strip()):
                errors.append(f"{other.get('label', 'Другой вариант')}: заполните поле уточнения.")
    return errors


class PreviewWindow(tk.Toplevel):
    """Scroll-friendly native-widget preview with live conditional visibility."""
    def __init__(self, parent: tk.Misc, config: dict):
        engine.validate_config(config)
        super().__init__(parent)
        self.title("Предпросмотр формы — локально, без отправки")
        self.geometry("880x720")
        self.minsize(560, 410)
        self.config_data = config
        self.answer_readers: dict[str, Any] = {}
        self.resetters: list[Any] = []
        self.blocks: dict[str, ttk.Frame] = {}
        self.last_visible: set[str] = set()
        self._wrapping_labels: list[ttk.Label] = []
        self._rendering = False

        bar = ttk.Frame(self, padding=(14, 12))
        bar.pack(fill="x")
        ttk.Label(bar, text="Интерактивный предпросмотр", font=("Segoe UI", 13, "bold")).pack(side="left")
        ttk.Button(bar, text="Закрыть", command=self.destroy).pack(side="right")
        ttk.Button(bar, text="Проверить ответы", command=self.check_responses).pack(side="right", padx=6)
        ttk.Button(bar, text="Очистить", command=self.clear_answers).pack(side="right", padx=4)

        canvas_area = ttk.Frame(self)
        canvas_area.pack(fill="both", expand=True, padx=(14, 9), pady=(0, 8))
        self.canvas = tk.Canvas(canvas_area, borderwidth=0, highlightthickness=0)
        scroller = ttk.Scrollbar(canvas_area, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroller.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scroller.pack(side="right", fill="y")
        self.content = ttk.Frame(self.canvas, padding=(4, 4, 10, 10))
        self.content_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._on_content_resize)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.bind("<MouseWheel>", self._on_mousewheel)    # Windows / macOS
        self.bind("<Button-4>", lambda _e: self.canvas.yview_scroll(-3, "units"))  # Linux
        self.bind("<Button-5>", lambda _e: self.canvas.yview_scroll(3, "units"))

        form_title = ttk.Label(self.content, text=config["form"]["name"],
                               font=("Segoe UI", 16, "bold"), wraplength=730,
                               justify="left")
        form_title.pack(fill="x", anchor="w", pady=(5, 14))
        self._wrapping_labels.append(form_title)
        count = 0
        for q in config["questions"]:
            if q.get("hidden"):
                continue
            if q["type"] in {"section", "comment"}:
                label = ttk.Label(self.content, text=q["label"],
                                  font=("Segoe UI", 12, "bold" if q["type"] == "section" else "normal"),
                                  wraplength=730, justify="left")
                label.pack(fill="x", anchor="w", pady=(12, 5))
                if q.get("comment"):
                    ttk.Label(self.content, text=q["comment"], wraplength=730,
                              justify="left").pack(fill="x", anchor="w", pady=(0, 8))
                continue
            count += 1
            self._add_question(q, count)
        ttk.Label(self.content, text="Демонстрация: ответы никуда не отправляются. "
                  "Точное отображение и проверка условий зависят от Яндекс Форм.",
                  foreground="#777777", wraplength=730).pack(fill="x", pady=(8, 16))
        self.update_visibility()
        self.canvas.yview_moveto(0)

    def _on_content_resize(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_resize(self, event):
        self.canvas.itemconfigure(self.content_id, width=event.width)
        for label in self._wrapping_labels:
            label.configure(wraplength=max(260, event.width - 75))

    def _on_mousewheel(self, event):
        if getattr(event, "delta", 0):
            self.canvas.yview_scroll(-int(event.delta / 120) or (-1 if event.delta > 0 else 1), "units")

    def _observe(self, var: tk.Variable):
        var.trace_add("write", lambda *_: self.update_visibility())
        self.resetters.append(lambda: var.set(False if isinstance(var, tk.BooleanVar) else ""))
        return var

    def _add_question(self, q: dict, number: int):
        slug = q["slug"]
        slot = ttk.Frame(self.content)
        slot.pack(fill="x")
        frame = ttk.Frame(slot, padding=(12, 10), borderwidth=1, relief="solid")
        frame.pack(fill="x", anchor="n", pady=(0, 12))
        heading = ttk.Label(frame, text=f"{number}. {q['label']}" +
                            ("  *" if q.get("required") else ""),
                            font=("Segoe UI", 11, "bold"), wraplength=730, justify="left")
        heading.pack(fill="x", anchor="w", pady=(0, 6))
        self._wrapping_labels.append(heading)
        self.blocks[slug] = frame
        if q.get("comment"):
            ttk.Label(frame, text=q["comment"], wraplength=730, justify="left",
                      foreground="#6b7280").pack(fill="x", pady=(0, 6))
        qtype = q["type"]
        options = option_labels(q)
        if qtype in {"radio", "checkbox"}:
            ttk.Label(frame, text="Выберите один вариант" if qtype == "radio" else
                      "Можно выбрать несколько вариантов", foreground="#6b7280").pack(
                          anchor="w", pady=(0, 4))
        if qtype in engine.ENUM_TYPES:
            self._render_enum(q, frame, options)
        elif qtype == "boolean":
            variable = self._observe(tk.StringVar(value=""))
            self.answer_readers[slug] = variable.get
            for label in ("Да", "Нет"):
                ttk.Radiobutton(frame, text=label, variable=variable, value=label).pack(anchor="w", pady=2)
        elif qtype in {"text", "integer", "date"}:
            self._render_entry(q, frame)
        elif qtype == "matrix":
            self._render_matrix(q, frame)
        elif qtype == "api":
            ttk.Label(frame, text=f"API-тип: {q['payload']['type']}. "
                      "Для этого расширенного вопроса интерактивная имитация недоступна.",
                      wraplength=680, foreground="#777777").pack(anchor="w")
            self.answer_readers[slug] = lambda: ""
        else:
            ttk.Label(frame, text=f"Неизвестный тип: {qtype}").pack(anchor="w")
        if q.get("other"):
            other = q["other"]
            other_slug = other.get("slug", slug + "_other")
            other_slot = ttk.Frame(self.content)
            other_slot.pack(fill="x")
            f = ttk.Frame(other_slot, padding=(28, 0, 12, 12))
            f.pack(fill="x", pady=(0, 9))
            ttk.Label(f, text=other.get("label", "Укажите свой вариант") +
                      ("  *" if other.get("required", True) else "")).pack(anchor="w")
            variable = self._observe(tk.StringVar(value=""))
            ttk.Entry(f, textvariable=variable).pack(fill="x", pady=4)
            self.answer_readers[other_slug] = variable.get
            self.blocks[other_slug] = f

    def _render_enum(self, q: dict, frame: ttk.Frame, options: list[str]):
        slug, qtype = q["slug"], q["type"]
        if qtype == "checkbox":
            vars_ = {label: self._observe(tk.BooleanVar(value=False)) for label in options}
            self.answer_readers[slug] = lambda v=vars_: [k for k, val in v.items() if val.get()]
            for label, var in vars_.items():
                ttk.Checkbutton(frame, text=label, variable=var).pack(anchor="w", pady=2)
            return
        variable = self._observe(tk.StringVar(value=""))
        self.answer_readers[slug] = variable.get
        if qtype == "dropdown":
            ttk.Combobox(frame, values=options, state="readonly", textvariable=variable).pack(
                fill="x", pady=4)
        elif qtype in {"onerow", "scale", "stars"}:
            row = ttk.Frame(frame); row.pack(anchor="w", fill="x")
            for label in options:
                caption = ("★ " if qtype == "stars" else "") + label
                ttk.Radiobutton(row, text=caption, variable=variable, value=label).pack(side="left", padx=(0, 9))
        else:
            for label in options:
                ttk.Radiobutton(frame, text=label, variable=variable, value=label).pack(anchor="w", pady=2)

    def _render_entry(self, q: dict, frame: ttk.Frame):
        slug = q["slug"]
        if q["type"] == "text" and q.get("multiline", True):
            widget = tk.Text(frame, height=3, wrap="word", relief="solid", bd=1)
            widget.pack(fill="x", pady=4)
            self.answer_readers[slug] = lambda w=widget: w.get("1.0", "end-1c")
            self.resetters.append(lambda w=widget: w.delete("1.0", "end"))
            return
        variable = self._observe(tk.StringVar(value=""))
        self.answer_readers[slug] = variable.get
        hint = " (YYYY-MM-DD)" if q["type"] == "date" else (" (целое число)" if q["type"] == "integer" else "")
        if hint:
            ttk.Label(frame, text=hint, foreground="#777777").pack(anchor="w")
        ttk.Entry(frame, textvariable=variable).pack(fill="x", pady=4)

    def _render_matrix(self, q: dict, frame: ttk.Frame):
        columns = [r if isinstance(r, str) else r["label"] for r in q["columns"]]
        rows = [r if isinstance(r, str) else r["label"] for r in q["rows"]]
        grid = ttk.Frame(frame); grid.pack(fill="x")
        ttk.Label(grid, text="").grid(row=0, column=0, sticky="w")
        for col, label in enumerate(columns, 1):
            ttk.Label(grid, text=label, wraplength=100).grid(row=0, column=col, padx=7, pady=3)
        row_vars = {}
        for pos, label in enumerate(rows, 1):
            ttk.Label(grid, text=label, wraplength=230).grid(row=pos, column=0, sticky="w", padx=(0, 12))
            row_vars[label] = self._observe(tk.StringVar(value=""))
            for col, option in enumerate(columns, 1):
                ttk.Radiobutton(grid, variable=row_vars[label], value=option).grid(
                    row=pos, column=col, padx=8, pady=4)
        self.answer_readers[q["slug"]] = lambda v=row_vars: {k: var.get() for k, var in v.items()}

    def collect_answers(self) -> dict:
        return {slug: getter() for slug, getter in self.answer_readers.items()}

    def update_visibility(self):
        if self._rendering:
            return
        self._rendering = True
        try:
            visible = visible_slugs(self.config_data, self.collect_answers())
            if visible == self.last_visible:
                return
            for slug, block in self.blocks.items():
                # Each question has a stable parent slot, so hidden questions
                # reappear at the original position (also across sections).
                if slug not in visible:
                    block.pack_forget()
                elif not block.winfo_manager():
                    block.pack(fill="x", anchor="n", pady=(0, 10))
            self.last_visible = visible
        finally:
            self._rendering = False

    def clear_answers(self):
        for fn in self.resetters:
            fn()
        self.update_visibility()
        self.canvas.yview_moveto(0)

    def check_responses(self):
        errors = check_answers(self.config_data, self.collect_answers())
        if errors:
            messagebox.showwarning("Проверка ответов (локально)", "Проверьте ответы:\n\n" +
                                   "\n".join(f"• {error}" for error in errors[:20]), parent=self)
        else:
            messagebox.showinfo("Проверка ответов (локально)",
                                "Ответы прошли предварительную проверку. Никакие данные не отправлены.", parent=self)
