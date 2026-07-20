"""ZIP to PDF — standalone app.

This is the zip-to-pdf branch: a single-tool build of the Energuy
R-Team Tools suite. See the exif-watermarker and master branches for
the other tool and the combined multi-tool app, respectively.
"""
import tkinter as tk

from tools.zip_to_pdf import ZipToPdfFrame


def main():
    root = tk.Tk()
    root.title("ZIP to PDF")
    root.geometry("640x680")
    frame = ZipToPdfFrame(root)
    frame.pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()
