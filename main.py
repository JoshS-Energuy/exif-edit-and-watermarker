"""EXIF Geotag / Date Editor & Watermarker — standalone app.

This is the exif-watermarker branch: a single-tool build of the
Energuy R-Team Tools suite. See the zip-to-pdf and master branches for
the other tool and the combined multi-tool app, respectively.
"""
import tkinter as tk

from tools.exif_watermarker import ExifWatermarkerFrame


def main():
    root = tk.Tk()
    root.title("EXIF Geotag / Date Editor & Watermarker")
    root.geometry("560x640")
    frame = ExifWatermarkerFrame(root)
    frame.pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
