# ImgLab — Image Toolkit

Alat pengolah gambar offline berbasis GUI (Python + CustomTkinter). Tanpa login, data tidak keluar dari PC.

## Fitur

- **Konversi & Resize** — ubah JPG/PNG/WebP/BMP, atur kualitas (JPG/WebP), resize persentase atau kustom
- **OCR (Ekstrak Teks)** — ambil teks dari foto/scan/screenshot, hasil bisa disalin atau disimpan `.txt`
- **Hapus Background** — AI (rembg) → PNG transparan
- **Rename Massal** — pola `IMG_{n:03d}` dst., nomor mulai bebas
- **Crop & Rotate** — potong area gambar dengan preview drag, putar 90°/180°, flip horizontal/vertikal (batch)
- **PDF** — gabung banyak gambar jadi satu PDF (A4/Letter/A5) atau ubah PDF menjadi gambar per halaman (PNG/JPG)
- **Upscale** — perbesar gambar 2-4× berkualitas (Lanczos), opsional ditambah penajaman
- Proses batch, progress bar global tipis, nama file otomatis unik (tidak menimpa file lama)
- Jendela bisa di-resize & fullscreen (F11)

## Persyaratan

- Windows 10/11
- Python 3.9+

## Install

```bash
pip install customtkinter Pillow
```

## Instalasi dari GitHub

Syarat: **Git** terpasang (Windows: [git-scm.com](https://git-scm.com/) | Linux: `sudo apt install git`).

### Windows

```bat
git clone https://github.com/jinsakai-j/ImgLab.git
cd ImgLab
python -m pip install -r requirements.txt
python ImgLab.py
```

> Ganti `python` dengan `py -3` bila perintah `python` tidak dikenali di CMD.
> (Opsional) buat shortcut desktop tanpa CMD: `python create_shortcut.py`

### Linux (Ubuntu / Debian)

```bash
sudo apt update
sudo apt install -y git python3 python3-pip python3-tk
git clone https://github.com/jinsakai-j/ImgLab.git
cd ImgLab
python3 -m pip install -r requirements.txt
python3 ImgLab.py
```

> Catatan Linux:
> - `create_shortcut.py` dan `Run_ImgLab.bat` khusus Windows — di Linux cukup jalankan `python3 ImgLab.py`.
> - Fitur `Hapus Background` / `OCR` / `PDF → Gambar` di Linux: `python3 -m pip install rembg onnxruntime rapidocr_onnxruntime pymupdf` (lihat bagian di bawah).
> - Shortcut F11 fullscreen dan resize tetap berfungsi normal di Linux.

### Fitur opsional

```bash
pip install rembg onnxruntime            # Hapus Background (unduh model ~176 MB saat pertama dipakai)
pip install rapidocr_onnxruntime         # OCR (model diunduh otomatis saat pertama dipakai)
pip install pymupdf                      # PDF → Gambar (opsional, gambar→PDF sudah bawaan Pillow)
```

## Cara Pakai

```bash
python ImgLab.py
```

Atau:

```bash
python create_shortcut.py   # buat shortcut Desktop (tanpa window CMD, langsung pythonw)
```

Bisa juga double-click `Run_ImgLab.bat`.

## Struktur Folder

```
ImgLab/
├── ImgLab.py               # Aplikasi utama (GUI)
├── create_shortcut.py      # Skrip pembuat shortcut Desktop
├── Run_ImgLab.bat          # Peluncur alternatif (pythonw, tanpa CMD)
├── requirements.txt
├── README.md
└── assets/
    ├── imglab_icon.ico     # Icon aplikasi + shortcut
    └── imglab_icon.png     # Sumber icon (PNG)
```

## Catatan

- Hasil konversi disimpan ke folder tujuan (default: `Downloads\ImgLab_Converted`).
- Proses **Hapus Background** dan **OCR** butuh koneksi internet sekali saja saat unduh model;
  setelah itu berjalan offline.
- Rename massal hanya memproses file gambar di folder yang dipilih (bukan subfolder).
- OCR berjalan lokal (RapidOCR) dan teks disusun sesuai posisi (kiri-ke-kanan, atas-ke-bawah).

## Lisensi

Personal use.