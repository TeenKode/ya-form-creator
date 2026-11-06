"""Shared native Tk styling and bundled resource lookup (also in one-file EXE)."""
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont

BG = "#F5F4F0"
PAPER = "#FFFFFF"
INK = "#20251F"
MUTED = "#62685E"
ACCENT = "#F4C542"


def resource_path(name: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name


def apply_theme(root):
    root.configure(background=BG)
    tkfont.nametofont("TkDefaultFont").configure(family="Segoe UI", size=10)
    tkfont.nametofont("TkTextFont").configure(family="Segoe UI", size=10)
    root.option_add("*Text.background", PAPER)
    root.option_add("*Text.foreground", INK)
    root.option_add("*Text.selectBackground", "#E8EDDD")
    root.option_add("*Text.relief", "flat")
    root.option_add("*Text.highlightThickness", 1)
    root.option_add("*Text.highlightBackground", "#D9DDD3")
    root.option_add("*Text.padX", 10)
    root.option_add("*Text.padY", 8)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=INK, font=("Segoe UI", 10))
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"))
    style.configure("Heading.TLabel", font=("Segoe UI", 12, "bold"))
    style.configure("TButton", padding=(12, 8), background=PAPER, borderwidth=1,
                    bordercolor="#D9DDD3", focusthickness=2, focuscolor="#7A824F")
    style.map("TButton", background=[("active", "#ECEEE6"), ("disabled", "#E9EAE5")],
              foreground=[("disabled", "#92978C")])
    style.configure("Accent.TButton", background=ACCENT, bordercolor=ACCENT, font=("Segoe UI", 10, "bold"))
    style.map("Accent.TButton", background=[("active", "#E8B52F"), ("disabled", "#E9EAE5")])
    style.configure("TEntry", padding=7, fieldbackground=PAPER)
    style.configure("TCombobox", padding=6, fieldbackground=PAPER)
    style.map("TCombobox", fieldbackground=[("readonly", PAPER)])
    style.configure("Treeview", background=PAPER, fieldbackground=PAPER, rowheight=43,
                    borderwidth=0, font=("Segoe UI", 10))
    style.configure("Treeview.Heading", background="#EBEDE6", relief="flat", padding=(10, 11),
                    font=("Segoe UI", 10, "bold"))
    style.map("Treeview", background=[("selected", "#E3EBCF")], foreground=[("selected", INK)])
    style.configure("TLabelframe", bordercolor="#D9DDD3")
    style.configure("TLabelframe.Label", foreground=MUTED)
    style.configure("TNotebook", borderwidth=0)
    style.configure("TNotebook.Tab", padding=(14, 7))


def set_icon(window):
    try:
        path = resource_path("assets/app-icon.png")
        window._app_icon = tk.PhotoImage(file=str(path))
        window.iconphoto(True, window._app_icon)
        if sys.platform == "win32":
            window.iconbitmap(str(resource_path("assets/app-icon.ico")))
    except (tk.TclError, OSError):
        pass


class ScrollFrame(ttk.Frame):
    """Scrollable dialog body with local wheel handling, never bind_all."""
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, highlightthickness=0, background=BG)
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.canvas, padding=16)
        self.item = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.item, width=e.width))
        # A toplevel bind receives wheel events from descendants as well.
        parent.bind("<MouseWheel>", self._wheel, add="+")

    def _wheel(self, event):
        if isinstance(event.widget, (tk.Text, ttk.Combobox)):
            return
        self.canvas.yview_scroll(-int(event.delta / 120), "units")


def dialog_size(window, width, height):
    screen_w, screen_h = window.winfo_screenwidth(), window.winfo_screenheight()
    width, height = min(width, screen_w-60), min(height, screen_h-100)
    parent = window.master
    x = min(max(0, parent.winfo_rootx() + (parent.winfo_width()-width)//2), screen_w-width-20)
    y = min(max(0, parent.winfo_rooty() + (parent.winfo_height()-height)//2), screen_h-height-60)
    window.geometry(f"{width}x{height}+{x}+{y}")
    window.bind("<Escape>", lambda e: window.destroy())
