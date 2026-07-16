"""GUI tool to edit EXIF geotag/date-taken fields and to burn the geotag
into the photo as a visible watermark.
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from fractions import Fraction

import piexif
from PIL import Image, ImageDraw, ImageFont, ImageTk

PREVIEW_MAX = 480
DATE_FORMAT_HINT = "YYYY:MM:DD HH:MM:SS  (e.g. 2026:07:16 14:30:00)"


def dms_to_decimal(dms, ref):
    deg, minute, sec = dms
    value = deg[0] / deg[1] + (minute[0] / minute[1]) / 60 + (sec[0] / sec[1]) / 3600
    if ref in ("S", "W"):
        value = -value
    return value


def decimal_to_dms(value):
    value = abs(value)
    deg = int(value)
    minute_float = (value - deg) * 60
    minute = int(minute_float)
    sec_float = (minute_float - minute) * 3600
    sec = Fraction(sec_float).limit_denominator(1000)
    return (
        (deg, 1),
        (minute, 1),
        (sec.numerator, sec.denominator),
    )


class ExifWatermarkApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EXIF Geotag / Date Editor & Watermarker")
        self.image_path = None
        self.preview_image = None  # keep reference

        self._build_ui()

    def _build_ui(self):
        frm = ttk.Frame(self.root, padding=10)
        frm.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)

        # File picker
        ttk.Button(frm, text="Open Photo...", command=self.open_photo).grid(
            row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8)
        )
        self.path_label = ttk.Label(frm, text="No file loaded", foreground="gray")
        self.path_label.grid(row=1, column=0, columnspan=2, sticky="w")

        # Preview
        self.preview_label = ttk.Label(frm)
        self.preview_label.grid(row=2, column=0, columnspan=2, pady=10)

        # Date taken
        ttk.Label(frm, text="Date Taken:").grid(row=3, column=0, sticky="w")
        self.date_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.date_var, width=30).grid(row=3, column=1, sticky="w")
        ttk.Label(frm, text=DATE_FORMAT_HINT, foreground="gray", font=("Segoe UI", 8)).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        # Latitude / Longitude
        ttk.Label(frm, text="Latitude:").grid(row=5, column=0, sticky="w")
        self.lat_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.lat_var, width=30).grid(row=5, column=1, sticky="w")

        ttk.Label(frm, text="Longitude:").grid(row=6, column=0, sticky="w")
        self.lon_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.lon_var, width=30).grid(row=6, column=1, sticky="w")
        ttk.Label(
            frm,
            text="Decimal degrees, e.g. 39.7392, -104.9903 (negative = S / W)",
            foreground="gray",
            font=("Segoe UI", 8),
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # Watermark options
        ttk.Separator(frm).grid(row=8, column=0, columnspan=2, sticky="ew", pady=8)
        ttk.Label(frm, text="Watermark text (blank = auto from lat/lon):").grid(
            row=9, column=0, columnspan=2, sticky="w"
        )
        self.watermark_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.watermark_var, width=45).grid(
            row=10, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        # Actions
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(btn_frame, text="Save EXIF Changes", command=self.save_exif).pack(
            side="left", expand=True, fill="x", padx=(0, 4)
        )
        ttk.Button(
            btn_frame, text="Save EXIF + Watermark As...", command=self.save_with_watermark
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(frm, textvariable=self.status_var, foreground="gray").grid(
            row=12, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

    def open_photo(self):
        path = filedialog.askopenfilename(
            title="Select a photo",
            filetypes=[("JPEG images", "*.jpg *.jpeg"), ("All files", "*.*")],
        )
        if not path:
            return
        self.image_path = path
        self.path_label.config(text=path)
        self._load_preview(path)
        self._load_exif_fields(path)
        self.status_var.set("Loaded.")

    def _load_preview(self, path):
        img = Image.open(path)
        img.thumbnail((PREVIEW_MAX, PREVIEW_MAX))
        self.preview_image = ImageTk.PhotoImage(img)
        self.preview_label.config(image=self.preview_image)

    def _load_exif_fields(self, path):
        self.date_var.set("")
        self.lat_var.set("")
        self.lon_var.set("")
        try:
            exif_dict = piexif.load(path)
        except Exception:
            return

        exif_ifd = exif_dict.get("Exif", {})
        date_bytes = exif_ifd.get(piexif.ExifIFD.DateTimeOriginal)
        if date_bytes:
            self.date_var.set(date_bytes.decode("ascii", errors="ignore"))

        gps_ifd = exif_dict.get("GPS", {})
        lat = gps_ifd.get(piexif.GPSIFD.GPSLatitude)
        lat_ref = gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef)
        lon = gps_ifd.get(piexif.GPSIFD.GPSLongitude)
        lon_ref = gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef)
        if lat and lat_ref:
            self.lat_var.set(f"{dms_to_decimal(lat, lat_ref.decode()):.6f}")
        if lon and lon_ref:
            self.lon_var.set(f"{dms_to_decimal(lon, lon_ref.decode()):.6f}")

    def _read_fields(self):
        """Validate and return (date_str, lat, lon). lat/lon may be None."""
        date_str = self.date_var.get().strip()
        if date_str:
            try:
                parts = date_str.replace("-", ":").split(" ")
                if len(parts) != 2 or len(parts[0].split(":")) != 3:
                    raise ValueError
            except Exception:
                raise ValueError(f"Date must look like: {DATE_FORMAT_HINT}")

        lat_str = self.lat_var.get().strip()
        lon_str = self.lon_var.get().strip()
        lat = lon = None
        if lat_str or lon_str:
            try:
                lat = float(lat_str)
                lon = float(lon_str)
            except ValueError:
                raise ValueError("Latitude/Longitude must both be decimal numbers.")
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("Latitude must be -90..90 and Longitude -180..180.")

        return date_str, lat, lon

    def _build_exif_bytes(self, existing_path, date_str, lat, lon):
        try:
            exif_dict = piexif.load(existing_path)
        except Exception:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        if date_str:
            date_bytes = date_str.encode("ascii")
            exif_dict.setdefault("Exif", {})[piexif.ExifIFD.DateTimeOriginal] = date_bytes
            exif_dict.setdefault("Exif", {})[piexif.ExifIFD.DateTimeDigitized] = date_bytes
            exif_dict.setdefault("0th", {})[piexif.ImageIFD.DateTime] = date_bytes

        if lat is not None and lon is not None:
            gps_ifd = {
                piexif.GPSIFD.GPSLatitudeRef: "N" if lat >= 0 else "S",
                piexif.GPSIFD.GPSLatitude: decimal_to_dms(lat),
                piexif.GPSIFD.GPSLongitudeRef: "E" if lon >= 0 else "W",
                piexif.GPSIFD.GPSLongitude: decimal_to_dms(lon),
            }
            exif_dict["GPS"] = gps_ifd

        return piexif.dump(exif_dict)

    def save_exif(self):
        if not self.image_path:
            messagebox.showwarning("No photo", "Open a photo first.")
            return
        try:
            date_str, lat, lon = self._read_fields()
            exif_bytes = self._build_exif_bytes(self.image_path, date_str, lat, lon)
            piexif.insert(exif_bytes, self.image_path)
            self.status_var.set("EXIF data saved.")
            messagebox.showinfo("Saved", "EXIF data updated successfully.")
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
        except Exception as e:
            messagebox.showerror("Error", f"Could not save EXIF data:\n{e}")

    def _watermark_text(self, lat, lon):
        custom = self.watermark_var.get().strip()
        if custom:
            return custom
        if lat is not None and lon is not None:
            lat_ref = "N" if lat >= 0 else "S"
            lon_ref = "E" if lon >= 0 else "W"
            return f"{abs(lat):.5f}°{lat_ref}, {abs(lon):.5f}°{lon_ref}"
        return ""

    def _apply_watermark(self, img, text):
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)
        font_size = max(18, img.width // 40)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

        margin = font_size // 2
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = img.width - text_w - margin * 2
        y = img.height - text_h - margin * 2

        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        pad = 8
        odraw.rectangle(
            [x - pad, y - pad, x + text_w + pad, y + text_h + pad],
            fill=(0, 0, 0, 140),
        )
        odraw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        return img

    def save_with_watermark(self):
        if not self.image_path:
            messagebox.showwarning("No photo", "Open a photo first.")
            return
        try:
            date_str, lat, lon = self._read_fields()
        except ValueError as e:
            messagebox.showerror("Invalid input", str(e))
            return

        text = self._watermark_text(lat, lon)
        if not text:
            messagebox.showwarning(
                "No geotag", "Enter latitude/longitude or custom watermark text first."
            )
            return

        base, ext = os.path.splitext(self.image_path)
        default_name = os.path.basename(base) + "_watermarked" + (ext or ".jpg")
        out_path = filedialog.asksaveasfilename(
            title="Save watermarked photo as",
            defaultextension=ext or ".jpg",
            initialfile=default_name,
            filetypes=[("JPEG images", "*.jpg *.jpeg"), ("All files", "*.*")],
        )
        if not out_path:
            return

        try:
            exif_bytes = self._build_exif_bytes(self.image_path, date_str, lat, lon)
            img = Image.open(self.image_path)
            watermarked = self._apply_watermark(img, text)
            watermarked.save(out_path, exif=exif_bytes, quality=95)
            self.status_var.set(f"Saved watermarked photo to {out_path}")
            messagebox.showinfo("Saved", f"Watermarked photo saved:\n{out_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save watermarked photo:\n{e}")


def main():
    root = tk.Tk()
    ExifWatermarkApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
