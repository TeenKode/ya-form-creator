"""User-facing help, conditional branching and creation results."""
from copy import deepcopy
import re
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

import engine
from ui_theme import dialog_size, resource_path, ScrollFrame


def replace_question(config, index, question):
    """Preserve references when renaming a question, including its other field."""
    candidate = deepcopy(config)
    old = candidate["questions"][index]
    renames = {}
    if old.get("slug") and question.get("slug"):
        renames[old["slug"]] = question["slug"]
        if old.get("other") and question.get("other"):
            renames[old["other"].get("slug", old["slug"] + "_other")] = question["other"].get("slug", question["slug"] + "_other")
    candidate["questions"][index] = deepcopy(question)
    for condition in candidate.get("conditions", []):
        for field in ("source", "target"):
            condition[field] = renames.get(condition[field], condition[field])
    return candidate


class HelpWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Как начать — YaFormCreator")
        dialog_size(self, 920, 740)
        self.transient(parent)
        bar = ttk.Frame(self, padding=14); bar.pack(fill="x")
        ttk.Label(bar, text="От первой анкеты до Яндекс Форм", style="Heading.TLabel").pack(side="left")
        ttk.Button(bar, text="Документация Яндекса ↗", command=lambda: webbrowser.open("https://yandex.ru/support/forms/ru/api-ref/access")).pack(side="right")
        frame = ttk.Frame(self, padding=(14, 0, 14, 14)); frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word", font=("Segoe UI", 11))
        scroll = ttk.Scrollbar(frame, command=text.yview); text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y"); text.pack(fill="both", expand=True)
        text.tag_configure("heading", font=("Segoe UI", 14, "bold"), spacing1=14, spacing3=8)
        text.tag_configure("code", font=("Consolas", 10), background="#F0F2E9")
        try:
            content = resource_path("docs/SETUP_RU.md").read_text(encoding="utf-8")
        except OSError:
            content = "Откройте инструкцию в репозитории: https://github.com/TeenKode/ya-form-creator/blob/main/docs/SETUP_RU.md"
        code = False
        for line in content.splitlines():
            if line.startswith("```"):
                code = not code
                continue
            tag = "code" if code else "heading" if line.startswith("#") else ""
            if not code:
                line = re.sub(r"^#+\s*", "", line).replace("**", "").replace("`", "")
                line = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r"\1 (\2)", line)
            text.insert("end", line + "\n", tag)
        text.configure(state="disabled")


class ResultDialog(tk.Toplevel):
    def __init__(self, parent, result):
        super().__init__(parent)
        self.title("Форма готова")
        dialog_size(self, 680, 350)
        self.transient(parent)
        box = ttk.Frame(self, padding=24); box.pack(fill="both", expand=True)
        ttk.Label(box, text="Форма создана" if result["published"] else "Черновик создан", style="Title.TLabel").pack(anchor="w")
        ttk.Label(box, text="Можно отправлять ссылку участникам." if result["published"] else
                  "Откройте форму в Яндексе, проверьте её и нажмите «Опубликовать».", wraplength=580).pack(anchor="w", pady=12)
        for label, key in (("Редактирование", "edit_url"), ("Заполнение", "fill_url")):
            ttk.Label(box, text=label).pack(anchor="w", pady=(8, 3))
            row = ttk.Frame(box); row.pack(fill="x")
            value = tk.StringVar(value=result[key])
            ttk.Entry(row, textvariable=value, state="readonly").pack(side="left", fill="x", expand=True)
            ttk.Button(row, text="Открыть ↗", command=lambda url=result[key]: webbrowser.open(url)).pack(side="left", padx=4)
            ttk.Button(row, text="Копировать", command=lambda url=result[key]: self.copy(url)).pack(side="left")

    def copy(self, url):
        self.clipboard_clear(); self.clipboard_append(url)


class ConditionsDialog(tk.Toplevel):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.title("Когда показывать вопрос")
        dialog_size(self, 800, 710)
        self.transient(parent)
        self.result = None
        self.config = deepcopy(config)
        self.rules = deepcopy(config.get("conditions", []))
        self.questions = {q["slug"]: q for q in config["questions"] if q.get("slug") and q["type"] not in ("section", "comment")}
        self.names = {slug: f"{i+1}. {q['label'][:65]} ({slug})" for i, (slug, q) in enumerate(self.questions.items())}
        area = ScrollFrame(self); area.pack(fill="both", expand=True)
        body = area.body
        ttk.Label(body, text="Показывать вопрос, если…", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(body, text="Выберите предыдущий вопрос и подходящие ответы.\nНесколько правил для одного вопроса действуют вместе (И).",
                  style="Muted.TLabel").pack(anchor="w", pady=(8, 14))
        self.listbox = tk.Listbox(body, height=5, exportselection=False, relief="flat", borderwidth=1)
        self.listbox.pack(fill="x")
        ttk.Button(body, text="Удалить выбранное правило", command=self.remove).pack(anchor="w", pady=8)
        self.target = tk.StringVar(); self.source = tk.StringVar()
        ttk.Label(body, text="Какой вопрос показывать").pack(anchor="w", pady=(8, 3))
        self.target_box = ttk.Combobox(body, state="readonly", textvariable=self.target, values=list(self.names.values()))
        self.target_box.pack(fill="x")
        self.target_box.bind("<<ComboboxSelected>>", self.update_sources)
        ttk.Label(body, text="Ответ на предыдущий вопрос").pack(anchor="w", pady=(12, 3))
        self.source_box = ttk.Combobox(body, state="readonly", textvariable=self.source)
        self.source_box.pack(fill="x"); self.source_box.bind("<<ComboboxSelected>>", self.update_answers)
        row = ttk.Frame(body); row.pack(fill="x", pady=12)
        self.comparison = tk.StringVar(value="Совпадает")
        ttk.Combobox(row, state="readonly", values=["Совпадает", "Не совпадает"], textvariable=self.comparison, width=18).pack(side="left")
        self.operator = tk.StringVar(value="Любой из выбранных")
        ttk.Combobox(row, state="readonly", values=["Любой из выбранных", "Все выбранные"], textvariable=self.operator, width=24).pack(side="left", padx=8)
        ttk.Label(body, text="Выберите ответы (можно несколько)").pack(anchor="w")
        self.answers = tk.Listbox(body, selectmode="multiple", exportselection=False, height=5, relief="flat")
        self.answers.pack(fill="x", pady=6)
        ttk.Button(body, text="+ Добавить правило", command=self.add).pack(anchor="w", pady=8)
        buttons = ttk.Frame(self, padding=14); buttons.pack(fill="x")
        ttk.Button(buttons, text="Отмена", command=self.destroy).pack(side="right", padx=6)
        ttk.Button(buttons, text="Сохранить условия", style="Accent.TButton", command=self.save).pack(side="right")
        self.refresh()
        self.grab_set(); self.wait_window()

    def slug(self, value):
        return next((key for key, name in self.names.items() if name == value), None)

    def update_sources(self, event=None):
        target = self.slug(self.target.get())
        previous = []
        for slug, question in self.questions.items():
            if slug == target:
                break
            if question["type"] in engine.CONDITION_SOURCE_TYPES:
                previous.append(self.names[slug])
        self.source_box.configure(values=previous)
        self.source.set(previous[0] if previous else "")
        self.update_answers()

    def update_answers(self, event=None):
        self.answers.delete(0, "end")
        question = self.questions.get(self.slug(self.source.get()), {})
        for option in question.get("options", []):
            self.answers.insert("end", option if isinstance(option, str) else option["label"])

    def refresh(self):
        self.listbox.delete(0, "end")
        for rule in self.rules:
            self.listbox.insert("end", f"{rule['target']} ← {rule['source']}: {', '.join(rule['answers'])} ({rule.get('condition', 'eq')}, {rule.get('operator', 'and')})")

    def remove(self):
        selected = self.listbox.curselection()
        if selected:
            self.rules.pop(selected[0]); self.refresh()

    def add(self):
        source, target = self.slug(self.source.get()), self.slug(self.target.get())
        answers = [self.answers.get(i) for i in self.answers.curselection()]
        if not source or not target or not answers:
            messagebox.showinfo("Заполните правило", "Выберите оба вопроса и хотя бы один ответ.", parent=self)
            return
        rule = {"target": target, "source": source, "answers": answers,
                "operator": "or" if self.operator.get() == "Любой из выбранных" else "and",
                "condition": "eq" if self.comparison.get() == "Совпадает" else "neq"}
        self.rules.append(rule); self.refresh()

    def save(self):
        candidate = deepcopy(self.config); candidate["conditions"] = self.rules
        try:
            engine.validate_config(candidate, allow_empty=True)
        except engine.ConfigError as exc:
            messagebox.showerror("Проверьте условия", str(exc), parent=self)
            return
        self.result = self.rules; self.destroy()
