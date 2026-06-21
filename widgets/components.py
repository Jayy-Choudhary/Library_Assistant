"""Reusable UI components extracted from library_assistant.py."""

from tkinter import ttk
import tkinter as tk
from tkinter import ttk as _ttk  # kept to preserve original ttk usage expectations

from config.theme import COLORS, FONT_BODY, FONT_CARD_LBL, FONT_CARD_NUM, FONT_HEADER


def styled_treeview(parent, columns: list, col_widths: dict = None, height=18):
    """Return a styled ttk.Treeview with scrollbars."""
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("LibTree.Treeview",
        background="#FFFFFF", fieldbackground="#FFFFFF",
        foreground=COLORS["text_primary"],
        rowheight=32, font=FONT_BODY, borderwidth=0
    )
    style.configure("LibTree.Treeview.Heading",
        background=COLORS["treeview_header"],
        foreground=COLORS["text_primary"],
        font=FONT_HEADER, relief="flat", borderwidth=0
    )
    style.map("LibTree.Treeview",
        background=[("selected", COLORS["accent"])],
        foreground=[("selected", "#FFFFFF")]
    )

    frame = tk.Frame(parent, bg=COLORS["card_bg"], bd=0)
    tree = ttk.Treeview(frame, columns=columns, show="headings",
                        style="LibTree.Treeview", height=height)

    col_widths = col_widths or {}
    for col in columns:
        w = col_widths.get(col, 140)
        tree.heading(col, text=col)
        tree.column(col, width=w, anchor="center", minwidth=60)

    sb_y = ttk.Scrollbar(frame, orient="vertical",   command=tree.yview)
    sb_x = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

    tree.grid(row=0, column=0, sticky="nsew")
    sb_y.grid(row=0, column=1, sticky="ns")
    sb_x.grid(row=1, column=0, sticky="ew")
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    return frame, tree


def card(parent, title, value, color, col, row):
    """Stat card widget."""
    f = tk.Frame(parent, bg=color, bd=0, padx=18, pady=14)
    f.grid(row=row, column=col, padx=8, pady=8, sticky="ew")
    tk.Label(f, text=str(value), font=FONT_CARD_NUM, bg=color, fg="#FFFFFF").pack(anchor="w")
    tk.Label(f, text=title,      font=FONT_CARD_LBL, bg=color, fg="white").pack(anchor="w")
    return f


def label_entry(parent, label_text, row, default="", width=260):
    """Label + Entry pair in a grid parent."""
    tk.Label(parent, text=label_text, font=FONT_BODY,
             bg=COLORS["card_bg"], fg=COLORS["text_primary"]).grid(
        row=row, column=0, sticky="w", pady=6, padx=(0, 16))
    var = tk.StringVar(value=default)
    e = tk.Entry(parent, textvariable=var, font=FONT_BODY, width=28,
                 bg="#F9FAFB", relief="flat", bd=6, fg=COLORS["text_primary"],
                 insertbackground=COLORS["text_primary"])
    e.grid(row=row, column=1, sticky="ew", pady=6)
    return var, e


def action_button(parent, text, command, color=None, **kwargs):
    color = color or COLORS["accent"]
    b = tk.Button(parent, text=text, command=command,
                  bg=color, fg="#FFFFFF", font=FONT_BODY,
                  relief="flat", bd=0, padx=14, pady=7,
                  activebackground=color, cursor="hand2", **kwargs)
    return b

