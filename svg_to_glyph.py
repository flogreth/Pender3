import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk

CANVAS_WIDTH = 700
CANVAS_HEIGHT = 700

class LineDrawer:
    def __init__(self, root):
        self.root = root
        self.root.title("Linien Zeichnen mit Bild-Hintergrund")

        # Buttons
        self.button_frame = tk.Frame(root)
        self.button_frame.pack(pady=5)
        self.load_button = tk.Button(self.button_frame, text="Bild laden", command=self.load_image_dialog)
        self.load_button.pack()

        # Zeichenfläche
        self.canvas = tk.Canvas(root, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg="white")
        self.canvas.pack()

        self.bg_image = None
        self.bg_image_obj = None  # Referenz zum Canvas-Objekt
        self.current_line = []
        self.lines = []

        self.canvas.bind("<Button-1>", self.left_click)
        self.canvas.bind("<Button-3>", self.right_click)

    def load_image_dialog(self):
        filetypes = [("Bilddateien", "*.png *.jpg *.jpeg *.bmp"), ("Alle Dateien", "*.*")]
        filepath = filedialog.askopenfilename(title="Bild auswählen", filetypes=filetypes)
        if filepath:
            self.load_background(filepath)

    def load_background(self, path):
        img = Image.open(path)
        img = img.resize((CANVAS_WIDTH, CANVAS_HEIGHT))
        self.bg_image = ImageTk.PhotoImage(img)
        if self.bg_image_obj:
            self.canvas.delete(self.bg_image_obj)
        self.bg_image_obj = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.bg_image)
        self.canvas.tag_lower(self.bg_image_obj)  # Hintergrund nach unten

    def left_click(self, event):
        x, y = event.x, event.y
        if self.current_line:
            x0, y0 = self.current_line[-1]
            self.canvas.create_line(x0, y0, x, y, fill="red", width=3)
        self.current_line.append((x, y))

    def right_click(self, event):
        if self.current_line:
            self.lines.append(self.current_line)
            self.current_line = []
            print("Linie abgeschlossen.")
            self.print_svg_combined_path()

    def print_svg_combined_path(self):
        if not self.lines:
            print("Keine Linien vorhanden.")
            return

        path = ""
        for line in self.lines:
            if not line:
                continue
            x0, y0 = line[0]
            path += f'M {x0} {CANVAS_HEIGHT - y0} '
            for x, y in line[1:]:
                path += f'L {x} {CANVAS_HEIGHT - y} '
        glyph_str = f'<glyph unicode="R" glyph-name="R" horiz-adv-x="{CANVAS_WIDTH}" d="{path.strip()}" />'
        print("\nKombinierter Glyph-Pfad (Y gespiegelt):")
        print(glyph_str)

if __name__ == "__main__":
    root = tk.Tk()
    app = LineDrawer(root)
    root.mainloop()
