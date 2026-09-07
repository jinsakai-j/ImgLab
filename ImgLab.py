import os
import sys
import io
import re
import threading
import subprocess
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageTk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

COLOR_BG = "#0E1117"
COLOR_BG_DARK = "#0B0F14"
COLOR_CARD_BG = "#151B23"
COLOR_CARD_BORDER = "#2A313C"
COLOR_INPUT_BG = "#0D1117"
COLOR_ACCENT = "#2DA44E"
COLOR_ACCENT_HOVER = "#269642"
COLOR_SUCCESS = "#3FB950"
COLOR_DANGER = "#F85149"
COLOR_TEXT_MAIN = "#E6EDF3"
COLOR_TEXT_MUTED = "#8B949E"
COLOR_TEXT_DIM = "#6E7681"
SURFACE = "#21262D"
SURFACE_HOVER = "#30363D"

APP_NAME = "ImgLab"
APP_SUBTITLE = "Image Toolkit"
APP_VERSION = "v1.1"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff")

MODES = [
    ("Konversi & Resize", "Ubah format, kualitas, dan ukuran gambar"),
    ("OCR (Ekstrak Teks)", "Ambil teks dari gambar atau screenshot"),
    ("Hapus Background", "Hapus latar belakang dengan AI (rembg)"),
    ("Rename Massal", "Renama banyak file gambar sekaligus"),
]


class _Cancelled(Exception):
    pass


class ImgLabApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("JinsakaiCorp.ImgLab.2")
        except Exception:
            pass

        self.title("ImgLab - Image Toolkit")
        self.configure(fg_color=COLOR_BG)
        self.resizable(True, True)
        self.minsize(900, 660)
        self.center_window(900, 670)

        self._busy = False
        self.cancel_requested = False
        self._conv_files = []
        self._ocr_files = []
        self._bg_files = []

        self._build_ui()

        try:
            self.iconbitmap(self.resource_path("assets\\imglab_icon.ico"))
        except Exception:
            pass

        self.bind("<Escape>", lambda e: self._maybe_quit())
        self.bind("<F11>", lambda e: self._toggle_fullscreen())

    def _toggle_fullscreen(self):
        self.attributes("-fullscreen", not bool(self.attributes("-fullscreen")))

    @staticmethod
    def resource_path(rel):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, rel)

    def center_window(self, w, h):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = max((sh - h) // 2 - 20, 0)
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---- Sidebar kiri ----
        self.sidebar = ctk.CTkFrame(self, width=180, corner_radius=0, fg_color=COLOR_BG_DARK)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(self.sidebar, text="ImgLab",
                     font=ctk.CTkFont(family="Segoe UI", size=19, weight="bold"),
                     text_color=COLOR_TEXT_MAIN, anchor="w").pack(fill="x", padx=18, pady=(20, 0))
        ctk.CTkLabel(self.sidebar, text=APP_SUBTITLE,
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=COLOR_TEXT_DIM, anchor="w").pack(fill="x", padx=18, pady=(0, 18))

        self.nav_buttons = []
        for i, (name, _desc) in enumerate(MODES):
            btn = ctk.CTkButton(self.sidebar, text=name, height=38, corner_radius=7,
                                anchor="w", fg_color="transparent",
                                hover_color=SURFACE_HOVER,
                                text_color=COLOR_TEXT_MUTED,
                                font=ctk.CTkFont(family="Segoe UI", size=12, weight="normal"),
                                command=lambda idx=i: self._show_panel(idx))
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_buttons.append(btn)

        ctk.CTkLabel(self.sidebar, text="Proses lokal, tanpa login.",
                     font=ctk.CTkFont(family="Segoe UI", size=9),
                     text_color=COLOR_TEXT_DIM, anchor="w").pack(side="bottom", fill="x", padx=18, pady=14)

        # ---- Area konten ----
        self.content = ctk.CTkFrame(self, fg_color=COLOR_BG)
        self.content.grid(row=0, column=1, sticky="nsew", padx=(0, 0), pady=0)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.panels = []
        for name, desc in MODES:
            panel = ctk.CTkFrame(self.content, fg_color=COLOR_BG)
            panel.grid_columnconfigure(0, weight=1)
            panel.grid_rowconfigure(1, weight=1)
            panel.grid(row=0, column=0, sticky="nsew", padx=24, pady=20)
            ctk.CTkLabel(panel, text=name,
                         font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                         text_color=COLOR_TEXT_MAIN, anchor="w").grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(panel, text=desc,
                         font=ctk.CTkFont(family="Segoe UI", size=11),
                         text_color=COLOR_TEXT_MUTED, anchor="w").grid(row=0, column=0, sticky="w", pady=(24, 0))
            self.panels.append(panel)

        self._build_conv_panel(self.panels[0])
        self._build_ocr_panel(self.panels[1])
        self._build_bg_panel(self.panels[2])
        self._build_ren_panel(self.panels[3])
        for p in self.panels:
            p.grid_remove()
        self._show_panel(0)

        self.status_label = ctk.CTkLabel(self.content, text="Siap.",
                                         anchor="w", font=ctk.CTkFont(family="Segoe UI", size=11),
                                         text_color=COLOR_TEXT_MUTED)
        self.status_label.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 10))

        self.progress_bar = ctk.CTkProgressBar(self.content, height=6, corner_radius=3,
                                               progress_color=COLOR_ACCENT)
        self.progress_bar.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 6))
        self.progress_bar.grid_remove()

    def _show_progress(self, value=0, visible=True):
        if visible:
            self.progress_bar.grid()
        else:
            self.progress_bar.grid_remove()
            return
        self.progress_bar.set(value)

    def _show_panel(self, idx):
        for i, p in enumerate(self.panels):
            if i == idx:
                p.grid()
            else:
                p.grid_remove()
        for i, btn in enumerate(self.nav_buttons):
            if i == idx:
                btn.configure(fg_color=SURFACE, text_color=COLOR_TEXT_MAIN,
                              font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"))
            else:
                btn.configure(fg_color="transparent", text_color=COLOR_TEXT_MUTED,
                              font=ctk.CTkFont(family="Segoe UI", size=12, weight="normal"))

    def set_status(self, text, color=COLOR_TEXT_MUTED):
        self.status_label.configure(text=text, text_color=color)

    # ---- widget helper ----
    def _card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD_BG, corner_radius=10,
                            border_width=1, border_color=COLOR_CARD_BORDER)
        return card

    def _file_list_card(self, parent, var_holder, on_add, on_clear, hint="Daftar file kosong. Klik Pilih Gambar."):
        card = self._card(parent)
        card.grid(row=1, column=0, sticky="nsew", pady=(30, 12))
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)

        bar = ctk.CTkFrame(card, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        bar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(bar, text=hint, font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=COLOR_TEXT_DIM, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(bar, text="Hapus Semua", width=92, height=28, corner_radius=6,
                      fg_color=SURFACE, hover_color=SURFACE_HOVER, text_color=COLOR_TEXT_MAIN,
                      font=ctk.CTkFont(family="Segoe UI", size=10), command=on_clear
                      ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(bar, text="Pilih Gambar", width=100, height=28, corner_radius=6,
                      fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color="#FFFFFF",
                      font=ctk.CTkFont(family="Segoe UI", size=10), command=on_add
                      ).grid(row=0, column=2)

        box = ctk.CTkTextbox(card, corner_radius=6, fg_color=COLOR_INPUT_BG,
                             border_width=1, border_color=COLOR_CARD_BORDER,
                             font=ctk.CTkFont(family="Consolas", size=10),
                             text_color=COLOR_TEXT_MUTED, wrap="none")
        box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        var_holder.append(box)
        return card

    def _param_row(self, parent, row, text, widget, note=None):
        ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=COLOR_TEXT_MAIN, anchor="w").grid(row=row, column=0, sticky="w", pady=4)
        widget.grid(row=row, column=1, sticky="w", padx=(18, 0), pady=4)
        if note:
            ctk.CTkLabel(parent, text=note, font=ctk.CTkFont(family="Segoe UI", size=10),
                         text_color=COLOR_TEXT_DIM, anchor="w").grid(row=row, column=2, sticky="w",
                                                                     padx=(14, 0), pady=4)

    def _action_button(self, parent, text, command):
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        bar.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(bar, text=text, height=38, corner_radius=8,
                      fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color="#FFFFFF",
                      font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                      command=command).grid(row=0, column=0, sticky="ew")

    # ---- Panel: Konversi & Resize ----
    def _build_conv_panel(self, parent):
        self._file_list_card(parent, self._conv_files,
                             lambda: self._add_images("conv"), lambda: self._clear_images("conv"))

        params = ctk.CTkFrame(parent, fg_color="transparent")
        params.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        params.grid_columnconfigure(1, weight=1)

        self.conv_format = ctk.CTkOptionMenu(params, values=["JPG", "PNG", "WebP", "BMP"], width=120,
                                             height=32, corner_radius=6, fg_color=COLOR_INPUT_BG,
                                             button_color=COLOR_CARD_BORDER, button_hover_color=SURFACE_HOVER,
                                             font=ctk.CTkFont(family="Segoe UI", size=11),
                                             command=self._on_format_change)
        self.conv_format.set("JPG")
        self._param_row(params, 0, "Format output", self.conv_format,
                        "Simpan ke folder:  ")

        dir_row = ctk.CTkFrame(params, fg_color="transparent")
        dir_row.grid(row=1, column=1, sticky="ew", padx=(18, 0), pady=4)
        dir_row.grid_columnconfigure(0, weight=1)
        self.conv_out = ctk.CTkEntry(dir_row, height=32, corner_radius=6, border_color=COLOR_CARD_BORDER,
                                     fg_color=COLOR_INPUT_BG, text_color=COLOR_TEXT_MAIN,
                                     font=ctk.CTkFont(family="Segoe UI", size=10))
        self.conv_out.insert(0, os.path.join(os.path.expanduser("~"), "Downloads", "ImgLab_Converted"))
        self.conv_out.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(dir_row, text="...", width=30, height=32, corner_radius=6, fg_color=SURFACE,
                      hover_color=SURFACE_HOVER, text_color=COLOR_TEXT_MAIN,
                      command=lambda: self._pick_folder(self.conv_out)).grid(row=0, column=1, padx=(4, 0))
        ctk.CTkButton(dir_row, text="Buka", width=46, height=32, corner_radius=6, fg_color=SURFACE,
                      hover_color=SURFACE_HOVER, text_color=COLOR_TEXT_MAIN,
                      font=ctk.CTkFont(family="Segoe UI", size=10),
                      command=lambda: self._open_folder(self.conv_out.get())).grid(row=0, column=2, padx=(4, 0))

        ctk.CTkLabel(params, text="Kualitas (JPG/WebP):", font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=COLOR_TEXT_MAIN, anchor="w").grid(row=2, column=0, sticky="w", pady=4)
        qrow = ctk.CTkFrame(params, fg_color="transparent")
        qrow.grid(row=2, column=1, sticky="w", padx=(18, 0), pady=4)
        self.conv_quality = ctk.CTkSlider(qrow, from_=10, to=100, number_of_steps=90, width=150,
                                          command=lambda v: self.conv_quality_v.configure(text=str(int(v))))
        self.conv_quality.set(90)
        self.conv_quality.pack(side="left")
        self.conv_quality_v = ctk.CTkLabel(qrow, text="90", width=30,
                                          font=ctk.CTkFont(family="Segoe UI", size=11),
                                          text_color=COLOR_TEXT_MUTED)
        self.conv_quality_v.pack(side="left", padx=(8, 0))

        ctk.CTkLabel(params, text="Resize:", font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=COLOR_TEXT_MAIN, anchor="w").grid(row=3, column=0, sticky="w", pady=4)
        rrow = ctk.CTkFrame(params, fg_color="transparent")
        rrow.grid(row=3, column=1, sticky="w", padx=(18, 0), pady=4)
        self.conv_scale = ctk.CTkOptionMenu(rrow, values=["Original", "50%", "75%", "Kustom (%)"],
                                            width=130, height=30, corner_radius=6, fg_color=COLOR_INPUT_BG,
                                            button_color=COLOR_CARD_BORDER, button_hover_color=SURFACE_HOVER,
                                            font=ctk.CTkFont(family="Segoe UI", size=11))
        self.conv_scale.set("Original")
        self.conv_scale.pack(side="left")
        self.conv_scale_pct = ctk.CTkEntry(rrow, placeholder_text="mis. 120", width=90, height=30,
                                           corner_radius=6, border_color=COLOR_CARD_BORDER,
                                           fg_color=COLOR_INPUT_BG, text_color=COLOR_TEXT_MAIN,
                                           font=ctk.CTkFont(family="Segoe UI", size=11))
        self.conv_scale_pct.pack(side="left", padx=(10, 0))

        self._action_button(parent, "Konversi", self.start_convert)

# ---- Panel: OCR (Ekstrak Teks) ----
    def _build_ocr_panel(self, parent):
        hint = self._card(parent)
        hint.grid(row=0, column=0, sticky="ew", pady=(30, 0))
        ctk.CTkLabel(hint, text="OCR berjalan 100% lokal (RapidOCR/onnx). Cocok untuk foto, scan, dan screenshot. "
                                "Hasil teks otomatis diurutkan sesuai posisi (kiri-ke-kanan, atas-ke-bawah).",
                     anchor="w", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=COLOR_TEXT_DIM,
                     wraplength=620, justify="left").pack(anchor="w", padx=12, pady=8)

        self._file_list_card(parent, self._ocr_files,
                             lambda: self._add_images("ocr"), lambda: self._clear_images("ocr"))

        self._action_button(parent, "Ekstrak Teks", self.start_ocr)

        result_card = self._card(parent)
        result_card.grid(row=4, column=0, sticky="nsew", pady=(14, 0))
        result_card.grid_columnconfigure(0, weight=1)
        result_card.grid_rowconfigure(1, weight=1)
        bar = ctk.CTkFrame(result_card, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 4))
        bar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(bar, text="Hasil Teks", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                     text_color=COLOR_TEXT_MAIN, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(bar, text="Salin", width=70, height=26, corner_radius=6, fg_color=SURFACE,
                      hover_color=SURFACE_HOVER, text_color=COLOR_TEXT_MAIN,
                      font=ctk.CTkFont(family="Segoe UI", size=10), command=self.copypaste_ocr
                      ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(bar, text="Simpan .txt", width=90, height=26, corner_radius=6,
                      fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color="#FFFFFF",
                      font=ctk.CTkFont(family="Segoe UI", size=10), command=self.save_ocr_txt
                      ).grid(row=0, column=2)

        self.ocr_result = ctk.CTkTextbox(result_card, corner_radius=6, fg_color=COLOR_INPUT_BG,
                                         border_width=1, border_color=COLOR_CARD_BORDER,
                                         font=ctk.CTkFont(family="Consolas", size=10),
                                         text_color=COLOR_TEXT_MAIN, wrap="word")
        self.ocr_result.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.ocr_result.insert("end", "Hasil ekstraksi teks akan muncul di sini...")

    # ---- Panel: Hapus Background ----
    def _build_bg_panel(self, parent):
        hint = self._card(parent)
        hint.grid(row=0, column=0, sticky="ew", pady=(30, 0))
        ctk.CTkLabel(hint, text="Menggunakan rembg (AI). Pertama kali dijalankan akan mengunduh model (~176 MB). "
                                "Butuh:  pip install rembg onnxruntime", anchor="w",
                     font=ctk.CTkFont(family="Segoe UI", size=10), text_color=COLOR_TEXT_DIM,
                     wraplength=560, justify="left").pack(anchor="w", padx=12, pady=8)

        self._file_list_card(parent, self._bg_files,
                             lambda: self._add_images("bg"), lambda: self._clear_images("bg"))

        params = ctk.CTkFrame(parent, fg_color="transparent")
        params.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        params.grid_columnconfigure(1, weight=1)
        dir_row = ctk.CTkFrame(params, fg_color="transparent")
        dir_row.grid(row=0, column=1, sticky="ew", padx=(18, 0), pady=4)
        dir_row.grid_columnconfigure(0, weight=1)
        self.bg_out = ctk.CTkEntry(dir_row, height=32, corner_radius=6, border_color=COLOR_CARD_BORDER,
                                   fg_color=COLOR_INPUT_BG, text_color=COLOR_TEXT_MAIN,
                                   font=ctk.CTkFont(family="Segoe UI", size=10))
        self.bg_out.insert(0, os.path.join(os.path.expanduser("~"), "Downloads", "ImgLab_NoBG"))
        self.bg_out.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(dir_row, text="...", width=30, height=32, corner_radius=6, fg_color=SURFACE,
                      hover_color=SURFACE_HOVER, text_color=COLOR_TEXT_MAIN,
                      command=lambda: self._pick_folder(self.bg_out)).grid(row=0, column=1, padx=(4, 0))
        ctk.CTkButton(dir_row, text="Buka", width=46, height=32, corner_radius=6, fg_color=SURFACE,
                      hover_color=SURFACE_HOVER, text_color=COLOR_TEXT_MAIN,
                      font=ctk.CTkFont(family="Segoe UI", size=10),
                      command=lambda: self._open_folder(self.bg_out.get())).grid(row=0, column=2, padx=(4, 0))
        ctk.CTkLabel(params, text="Simpan ke:", font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=COLOR_TEXT_MAIN, anchor="w").grid(row=0, column=0, sticky="w", pady=4)

        self._action_button(parent, "Hapus Background", self.start_bg)

    # ---- Panel: Rename Massal ----
    def _build_ren_panel(self, parent):
        card = self._card(parent)
        card.grid(row=1, column=0, sticky="nsew", pady=(30, 12))
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text="Pilih folder yang berisi gambar yang ingin direname.",
                     font=ctk.CTkFont(family="Segoe UI", size=10), text_color=COLOR_TEXT_DIM,
                     anchor="w").grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        row.grid_columnconfigure(0, weight=1)
        self.ren_folder = ctk.CTkEntry(row, height=32, corner_radius=6, border_color=COLOR_CARD_BORDER,
                                       fg_color=COLOR_INPUT_BG, text_color=COLOR_TEXT_MUTED,
                                       font=ctk.CTkFont(family="Segoe UI", size=10))
        self.ren_folder.insert(0, "(belum pilih folder)")
        self.ren_folder.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(row, text="Pilih Folder", width=100, height=32, corner_radius=6,
                      fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color="#FFFFFF",
                      font=ctk.CTkFont(family="Segoe UI", size=11),
                      command=self._pick_rename_folder).grid(row=0, column=1, padx=(8, 0), sticky="w")

        params = ctk.CTkFrame(parent, fg_color="transparent")
        params.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        params.grid_columnconfigure(1, weight=1)
        self.ren_pattern = ctk.CTkEntry(params, width=220, height=32, corner_radius=6,
                                        border_color=COLOR_CARD_BORDER, fg_color=COLOR_INPUT_BG,
                                        text_color=COLOR_TEXT_MAIN,
                                        font=ctk.CTkFont(family="Consolas", size=11))
        self.ren_pattern.insert(0, "IMG_{n:03d}")
        self._param_row(params, 0, "Pola nama", self.ren_pattern,
                        "placeholder {n} = nomor. Ekstensi file dipertahankan.")

        self.ren_start = ctk.CTkEntry(params, width=70, height=32, corner_radius=6,
                                      border_color=COLOR_CARD_BORDER, fg_color=COLOR_INPUT_BG,
                                      text_color=COLOR_TEXT_MAIN,
                                      font=ctk.CTkFont(family="Consolas", size=11))
        self.ren_start.insert(0, "1")
        self._param_row(params, 1, "Mulai dari", self.ren_start)

        self.ren_progress_placeholder = None
        self._action_button(parent, "Rename Semua", self.start_rename)

        self.ren_result = ctk.CTkTextbox(parent, height=130, corner_radius=6, fg_color=COLOR_INPUT_BG,
                                         border_width=1, border_color=COLOR_CARD_BORDER,
                                         font=ctk.CTkFont(family="Consolas", size=10),
                                         text_color=COLOR_TEXT_MUTED, wrap="none")
        self.ren_result.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        self.ren_result.insert("end", "Log rename muncul di sini...")

    # ---------------------------------------------------------------- helpers
    def _list_box(self, key):
        widgets = self._conv_files if key == "conv" else (self._ocr_files if key == "ocr" else self._bg_files)
        return widgets[0] if widgets else None

    def _add_images(self, key):
        files = filedialog.askopenfilenames(title="Pilih gambar", filetypes=[
            ("Gambar", "".join("*" + e for e in IMAGE_EXTS)),
            ("Semua File", "*.*"),
        ])
        if not files:
            return
        box = self._list_box(key)
        for f in files:
            if f.lower().endswith(IMAGE_EXTS):
                box.insert("end", f)
        box.see("end")
        self.set_status(f"{len(files)} gambar ditambahkan.", COLOR_TEXT_MUTED)

    def _clear_images(self, key):
        box = self._list_box(key)
        if box:
            box.delete("1.0", "end")
        self.set_status("Daftar file dikosongkan.", COLOR_TEXT_MUTED)

    def _selected_files(self, key):
        box = self._list_box(key)
        if not box:
            return []
        text = box.get("1.0", "end").strip()
        return [ln for ln in text.splitlines() if ln.strip() and os.path.isfile(ln.strip())]

    def _pick_folder(self, entry):
        d = filedialog.askdirectory(title="Pilih folder tujuan")
        if d:
            entry.delete(0, "end")
            entry.insert(0, d)

    def _on_format_change(self, choice):
        on = choice in ("JPG", "WebP")
        state = "normal" if on else "disabled"
        self.conv_quality.configure(state=state)
        if not on:
            self.conv_quality_v.configure(text="-")
        else:
            self.conv_quality_v.configure(text=str(int(self.conv_quality.get())))

    def _open_folder(self, folder):
        if folder and os.path.exists(folder):
            os.startfile(folder)
        else:
            messagebox.showinfo("Folder", "Folder belum ada. Jalankan prosesnya dulu.")

    def _pick_rename_folder(self):
        d = filedialog.askdirectory(title="Pilih folder gambar")
        if d:
            self.ren_folder.delete(0, "end")
            self.ren_folder.insert(0, d)

    def _unique_path(self, base, ext):
        out = base + ext
        i = 1
        while os.path.exists(out):
            out = f"{base} ({i}){ext}"
            i += 1
        return out

    def _ensure_dir(self, path):
        os.makedirs(path, exist_ok=True)
        return path

    def _maybe_quit(self):
        if not self._busy:
            self.destroy()

    # ---------------------------------------------------------------- convert
    def start_convert(self):
        files = self._selected_files("conv")
        if not files:
            messagebox.showwarning("ImgLab", "Pilih minimal 1 gambar dulu.")
            return
        self._run_job(lambda: self._conv_worker(files))

    def _conv_worker(self, files):
        fmt = self.conv_format.get()
        ext_map = {"JPG": ".jpg", "PNG": ".png", "WebP": ".webp", "BMP": ".bmp"}
        ext = ext_map[fmt]
        quality = int(self.conv_quality.get())
        scale = self.conv_scale.get()
        scale_pct = None
        if scale == "Kustom (%)":
            try:
                scale_pct = float(re.sub(r"[^\d.]", "", self.conv_scale_pct.get())) / 100.0
            except Exception:
                scale_pct = 1.0
        elif scale != "Original":
            scale_pct = int(scale.replace("%", "")) / 100.0

        out_dir = self._ensure_dir(self.conv_out.get().strip())
        done = 0
        ok = 0
        for f in files:
            if self.cancel_requested:
                raise _Cancelled()
            try:
                img = Image.open(f)
                img.load()
                if scale_pct:
                    img = img.resize(
                        (max(1, int(img.width * scale_pct)), max(1, int(img.height * scale_pct))),
                        Image.Resampling.LANCZOS,
                    )
                if fmt == "JPG":
                    if img.mode in ("RGBA", "LA", "P"):
                        base = Image.new("RGB", img.size, "white")
                        if img.mode in ("RGBA", "LA"):
                            base.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
                            img = base
                        else:
                            img = img.convert("RGB")
                    else:
                        img = img.convert("RGB")
                elif fmt == "BMP":
                    img = img.convert("RGB")
                else:
                    img = img.convert("RGBA" if fmt == "PNG" else "RGB")

                base_name = os.path.splitext(os.path.basename(f))[0]
                out_path = self._unique_path(os.path.join(out_dir, base_name), ext)
                if fmt == "JPG":
                    img.save(out_path, "JPEG", quality=quality, optimize=True)
                elif fmt == "WebP":
                    img.save(out_path, "WEBP", quality=quality, method=4)
                elif fmt == "BMP":
                    img.save(out_path, "BMP")
                else:
                    img.save(out_path, "PNG", optimize=True)
                ok += 1
            except Exception:
                pass
            done += 1
            self.after(0, lambda p=done / len(files): (self._show_progress(p),
                                                       self.set_status(f"Konversi {done}/{len(files)}", COLOR_ACCENT)))
        self.after(0, lambda: self.job_finish(files, out_dir, ok))

    # ---------------------------------------------------------------- OCR
    def start_ocr(self):
        files = self._selected_files("ocr")
        if not files:
            messagebox.showwarning("ImgLab", "Pilih minimal 1 gambar dulu.")
            return
        self.ocr_result.delete("1.0", "end")
        self.ocr_result.configure(text_color=COLOR_TEXT_MUTED)
        self._run_job(lambda: self._ocr_worker(files))

    @staticmethod
    def _ocr_text_of(engine, f):
        res, _ = engine(f)
        if not res:
            return ""
        items = []
        for r in res:
            if isinstance(r, dict):
                box = r.get("box") or r.get("boxes") or []
                text = str(r.get("text") or r.get("txt") or "").strip()
            else:
                text = str(r[1]).strip() if len(r) > 1 else ""
                box = r[0] if r and isinstance(r[0], list) else []
            if text:
                items.append((box, text))
        if not items:
            return ""
        items.sort(key=lambda it: (it[0][0][1], it[0][0][0]) if it[0] else (0, 0))
        return "\n".join(t for _, t in items)

    def _ocr_worker(self, files):
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            self.after(0, lambda: messagebox.showerror(
                "ImgLab", "RapidOCR belum terpasang.\n\nJalankan:\npip install rapidocr_onnxruntime\n\nLalu tutup & buka ImgLab lagi."))
            return
        try:
            engine = RapidOCR()
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("ImgLab", f"Gagal memuat engine OCR: {e}"))
            return

        done = 0
        all_lines = []
        for f in files:
            if self.cancel_requested:
                raise _Cancelled()
            name = os.path.basename(f)
            try:
                text = self._ocr_text_of(engine, f)
                if text:
                    all_lines.append(f"[{name}]")
                    all_lines.append(text)
                    all_lines.append("")
            except Exception:
                pass
            done += 1
            self.after(0, lambda p=done / len(files): (self._show_progress(p),
                                                       self.set_status(f"OCR {done}/{len(files)}", COLOR_ACCENT)))

        result_text = "\n".join(all_lines).strip()
        self._busy = False
        self.after(0, lambda: self._ocr_done(result_text, len(files), all_lines))

    def _ocr_done(self, result_text, total, all_lines):
        self.ocr_result.delete("1.0", "end")
        self._show_progress(0, False)
        if not result_text:
            self.ocr_result.insert("end", "Tidak ada teks yang terdeteksi.")
            self.set_status(f"OCR {total} file: tidak ada teks ditemukan.", COLOR_TEXT_MUTED)
            return
        self.ocr_result.insert("end", result_text)
        self.ocr_result.configure(text_color=COLOR_TEXT_MAIN)
        n = len([l for l in all_lines if l and not l.startswith("[")])
        self.set_status(f"OCR selesai: {total} file diproses, {n} baris teks.", COLOR_SUCCESS)

    def copypaste_ocr(self):
        text = self.ocr_result.get("1.0", "end").strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.set_status("Teks hasil OCR disalin ke clipboard.", COLOR_SUCCESS)

    def save_ocr_txt(self):
        text = self.ocr_result.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("ImgLab", "Belum ada hasil OCR untuk disimpan.")
            return
        default = os.path.join(os.path.expanduser("~"), "Downloads", "ImgLab_OCR", "hasil_ocr.txt")
        path = filedialog.asksaveasfilename(
            title="Simpan hasil OCR", defaultextension=".txt", filetypes=[("Teks", "*.txt"), ("Semua", "*.*")],
            initialdir=os.path.dirname(default), initialfile=os.path.basename(default))
        if not path:
            return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            self.set_status(f"Hasil OCR disimpan: {path}", COLOR_SUCCESS)
        except Exception as e:
            messagebox.showerror("ImgLab", f"Gagal menyimpan: {e}")

    # ---------------------------------------------------------------- background
    def start_bg(self):
        files = self._selected_files("bg")
        if not files:
            messagebox.showwarning("ImgLab", "Pilih minimal 1 gambar dulu.")
            return
        self._run_job(lambda: self._bg_worker(files))

    def _bg_worker(self, files):
        try:
            from rembg import remove
        except ImportError:
            self.after(0, lambda: messagebox.showerror(
                "ImgLab", "rembg belum terpasang.\n\nJalankan:\npip install rembg onnxruntime\n\nLalu tutup & buka ImgLab lagi."))
            return
        out_dir = self._ensure_dir(self.bg_out.get().strip())
        done = 0
        ok = 0
        for f in files:
            if self.cancel_requested:
                raise _Cancelled()
            try:
                with Image.open(f) as img:
                    out = remove(img)
                base_name = os.path.splitext(os.path.basename(f))[0]
                out_path = self._unique_path(os.path.join(out_dir, base_name), ".png")
                out.convert("RGBA").save(out_path, "PNG")
                ok += 1
            except Exception:
                pass
            done += 1
            self.after(0, lambda p=done / len(files): (self._show_progress(p),
                                                       self.set_status(f"Hapus BG {done}/{len(files)}", COLOR_ACCENT)))
        self.after(0, lambda: self.job_finish(files, out_dir, ok))

    # ---------------------------------------------------------------- rename
    def start_rename(self):
        folder = self.ren_folder.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("ImgLab", "Pilih folder yang valid dulu.")
            return
        pattern = self.ren_pattern.get().strip()
        if not pattern:
            messagebox.showwarning("ImgLab", "Isi pola nama dulu. Contoh: IMG_{n:03d}")
            return
        try:
            start = int(self.ren_start.get().strip() or "1")
        except Exception:
            start = 1

        if self._busy:
            return
        self._busy = True
        self._show_progress(0)
        self.ren_result.delete("1.0", "end")
        self.set_status("Merename file...", COLOR_ACCENT)
        threading.Thread(target=self._rename_worker, args=(folder, pattern, start), daemon=True).start()

    def _rename_worker(self, folder, pattern, start):
        files = [f for f in os.listdir(folder)
                 if os.path.isfile(os.path.join(folder, f)) and f.lower().endswith(IMAGE_EXTS)]
        files.sort()
        renamed = []
        n = start
        for i, f in enumerate(files):
            try:
                name = pattern.format(n=n)
            except Exception:
                name = pattern.replace("{n}", str(n))
            name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip() or "gambar"
            ext = os.path.splitext(f)[1]
            target = os.path.join(folder, name + ext)
            if os.path.normcase(os.path.basename(target)) == os.path.normcase(f):
                continue
            base = target
            j = 1
            while os.path.exists(base):
                base = os.path.join(folder, f"{name} ({j}){ext}")
                j += 1
            os.replace(os.path.join(folder, f), base)
            renamed.append(f"{f} -> {os.path.basename(base)}")
            n += 1
            self.after(0, lambda p=(i + 1) / len(files): (self._show_progress(p),
                                                          self.set_status(f"Rename {i + 1}/{len(files)}", COLOR_ACCENT)))
        if not files:
            self.after(0, lambda: (self._show_progress(0, False), self.set_status("Tidak ada file gambar di folder.", COLOR_TEXT_MUTED)))
        self._busy = False
        self.after(0, lambda: self._rename_done(renamed))

    def _rename_done(self, renamed):
        self._show_progress(0, False)
        self.ren_result.delete("1.0", "end")
        if not renamed:
            self.ren_result.insert("end", "Tidak ada file yang direname.")
            self.set_status("Rename selesai (tidak ada perubahan).", COLOR_TEXT_MUTED)
            return
        for r in renamed:
            self.ren_result.insert("end", r + "\n")
        self.set_status(f"Rename selesai: {len(renamed)} file.", COLOR_SUCCESS)

    # ---------------------------------------------------------------- job runner
    def _run_job(self, fn):
        if self._busy:
            return
        self._busy = True
        self.cancel_requested = False
        self._show_progress(0)
        self.set_status("Memulai proses...", COLOR_ACCENT)
        threading.Thread(target=self._job_runner, args=(fn,), daemon=True).start()

    def _job_runner(self, fn):
        try:
            fn()
        except _Cancelled:
            self._busy = False
            self.after(0, lambda: (self._show_progress(0, False), self.set_status("Dibatalkan.", "#D29922")))
        except Exception as e:
            self._busy = False
            self.after(0, lambda: (self._show_progress(0, False), self.set_status(f"Error: {str(e)[:100]}", COLOR_DANGER)))

    def job_finish(self, files, out_dir, ok):
        self._busy = False
        if ok == len(files):
            self.set_status(f"Selesai! {ok} file tersimpan: {out_dir}", COLOR_SUCCESS)
        else:
            self.set_status(f"{ok}/{len(files)} file berhasil. Cek folder: {out_dir}", "#D29922")
        self.after(50, lambda: self._show_progress(0, False))
        if ok:
            var = messagebox.askyesno("ImgLab", f"{ok} file selesai.\n\nBuka folder hasil?")
            if var:
                os.startfile(out_dir)


if __name__ == "__main__":
    app = ImgLabApp()
    app.mainloop()