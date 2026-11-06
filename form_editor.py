#!/usr/bin/env python3
"""Графический конструктор Яндекс Форм (Tkinter из стандартной библиотеки)."""
from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from copy import deepcopy
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import engine

LABELS = {
    "radio": "Один вариант", "checkbox": "Несколько вариантов", "dropdown": "Выпадающий список",
    "scale": "Шкала", "stars": "Звёзды", "onerow": "В одну строку", "text": "Текст",
    "matrix": "Матрица", "boolean": "Да/нет", "integer": "Число", "date": "Дата",
    "section": "Раздел", "comment": "Текстовый блок", "api": "API / расширенный JSON",
}


def pretty(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


class JsonDialog(tk.Toplevel):
    """Full JSON editing so uncommon/API-native question types remain available."""
    def __init__(self, parent, title: str, data: object, validator=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("850x670")
        self.minsize(540, 350)
        self.transient(parent)
        self.result = None
        ttk.Label(self, text="Редактируйте JSON. Нажмите «Проверить», чтобы найти ошибки.").pack(
            anchor="w", padx=12, pady=(10, 2))
        wrap = ttk.Frame(self); wrap.pack(fill="both", expand=True, padx=12, pady=8)
        self.editor = tk.Text(wrap, undo=True, wrap="none", font=("Consolas", 11))
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.editor.yview)
        hs = ttk.Scrollbar(wrap, orient="horizontal", command=self.editor.xview)
        self.editor.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.editor.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1); wrap.columnconfigure(0, weight=1)
        self.editor.insert("1.0", pretty(data))
        buttons = ttk.Frame(self); buttons.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(buttons, text="Проверить", command=lambda: self.check(False, validator)).pack(side="left")
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Сохранить", command=lambda: self.check(True, validator)).pack(side="right")
        self.grab_set()
        self.wait_window()

    def check(self, save, validator):
        try:
            data = json.loads(self.editor.get("1.0", "end-1c"))
            if validator:
                validator(data)
        except (ValueError, engine.ConfigError, TypeError) as exc:
            messagebox.showerror("Ошибка JSON", str(exc), parent=self)
            return
        if save:
            self.result = data
            self.destroy()
        else:
            messagebox.showinfo("Проверка", "JSON корректен.", parent=self)


class QuestionDialog(tk.Toplevel):
    def __init__(self, parent, current: dict | None = None, suggested_slug="q1"):
        super().__init__(parent)
        self.title("Редактировать вопрос" if current else "Новый вопрос")
        self.geometry("770x760")
        self.minsize(590, 540)
        self.transient(parent)
        self.result = None
        self.original = deepcopy(current or {})
        self.v_type = tk.StringVar(value=self.original.get("type", "radio"))
        self.v_slug = tk.StringVar(value=self.original.get("slug", suggested_slug))
        self.v_required = tk.BooleanVar(value=self.original.get("required", True))
        self.v_multiline = tk.BooleanVar(value=self.original.get("multiline", True))
        self.v_other = tk.BooleanVar(value=bool(self.original.get("other")))
        self.v_other_label = tk.StringVar(value=self.original.get("other", {}).get("label", "Укажите свой вариант"))
        self.v_other_option = tk.StringVar(value=self.original.get("other", {}).get("option", "Другое"))
        self.v_min = tk.StringVar(value=str(self.original.get("min", self.original.get("min_choices", self.original.get("min_length", "")))))
        self.v_max = tk.StringVar(value=str(self.original.get("max", self.original.get("max_choices", self.original.get("max_length", "")))))
        controls = ttk.Frame(self, padding=12)
        controls.pack(fill="both", expand=True)
        controls.columnconfigure(1, weight=1)
        r = 0
        ttk.Label(controls, text="Тип вопроса:").grid(row=r, column=0, sticky="w", pady=4)
        self.type_box = ttk.Combobox(controls, values=list(LABELS.keys()), textvariable=self.v_type, state="readonly")
        self.type_box.grid(row=r, column=1, sticky="ew", pady=4)
        self.type_box.bind("<<ComboboxSelected>>", lambda e: self.show_type_fields())
        r += 1
        ttk.Label(controls, text="Формулировка вопроса:").grid(row=r, column=0, sticky="nw", pady=4)
        self.label_box = tk.Text(controls, height=3, wrap="word")
        self.label_box.insert("1.0", self.original.get("label", ""))
        self.label_box.grid(row=r, column=1, sticky="nsew", pady=4)
        r += 1
        ttk.Label(controls, text="Код (slug):").grid(row=r, column=0, sticky="w", pady=4)
        ttk.Entry(controls, textvariable=self.v_slug).grid(row=r, column=1, sticky="ew", pady=4)
        r += 1
        ttk.Label(controls, text="Подсказка:").grid(row=r, column=0, sticky="nw", pady=4)
        self.comment_box = tk.Text(controls, height=2, wrap="word")
        self.comment_box.insert("1.0", self.original.get("comment", ""))
        self.comment_box.grid(row=r, column=1, sticky="nsew", pady=4)
        r += 1
        ttk.Checkbutton(controls, text="Обязательный ответ", variable=self.v_required).grid(
            row=r, column=1, sticky="w", pady=4)
        r += 1
        self.enum_frame = ttk.LabelFrame(controls, text="Варианты ответа (каждый с новой строки)", padding=6)
        self.enum_frame.grid(row=r, column=0, columnspan=2, sticky="nsew", pady=7)
        self.enum_frame.columnconfigure(0, weight=1)
        self.options_box = tk.Text(self.enum_frame, height=6, wrap="word")
        opts = self.original.get("options", ["Да", "Нет"])
        self.options_box.insert("1.0", "\n".join(v if isinstance(v, str) else v.get("label", "") for v in opts))
        self.options_box.grid(row=0, column=0, sticky="nsew")
        ttk.Checkbutton(self.enum_frame, text="Добавить поле «Другое»", variable=self.v_other).grid(
            row=1, column=0, sticky="w", pady=4)
        other_row = ttk.Frame(self.enum_frame)
        other_row.grid(row=2, column=0, sticky="ew", pady=(2, 4))
        ttk.Label(other_row, text="Вариант:").pack(side="left")
        ttk.Entry(other_row, textvariable=self.v_other_option, width=15).pack(side="left", padx=4)
        ttk.Label(other_row, text="Текст доп. поля:").pack(side="left")
        ttk.Entry(other_row, textvariable=self.v_other_label, width=28).pack(side="left", padx=4, fill="x", expand=True)
        r += 1
        self.matrix_frame = ttk.LabelFrame(controls, text="Строки и столбцы матрицы", padding=6)
        self.matrix_frame.grid(row=r, column=0, columnspan=2, sticky="ew", pady=7)
        self.matrix_frame.columnconfigure(0, weight=1); self.matrix_frame.columnconfigure(1, weight=1)
        ttk.Label(self.matrix_frame, text="Строки (по одной)").grid(row=0, column=0, sticky="w")
        ttk.Label(self.matrix_frame, text="Столбцы (по одному)").grid(row=0, column=1, sticky="w")
        self.rows_box = tk.Text(self.matrix_frame, height=4)
        self.cols_box = tk.Text(self.matrix_frame, height=4)
        self.rows_box.insert("1.0", "\n".join(v if isinstance(v,str) else v.get("label", "") for v in self.original.get("rows", [])))
        self.cols_box.insert("1.0", "\n".join(v if isinstance(v,str) else v.get("label", "") for v in self.original.get("columns", [])))
        self.rows_box.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        self.cols_box.grid(row=1, column=1, sticky="nsew")
        r += 1
        self.text_frame = ttk.Frame(controls)
        self.text_frame.grid(row=r, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Checkbutton(self.text_frame, text="Многострочный ответ", variable=self.v_multiline).pack(anchor="w")
        r += 1
        self.bounds_frame = ttk.Frame(controls)
        self.bounds_frame.grid(row=r, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Label(self.bounds_frame, text="Минимум:").pack(side="left")
        ttk.Entry(self.bounds_frame, width=12, textvariable=self.v_min).pack(side="left", padx=(5, 12))
        ttk.Label(self.bounds_frame, text="Максимум:").pack(side="left")
        ttk.Entry(self.bounds_frame, width=12, textvariable=self.v_max).pack(side="left", padx=5)
        r += 1
        self.api_frame = ttk.Frame(controls)
        self.api_frame.grid(row=r, column=0, columnspan=2, sticky="ew")
        ttk.Label(self.api_frame, text="Дополнительные поля API задаются через кнопку «JSON вопроса».").pack(anchor="w")
        self.show_type_fields()
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(buttons, text="JSON вопроса...", command=self.edit_as_json).pack(side="left")
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Сохранить вопрос", command=self.save).pack(side="right")
        self.grab_set()
        self.wait_window()

    def show_type_fields(self):
        qtype = self.v_type.get()
        for frame in (self.enum_frame, self.matrix_frame, self.text_frame, self.bounds_frame, self.api_frame):
            frame.grid_remove()
        if qtype in engine.ENUM_TYPES:
            self.enum_frame.grid()
        if qtype == "matrix":
            self.matrix_frame.grid()
        if qtype == "text":
            self.text_frame.grid()
        if qtype in {"integer", "date", "checkbox", "text"}:
            self.bounds_frame.grid()
        if qtype == "api":
            self.api_frame.grid()

    def collect(self):
        qtype = self.v_type.get()
        label = self.label_box.get("1.0", "end-1c").strip()
        slug = self.v_slug.get().strip()
        result = {"type": qtype, "label": label}
        if qtype not in {"section", "comment"}:
            result["slug"] = slug
            result["required"] = self.v_required.get()
        comment = self.comment_box.get("1.0", "end-1c").strip()
        if comment:
            result["comment"] = comment
        if qtype in engine.ENUM_TYPES:
            labels = [x.strip() for x in self.options_box.get("1.0", "end-1c").splitlines() if x.strip()]
            old_opts = self.original.get("options", [])
            original_by_label = {x["label"]: x for x in old_opts if isinstance(x, dict) and "label" in x}
            result["options"] = [deepcopy(original_by_label.get(s, s)) for s in labels]
            if self.v_other.get():
                opt = self.v_other_option.get().strip() or "Другое"
                if opt not in labels:
                    result["options"].append(opt)
                result["other"] = deepcopy(self.original.get("other", {}))
                result["other"].update({"option": opt, "label": self.v_other_label.get().strip() or "Укажите свой вариант"})
        if qtype == "matrix":
            result["rows"] = [x.strip() for x in self.rows_box.get("1.0", "end-1c").splitlines() if x.strip()]
            result["columns"] = [x.strip() for x in self.cols_box.get("1.0", "end-1c").splitlines() if x.strip()]
        if qtype == "text":
            result["multiline"] = self.v_multiline.get()
        if qtype in {"integer", "date", "checkbox", "text"}:
            fields = {"checkbox": ("min_choices", "max_choices"), "text": ("min_length", "max_length")}.get(qtype, ("min", "max"))
            for key, raw in zip(fields, (self.v_min.get().strip(), self.v_max.get().strip())):
                if raw:
                    result[key] = raw if qtype == "date" else int(raw)
        if qtype == "api":
            result["payload"] = deepcopy(self.original.get("payload", {"type": "string", "label": label, "slug": slug}))
        if qtype == self.original.get("type"):
            used = set(result)
            excluded = {"type", "label", "slug", "options", "other", "rows", "columns", "multiline",
                        "min", "max", "min_choices", "max_choices", "min_length", "max_length", "required", "comment"}
            for key, value in self.original.items():
                if key not in used and key not in excluded:
                    result[key] = deepcopy(value)
        return result

    def save(self):
        try:
            obj = self.collect()
        except ValueError:
            messagebox.showerror("Ошибка", "В числовом поле минимум/максимум должно быть целое число.", parent=self)
            return
        # Validate the isolated question before returning it to the full form.
        try:
            engine.validate_config({"form": {"name": "Проверка"}, "questions": [obj]})
        except engine.ConfigError as exc:
            messagebox.showerror("Ошибка вопроса", str(exc), parent=self)
            return
        self.result = obj
        self.destroy()

    def edit_as_json(self):
        try:
            initial = self.collect()
        except ValueError:
            initial = self.original
        dialog = JsonDialog(self, "Расширенный редактор вопроса", initial,
                            lambda q: engine.validate_config({"form": {"name": "Проверка"}, "questions": [q]}))
        if dialog.result is not None:
            self.result = dialog.result
            self.destroy()


class FormSettingsDialog(tk.Toplevel):
    def __init__(self, parent, form):
        super().__init__(parent)
        self.title("Параметры формы")
        self.geometry("670x465")
        self.transient(parent)
        self.result = None
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        self.vars = {}
        fields = [("name", "Название формы"), ("submit_text", "Текст кнопки"),
                  ("success_title", "Заголовок после отправки"),
                  ("success_subtitle", "Подзаголовок после отправки")]
        for r, (key, label) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=r, column=0, sticky="w", pady=8, padx=(0, 12))
            v = tk.StringVar(value=form.get(key, "")); self.vars[key] = v
            ttk.Entry(frame, textvariable=v).grid(row=r, column=1, sticky="ew", pady=8)
        for r, (key, label) in enumerate((("allow_multiple_answers", "Разрешить повторные ответы"),
                                          ("need_auth", "Требовать авторизацию"),
                                          ("publish_by_default", "Предлагать публикацию сразу")), 4):
            v = tk.BooleanVar(value=form.get(key, {"allow_multiple_answers": True}.get(key, False)))
            self.vars[key] = v
            ttk.Checkbutton(frame, text=label, variable=v).grid(row=r, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Label(frame, text="Внимание: доступность анонимного заполнения зависит также от настроек Яндекса.",
                  foreground="#777").grid(row=7, column=0, columnspan=2, sticky="w", pady=10)
        btns = ttk.Frame(self); btns.pack(fill="x", padx=16, pady=12)
        ttk.Button(btns, text="Отмена", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(btns, text="Сохранить", command=self.save).pack(side="right")
        self.grab_set(); self.wait_window()

    def save(self):
        data = {k: v.get() for k, v in self.vars.items()}
        if not data["name"].strip():
            messagebox.showerror("Ошибка", "Укажите название формы.", parent=self)
            return
        self.result = data
        self.destroy()


class CredentialsDialog(tk.Toplevel):
    def __init__(self, parent, current=None):
        super().__init__(parent)
        self.title("Авторизация Яндекс Форм")
        self.geometry("620x350")
        self.transient(parent)
        self.result = None
        self.saved = False
        current = current or {}
        frame = ttk.Frame(self, padding=16); frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        self.auth = tk.StringVar(value=current.get("auth_scheme", "OAuth"))
        self.org_header = tk.StringVar(value=current.get("org_header", "X-Org-Id"))
        self.token = tk.StringVar(value=current.get("token", ""))
        self.org_id = tk.StringVar(value=current.get("org_id", ""))
        self.remember = tk.BooleanVar(value=False)
        for r, (label, var, vals) in enumerate((
            ("Тип токена", self.auth, ["OAuth", "Bearer"]),
            ("Тип организации", self.org_header, ["X-Org-Id", "X-Cloud-Org-Id"]))):
            ttk.Label(frame, text=label).grid(row=r, column=0, sticky="w", pady=7)
            ttk.Combobox(frame, values=vals, textvariable=var, state="readonly").grid(row=r, column=1, sticky="ew", pady=7)
        for r, (label, var, secret) in enumerate((("Токен API", self.token, True), ("ID организации", self.org_id, False)), 2):
            ttk.Label(frame, text=label).grid(row=r, column=0, sticky="w", pady=7)
            ttk.Entry(frame, textvariable=var, show="●" if secret else "").grid(row=r, column=1, sticky="ew", pady=7)
        ttk.Checkbutton(frame, text="Запомнить токен в локальном файле (не зашифрован)",
                        variable=self.remember).grid(row=4, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Label(frame, text="Токен не добавляется в анкету. Сохранённый файл нельзя передавать другим.",
                  foreground="#777").grid(row=5, column=0, columnspan=2, sticky="w", pady=5)
        buttons = ttk.Frame(self); buttons.pack(fill="x", padx=16, pady=12)
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(buttons, text="Продолжить", command=self.confirm).pack(side="right")
        self.grab_set(); self.wait_window()

    def confirm(self):
        if not self.token.get().strip() or not self.org_id.get().strip():
            messagebox.showerror("Ошибка", "Не заполнены токен или ID организации.", parent=self)
            return
        self.result = {"auth_scheme": self.auth.get(), "org_header": self.org_header.get(),
                       "token": self.token.get().strip(), "org_id": self.org_id.get().strip()}
        self.saved = self.remember.get()
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Яндекс Формы — универсальный конструктор")
        self.user_settings = engine.load_settings()
        self.geometry(self.user_settings.get("window_geometry", "1240x780"))
        self.minsize(960, 600)
        self.config_data = {"form": {"name": "Новая анкета", "allow_multiple_answers": True,
                                     "need_auth": False, "publish_by_default": False}, "questions": []}
        self.path: Path | None = None
        self.dirty = False
        self.busy = False
        self.messages = queue.Queue()
        self._build()
        self._bind_shortcuts()
        last_form = Path(self.user_settings.get("last_form_path", "")) if self.user_settings.get("last_form_path") else None
        if last_form and last_form.is_file():
            self.open_path(last_form)
        else:
            self.refresh()
        self.after(120, self.poll_messages)
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

    def _build(self):
        bar = ttk.Frame(self, padding=(10, 10)); bar.pack(fill="x")
        buttons = [("Новая", self.new), ("Открыть JSON", self.open_file), ("Сохранить", self.save),
                   ("Сохранить как", self.save_as), ("Параметры", self.settings),
                   ("Весь JSON", self.edit_json), ("Проверить", self.validate),
                   ("Предпросмотр", self.preview)]
        for title, callback in buttons:
            ttk.Button(bar, text=title, command=callback).pack(side="left", padx=2)
        self.publish_btn = ttk.Button(bar, text="Создать в Яндексе", command=self.create)
        self.publish_btn.pack(side="right", padx=5)
        self.name_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.name_var, font=("Segoe UI", 14, "bold"), padding=(12, 8)).pack(anchor="w")
        main = ttk.Panedwindow(self, orient="horizontal"); main.pack(fill="both", expand=True, padx=12, pady=7)
        left = ttk.Frame(main, width=790); main.add(left, weight=5)
        right = ttk.Frame(main, width=380); main.add(right, weight=3)
        left.rowconfigure(0, weight=1); left.columnconfigure(0, weight=1)
        columns = ("type", "label", "required", "slug")
        self.tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("type", text="Тип"); self.tree.heading("label", text="Вопрос")
        self.tree.heading("required", text="Обяз."); self.tree.heading("slug", text="Slug")
        self.tree.column("type", width=160, stretch=False)
        self.tree.column("label", width=420, stretch=True)
        self.tree.column("required", width=55, stretch=False, anchor="center")
        self.tree.column("slug", width=115, stretch=False)
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        scroll_h = ttk.Scrollbar(left, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=scroll_h.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        scroll_h.grid(row=1, column=0, sticky="ew")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.render_selected())
        self.tree.bind("<Double-Button-1>", lambda e: self.edit_question())
        ttk.Label(right, text="Содержимое выбранного элемента", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.detail = tk.Text(right, wrap="word", state="disabled", font=("Consolas", 10), height=12)
        self.detail.pack(fill="both", expand=True, pady=(8, 0))
        ops = ttk.Frame(self, padding=(10, 2)); ops.pack(fill="x")
        for label, cmd in [("+ Добавить", self.add_question), ("Изменить", self.edit_question),
                           ("JSON вопроса", self.edit_question_json), ("Дублировать", self.duplicate),
                           ("Удалить", self.delete), ("↑ Выше", lambda: self.move(-1)),
                           ("↓ Ниже", lambda: self.move(+1)), ("Условия показа", self.edit_conditions)]:
            ttk.Button(ops, text=label, command=cmd).pack(side="left", padx=3, pady=6)
        ttk.Label(self, text="Журнал операции:", padding=(12, 3)).pack(anchor="w")
        self.log_view = tk.Text(self, height=5, wrap="word", state="disabled", font=("Consolas", 9))
        self.log_view.pack(fill="x", padx=12, pady=(0, 3))
        self.status = tk.StringVar(value="Готово")
        ttk.Label(self, textvariable=self.status, relief="sunken", padding=(10, 4)).pack(fill="x", side="bottom")

    def _bind_shortcuts(self):
        """Shortcuts work regardless of keyboard focus; deletion remains tree-only."""
        for keys, handler in (("<Control-n>", self.new),
                              ("<Control-o>", self.open_file),
                              ("<Control-s>", self.save),
                              ("<Control-Shift-S>", self.save_as),
                              ("<F5>", self.preview)):
            self.bind_all(keys, lambda _event, callback=handler: (callback(), "break")[1])
        self.tree.bind("<Delete>", lambda _event: (self.delete(), "break")[1])

    def log(self, text: str):
        self.log_view.configure(state="normal")
        self.log_view.insert("end", text + "\n")
        self.log_view.see("end")
        self.log_view.configure(state="disabled")
        self.status.set(text)

    def refresh(self, selected=None):
        selected = selected if selected is not None else self.selected_index()
        for id_ in self.tree.get_children():
            self.tree.delete(id_)
        for i, q in enumerate(self.config_data["questions"]):
            self.tree.insert("", "end", iid=str(i), values=(LABELS.get(q.get("type"), q.get("type")),
                q.get("label", "").replace("\n", " ")[:130], "Да" if q.get("required") else "", q.get("slug", "")))
        if selected is not None and self.tree.exists(str(selected)):
            self.tree.selection_set(str(selected)); self.tree.focus(str(selected)); self.tree.see(str(selected))
        self.render_selected()
        file = self.path.name if self.path else "(не сохранено)"
        self.title(f"{'* ' if self.dirty else ''}Яндекс Формы — {file}")
        self.name_var.set(f"{self.config_data['form']['name']}  •  {len(self.config_data['questions'])} элементов")

    def selected_index(self):
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def render_selected(self):
        i = self.selected_index()
        self.detail.configure(state="normal"); self.detail.delete("1.0", "end")
        if i is not None and i < len(self.config_data["questions"]):
            self.detail.insert("1.0", pretty(self.config_data["questions"][i]))
        self.detail.configure(state="disabled")

    def unsaved(self):
        if not self.dirty:
            return True
        return messagebox.askyesno("Несохранённые изменения", "Есть изменения. Продолжить без сохранения?")

    def new(self):
        if not self.unsaved(): return
        self.config_data = {"form": {"name": "Новая анкета", "allow_multiple_answers": True,
                                    "need_auth": False, "publish_by_default": False}, "questions": []}
        self.path = None; self.dirty = False
        self.refresh()

    def open_file(self):
        if not self.unsaved(): return
        path = filedialog.askopenfilename(title="Открыть анкету", filetypes=[("JSON анкеты", "*.json")])
        if path: self.open_path(Path(path))

    def open_path(self, path: Path):
        try:
            data = engine.load_config(path)
        except engine.ConfigError as exc:
            messagebox.showerror("Ошибка открытия", str(exc)); return
        self.config_data = data; self.path = path; self.dirty = False
        self.refresh(0); self.log(f"Открыт файл: {path}")
        self.persist_settings()

    def _write(self, path: Path):
        try:
            engine.validate_config(self.config_data)
            payload = pretty(self.config_data) + "\n"
            tmp = path.with_name(path.name + ".tmp")
            try:
                tmp.write_text(payload, encoding="utf-8")
                tmp.replace(path)
            finally:
                if tmp.exists(): tmp.unlink()
        except (OSError, engine.ConfigError) as exc:
            messagebox.showerror("Ошибка сохранения", str(exc)); return False
        self.path = path; self.dirty = False; self.refresh()
        self.persist_settings()
        self.log(f"Сохранено: {path}")
        return True

    def save(self):
        return self._write(self.path) if self.path else self.save_as()

    def save_as(self):
        file = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")],
                                            initialfile=self.path.name if self.path else "form_config.json")
        return self._write(Path(file)) if file else False

    def mark_dirty(self, selected=None):
        self.dirty = True; self.refresh(selected)

    def settings(self):
        dialog = FormSettingsDialog(self, self.config_data["form"])
        if dialog.result is not None:
            self.config_data["form"].update(dialog.result); self.mark_dirty()

    def next_slug(self):
        taken = {q.get("slug") for q in self.config_data["questions"]}
        i = 1
        while f"q{i}" in taken: i += 1
        return f"q{i}"

    def add_question(self):
        dialog = QuestionDialog(self, suggested_slug=self.next_slug())
        if dialog.result is not None:
            self.config_data["questions"].append(dialog.result)
            self.mark_dirty(len(self.config_data["questions"]) - 1)

    def edit_question(self):
        i = self.selected_index()
        if i is None: return
        dialog = QuestionDialog(self, self.config_data["questions"][i])
        if dialog.result is not None:
            self.config_data["questions"][i] = dialog.result; self.mark_dirty(i)

    def edit_question_json(self):
        i = self.selected_index()
        if i is None: return
        dlg = JsonDialog(self, "JSON выбранного вопроса", self.config_data["questions"][i],
                         lambda q: engine.validate_config({"form": {"name": "Тест"}, "questions": [q]}))
        if dlg.result is not None:
            self.config_data["questions"][i] = dlg.result; self.mark_dirty(i)

    def duplicate(self):
        i = self.selected_index()
        if i is None: return
        obj = deepcopy(self.config_data["questions"][i])
        if "slug" in obj:
            obj["slug"] = self.next_slug()
            if "other" in obj: obj["other"].pop("slug", None)
            if obj.get("type") == "api": obj.get("payload", {}).update(slug=obj["slug"])
        self.config_data["questions"].insert(i + 1, obj); self.mark_dirty(i + 1)

    def delete(self):
        i = self.selected_index()
        if i is None: return
        if not messagebox.askyesno("Удаление", "Удалить выбранный элемент?"): return
        q = self.config_data["questions"].pop(i)
        slug = q.get("slug")
        deleted_slugs = {slug}
        if slug and q.get("other"):
            deleted_slugs.add(q["other"].get("slug", f"{slug}_other"))
        # Remove references to deleted question; dependent conditions cannot remain valid.
        removed = [c for c in self.config_data.get("conditions", []) if (c.get("source") in deleted_slugs or c.get("target") in deleted_slugs)]
        if removed:
            self.config_data["conditions"] = [c for c in self.config_data["conditions"] if c not in removed]
            self.log(f"Удалено связанных условий: {len(removed)}")
        self.mark_dirty(min(i, len(self.config_data["questions"]) - 1))

    def move(self, step):
        i = self.selected_index(); j = (i + step) if i is not None else -1
        if i is None or not (0 <= j < len(self.config_data["questions"])): return
        qs = self.config_data["questions"]; qs[i], qs[j] = qs[j], qs[i]
        self.mark_dirty(j)

    def edit_conditions(self):
        dlg = JsonDialog(self, "Условия показа (JSON)", self.config_data.get("conditions", []),
                         self._validate_conditions)
        if dlg.result is not None:
            self.config_data["conditions"] = dlg.result; self.mark_dirty()

    def _validate_conditions(self, candidate):
        data = deepcopy(self.config_data); data["conditions"] = candidate
        engine.validate_config(data)

    def edit_json(self):
        dlg = JsonDialog(self, "Полный JSON анкеты", self.config_data, engine.validate_config)
        if dlg.result is not None:
            self.config_data = dlg.result; self.mark_dirty()

    def validate(self):
        try:
            engine.validate_config(self.config_data)
            payloads, conds = engine.expand_questions(self.config_data)
        except engine.ConfigError as exc:
            messagebox.showerror("Ошибки в анкете", str(exc)); return False
        messagebox.showinfo("Проверка завершена", f"Конфигурация корректна.\n"
                           f"Блоков/вопросов: {len(payloads)}\nУсловий показа: {len(conds)}")
        return True

    def preview(self):
        try:
            engine.validate_config(self.config_data)
        except engine.ConfigError as exc:
            messagebox.showerror("Ошибка анкеты", str(exc), parent=self)
            return
        from form_preview import PreviewWindow
        PreviewWindow(self, deepcopy(self.config_data))

    def create(self):
        if self.busy: return
        try:
            engine.validate_config(self.config_data)
        except engine.ConfigError as exc:
            messagebox.showerror("Ошибка анкеты", str(exc)); return
        if self.dirty and not self.save(): return
        remembered = engine.environment_credentials() or engine.load_credentials()
        dialog = CredentialsDialog(self, remembered)
        if dialog.result is None: return
        if dialog.saved:
            try: engine.save_credentials(dialog.result)
            except OSError as exc:
                messagebox.showwarning("Сохранение токена", str(exc))
        publish = bool(self.config_data["form"].get("publish_by_default", False))
        count = len(self.config_data["questions"])
        if not messagebox.askyesno("Создание новой формы", f"Будет создана НОВАЯ форма:\n"
                                   f"{self.config_data['form']['name']}\nЭлементов: {count}\n"
                                   f"Сразу опубликовать: {'да' if publish else 'нет'}\n\nПродолжить?"):
            return
        self.busy = True; self.publish_btn.configure(state="disabled")
        config = deepcopy(self.config_data)
        credentials = dialog.result
        def worker():
            try:
                result = engine.create_form(config, credentials, publish=publish,
                                            progress=lambda msg: self.messages.put(("log", msg)))
                self.messages.put(("success", result))
            except Exception as exc:
                self.messages.put(("error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll_messages(self):
        try:
            while True:
                kind, payload = self.messages.get_nowait()
                if kind == "log": self.log(payload)
                elif kind == "error":
                    self.busy = False; self.publish_btn.configure(state="normal")
                    self.log("Ошибка создания: " + payload)
                    messagebox.showerror("Создание остановлено", payload)
                elif kind == "success":
                    self.busy = False; self.publish_btn.configure(state="normal")
                    msg = (f"Форма создана.\n\nРедактирование:\n{payload['edit_url']}\n\n"
                           f"Заполнение:\n{payload['fill_url']}\n\n"
                           f"Опубликована: {'да' if payload['published'] else 'нет'}")
                    self.log(msg)
                    messagebox.showinfo("Готово", msg)
        except queue.Empty:
            pass
        self.after(120, self.poll_messages)

    def persist_settings(self):
        self.user_settings["window_geometry"] = self.geometry()
        if self.path:
            self.user_settings["last_form_path"] = str(self.path.resolve())
        else:
            self.user_settings.pop("last_form_path", None)
        try:
            engine.save_settings(self.user_settings)
        except OSError as exc:
            self.log(f"Не удалось сохранить настройки рядом с EXE: {exc}")

    def on_exit(self):
        if self.busy:
            messagebox.showwarning("Выполняется создание", "Дождитесь завершения операции, чтобы не прервать создание формы.")
            return
        if self.unsaved():
            self.persist_settings()
            self.destroy()


if __name__ == "__main__":
    App().mainloop()