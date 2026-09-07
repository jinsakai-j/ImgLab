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
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageTk

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
    ("Crop & Rotate", "Potong area gambar, putar, dan balik secara batch"),
    ("PDF", "Gabung gambar jadi PDF atau ubah PDF jadi gambar"),
    ("Upscale", "Perbesar gambar dengan kualitas tinggi"),
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
        self.minsize(900, 700)
        self.center_window(900, 780)

        self._busy = False
        self.cancel_requested = False
        self._conv_files = []
        self._ocr_files = []
        self._bg_files = []
        self._crop_files = []
        self._pdf_files = []
        self._up_files = []
        self._crop_rect = None
        self._crop_angle = 0
        self._crop_flip_h = False
        self._crop_flip_v = False
        self._preview_photo = None

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
            hdr = ctk.CTkFrame(panel, fg_color="transparent")
            hdr.grid(row=0, column=0, sticky="ew")
            ctk.CTkLabel(hdr, text=name,
                         font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                         text_color=COLOR_TEXT_MAIN, anchor="w").grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(hdr, text=desc,
                         font=ctk.CTkFont(family="Segoe UI", size=11),
                         text_color=COLOR_TEXT_MUTED, anchor="w").grid(row=1, column=0, sticky="w", pady=(2, 0))
            self.panels.append(panel)

        self._build_conv_panel(self.panels[0])
        self._build_ocr_panel(self.panels[1])
        self._build_bg_panel(self.panels[2])
        self._build_ren_panel(self.panels[3])
        self._build_crop_panel(self.panels[4])
        self._build_pdf_panel(self.panels[5])
        self._build_up_panel(self.panels[6])
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

    def _file_list_card(self, parent, var_holder, on_add, on_clear,
                        hint="Daftar file kosong. Klik Pilih Gambar.", box_height=None, grid_row=1):
        card = self._card(parent)
        card.grid(row=grid_row, column=0, sticky="nsew", pady=(18, 10))
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
                             text_color=COLOR_TEXT_MUTED, wrap="none",
                             height=box_height if box_height else 200)
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

    def _action_button(self, parent, text, command, grid_row=3):
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.grid(row=grid_row, column=0, sticky="ew", pady=(12, 0))
        bar.grid_columnconfigure(0, weight=1)
        btn = ctk.CTkButton(bar, text=text, height=38, corner_radius=8,
                            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER, text_color="#FFFFFF",
                            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                            command=command)
        btn.grid(row=0, column=0, sticky="ew")
        return btn

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
        self._file_list_card(parent, self._ocr_files,
                             lambda: self._add_images("ocr"), lambda: self._clear_images("ocr"),
                             "Foto/scan/screenshot berisi teks. Butuh: pip install rapidocr_onnxruntime", box_height=120)

        self._action_button(parent, "Ekstrak Teks", self.start_ocr)

        result_card = self._card(parent)
        result_card.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
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
                                         text_color=COLOR_TEXT_MAIN, wrap="word", height=150, width=400)
        self.ocr_result.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.ocr_result.insert("end", "Hasil ekstraksi teks akan muncul di sini...")

    # ---- Panel: Hapus Background ----
    def _build_bg_panel(self, parent):
        self._file_list_card(parent, self._bg_files,
                             lambda: self._add_images("bg"), lambda: self._clear_images("bg"),
                             "Latar jelas = hasil lebih mantap. Butuh: pip install rembg onnxruntime")

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
        card.grid(row=1, column=0, sticky="nsew", pady=(18, 10))
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

    # ---- Panel: Crop & Rotate ----
    def _build_crop_panel(self, parent):
        self._file_list_card(parent, self._crop_files,
                             lambda: self._add_crop_images(), lambda: self._clear_crop_files(),
                             "Pilih 1+ gambar. Klik 'Muat Preview' lalu seret area untuk crop.", box_height=60)

        params = ctk.CTkFrame(parent, fg_color="transparent")
        params.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        params.grid_columnconfigure(1, weight=1)
        dir_row = ctk.CTkFrame(params, fg_color="transparent")
        dir_row.grid(row=0, column=1, sticky="ew", padx=(18, 0), pady=4)
        dir_row.grid_columnconfigure(0, weight=1)
        self.crop_out = ctk.CTkEntry(dir_row, height=30, corner_radius=6, border_color=COLOR_CARD_BORDER,
                                     fg_color=COLOR_INPUT_BG, text_color=COLOR_TEXT_MAIN,
                                     font=ctk.CTkFont(family="Segoe UI", size=10))
        self.crop_out.insert(0, os.path.join(os.path.expanduser("~"), "Downloads", "ImgLab_Crop"))
        self.crop_out.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(dir_row, text="...", width=30, height=30, corner_radius=6, fg_color=SURFACE,
                      hover_color=SURFACE_HOVER, text_color=COLOR_TEXT_MAIN,
                      command=lambda: self._pick_folder(self.crop_out)).grid(row=0, column=1, padx=(4, 0))
        ctk.CTkButton(dir_row, text="Buka", width=46, height=30, corner_radius=6, fg_color=SURFACE,
                      hover_color=SURFACE_HOVER, text_color=COLOR_TEXT_MAIN,
                      font=ctk.CTkFont(family="Segoe UI", size=10),
                      command=lambda: self._open_folder(self.crop_out.get())).grid(row=0, column=2, padx=(4, 0))
        ctk.CTkLabel(params, text="Simpan ke:", font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=COLOR_TEXT_MAIN, anchor="w").grid(row=0, column=0, sticky="w", pady=4)

        preview_card = self._card(parent)
        preview_card.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        bar = ctk.CTkFrame(preview_card, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
        bar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(bar, text="Preview (seret area yang ingin dipotong)", font=ctk.CTkFont(
            family="Segoe UI", size=11, weight="bold"), text_color=COLOR_TEXT_MAIN, anchor="w"
        ).grid(row=0, column=0, sticky="w")
        self.crop_status_v = ctk.CTkLabel(bar, text="Area: belum dipilih", font=ctk.CTkFont(
            family="Segoe UI", size=10), text_color=COLOR_TEXT_DIM)
        self.crop_status_v.grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(bar, text="Muat Preview", width=90, height=26, corner_radius=6, fg_color=SURFACE,
                      hover_color=SURFACE_HOVER, text_color=COLOR_TEXT_MAIN,
                      font=ctk.CTkFont(family="Segoe UI", size=10),
                      command=self._show_crop_preview).grid(row=0, column=2)
        ctk.CTkButton(bar, text="Bersih", width=60, height=26, corner_radius=6, fg_color=SURFACE,
                      hover_color=SURFACE_HOVER, text_color=COLOR_TEXT_MAIN,
                      font=ctk.CTkFont(family="Segoe UI", size=10),
                      command=self._reset_crop_rect).grid(row=0, column=3, padx=(6, 0))

        self.crop_canvas = tk.Canvas(preview_card, height=176, bg=COLOR_INPUT_BG, highlightthickness=1,
                                     highlightbackground=COLOR_CARD_BORDER)
        self.crop_canvas.grid(row=1, column=0, sticky="ew", padx=12, pady=(8, 12))
        self.crop_canvas.bind("<ButtonPress-1>", self._crop_rect_start)
        self.crop_canvas.bind("<B1-Motion>", self._crop_rect_drag)
        self.crop_canvas.bind("<ButtonRelease-1>", self._crop_rect_end)

        rot = ctk.CTkFrame(parent, fg_color="transparent")
        rot.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        ctk.CTkLabel(rot, text="Rotate / Flip:", font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=COLOR_TEXT_MAIN).pack(side="left")
        for text, cmd in [("⟲ 90°", "l"), ("⟳ 90°", "r"), ("180°", "180"),
                          ("Flip H", "fh"), ("Flip V", "fv"), ("Reset", "rst")]:
            ctk.CTkButton(rot, text=text, width=58, height=28, corner_radius=6, fg_color=SURFACE,
                          hover_color=SURFACE_HOVER, text_color=COLOR_TEXT_MAIN,
                          font=ctk.CTkFont(family="Segoe UI", size=10),
                          command=lambda c=cmd: self._crop_transform(c)).pack(side="left", padx=(8, 0))

        self._action_button(parent, "Terapkan (Crop + Putar)", self.start_crop, grid_row=5)

    def _add_crop_images(self):
        self._add_images("crop")

    def _clear_crop_files(self):
        self._clear_images("crop")
        self.crop_canvas.delete("all")
        self._crop_rect = None

    def _show_crop_preview(self):
        files = self._selected_files("crop")
        if not files:
            messagebox.showwarning("ImgLab", "Pilih minimal 1 gambar dulu.")
            return
        try:
            img = Image.open(files[0])
            img.load()
            w = max(self.crop_canvas.winfo_width() or 0, 560)
            img.thumbnail((w - 24, 166), Image.Resampling.LANCZOS)
        except Exception as e:
            messagebox.showerror("ImgLab", f"Preview gagal: {e}")
            return
        self._preview_photo = ImageTk.PhotoImage(img)
        self._preview_img = img
        self.crop_canvas.delete("all")
        self.crop_canvas.img_w, self.crop_canvas.img_h = img.size
        self.crop_canvas.create_image(0, 0, anchor="nw", image=self._preview_photo)
        self._reset_crop_rect()

    def _reset_crop_rect(self):
        self._crop_rect = None
        self.crop_canvas.delete("rect")
        self.crop_status_v.configure(text="Area: belum dipilih")

    def _crop_rect_start(self, ev):
        self.crop_canvas.delete("rect")
        self._drag_x0, self._drag_y0 = ev.x, ev.y

    def _crop_rect_drag(self, ev):
        self.crop_canvas.delete("rect")
        self.crop_canvas.create_rectangle(self._drag_x0, self._drag_y0, ev.x, ev.y,
                                          outline=COLOR_ACCENT, width=2, tags="rect")

    def _crop_rect_end(self, ev):
        x0, y0 = self._drag_x0, self._drag_y0
        x1, y1 = ev.x, ev.y
        if x1 < x0: x0, x1 = x1, x0
        if y1 < y0: y0, y1 = y1, y0
        iw = self.crop_canvas.img_w
        ih = self.crop_canvas.img_h
        if iw <= 0 or ih <= 0 or (x1 - x0) < 4 or (y1 - y0) < 4 or y1 > ih or x1 > iw:
            self._reset_crop_rect()
            return
        self._crop_rect = (x0 / iw, y0 / ih, x1 / iw, y1 / ih)
        self.crop_status_v.configure(
            text=f"Area: {int(x0)}-{int(x1)} px × {int(y0)}-{int(y1)} px")

    def _crop_transform(self, cmd):
        if cmd == "l": self._crop_angle = (self._crop_angle + 90) % 360
        elif cmd == "r": self._crop_angle = (self._crop_angle - 90) % 360
        elif cmd == "180": self._crop_angle = (self._crop_angle + 180) % 360
        elif cmd == "fh": self._crop_flip_h = not self._crop_flip_h
        elif cmd == "fv": self._crop_flip_v = not self._crop_flip_v
        elif cmd == "rst":
            self._crop_angle = 0
            self._crop_flip_h = self._crop_flip_v = False
        self.set_status(f"Transform: putar {self._crop_angle}°, flipH={self._crop_flip_h}, flipV={self._crop_flip_v}",
                        COLOR_TEXT_MUTED)

    # ---- Panel: PDF ----
    def _build_pdf_panel(self, parent):
        self.pdf_mode = ctk.CTkSegmentedButton(parent, values=["Gambar → PDF", "PDF → Gambar"],
                                               height=32, corner_radius=8, fg_color=COLOR_INPUT_BG,
                                               selected_color=COLOR_ACCENT, selected_hover_color=COLOR_ACCENT_HOVER,
                                               unselected_color=SURFACE, unselected_hover_color=SURFACE_HOVER,
                                               text_color=COLOR_TEXT_MAIN, font=ctk.CTkFont(family="Segoe UI", size=11),
                                               command=self._pdf_mode_change)
        self.pdf_mode.set("Gambar → PDF")
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        self.pdf_mode.grid(row=0, column=0, sticky="w")

        self._file_list_card(parent, self._pdf_files,
                             lambda: self._add_pdf_files(), lambda: self._clear_pdf_files(),
                             "Pilih file sesuai mode di atas.", box_height=50, grid_row=2)

        params = ctk.CTkFrame(parent, fg_color="transparent")
        params.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        params.grid_columnconfigure(1, weight=1)

        self.pdf_label1 = ctk.CTkLabel(params, text="Ukuran halaman:", font=ctk.CTkFont(family="Segoe UI", size=11),
                                       text_color=COLOR_TEXT_MAIN, anchor="w")
        self.pdf_label1.grid(row=0, column=0, sticky="w", pady=4)
        self.pdf_label2 = ctk.CTkLabel(params, text="Resolusi:", font=ctk.CTkFont(family="Segoe UI", size=11),
                                       text_color=COLOR_TEXT_MAIN, anchor="w")
        self.pdf_label2.grid(row=1, column=0, sticky="w", pady=4)

        self.pdf_size = ctk.CTkOptionMenu(params, values=["Asli (ikuti gambar)", "A4", "Letter", "A5"],
                                          width=180, height=30, corner_radius=6, fg_color=COLOR_INPUT_BG,
                                          button_color=COLOR_CARD_BORDER, button_hover_color=SURFACE_HOVER,
                                          font=ctk.CTkFont(family="Segoe UI", size=11))
        self.pdf_size.set("A4")
        self.pdf_size.grid(row=0, column=1, sticky="w", padx=(18, 0), pady=4)

        self.pdf_imgfmt = ctk.CTkOptionMenu(params, values=["PNG", "JPG"], width=100, height=30,
                                            corner_radius=6, fg_color=COLOR_INPUT_BG,
                                            button_color=COLOR_CARD_BORDER, button_hover_color=SURFACE_HOVER,
                                            font=ctk.CTkFont(family="Segoe UI", size=11))
        self.pdf_imgfmt.set("PNG")
        self.pdf_imgfmt.grid_remove()

        self.pdf_dpi = ctk.CTkOptionMenu(params, values=["72 DPI (kecil)", "150 DPI", "300 DPI (cetak)"],
                                         width=140, height=30, corner_radius=6, fg_color=COLOR_INPUT_BG,
                                         button_color=COLOR_CARD_BORDER, button_hover_color=SURFACE_HOVER,
                                         font=ctk.CTkFont(family="Segoe UI", size=11))
        self.pdf_dpi.set("150 DPI")
        self.pdf_dpi.grid_remove()

        dir_row = ctk.CTkFrame(params, fg_color="transparent")
        dir_row.grid(row=2, column=1, sticky="ew", padx=(18, 0), pady=4)
        dir_row.grid_columnconfigure(0, weight=1)
        self.pdf_out = ctk.CTkEntry(dir_row, height=32, corner_radius=6, border_color=COLOR_CARD_BORDER,
                                    fg_color=COLOR_INPUT_BG, text_color=COLOR_TEXT_MAIN,
                                    font=ctk.CTkFont(family="Segoe UI", size=10))
        self.pdf_out.insert(0, os.path.join(os.path.expanduser("~"), "Downloads", "ImgLab_PDF"))
        self.pdf_out.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(dir_row, text="...", width=30, height=32, corner_radius=6, fg_color=SURFACE,
                      hover_color=SURFACE_HOVER, text_color=COLOR_TEXT_MAIN,
                      command=lambda: self._pick_folder(self.pdf_out)).grid(row=0, column=1, padx=(4, 0))
        ctk.CTkButton(dir_row, text="Buka", width=46, height=32, corner_radius=6, fg_color=SURFACE,
                      hover_color=SURFACE_HOVER, text_color=COLOR_TEXT_MAIN,
                      font=ctk.CTkFont(family="Segoe UI", size=10),
                      command=lambda: self._open_folder(self.pdf_out.get())).grid(row=0, column=2, padx=(4, 0))
        ctk.CTkLabel(params, text="Simpan ke:", font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=COLOR_TEXT_MAIN, anchor="w").grid(row=2, column=0, sticky="w", pady=4)

        self.pdf_action = self._action_button(parent, "Gabung Jadi PDF", self.start_pdf, grid_row=4)

    def _pdf_mode_change(self, choice):
        is_img2pdf = choice.startswith("Gambar")
        self.pdf_label1.configure(text="Ukuran halaman:" if is_img2pdf else "Format gambar:")
        self.pdf_size.grid_remove()
        self.pdf_imgfmt.grid_remove()
        self.pdf_dpi.grid_remove()
        if is_img2pdf:
            self.pdf_label2.grid_remove()
            self.pdf_size.grid(row=0, column=1, sticky="w", padx=(18, 0), pady=4)
        else:
            self.pdf_label2.grid(row=1, column=0, sticky="w", pady=4)
            self.pdf_imgfmt.grid(row=0, column=1, sticky="w", padx=(18, 0), pady=4)
            self.pdf_dpi.grid(row=1, column=1, sticky="w", padx=(18, 0), pady=4)
        self.pdf_action.configure(text="Gabung Jadi PDF" if is_img2pdf else "Ubah ke Gambar")
        self._clear_pdf_files()
        self.set_status("Mode diganti. Pilih file baru sesuai mode.", COLOR_TEXT_MUTED)

    def _add_pdf_files(self):
        img2pdf = self.pdf_mode.get().startswith("Gambar")
        allowed = IMAGE_EXTS if img2pdf else (".pdf",)
        files = filedialog.askopenfilenames(
            title="Pilih file", filetypes=[("File cocok", "".join("*" + e for e in allowed)),
                                          ("Semua File", "*.*")])
        box = self._list_box("pdf")
        for f in files:
            if f.lower().endswith(allowed):
                box.insert("end", f)
        box.see("end")

    def _clear_pdf_files(self):
        box = self._list_box("pdf")
        if box:
            box.delete("1.0", "end")

    # ---- Panel: Upscale ----
    def _build_up_panel(self, parent):
        self._file_list_card(parent, self._up_files,
                             lambda: self._add_images("up"), lambda: self._clear_images("up"),
                             "Perbesar gambar 2-4×, offline dengan Lanczos.", box_height=110)

        params = ctk.CTkFrame(parent, fg_color="transparent")
        params.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        params.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(params, text="Skala:", font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=COLOR_TEXT_MAIN, anchor="w").grid(row=0, column=0, sticky="w", pady=4)
        self.up_scale = ctk.CTkOptionMenu(params, values=["2x", "3x", "4x"], width=100, height=30,
                                          corner_radius=6, fg_color=COLOR_INPUT_BG,
                                          button_color=COLOR_CARD_BORDER, button_hover_color=SURFACE_HOVER,
                                          font=ctk.CTkFont(family="Segoe UI", size=11))
        self.up_scale.set("2x")
        self.up_scale.grid(row=0, column=1, sticky="w", padx=(18, 0), pady=4)

        ctk.CTkLabel(params, text="Metode:", font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=COLOR_TEXT_MAIN, anchor="w").grid(row=1, column=0, sticky="w", pady=4)
        self.up_method = ctk.CTkOptionMenu(params,
                                           values=["Lanczos (halus)", "Lanczos + Tajam"], width=160, height=30,
                                           corner_radius=6, fg_color=COLOR_INPUT_BG,
                                           button_color=COLOR_CARD_BORDER, button_hover_color=SURFACE_HOVER,
                                           font=ctk.CTkFont(family="Segoe UI", size=11))
        self.up_method.set("Lanczos + Tajam")
        self.up_method.grid(row=1, column=1, sticky="w", padx=(18, 0), pady=4)

        dir_row = ctk.CTkFrame(params, fg_color="transparent")
        dir_row.grid(row=2, column=1, sticky="ew", padx=(18, 0), pady=4)
        dir_row.grid_columnconfigure(0, weight=1)
        self.up_out = ctk.CTkEntry(dir_row, height=32, corner_radius=6, border_color=COLOR_CARD_BORDER,
                                   fg_color=COLOR_INPUT_BG, text_color=COLOR_TEXT_MAIN,
                                   font=ctk.CTkFont(family="Segoe UI", size=10))
        self.up_out.insert(0, os.path.join(os.path.expanduser("~"), "Downloads", "ImgLab_Upscale"))
        self.up_out.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(dir_row, text="...", width=30, height=32, corner_radius=6, fg_color=SURFACE,
                      hover_color=SURFACE_HOVER, text_color=COLOR_TEXT_MAIN,
                      command=lambda: self._pick_folder(self.up_out)).grid(row=0, column=1, padx=(4, 0))
        ctk.CTkButton(dir_row, text="Buka", width=46, height=32, corner_radius=6, fg_color=SURFACE,
                      hover_color=SURFACE_HOVER, text_color=COLOR_TEXT_MAIN,
                      font=ctk.CTkFont(family="Segoe UI", size=10),
                      command=lambda: self._open_folder(self.up_out.get())).grid(row=0, column=2, padx=(4, 0))
        ctk.CTkLabel(params, text="Simpan ke:", font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=COLOR_TEXT_MAIN, anchor="w").grid(row=2, column=0, sticky="w", pady=4)

        self._action_button(parent, "Perbesar Gambar", self.start_upscale)

    # ---------------------------------------------------------------- helpers
    def _list_box(self, key):
        widgets = {"conv": self._conv_files, "ocr": self._ocr_files, "bg": self._bg_files,
                   "crop": self._crop_files, "pdf": self._pdf_files, "up": self._up_files}.get(key, [])
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
    # ---------------------------------------------------------------- crop & rotate
    def start_crop(self):
        files = self._selected_files("crop")
        if not files:
            messagebox.showwarning("ImgLab", "Pilih minimal 1 gambar dulu.")
            return
        self._run_job(lambda: self._crop_worker(files))

    def _crop_worker(self, files):
        rect = self._crop_rect
        angle = self._crop_angle
        flip_h = self._crop_flip_h
        flip_v = self._crop_flip_v
        out_dir = self._ensure_dir(self.crop_out.get().strip())
        done = 0
        ok = 0
        for f in files:
            if self.cancel_requested:
                raise _Cancelled()
            try:
                img = Image.open(f)
                img.load()
                if rect:
                    x0, y0, x1, y1 = rect
                    img = img.crop((int(x0 * img.width), int(y0 * img.height),
                                    int(x1 * img.width), int(y1 * img.height)))
                if flip_h:
                    img = img.transpose(Image.FLIP_LEFT_RIGHT)
                if flip_v:
                    img = img.transpose(Image.FLIP_TOP_BOTTOM)
                if angle:
                    img = img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
                base_name = os.path.splitext(os.path.basename(f))[0]
                out_path = self._unique_path(os.path.join(out_dir, base_name), ".png")
                img.convert("RGBA").save(out_path, "PNG")
                ok += 1
            except Exception:
                pass
            done += 1
            self.after(0, lambda p=done / len(files): (self._show_progress(p),
                                                       self.set_status(f"Crop & Rotate {done}/{len(files)}", COLOR_ACCENT)))
        self.after(0, lambda: self.job_finish(files, out_dir, ok))

    # ---------------------------------------------------------------- PDF
    def start_pdf(self):
        files = self._selected_files("pdf")
        if not files:
            messagebox.showwarning("ImgLab", "Pilih file dulu (sesuai mode).")
            return
        self._run_job(lambda: self._pdf_worker(files))

    @staticmethod
    def _pdf_page_size(choice):
        return {"A4": (1240, 1754), "Letter": (1275, 1650), "A5": (874, 1240)}.get(choice, None)

    def _pdf_worker(self, files):
        img2pdf = self.pdf_mode.get().startswith("Gambar")
        out_dir = self._ensure_dir(self.pdf_out.get().strip())
        done = 0
        ok = 0
        if img2pdf:
            size_choice = self.pdf_size.get()
            page = self._pdf_page_size(size_choice)
            images = []
            for f in files:
                if self.cancel_requested:
                    raise _Cancelled()
                try:
                    im = Image.open(f).convert("RGB")
                    if page:
                        pw, ph = page
                        scale = min(pw / im.width, ph / im.height, 1.0)
                        if scale < 1.0:
                            im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))),
                                           Image.Resampling.LANCZOS)
                        canvas = Image.new("RGB", page, "white")
                        canvas.paste(im, ((pw - im.width) // 2, (ph - im.height) // 2))
                        im = canvas
                    images.append(im)
                except Exception:
                    pass
                done += 1
                self.after(0, lambda p=done / len(files): (self._show_progress(p),
                                                           self.set_status(f"Menyiapkan gambar {done}/{len(files)}", COLOR_ACCENT)))
            if images:
                name = os.path.splitext(os.path.basename(files[0]))[0]
                out_path = self._unique_path(os.path.join(out_dir, name + "_gabungan"), ".pdf")
                first, rest = images[0], images[1:]
                first.save(out_path, "PDF", save_all=True, append_images=rest, resolution=150)
                ok = 1
            self.after(0, lambda: self._pdf_done(img2pdf, out_dir, ok, len(files)))
        else:
            dpi = int(re.search(r"\d+", self.pdf_dpi.get()).group())
            fmt = self.pdf_imgfmt.get()
            zoom = dpi / 72.0
            try:
                import fitz
            except ImportError:
                self.after(0, lambda: messagebox.showerror(
                    "ImgLab", "Butuh PyMuPDF untuk PDF → Gambar.\n\npip install pymupdf"))
                raise _Cancelled()
            for f in files:
                if self.cancel_requested:
                    raise _Cancelled()
                try:
                    base_name = os.path.splitext(os.path.basename(f))[0]
                    doc = fitz.open(f)
                    for pno in range(len(doc)):
                        if self.cancel_requested:
                            raise _Cancelled()
                        page = doc.load_page(pno)
                        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
                        ext = ".png" if fmt == "PNG" else ".jpg"
                        out_path = self._unique_path(os.path.join(out_dir, f"{base_name}_p{pno+1:03d}"), ext)
                        if fmt == "PNG":
                            pix.save(out_path)
                        else:
                            Image.frombytes("RGB", (pix.width, pix.height), pix.samples).save(out_path, "JPEG", quality=92)
                        done += 1
                        self.after(0, lambda p=min(done / (len(files) * max(len(doc), 1)), 1.0): (
                            self._show_progress(p), self.set_status(f"PDF {base_name} halaman {pno+1}/{len(doc)}", COLOR_ACCENT)))
                    doc.close()
                    ok += 1
                except Exception:
                    pass
            self.after(0, lambda: self._pdf_done(img2pdf, out_dir, ok, len(files)))

    def _pdf_done(self, img2pdf, out_dir, ok, n):
        self._busy = False
        self._show_progress(0, False)
        self.set_status(f"PDF: {ok} berhasil dari {n} file → {out_dir}", COLOR_SUCCESS if ok == n else "#D29922")
        if ok:
            self.after(50, lambda: messagebox.askyesno("ImgLab", "Hasil PDF selesai.\n\nBuka folder hasil?") and os.startfile(out_dir))

    # ---------------------------------------------------------------- upscale
    def start_upscale(self):
        files = self._selected_files("up")
        if not files:
            messagebox.showwarning("ImgLab", "Pilih minimal 1 gambar dulu.")
            return
        self._run_job(lambda: self._up_worker(files))

    def _up_worker(self, files):
        factor = int(re.sub(r"\D", "", self.up_scale.get()) or 2)
        method = self.up_method.get()
        out_dir = self._ensure_dir(self.up_out.get().strip())
        done = 0
        ok = 0
        for f in files:
            if self.cancel_requested:
                raise _Cancelled()
            try:
                img = Image.open(f)
                img.load()
                img = img.convert("RGB")
                img = img.resize((img.width * factor, img.height * factor), Image.Resampling.LANCZOS)
                if "Tajam" in method:
                    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=120))
                ext = os.path.splitext(f)[1].lower()
                if ext not in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
                    ext = ".png"
                base = os.path.splitext(os.path.basename(f))[0]
                out_path = self._unique_path(os.path.join(out_dir, f"{base}_{factor}x"), ext)
                if ext in (".jpg", ".jpeg"):
                    img.save(out_path, "JPEG", quality=95)
                else:
                    img.save(out_path)
                ok += 1
            except Exception:
                pass
            done += 1
            self.after(0, lambda p=done / len(files): (self._show_progress(p),
                                                       self.set_status(f"Upscale {done}/{len(files)}", COLOR_ACCENT)))
        self.after(0, lambda: self.job_finish(files, out_dir, ok))

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