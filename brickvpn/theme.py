"""Colours, fonts and ttk styles shared by the Switcher windows."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

NAVY = "#16243d"
NAVY_SOFT = "#24365a"
INK = "#14213a"
MUTED = "#5d6b82"
BG = "#f4f6fb"
CARD = "#ffffff"
BORDER = "#dfe5f0"
STRIPE = "#fbfcfe"
ACCENT = "#0f766e"
ACCENT_HOVER = "#0b5c56"
OK = "#15803d"
WARN = "#b45309"
ERROR = "#b91c1c"

TONE_NEUTRAL = ("#eef2f9", "#475569")
TONE_OK = ("#e7f6ec", OK)
TONE_WARN = ("#fdf0e3", WARN)
TONE_ERROR = ("#fdecec", ERROR)

FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_SMALL_BOLD = ("Segoe UI", 9, "bold")
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_VALUE = ("Segoe UI", 12, "bold")
FONT_TITLE = ("Segoe UI", 20, "bold")
FONT_SECTION = ("Segoe UI", 8, "bold")


def install(root: tk.Misc) -> ttk.Style:
    """Apply the application palette and widget styles to *root*."""
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    root.configure(bg=BG)

    style.configure(".", background=BG, foreground=INK, font=FONT)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=CARD)
    style.configure("TLabel", background=BG, foreground=INK, font=FONT)
    style.configure("Card.TLabel", background=CARD, foreground=INK, font=FONT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=FONT_SMALL)
    style.configure("CardMuted.TLabel", background=CARD, foreground=MUTED, font=FONT_SMALL)
    style.configure("Value.TLabel", background=CARD, foreground=INK, font=FONT_VALUE)
    style.configure(
        "SecondaryValue.TLabel", background=CARD, foreground=INK, font=FONT
    )

    style.configure(
        "TButton",
        background="#eef2f9",
        foreground=INK,
        bordercolor=BORDER,
        lightcolor="#eef2f9",
        darkcolor="#eef2f9",
        focuscolor="#eef2f9",
        focusthickness=0,
        padding=(14, 7),
        relief="flat",
        font=FONT,
    )
    style.map(
        "TButton",
        background=[
            ("disabled", "#f1f4f9"),
            ("pressed", "#dde5f1"),
            ("active", "#e4eaf4"),
        ],
        foreground=[("disabled", "#a3adbf")],
    )

    style.configure(
        "Accent.TButton",
        background=ACCENT,
        foreground="#ffffff",
        bordercolor=ACCENT,
        lightcolor=ACCENT,
        darkcolor=ACCENT,
        focuscolor=ACCENT,
        focusthickness=0,
        padding=(18, 9),
        relief="flat",
        font=FONT_BOLD,
    )
    style.map(
        "Accent.TButton",
        background=[
            ("disabled", "#a8cfcb"),
            ("pressed", ACCENT_HOVER),
            ("active", ACCENT_HOVER),
        ],
        foreground=[("disabled", "#f2fbfa")],
    )

    style.configure(
        "Link.TButton",
        background=CARD,
        foreground=ACCENT,
        bordercolor=CARD,
        lightcolor=CARD,
        darkcolor=CARD,
        focuscolor=CARD,
        focusthickness=0,
        padding=(8, 3),
        relief="flat",
        font=FONT_SMALL_BOLD,
    )
    style.map(
        "Link.TButton",
        background=[("active", CARD)],
        foreground=[("active", ACCENT_HOVER)],
    )

    style.configure(
        "Treeview",
        background=CARD,
        fieldbackground=CARD,
        foreground=INK,
        borderwidth=0,
        rowheight=30,
        font=FONT,
    )
    style.configure(
        "Treeview.Heading",
        background="#f2f5fa",
        foreground=MUTED,
        font=FONT_SMALL_BOLD,
        relief="flat",
        padding=(10, 7),
        bordercolor=BORDER,
    )
    style.map("Treeview.Heading", background=[("active", "#e9eef7")])
    style.map(
        "Treeview",
        background=[("selected", "#e2f0ee")],
        foreground=[("selected", INK)],
    )

    style.configure(
        "TEntry",
        fieldbackground="#ffffff",
        foreground=INK,
        bordercolor=BORDER,
        lightcolor=BORDER,
        darkcolor=BORDER,
        insertcolor=INK,
        padding=5,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", ACCENT)],
        lightcolor=[("focus", ACCENT)],
        darkcolor=[("focus", ACCENT)],
    )

    style.configure(
        "TCheckbutton",
        background=CARD,
        foreground=INK,
        font=FONT,
        indicatorsize=12,
        indicatormargin=4,
        indicatorbackground="#ffffff",
        indicatorforeground="#8fa3c4",
        upperbordercolor=BORDER,
        lowerbordercolor=BORDER,
    )
    style.map(
        "TCheckbutton",
        background=[("active", CARD)],
        indicatorbackground=[("selected", ACCENT), ("active", "#eef2f9")],
        indicatorforeground=[("selected", "#ffffff"), ("active", INK)],
    )

    style.configure(
        "TScrollbar",
        background="#dfe5f0",
        troughcolor=BG,
        bordercolor=BG,
        arrowcolor=MUTED,
        relief="flat",
    )
    style.configure(
        "Horizontal.TProgressbar",
        background=ACCENT,
        troughcolor="#e6ebf4",
        bordercolor="#e6ebf4",
        lightcolor=ACCENT,
        darkcolor=ACCENT,
        thickness=10,
    )
    return style


def card(parent: tk.Misc) -> tk.Frame:
    """Return a white card with a subtle border."""
    return tk.Frame(
        parent,
        bg=CARD,
        highlightbackground=BORDER,
        highlightthickness=1,
        bd=0,
    )
