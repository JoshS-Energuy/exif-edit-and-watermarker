# EXIF Geotag / Date Editor & Watermarker

A small Tkinter GUI app for JPEG photos that lets you:

- View and edit the **Date Taken** (`DateTimeOriginal`) EXIF field
- View and edit the **GPS geotag** (latitude/longitude) EXIF fields
- Save those EXIF changes back to the original file
- Burn the geotag (or custom text) onto the photo itself as a visible
  watermark and save the result as a new file

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

## Usage

1. **Open Photo...** to load a JPEG. Existing date/GPS EXIF values (if any)
   are pre-filled.
2. Edit **Date Taken** as `YYYY:MM:DD HH:MM:SS` and/or **Latitude**/
   **Longitude** as decimal degrees (negative = South / West).
3. **Save EXIF Changes** writes the fields back into the original file
   in place.
4. **Save EXIF + Watermark As...** writes the EXIF fields into a copy and
   stamps the geotag (or your custom text in the watermark box) onto the
   bottom-right corner of the image, then prompts for a save location.

## Building a standalone .exe

```
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "ExifWatermarker" main.py
```

The output is `dist\ExifWatermarker.exe` — a single file with no console
window that runs without a Python install. Rebuild it after any code change.

## Notes

- Only JPEG files are supported for EXIF read/write (the `piexif` library
  requirement). PNG/other formats can still be watermarked but won't carry
  EXIF metadata.
- The watermark font falls back to Pillow's built-in default font if
  `arial.ttf` isn't available on the system.
