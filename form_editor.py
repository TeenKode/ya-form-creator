#!/usr/bin/env python3
"""Графический конструктор Яндекс Форм (Tkinter из стандартной библиотеки)."""
from __future__ import annotations

import json
import queue
import threading
import webbrowser
import tkinter as tk
from copy import deepcopy
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import engine
import logic_analyzer
from logic_dialog import LogicReviewDialog
from ui_theme import apply_theme, set_icon, resource_path, ScrollFrame, dialog_size, BG, INK, MUTED
from dialogs import HelpWindow, ResultDialog, ConditionsDialog, replace_question

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
        dialog_size(self, 850, 670)
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
        dialog_size(self, 770, 780)
        self.minsize(570, 400)
        self.transient(parent)
        self.result = None
        self.original = deepcopy(current or {})
        self.v_type = tk.StringVar(value=LABELS[self.original.get("type", "radio")])
        self.v_slug = tk.StringVar(value=self.original.get("slug", suggested_slug))
        self.v_required = tk.BooleanVar(value=self.original.get("required", True))
        self.v_multiline = tk.BooleanVar(value=self.original.get("multiline", True))
        self.v_other = tk.BooleanVar(value=bool(self.original.get("other")))
        self.v_other_label = tk.StringVar(value=(self.original.get("other") or {}).get("label", "Укажите свой вариант"))
        self.v_other_option = tk.StringVar(value=(self.original.get("other") or {}).get("option", "Другое"))
        self.exclusive_initial = engine.exclusive_options(self.original)
        self.v_min = tk.StringVar(value=str(self.original.get("min", self.original.get("min_choices", self.original.get("min_length", "")))))
        self.v_max = tk.StringVar(value=str(self.original.get("max", self.original.get("max_choices", self.original.get("max_length", "")))))
        scroller = ScrollFrame(self)
        scroller.pack(fill="both", expand=True)
        controls = scroller.body
        controls.columnconfigure(1, weight=1)
        r = 0
        ttk.Label(controls, text="Тип вопроса:").grid(row=r, column=0, sticky="w", pady=4)
        self.type_box = ttk.Combobox(controls, values=list(LABELS.values()), textvariable=self.v_type, state="readonly")
        self.type_box.grid(row=r, column=1, sticky="ew", pady=4)
        self.type_box.bind("<<ComboboxSelected>>", lambda e: self.show_type_fields())
        r += 1
        ttk.Label(controls, text="Формулировка вопроса:").grid(row=r, column=0, sticky="nw", pady=4)
        self.label_box = tk.Text(controls, height=3, wrap="word")
        self.label_box.insert("1.0", self.original.get("label", ""))
        self.label_box.grid(row=r, column=1, sticky="nsew", pady=4)
        r += 1
        ttk.Label(controls, text="Код вопроса (авто):").grid(row=r, column=0, sticky="w", pady=4)
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
        self.other_toggle = ttk.Checkbutton(self.enum_frame, text="Добавить поле «Другое»", variable=self.v_other)
        self.other_toggle.grid(
            row=1, column=0, sticky="w", pady=4)
        other_row = ttk.Frame(self.enum_frame)
        self.other_row = other_row
        other_row.grid(row=2, column=0, sticky="ew", pady=(2, 4))
        ttk.Label(other_row, text="Вариант:").pack(side="left")
        ttk.Entry(other_row, textvariable=self.v_other_option, width=15).pack(side="left", padx=4)
        ttk.Label(other_row, text="Текст доп. поля:").pack(side="left")
        ttk.Entry(other_row, textvariable=self.v_other_label, width=28).pack(side="left", padx=4, fill="x", expand=True)
        self.exclusive_frame = ttk.LabelFrame(self.enum_frame, text="Исключающие варианты — каждый с новой строки", padding=6)
        self.exclusive_frame.grid(row=3, column=0, sticky="ew", pady=4)
        ttk.Label(self.exclusive_frame, text="Например, «Не использую». Выбор такого ответа исключит остальные.", wraplength=620).pack(anchor="w")
        self.exclusive_box = tk.Text(self.exclusive_frame, height=3, wrap="word")
        self.exclusive_box.insert("1.0", "\n".join(self.exclusive_initial))
        self.exclusive_box.pack(fill="x", pady=(4, 0))
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
        qtype = self.question_type()
        if qtype in engine.CONDITION_SOURCE_TYPES:
            self.other_toggle.grid(); self.other_row.grid()
        else:
            self.other_toggle.grid_remove(); self.other_row.grid_remove()
        if qtype == "checkbox":
            self.exclusive_frame.grid()
        else:
            self.exclusive_frame.grid_remove()
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

    def question_type(self):
        return next(key for key, label in LABELS.items() if label == self.v_type.get())

    def collect(self):
        qtype = self.question_type()
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
            if qtype == "checkbox":
                exclusive = [x.strip() for x in self.exclusive_box.get("1.0", "end-1c").splitlines() if x.strip()]
                # Explicit [] is allowed to disable automatic label recognition.
                if exclusive or "exclusive_options" in self.original:
                    result["exclusive_options"] = exclusive
            if self.v_other.get() and qtype in engine.CONDITION_SOURCE_TYPES:
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
            result["payload"]["slug"] = slug
        if qtype == self.original.get("type"):
            used = set(result)
            excluded = {"type", "label", "slug", "options", "other", "exclusive_options", "rows", "columns", "multiline",
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
        dialog_size(self, 720, 500)
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
        self.title("Подключение к Яндекс Формам")
        dialog_size(self, 720, 630)
        self.transient(parent)
        self.result = None
        self.saved = False
        current = current or {}
        area = ScrollFrame(self); area.pack(fill="both", expand=True)
        frame = area.body
        ttk.Label(frame, text="Подключите свою организацию", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Для создания форм нужен аккаунт с доступом к Фoрмам для бизнеса.\nАнкета останется на компьютере до подтверждения создания.",
                  style="Muted.TLabel").pack(anchor="w", pady=(8, 14))
        self.auth = tk.StringVar(value="IAM — Yandex Cloud" if current.get("auth_scheme") == "Bearer" else "OAuth — Яндекс ID")
        self.org_header = tk.StringVar(value="Yandex Cloud / Identity Hub" if current.get("org_header") == "X-Cloud-Org-Id" else "Яндекс 360 для бизнеса")
        self.token = tk.StringVar(value=current.get("token", ""))
        self.org_id = tk.StringVar(value=current.get("org_id", ""))
        self.remember = tk.BooleanVar(value=False)
        for label, var, values in (("Где создана организация", self.org_header, ["Яндекс 360 для бизнеса", "Yandex Cloud / Identity Hub"]),
                                  ("Способ входа", self.auth, ["OAuth — Яндекс ID", "IAM — Yandex Cloud"])):
            ttk.Label(frame, text=label).pack(anchor="w", pady=(8, 3))
            ttk.Combobox(frame, textvariable=var, values=values, state="readonly").pack(fill="x")
        ttk.Label(frame, text="Токен (без префикса OAuth или Bearer)").pack(anchor="w", pady=(12, 3))
        self.token_entry = ttk.Entry(frame, textvariable=self.token, show="●")
        self.token_entry.pack(fill="x")
        self.reveal = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Показать токен", variable=self.reveal,
                        command=lambda: self.token_entry.configure(show="" if self.reveal.get() else "●")).pack(anchor="w", pady=4)
        ttk.Label(frame, text="ID организации").pack(anchor="w", pady=(8, 3))
        ttk.Entry(frame, textvariable=self.org_id).pack(fill="x")
        ttk.Label(frame, text="Это идентификатор организации, а не ClientID приложения и не ID облака.", style="Muted.TLabel").pack(anchor="w", pady=6)
        ttk.Checkbutton(frame, text="Запомнить токен на этом компьютере (файл без шифрования)", variable=self.remember).pack(anchor="w", pady=12)
        ttk.Button(frame, text="Где взять токен и ID организации?", command=lambda: HelpWindow(self)).pack(anchor="w")
        ttk.Label(frame, text="Без отметки новый токен действует только для этой операции.\nРанее сохранённый токен можно удалить в меню «Дополнительно».",
                  style="Muted.TLabel").pack(anchor="w", pady=10)
        buttons = ttk.Frame(self, padding=16); buttons.pack(fill="x")
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="right", padx=6)
        ttk.Button(buttons, text="Продолжить", style="Accent.TButton", command=self.confirm).pack(side="right")
        self.grab_set(); self.wait_window()

    def confirm(self):
        data = {"auth_scheme": "Bearer" if self.auth.get().startswith("IAM") else "OAuth",
                "org_header": "X-Cloud-Org-Id" if self.org_header.get().startswith("Yandex") else "X-Org-Id",
                "token": self.token.get().strip(), "org_id": self.org_id.get().strip()}
        try:
            engine.validate_credentials(data)
        except engine.ConfigError as exc:
            messagebox.showerror("Проверьте подключение", str(exc), parent=self)
            return
        self.result = data
        self.saved = self.remember.get()
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Яндекс Формы — универсальный конструктор")
        apply_theme(self)
        set_icon(self)
        self.user_settings = engine.load_settings()
        try:
            self.geometry(self.user_settings.get("window_geometry", "1200x820"))
        except tk.TclError:
            self.geometry("1200x820")
        self.minsize(960, 640)
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
        menu = tk.Menu(self)
        self.configure(menu=menu)
        file_menu = tk.Menu(menu, tearoff=False)
        for title, callback, key in [("Новая анкета", self.new, "Ctrl+N"),
                ("Открыть анкету…", self.open_file, "Ctrl+O"),
                ("Сохранить", self.save, "Ctrl+S"), ("Сохранить как…", self.save_as, "Ctrl+Shift+S")]:
            file_menu.add_command(label=title, command=callback, accelerator=key)
        menu.add_cascade(label="Файл", menu=file_menu)
        advanced = tk.Menu(menu, tearoff=False)
        advanced.add_command(label="Весь JSON анкеты…", command=self.edit_json)
        advanced.add_command(label="JSON выбранного вопроса…", command=self.edit_question_json)
        advanced.add_command(label="Условия показа в JSON…", command=self.edit_conditions_json)
        advanced.add_command(label="Проверка логики между вопросами…", command=self.check_logic)
        advanced.add_separator()
        advanced.add_command(label="Удалить сохранённый токен…", command=self.forget_credentials)
        menu.add_cascade(label="Дополнительно", menu=advanced)
        menu.add_command(label="Инструкция", command=self.show_help)

        header = ttk.Frame(self, padding=(24, 20, 24, 10)); header.pack(fill="x")
        try:
            self.brand_icon = tk.PhotoImage(file=str(resource_path("assets/app-icon.png"))).subsample(4)
            ttk.Label(header, image=self.brand_icon).pack(side="left", padx=(0, 12))
        except tk.TclError:
            pass
        brand = ttk.Frame(header); brand.pack(side="left")
        ttk.Label(brand, text="YaFormCreator", style="Title.TLabel").pack(anchor="w")
        ttk.Label(brand, text="Ваши вопросы. Понятные формы.", style="Muted.TLabel").pack(anchor="w")
        ttk.Button(header, text="Как начать", command=self.show_help).pack(side="right")

        steps = ttk.Frame(self, padding=(24, 6, 24, 14)); steps.pack(fill="x")
        for text in ("01   Соберите анкету", "02   Проверьте ответы", "03   Создайте в Яндексе"):
            ttk.Label(steps, text=text, foreground="#59663D").pack(side="left", padx=(0, 32))
        bar = ttk.Frame(self, padding=(24, 0, 24, 12)); bar.pack(fill="x")
        for title, callback in [("Новая", self.new), ("Открыть…", self.open_file), ("Сохранить", self.save)]:
            ttk.Button(bar, text=title, command=callback).pack(side="left", padx=(0, 6))
        self.publish_btn = ttk.Button(bar, text="Создать в Яндексе →", style="Accent.TButton", command=self.create)
        self.publish_btn.pack(side="right")
        ttk.Button(bar, text="Предпросмотр", command=self.preview).pack(side="right", padx=6)
        ttk.Button(bar, text="Проверить", command=self.validate).pack(side="right")

        title_row = ttk.Frame(self, padding=(24, 0, 24, 10)); title_row.pack(fill="x")
        self.name_var = tk.StringVar()
        ttk.Label(title_row, textvariable=self.name_var, style="Heading.TLabel").pack(side="left")
        ttk.Button(title_row, text="Настройки анкеты", command=self.settings).pack(side="right")
        main = ttk.Panedwindow(self, orient="horizontal")
        left = ttk.Frame(main, width=650); main.add(left, weight=3)
        right = ttk.Frame(main, width=300, padding=(18, 0, 0, 0)); main.add(right, weight=1)
        left.rowconfigure(0, weight=1); left.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(left, columns=("type", "label", "required", "slug"),
                                 displaycolumns=("label", "type", "required"), show="headings", selectmode="browse", height=5)
        for key, title, width in [("label", "Вопрос или блок", 330), ("type", "Тип ответа", 155), ("required", "Обязательный", 110)]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=80, stretch=key == "label")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        scroll_h = ttk.Scrollbar(left, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=scroll_h.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns"); scroll_h.grid(row=1, column=0, sticky="ew")
        self.empty = ttk.Frame(left, padding=20)
        ttk.Label(self.empty, text="Начните с первого вопроса", style="Heading.TLabel").pack(pady=(0, 8))
        ttk.Label(self.empty, text="Добавьте вопрос вручную или откройте\nсвою анкету из файла JSON.",
                  justify="center", style="Muted.TLabel").pack()
        ttk.Button(self.empty, text="+ Добавить вопрос", command=self.add_question,
                   style="Accent.TButton").pack(pady=16)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.render_selected())
        self.tree.bind("<Double-Button-1>", lambda e: self.edit_question())
        self.tree.bind("<Return>", lambda e: self.edit_question())
        ttk.Label(right, text="Карточка вопроса", style="Heading.TLabel").pack(anchor="w", pady=(6, 12))
        self.detail = tk.Text(right, wrap="word", state="disabled", font=("Segoe UI", 11), height=8, width=28,
                              background=BG, highlightthickness=0)
        detail_scroll = ttk.Scrollbar(right, command=self.detail.yview)
        self.detail.configure(yscrollcommand=detail_scroll.set)
        detail_scroll.pack(side="right", fill="y")
        self.detail.pack(fill="both", expand=True)
        self.detail.tag_configure("heading", font=("Segoe UI", 15, "bold"))
        self.detail.tag_configure("muted", foreground=MUTED)
        footer = ttk.Frame(self); footer.pack(side="bottom", fill="x")
        ops = ttk.Frame(footer, padding=(24, 12)); ops.pack(fill="x")
        ttk.Button(ops, text="+ Добавить вопрос", style="Accent.TButton", command=self.add_question).pack(side="left", padx=(0, 6))
        self.selection_buttons = []
        for label, cmd in [("Изменить", self.edit_question), ("Копия", self.duplicate),
                           ("Удалить", self.delete), ("↑", lambda: self.move(-1)), ("↓", lambda: self.move(1))]:
            button = ttk.Button(ops, text=label, command=cmd, width=4 if label in ("↑", "↓") else 9)
            button.pack(side="left", padx=3); self.selection_buttons.append(button)
        ttk.Button(ops, text="Условия показа…", command=self.edit_conditions).pack(side="right")
        ttk.Button(ops, text="Проверка логики…", command=self.check_logic).pack(side="right", padx=(0, 10))
        self.progress = ttk.Progressbar(footer, mode="indeterminate")
        self.log_view = tk.Text(footer, height=3, wrap="word", state="disabled", font=("Segoe UI", 9), background="#EBEDE6")
        self.log_view.pack(fill="x", padx=24, pady=(0, 5))
        self.status = tk.StringVar(value="Добавьте первый вопрос — токен понадобится только при создании формы в Яндексе.")
        ttk.Label(footer, textvariable=self.status, style="Muted.TLabel", padding=(24, 7)).pack(fill="x", side="bottom")
        main.pack(fill="both", expand=True, padx=24)

    def _bind_shortcuts(self):
        """Shortcuts work regardless of keyboard focus; deletion remains tree-only."""
        for keys, handler in (("<Control-n>", self.new),
                              ("<Control-o>", self.open_file),
                              ("<Control-s>", self.save),
                              ("<Control-Shift-S>", self.save_as),
                              ("<F5>", self.preview),
                              ("<F6>", self.check_logic)):
            self.bind_all(keys, lambda event, callback=handler: self.shortcut(event, callback))
        self.tree.bind("<Delete>", lambda _event: (self.delete(), "break")[1])

    def shortcut(self, event, callback):
        if event.widget.winfo_toplevel() is self:
            callback()
            return "break"

    def accept_candidate(self, candidate):
        try:
            engine.validate_config(candidate, allow_empty=True)
            if candidate.get("questions"):
                engine.resolve_exclusive_config(candidate)
        except engine.ConfigError as exc:
            messagebox.showerror("Изменение нарушает условия анкеты", str(exc), parent=self)
            return False
        self.config_data = candidate
        return True

    def replace_question(self, index, question):
        candidate = replace_question(self.config_data, index, question)
        if self.accept_candidate(candidate):
            self.mark_dirty(index)

    def edit_conditions(self):
        dialog = ConditionsDialog(self, self.config_data)
        if dialog.result is not None:
            self.config_data["conditions"] = dialog.result
            self.mark_dirty()

    def show_help(self):
        HelpWindow(self)

    def forget_credentials(self):
        if messagebox.askyesno("Удалить сохранённый токен?", "Файл авторизации будет удалён с этого компьютера. Анкеты сохранятся.", parent=self):
            try:
                engine.CREDENTIALS_FILE.unlink(missing_ok=True)
                self.log("Сохранённый токен удалён. Переменные окружения, если заданы, продолжают действовать.")
            except OSError as exc:
                messagebox.showerror("Не удалось удалить токен", str(exc), parent=self)

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
        name = self.config_data['form']['name']
        self.name_var.set(f"{name[:48] + '…' if len(name) > 48 else name}  ·  {len(self.config_data['questions'])} элементов")
        if self.config_data["questions"]:
            self.empty.place_forget()
        else:
            self.empty.place(relx=.5, rely=.5, anchor="center")

    def selected_index(self):
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def render_selected(self):
        i = self.selected_index()
        self.detail.configure(state="normal"); self.detail.delete("1.0", "end")
        active = i is not None and i < len(self.config_data["questions"])
        for button in self.selection_buttons:
            button.configure(state="normal" if active else "disabled")
        if active:
            q = self.config_data["questions"][i]
            self.detail.insert("end", q["label"] + "\n\n", "heading")
            self.detail.insert("end", LABELS[q["type"]] + "\n", "muted")
            self.detail.insert("end", ("Обязательный ответ" if q.get("required") else "Можно пропустить") + "\n\n")
            if q.get("comment"):
                self.detail.insert("end", q["comment"] + "\n\n")
            for option in q.get("options", []):
                label = option if isinstance(option, str) else option["label"]
                self.detail.insert("end", ("□  " if q["type"] == "checkbox" else "○  ") + label + "\n")
            if q.get("other"):
                self.detail.insert("end", "\n+ Поле для своего варианта\n", "muted")
            if q.get("hidden"):
                self.detail.insert("end", "\nСкрытый вопрос\n", "muted")
            self.detail.insert("end", "\nДважды нажмите на вопрос,\nчтобы изменить его.", "muted")
        else:
            self.detail.insert("end", "Всё под рукой\n\n", "heading")
            self.detail.insert("end", "Выберите вопрос слева — здесь появятся его текст и варианты ответа.\n\n"
                               "Сначала соберите анкету, затем откройте предпросмотр и попробуйте её заполнить.\n\n"
                               "Токен и организация нужны только для отправки анкеты в Яндекс.", "muted")
        self.detail.configure(state="disabled")

    def unsaved(self):
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel("Сохранить анкету?", "Сохранить изменения перед продолжением?", parent=self)
        if answer is None:
            return False
        return bool(self.save()) if answer else True

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
            data = engine.load_config(path, allow_empty=True)
        except engine.ConfigError as exc:
            messagebox.showerror("Ошибка открытия", str(exc)); return
        self.config_data = data; self.path = path; self.dirty = False
        self.refresh(0); self.log(f"Открыт файл: {path}")
        self.persist_settings()

    def _write(self, path: Path):
        try:
            engine.validate_config(self.config_data, allow_empty=True)
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
        taken.update(q["other"].get("slug", q["slug"] + "_other")
                     for q in self.config_data["questions"] if q.get("other"))
        i = 1
        while f"q{i}" in taken or f"q{i}_other" in taken: i += 1
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
            self.replace_question(i, dialog.result)

    def edit_question_json(self):
        i = self.selected_index()
        if i is None: return
        dlg = JsonDialog(self, "JSON выбранного вопроса", self.config_data["questions"][i],
                         lambda q: engine.validate_config({"form": {"name": "Тест"}, "questions": [q]}))
        if dlg.result is not None:
            self.replace_question(i, dlg.result)

    def duplicate(self):
        i = self.selected_index()
        if i is None: return
        obj = deepcopy(self.config_data["questions"][i])
        if "slug" in obj:
            obj["slug"] = self.next_slug()
            if "other" in obj: obj["other"].pop("slug", None)
            if obj.get("type") == "api": obj.get("payload", {}).update(slug=obj["slug"])
        candidate = deepcopy(self.config_data)
        candidate["questions"].insert(i + 1, obj)
        if self.accept_candidate(candidate):
            self.mark_dirty(i + 1)

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
        candidate = deepcopy(self.config_data)
        qs = candidate["questions"]; qs[i], qs[j] = qs[j], qs[i]
        if self.accept_candidate(candidate):
            self.mark_dirty(j)

    def edit_conditions_json(self):
        dlg = JsonDialog(self, "Условия показа (JSON)", self.config_data.get("conditions", []),
                         self._validate_conditions)
        if dlg.result is not None:
            self.config_data["conditions"] = dlg.result; self.mark_dirty()

    def _validate_conditions(self, candidate):
        data = deepcopy(self.config_data); data["conditions"] = candidate
        engine.validate_config(data)

    def edit_json(self):
        dlg = JsonDialog(self, "Полный JSON анкеты", self.config_data, lambda data: engine.validate_config(data, allow_empty=True))
        if dlg.result is not None:
            self.config_data = dlg.result; self.mark_dirty()

    def check_logic(self):
        try:
            engine.validate_config(self.config_data, allow_empty=True)
            if self.config_data["questions"]:
                engine.resolve_exclusive_config(self.config_data)
            dialog = LogicReviewDialog(self, self.config_data)
        except (engine.ConfigError, ValueError) as exc:
            messagebox.showerror("Проверка логики", str(exc), parent=self)
            return
        if dialog.result is not None and dialog.result != self.config_data:
            if self.accept_candidate(dialog.result):
                self.mark_dirty()
                self.log("Предложенные условия показа добавлены. Сохраните анкету.")

    def validate(self):
        try:
            engine.validate_config(self.config_data)
            payloads, conds = engine.expand_questions(self.config_data)
            issues = logic_analyzer.analyze_logic(self.config_data)
        except (engine.ConfigError, ValueError) as exc:
            messagebox.showerror("Ошибки в анкете", str(exc), parent=self)
            return False
        if issues:
            fixes = sum(bool(issue.get("suggestion")) for issue in issues)
            self.log(f"Проверка: вероятных логических проблем: {len(issues)}")
            if messagebox.askyesno(
                "Проверка структуры и логики",
                f"JSON корректен. Элементов после развёртки: {len(payloads)}.\n"
                f"Условий показа: {len(conds)}.\n\n"
                f"Возможных логических проблем: {len(issues)}.\n"
                f"Предлагаемых исправлений: {fixes}.\n\n"
                "Открыть проверку логики?", parent=self,
            ):
                self.check_logic()
            return False
        messagebox.showinfo("Проверка завершена",
                            f"Конфигурация корректна.\n"
                            f"Блоков/вопросов: {len(payloads)}\n"
                            f"Условий показа: {len(conds)}.\n"
                            "Вероятных межвопросных противоречий не обнаружено.", parent=self)
        return True

    def preview(self):
        try:
            engine.resolve_exclusive_config(self.config_data)
        except engine.ConfigError as exc:
            messagebox.showerror("Ошибка анкеты", str(exc), parent=self)
            return
        from form_preview import PreviewWindow
        PreviewWindow(self, deepcopy(self.config_data))

    def create(self):
        if self.busy: return
        try:
            engine.resolve_exclusive_config(self.config_data)
            issues = logic_analyzer.analyze_logic(self.config_data)
        except (engine.ConfigError, ValueError) as exc:
            messagebox.showerror("Ошибка анкеты", str(exc), parent=self); return
        if issues:
            if messagebox.askyesno(
                "Проверка логики перед созданием",
                f"Обнаружены возможные логические противоречия: {len(issues)}.\n"
                "Открыть предложения по исправлению?\n\n"
                "Для создания без изменений нажмите «Нет».", parent=self,
            ):
                self.check_logic()
                return
            if not messagebox.askyesno(
                "Продолжить с предупреждениями?",
                "Создать форму, несмотря на возможные противоречия?\n"
                "Условия не будут исправлены автоматически.", parent=self,
            ):
                return
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
        self.progress.pack(fill="x", padx=24, before=self.log_view); self.progress.start(12)
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
                    self.progress.stop(); self.progress.pack_forget()
                    self.log("Ошибка создания: " + payload)
                    messagebox.showerror("Создание остановлено", payload)
                elif kind == "success":
                    self.busy = False; self.publish_btn.configure(state="normal")
                    self.progress.stop(); self.progress.pack_forget()
                    msg = (f"Форма создана.\n\nРедактирование:\n{payload['edit_url']}\n\n"
                           f"Заполнение:\n{payload['fill_url']}\n\n"
                           f"Опубликована: {'да' if payload['published'] else 'нет'}")
                    self.log(msg)
                    ResultDialog(self, payload)
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
