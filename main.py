"""Energuy R-Team Tools: a small suite of GUI utilities, switchable from a
navigation pane on the left.
"""
import tkinter as tk
from tkinter import ttk

from tools.exif_watermarker import ExifWatermarkerFrame
from tools.exif_watermarker import TOOL_NAME as EXIF_TOOL_NAME
from tools.zip_to_pdf import ZipToPdfFrame
from tools.zip_to_pdf import TOOL_NAME as ZIP_TOOL_NAME

TOOLS = [
    (EXIF_TOOL_NAME, ExifWatermarkerFrame),
    (ZIP_TOOL_NAME, ZipToPdfFrame),
]


class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Energuy R-Team Tools")
        self.root.geometry("820x640")

        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.nav_list = tk.Listbox(root, width=24, exportselection=False)
        self.nav_list.grid(row=0, column=0, sticky="ns")
        self.nav_list.bind("<<ListboxSelect>>", self._on_select)

        self.content = ttk.Frame(root)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.frames = {}
        for name, frame_cls in TOOLS:
            self.nav_list.insert(tk.END, name)
            frame = frame_cls(self.content)
            frame.grid(row=0, column=0, sticky="nsew")
            self.frames[name] = frame

        self.nav_list.selection_set(0)
        self._show(TOOLS[0][0])

    def _on_select(self, event):
        selection = self.nav_list.curselection()
        if not selection:
            return
        name = self.nav_list.get(selection[0])
        self._show(name)

    def _show(self, name):
        self.frames[name].tkraise()


def main():
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
