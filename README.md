# ZIP to PDF

A small Tkinter GUI app that converts a ZIP archive into a single PDF,
with one page per file inside it:

- Files load with a thumbnail preview (rendered from the actual image or
  the first page of embedded PDFs) and are ordered naturally by filename
  (e.g. `page2` before `page10`) to start
- Select an item in the list to **Move Up**/**Move Down** (reorder),
  **Rotate 90°** (repeatable, up to 270°), or **Remove** it before export
- Existing PDF documents (single or multi-page) have their pages copied in
- Images of any format/size/orientation that Pillow can open are each
  converted into a page (EXIF orientation is respected, multi-frame
  formats like animated GIF or multi-page TIFF become multiple pages)
- Hidden files, folders, and macOS `__MACOSX` metadata are ignored
- Unsupported files show up in the preview flagged as such, and are
  skipped (and listed in a summary) if left in when you convert

This is the `zip-to-pdf` branch: a standalone single-tool build. The
`master` branch has this tool plus an EXIF geotag/watermarker tool behind
a tool-picker pane; the `exif-watermarker` branch has that other tool
standalone.

## Setup

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```
python main.py
```

## Building a standalone .exe

```
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "ZipToPdf" main.py
```

The output is `dist\ZipToPdf.exe` — a single file with no console window
that runs without a Python install. Rebuild it after any code change.

## Notes

- PDF page thumbnails need `pymupdf`; if it's missing, PDFs still convert
  fine but show a generic "PDF" placeholder in the preview instead of a
  rendered thumbnail.
