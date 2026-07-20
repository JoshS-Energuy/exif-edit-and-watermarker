"""Tool: convert a ZIP archive into a single PDF, one page per file.

Handles images (any format/size/orientation Pillow can open, including
multi-frame TIFF/GIF) and existing PDF documents (single or multi-page).
Before exporting, the user can preview each file (thumbnail), reorder
entries, rotate them 90 degrees at a time, and drop ones they don't want.
"""
import io
import os
import queue
import re
import threading
import zipfile

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter

try:
    import fitz  # PyMuPDF, used only for rendering PDF page thumbnails
except ImportError:
    fitz = None

TOOL_NAME = "ZIP to PDF"

IMAGE_EXTS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff",
    ".webp", ".heic", ".heif",
}
PDF_EXT = ".pdf"

THUMB_SIZE = 96
ROW_BG = "#ffffff"
ROW_SELECTED_BG = "#cce5ff"

_NATSORT_RE = re.compile(r"(\d+)")


def _natural_key(name):
    parts = _NATSORT_RE.split(name.lower())
    return [int(p) if p.isdigit() else p for p in parts]


def _is_skippable(info):
    if info.is_dir():
        return True
    name = info.filename
    base = os.path.basename(name.rstrip("/"))
    if not base or base.startswith("."):
        return True
    if name.startswith("__MACOSX/"):
        return True
    return False


class ZipEntry:
    """One file extracted from the ZIP, with its preview/reorder state."""

    def __init__(self, filename, data, kind, page_count):
        self.filename = filename
        self.data = data
        self.kind = kind  # 'pdf' | 'image' | 'unsupported'
        self.page_count = page_count
        self.rotation = 0  # clockwise degrees: 0, 90, 180, 270
        self.base_thumb = None  # unrotated PIL.Image preview

    @property
    def label_text(self):
        if self.kind == "pdf":
            pages = "page" if self.page_count == 1 else "pages"
            return f"{self.filename}  (PDF, {self.page_count} {pages})"
        if self.kind == "image":
            if self.page_count > 1:
                return f"{self.filename}  (image, {self.page_count} frames)"
            return f"{self.filename}  (image)"
        return f"{self.filename}  (unsupported — will be skipped)"


def _placeholder_thumbnail(label_text):
    img = Image.new("RGB", (THUMB_SIZE, THUMB_SIZE), (235, 235, 235))
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [3, 3, THUMB_SIZE - 4, THUMB_SIZE - 4], outline=(170, 170, 170), width=2
    )
    font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label_text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((THUMB_SIZE - w) / 2, (THUMB_SIZE - h) / 2),
        label_text,
        fill=(120, 120, 120),
        font=font,
    )
    return img


def _render_pdf_thumbnail(data):
    if fitz is None:
        return None
    try:
        doc = fitz.open(stream=data, filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(0.4, 0.4))
        mode = "RGBA" if pix.alpha else "RGB"
        img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
        return img.convert("RGB")
    except Exception:
        return None


def _load_entry_thumbnail(entry):
    try:
        if entry.kind == "image":
            img = Image.open(io.BytesIO(entry.data))
            frame = ImageOps.exif_transpose(img)
            if frame.mode != "RGB":
                frame = frame.convert("RGB")
            frame.thumbnail((THUMB_SIZE, THUMB_SIZE))
            entry.base_thumb = frame
        elif entry.kind == "pdf":
            thumb = _render_pdf_thumbnail(entry.data)
            if thumb is None:
                thumb = _placeholder_thumbnail("PDF")
            else:
                thumb.thumbnail((THUMB_SIZE, THUMB_SIZE))
            entry.base_thumb = thumb
        else:
            ext = os.path.splitext(entry.filename)[1].lstrip(".").upper()
            entry.base_thumb = _placeholder_thumbnail(ext or "FILE")
    except (UnidentifiedImageError, Exception):
        entry.base_thumb = _placeholder_thumbnail("?")


def _rotated_display_image(entry):
    img = entry.base_thumb
    if entry.rotation:
        img = img.rotate(-entry.rotation, expand=True)
    if img.width > THUMB_SIZE or img.height > THUMB_SIZE:
        img = img.copy()
        img.thumbnail((THUMB_SIZE, THUMB_SIZE))
    canvas_img = Image.new("RGB", (THUMB_SIZE, THUMB_SIZE), (255, 255, 255))
    x = (THUMB_SIZE - img.width) // 2
    y = (THUMB_SIZE - img.height) // 2
    canvas_img.paste(img, (x, y))
    return ImageTk.PhotoImage(canvas_img)


def load_zip_entries(zip_path, progress_cb=None):
    """Read every usable file in zip_path into memory and classify it."""
    with zipfile.ZipFile(zip_path) as zf:
        infos = [i for i in zf.infolist() if not _is_skippable(i)]
        infos.sort(key=lambda i: _natural_key(i.filename))
        total = len(infos)

        entries = []
        for idx, info in enumerate(infos):
            if progress_cb:
                progress_cb(idx, total, info.filename)

            data = zf.read(info)
            ext = os.path.splitext(info.filename)[1].lower()

            if ext == PDF_EXT:
                kind = "pdf"
                try:
                    page_count = len(PdfReader(io.BytesIO(data)).pages)
                except Exception:
                    page_count = 0
            elif ext in IMAGE_EXTS:
                kind = "image"
                try:
                    img = Image.open(io.BytesIO(data))
                    page_count = getattr(img, "n_frames", 1)
                except Exception:
                    page_count = 1
            else:
                kind = "unsupported"
                page_count = 0

            entry = ZipEntry(info.filename, data, kind, page_count)
            _load_entry_thumbnail(entry)
            entries.append(entry)

    return entries


def _append_image_pages(writer, data, rotation=0):
    img = Image.open(io.BytesIO(data))
    frames = []
    try:
        n_frames = getattr(img, "n_frames", 1)
    except Exception:
        n_frames = 1

    for frame_idx in range(n_frames):
        img.seek(frame_idx)
        frame = ImageOps.exif_transpose(img)
        if rotation:
            frame = frame.rotate(-rotation, expand=True)
        if frame.mode != "RGB":
            frame = frame.convert("RGB")
        frames.append(frame.copy())

    pdf_buf = io.BytesIO()
    frames[0].save(
        pdf_buf, format="PDF", save_all=True, append_images=frames[1:]
    )
    pdf_buf.seek(0)
    reader = PdfReader(pdf_buf)
    for page in reader.pages:
        writer.add_page(page)
    return len(reader.pages)


def build_pdf_from_entries(entries, output_path, progress_cb=None):
    """Convert entries (in their given order) into a single PDF.

    Returns (page_count, skipped) where skipped is a list of
    (filename, reason) for entries that could not be converted.
    """
    writer = PdfWriter()
    skipped = []
    page_count = 0
    total = len(entries)

    for idx, entry in enumerate(entries):
        if progress_cb:
            progress_cb(idx, total, entry.filename)
        try:
            if entry.kind == "pdf":
                reader = PdfReader(io.BytesIO(entry.data))
                for page in reader.pages:
                    if entry.rotation:
                        page.rotate(entry.rotation)
                    writer.add_page(page)
                    page_count += 1
            elif entry.kind == "image":
                added = _append_image_pages(writer, entry.data, entry.rotation)
                page_count += added
            else:
                skipped.append((entry.filename, "unsupported file type"))
        except UnidentifiedImageError:
            skipped.append((entry.filename, "unrecognized image data"))
        except Exception as e:
            skipped.append((entry.filename, str(e)))

    if page_count == 0:
        raise ValueError("No convertible pages were found.")

    with open(output_path, "wb") as f:
        writer.write(f)

    return page_count, skipped


class ZipToPdfFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.zip_path = None
        self.entries = []
        self.selected_index = None
        self.row_widgets = []  # list of dicts: frame, thumb_label, text_label
        self._progress_queue = queue.Queue()
        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(3, weight=1)

        ttk.Button(frm, text="Select ZIP file...", command=self.select_zip).grid(
            row=0, column=0, sticky="ew", pady=(0, 8)
        )
        self.path_label = ttk.Label(frm, text="No ZIP loaded", foreground="gray")
        self.path_label.grid(row=1, column=0, sticky="w", pady=(0, 8))

        toolbar = ttk.Frame(frm)
        toolbar.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        self.up_btn = ttk.Button(
            toolbar, text="↑ Move Up", command=self.move_up, state="disabled"
        )
        self.up_btn.pack(side="left", padx=(0, 4))
        self.down_btn = ttk.Button(
            toolbar, text="↓ Move Down", command=self.move_down, state="disabled"
        )
        self.down_btn.pack(side="left", padx=4)
        self.rotate_btn = ttk.Button(
            toolbar, text="↻ Rotate 90°", command=self.rotate_selected, state="disabled"
        )
        self.rotate_btn.pack(side="left", padx=4)
        self.remove_btn = ttk.Button(
            toolbar, text="Remove", command=self.remove_selected, state="disabled"
        )
        self.remove_btn.pack(side="left", padx=4)

        list_frame = ttk.Frame(frm, relief="sunken", borderwidth=1)
        list_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 8))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(list_frame, background=ROW_BG, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=vsb.set)

        self.inner_frame = tk.Frame(self.canvas, background=ROW_BG)
        self.inner_window = self.canvas.create_window(
            (0, 0), window=self.inner_frame, anchor="nw"
        )
        self.inner_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.inner_window, width=e.width),
        )
        self.canvas.bind("<Enter>", lambda e: self._bind_mousewheel())
        self.canvas.bind("<Leave>", lambda e: self._unbind_mousewheel())

        self.convert_btn = ttk.Button(
            frm, text="Convert to PDF...", command=self.convert, state="disabled"
        )
        self.convert_btn.grid(row=4, column=0, sticky="ew", pady=(0, 8))

        self.progress = ttk.Progressbar(frm, mode="determinate")
        self.progress.grid(row=5, column=0, sticky="ew", pady=(0, 8))

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(frm, textvariable=self.status_var, foreground="gray").grid(
            row=6, column=0, sticky="w"
        )

    def _bind_mousewheel(self):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    # -- ZIP loading -----------------------------------------------------

    def select_zip(self):
        path = filedialog.askopenfilename(
            title="Select a ZIP file",
            filetypes=[("ZIP archives", "*.zip"), ("All files", "*.*")],
        )
        if not path:
            return

        self.zip_path = path
        self.path_label.config(text=path)
        self._set_controls_enabled(False)
        self.convert_btn.config(state="disabled")
        self.status_var.set("Loading...")
        self.progress.config(value=0, maximum=1)

        thread = threading.Thread(
            target=self._load_worker, args=(path,), daemon=True
        )
        thread.start()
        self.after(50, self._poll_load_progress)

    def _load_worker(self, path):
        def progress_cb(idx, total, name):
            self._progress_queue.put(("load_progress", idx, total, name))

        try:
            entries = load_zip_entries(path, progress_cb)
            self._progress_queue.put(("load_done", entries, None, None))
        except zipfile.BadZipFile:
            self._progress_queue.put(("load_error", "That file is not a valid ZIP archive.", None, None))
        except Exception as e:
            self._progress_queue.put(("load_error", str(e), None, None))

    def _poll_load_progress(self):
        try:
            while True:
                kind, a, b, c = self._progress_queue.get_nowait()
                if kind == "load_progress":
                    idx, total, name = a, b, c
                    self.progress.config(value=idx + 1, maximum=max(total, 1))
                    self.status_var.set(f"Loading {name} ({idx + 1}/{total})...")
                elif kind == "load_done":
                    entries = a
                    if not entries:
                        messagebox.showwarning("Empty ZIP", "That ZIP archive has no usable files.")
                        self.status_var.set("Ready.")
                        return
                    self.entries = entries
                    self.selected_index = None
                    self._render_rows()
                    self.convert_btn.config(state="normal")
                    self.status_var.set(f"Loaded {len(entries)} file(s).")
                    return
                elif kind == "load_error":
                    messagebox.showerror("Error", f"Could not read ZIP file:\n{a}")
                    self.status_var.set("Ready.")
                    return
        except queue.Empty:
            pass
        self.after(50, self._poll_load_progress)

    # -- Row list rendering ------------------------------------------------

    def _render_rows(self):
        for child in self.inner_frame.winfo_children():
            child.destroy()
        self.row_widgets = []

        for idx, entry in enumerate(self.entries):
            row = tk.Frame(self.inner_frame, background=ROW_BG)
            row.grid(row=idx, column=0, sticky="ew", padx=4, pady=2)
            self.inner_frame.columnconfigure(0, weight=1)

            photo = _rotated_display_image(entry)
            thumb_label = tk.Label(row, image=photo, background=ROW_BG)
            thumb_label.image = photo  # keep reference
            thumb_label.grid(row=0, column=0, padx=(4, 8), pady=4)

            text_label = tk.Label(
                row, text=entry.label_text, background=ROW_BG, anchor="w", justify="left"
            )
            text_label.grid(row=0, column=1, sticky="w")
            row.columnconfigure(1, weight=1)

            for widget in (row, thumb_label, text_label):
                widget.bind("<Button-1>", lambda e, i=idx: self._select_row(i))

            self.row_widgets.append(
                {"row": row, "thumb": thumb_label, "text": text_label}
            )

        self._apply_selection_highlight()

    def _select_row(self, idx):
        self.selected_index = idx
        self._apply_selection_highlight()
        self._set_controls_enabled(True)

    def _apply_selection_highlight(self):
        for i, widgets in enumerate(self.row_widgets):
            bg = ROW_SELECTED_BG if i == self.selected_index else ROW_BG
            widgets["row"].config(background=bg)
            widgets["thumb"].config(background=bg)
            widgets["text"].config(background=bg)

    def _set_controls_enabled(self, enabled):
        state = "normal" if enabled and self.selected_index is not None else "disabled"
        self.up_btn.config(state=state)
        self.down_btn.config(state=state)
        self.rotate_btn.config(state=state)
        self.remove_btn.config(state=state)

    # -- Row actions ---------------------------------------------------

    def move_up(self):
        i = self.selected_index
        if i is None or i == 0:
            return
        self.entries[i - 1], self.entries[i] = self.entries[i], self.entries[i - 1]
        self.selected_index = i - 1
        self._render_rows()

    def move_down(self):
        i = self.selected_index
        if i is None or i >= len(self.entries) - 1:
            return
        self.entries[i + 1], self.entries[i] = self.entries[i], self.entries[i + 1]
        self.selected_index = i + 1
        self._render_rows()

    def rotate_selected(self):
        i = self.selected_index
        if i is None:
            return
        entry = self.entries[i]
        entry.rotation = (entry.rotation + 90) % 360
        photo = _rotated_display_image(entry)
        widgets = self.row_widgets[i]
        widgets["thumb"].config(image=photo)
        widgets["thumb"].image = photo

    def remove_selected(self):
        i = self.selected_index
        if i is None:
            return
        del self.entries[i]
        self.selected_index = None
        self._render_rows()
        self._set_controls_enabled(False)
        if not self.entries:
            self.convert_btn.config(state="disabled")

    # -- Conversion ------------------------------------------------------

    def convert(self):
        if not self.entries:
            return

        base = os.path.splitext(os.path.basename(self.zip_path))[0]
        out_path = filedialog.asksaveasfilename(
            title="Save PDF as",
            defaultextension=".pdf",
            initialfile=base + ".pdf",
            filetypes=[("PDF documents", "*.pdf"), ("All files", "*.*")],
        )
        if not out_path:
            return

        self.convert_btn.config(state="disabled")
        self.progress.config(value=0, maximum=len(self.entries) or 1)
        self.status_var.set("Converting...")

        entries_snapshot = list(self.entries)
        thread = threading.Thread(
            target=self._convert_worker, args=(entries_snapshot, out_path), daemon=True
        )
        thread.start()
        self.after(50, self._poll_convert_progress, out_path)

    def _convert_worker(self, entries, out_path):
        def progress_cb(idx, total, name):
            self._progress_queue.put(("progress", idx, total, name))

        try:
            page_count, skipped = build_pdf_from_entries(entries, out_path, progress_cb)
            self._progress_queue.put(("done", page_count, skipped, None))
        except Exception as e:
            self._progress_queue.put(("error", None, None, str(e)))

    def _poll_convert_progress(self, out_path):
        try:
            while True:
                kind, a, b, c = self._progress_queue.get_nowait()
                if kind == "progress":
                    idx, total, name = a, b, c
                    self.progress.config(value=idx + 1, maximum=max(total, 1))
                    self.status_var.set(f"Processing {name} ({idx + 1}/{total})...")
                elif kind == "done":
                    page_count, skipped = a, b
                    self.convert_btn.config(state="normal")
                    msg = f"Saved {page_count}-page PDF to:\n{out_path}"
                    if skipped:
                        skip_lines = "\n".join(f"- {n}: {r}" for n, r in skipped)
                        msg += f"\n\nSkipped {len(skipped)} file(s):\n{skip_lines}"
                    self.status_var.set(f"Done: {page_count} page(s), {len(skipped)} skipped.")
                    messagebox.showinfo("Conversion complete", msg)
                    return
                elif kind == "error":
                    self.convert_btn.config(state="normal")
                    self.status_var.set("Conversion failed.")
                    messagebox.showerror("Error", f"Could not convert ZIP to PDF:\n{c}")
                    return
        except queue.Empty:
            pass
        self.after(50, self._poll_convert_progress, out_path)
