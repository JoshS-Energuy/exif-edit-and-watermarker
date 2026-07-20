# Energuy R-Team Tools

A small Tkinter GUI suite. Pick a tool from the pane on the left:

## EXIF Geotag / Watermarker

For JPEG photos:

- View and edit the **Date Taken** (`DateTimeOriginal`) EXIF field
- View and edit the **GPS geotag** (latitude/longitude) EXIF fields
- Save those EXIF changes back to the original file
- Burn the geotag (or custom text) onto the photo itself as a visible
  watermark and save the result as a new file

## ZIP to PDF

Converts a ZIP archive into a single PDF, with one page per file inside it:

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
pyinstaller --noconfirm --onefile --windowed --name "EnerguyRTeamTools" main.py
```

The output is `dist\EnerguyRTeamTools.exe` — a single file with no console
window that runs without a Python install. Rebuild it after any code change.

## Notes

- Only JPEG files are supported for EXIF read/write (the `piexif` library
  requirement). PNG/other formats can still be watermarked but won't carry
  EXIF metadata.
- The watermark font falls back to Pillow's built-in default font if
  `arial.ttf` isn't available on the system.
- PDF page thumbnails need `pymupdf` (in `requirements.txt`); if it's
  missing, PDFs still convert fine but show a generic "PDF" placeholder
  in the preview instead of a rendered thumbnail.
