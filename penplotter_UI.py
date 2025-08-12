import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import xml.etree.ElementTree as ET
import re
import time
import serial
import keyboard
from svgpathtools import svg2paths
from svg.path import parse_path as svg_parse_path
from svg.path.path import Move, Line, CubicBezier, QuadraticBezier, Close

from pathlib import Path
import serial.tools.list_ports


SVG_NS = "{http://www.w3.org/2000/svg}"

screen_size_x = 1920
screen_size_y = 1080

print_area = [25, 25, 240, 180]
neutralposition = 160
connection_status = ""
connection_color = "red"


try:
    ser = serial.Serial('COM4', 115200, timeout=1)
    time.sleep(2)
except Exception as e:
    ser=""
    connection_status = e
    print(f"Fehler: {e}")




def parse_path_image(d):
    path_obj = svg_parse_path(d)
    parsed = []

    for segment in path_obj:
        if isinstance(segment, Move):
            cmd = 'M'
        elif isinstance(segment, Line):
            cmd = 'L'
        elif isinstance(segment, CubicBezier):
            cmd = 'C'
        elif isinstance(segment, QuadraticBezier):
            cmd = 'Q'
        elif isinstance(segment, Close):
            cmd = 'Z'
        else:
            cmd = '?'

        parsed.append((cmd, segment))
    
    return parsed

def parse_path(d):
    tokens = re.findall(r'[ML]\s*[\d\.\-]+\s+[\d\.\-]+', d)
    path = []
    for token in tokens:
        cmd, *coords = token.split()
        x, y = map(float, coords)
        path.append((cmd, x, y))
    return path

def send_commands(commands):
    if isinstance(commands, str):
        commands = [commands]
    for cmd in commands:
        print("CMD:", cmd)
        ser.write(f'{cmd}\n'.encode())
        while True:
            response = ser.readline().decode().strip()
            print(f"Empfangen: {response}")
            time.sleep(0.1)
            if response == 'ok':
                break

def px_to_mm(x_px, y_px):
    scale_x = (print_area[2] - print_area[0]) / ((screen_size_x - 50) - 50)
    scale_y = (print_area[1] - print_area[3]) / ((screen_size_y - 50) - 50)
    offset_x = print_area[0] - scale_x * 50
    offset_y = print_area[3] - scale_y * 50
    x_mm = x_px * scale_x + offset_x
    y_mm = y_px * scale_y + offset_y
    return x_mm, y_mm



class SVGFontApp:
    def __init__(self, root):
        self.root = root
        self.show_help = 1
        self.abort = 0
         
        self.canvas = tk.Canvas(root, bg='black')
        self.canvas.pack(fill='both', expand=True)

        

        # MOUSE
        self.dragging = False
        self.drag_start = None
        self.canvas.bind("<Button-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        # Dropdown (Combobox)
        self.com_var = tk.StringVar()
        self.com_dropdown = ttk.Combobox(root, textvariable=self.com_var, state="readonly")
        self.com_dropdown.place(x=70, y=70, width=120)
        self.com_dropdown.bind("<<ComboboxSelected>>", self.reconnect_com)

        # Button zum Aktualisieren
        refresh_button = ttk.Button(root, text="Refresh", command=self.refresh_ports)
        refresh_button.place(x=200, y=70, width=120)


        # Text Object Button
        btn = tk.Button(root, text="Neues Textobjekt", command=self.add_text_object)
        btn.place(x=420, y=70, width=120)

        # LOAD SVG BUTTON
        btn2 = tk.Button(root, text="Tinkertank Logo", command=self.load_svg_object)
        btn2.place(x=570, y=70, width=120)

        # Help Button
        btn = tk.Button(root, text="Hilfe", command=self.hide_show_help)
        btn.place(x=720, y=70, width=120)

        self.text_bboxes = []
        self.calibration_mode = False
        self.text_objects = [{
            "type": "text",
            "text": "TINKERTANK",
            "font": 23,
            "offset_x": 120,
            "offset_y": 400,
            "scale": 0.1,
            "scale_y": 1
        }]
        self.number_textobjects = 0

        fonts_dir = Path(__file__).parent / "fonts"
        self.svg_fonts = [str(p) for p in fonts_dir.iterdir() if p.is_file() and p.suffix == ".svg"]
        self.svg_font_index = 0
        #print(self.svg_fonts)



        # Drag & Skalierung Flags
        self.dragging = False
        self.scaling = False
        self.drag_start = None
        self.current_index = 0
        self.text_bboxes = []

        self.calib_scale_x = 1.0
        self.calib_scale_y = 1.0
        self.calib_offset_x = 0
        self.calib_offset_y = 0

        self.canvas.bind_all("<Key>", self.on_key)
        self.render()

    def reconnect_com(self, event):
        global ser, connection_status, connection_color
        try:
            time.sleep(0.2)
            ser = serial.Serial(self.com_var.get(), 115200, timeout=1)
            time.sleep(0.3)
            connection_status = "connected to " + self.com_var.get()
            connection_color = "lime"
        except Exception as e:
            connection_status = e
            connection_color = "red"
            print(f"Fehler: {e}")
        self.render()

    def hide_show_help(self):
        self.show_help = 1-self.show_help
        self.render()

    def get_com_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def refresh_ports(self):
        ports = self.get_com_ports()
        self.com_dropdown['values'] = ports  # Neue Liste eintragen
        if ports:
            self.com_var.set(ports[0])  # Ersten Port automatisch auswählen
        else:
            self.com_var.set('')  # Kein Port gefunden, leeren
        try:
            ser.close()
        except: pass
        self.reconnect_com(ports[0])

    def load_glyphs_from_svg_font(self,file_path):
        tree = ET.parse(file_path)
        root = tree.getroot()
        glyphs = {}
        for glyph in root.iter():
            if glyph.tag.endswith('glyph'):
                unicode_char = glyph.attrib.get('unicode')
                horiz_adv_x = float(glyph.attrib.get('horiz-adv-x', 1000))
                d = glyph.attrib.get('d')
                if unicode_char and d:
                    glyphs[unicode_char] = {
                        "horiz-adv-x": horiz_adv_x,
                        "d": d
                    }
        return glyphs

    def on_mouse_down(self, event):
        x, y = event.x, event.y
        self.current_index = 100
        for i, bbox in enumerate(self.text_bboxes):
            min_x, min_y, max_x, max_y = bbox

            if max_x -3 <= x <= max_x+17 and min_y - 17 <= y <= min_y+3:
                self.current_index = i
                self.scaling = True
                self.dragging = False
                self.drag_start = (x, y)
            if min_x <= x <= max_x and min_y <= y <= max_y:
                self.current_index = i
                self.scaling = False
                self.dragging = True
                self.drag_start = (x, y)
                # Prüfen ob Klick in der rechten unteren Ecke ist (Skalier-Zone)

                
        self.render()

    def on_mouse_drag(self, event):
        if self.dragging and 0 <= self.current_index < len(self.text_objects):
            dx = event.x - self.drag_start[0]
            dy = event.y - self.drag_start[1]
            self.text_objects[self.current_index]["offset_x"] += dx
            self.text_objects[self.current_index]["offset_y"] += dy
            self.drag_start = (event.x, event.y)
        elif self.scaling:
            dx = event.x - self.drag_start[0]
            scale_factor = 1 + dx / 200.0
            self.text_objects[self.current_index]["scale"] *= scale_factor
            self.drag_start = (event.x, event.y)
        self.number_textobjects = self.current_index
        self.render()

    def on_mouse_up(self, event):
        self.dragging = False
        self.scaling = False
        self.number_textobjects = self.current_index
        self.render()

    def add_text_object(self):
        self.text_objects.append({
            "type": "text",
            "text": "Text",
            "font": 23,
            "offset_x": 100,
            "offset_y": 100 + len(self.text_objects) * 100,
            "scale": 0.1,
            "scale_y": 1,
        })
        self.number_textobjects = len(self.text_objects) - 1
        self.render()

    def load_svg_object(self):
        self.text_objects.append({
            "type": "text",
            "text": "A",
            "font": 40,
            "offset_x": 500,
            "offset_y": 500,
            "scale": 0.5,
            "scale_y": 1,
        })
        self.number_textobjects = len(self.text_objects) - 1
        self.render()

    def write_with_pen(self):


        if ser != "":
            for i, obj in enumerate(self.text_objects):
            
                x_cursor = obj["offset_x"]

                self.glyphs = self.load_glyphs_from_svg_font(self.svg_fonts[self.text_objects[i]["font"]])

                for char in obj["text"]:
                    print("char: ", char)
                    if self.abort == 1:
                        print("DRUCK WIRD ABGEBROCHEN")
                        self.abort = 0
                        break
                    if char == " ":
                        x_cursor += 300 * obj["scale"]
                    else:
                        glyph = self.glyphs.get(char)
                        if glyph:
                            path = parse_path(glyph["d"])
                            last_pos = None
                            for cmd, x, y in path:
                                sx, sy = px_to_mm((x_cursor + x * obj["scale"]), (obj["offset_y"] - y * obj["scale"] * obj["scale_y"]))
                                if cmd == "M":
                                    gcode_lines = [
                                        'G1 Z8 F22000',
                                        f'G0 X{sx:.2f} Y{sy:.2f} F4000'
                                    ]
                                elif cmd == "L" and last_pos:
                                    gcode_lines = [
                                        'G1 Z1 F22000',
                                        f'G1 X{sx:.2f} Y{sy:.2f} F4000'
                                    ]
                                else:
                                    gcode_lines = []
                                send_commands(gcode_lines)
                                last_pos = (sx, sy)
                                
                            x_cursor += glyph["horiz-adv-x"] * obj["scale"]
                send_commands([
                    'G0 Z15',
                    f'G0 X0 Y{neutralposition} Z20'
                ])
            print("G-Code erfolgreich gesendet.")

    def render(self):
        global connection_color, connection_status

        self.canvas.delete("all")
        if self.calibration_mode == True:
            rendercolor = "red"
            self.canvas.create_text(screen_size_x/2, (screen_size_y - 50)*self.calib_scale_y + self.calib_offset_y  , text="CALIBRATION MODE", font=("Arial", 100), fill="dark red", anchor="s")
        else:
            rendercolor = "white"

        self.canvas.create_text(70,110,text=f"{connection_status}\n" ,font=("Arial", 12), fill= connection_color, anchor="nw")

        # HELP TEXT
        if self.show_help:
            self.canvas.create_text(720,110,
                text=f"Pfeiltasten : \tVerschieben \n"
                "Shift+Pfeiltasten : \tSkalieren \n"
                "Strg+H : \t\tAuto Home\n"
                "Strg+K : \t\tCalibration Mode\n"
                "Bild↑ / Bild↓ : \tSchriftart wählen", font=("Arial", 12), fill=rendercolor, anchor="nw")

        coords = [
            50 * self.calib_scale_x + self.calib_offset_x,
            50 * self.calib_scale_y + self.calib_offset_y,
            (screen_size_x - 50) * self.calib_scale_x + self.calib_offset_x,
            (screen_size_y - 50) * self.calib_scale_y + self.calib_offset_y
        ]
        self.canvas.create_rectangle(coords[0], coords[1], coords[2], coords[3], outline=rendercolor, width=10)

        self.text_bboxes = []

        for i, obj in enumerate(self.text_objects):
            min_x = float('inf')
            min_y = float('inf')
            max_x = float('-inf')
            max_y = float('-inf')
            if obj["type"] == "text":
                # ==== TEXT RENDERING CODE ====
                x_cursor = obj["offset_x"]
                self.glyphs = self.load_glyphs_from_svg_font(self.svg_fonts[self.text_objects[i]["font"]])
                for char in obj["text"]:
                    glyph = self.glyphs.get(char)
                    if glyph:
                        path = parse_path(glyph["d"])
                        last_pos = None
                        for cmd, x, y in path:
                            sx = ((x_cursor + x * obj["scale"]) * self.calib_scale_x) + self.calib_offset_x
                            sy = ((obj["offset_y"] - y * obj["scale"] * obj["scale_y"]) * self.calib_scale_y) + self.calib_offset_y

                            min_x = min(min_x, sx)
                            min_y = min(min_y, sy)
                            max_x = max(max_x, sx)
                            max_y = max(max_y, sy)

                            if cmd == "M":
                                last_pos = (sx, sy)
                            elif cmd == "L" and last_pos:
                                self.canvas.create_line(last_pos[0], last_pos[1], sx, sy, width=5, fill=rendercolor)
                                last_pos = (sx, sy)
                        x_cursor += glyph["horiz-adv-x"] * obj["scale"]
                    elif char == " ":
                        x_cursor += 300 * obj["scale"]

                self.text_bboxes.append((min_x, min_y, max_x, max_y))

            elif obj["type"] == "image":
                for path_d in obj["paths"]:
                    path = parse_path_image(path_d)
                    last_pos = None
                    for cmd, segment in path:
                        if cmd == 'M':
                            x, y = segment.end.real, segment.end.imag
                            sx = ((obj["offset_x"] + x * obj["scale"]) * self.calib_scale_x) + self.calib_offset_x
                            sy = ((obj["offset_y"] - y * obj["scale"] * obj["scale_y"]) * self.calib_scale_y) + self.calib_offset_y
                            last_pos = (sx, sy)
                        elif cmd == 'L' and last_pos:
                            x, y = segment.end.real, segment.end.imag
                            sx = ((obj["offset_x"] + x * obj["scale"]) * self.calib_scale_x) + self.calib_offset_x
                            sy = ((obj["offset_y"] - y * obj["scale"] * obj["scale_y"]) * self.calib_scale_y) + self.calib_offset_y
                            self.canvas.create_line(last_pos[0], last_pos[1], sx, sy, fill=rendercolor, width=2)
                            last_pos = (sx, sy)
                        min_x = min(min_x, sx)
                        min_y = min(min_y, sy)
                        max_x = max(max_x, sx)
                        max_y = max(max_y, sy)
                self.text_bboxes.append((min_x, min_y, max_x, max_y))

            ####BOUNDING BOXES and INFO
            if i == self.number_textobjects:
                self.canvas.create_rectangle(min_x-10, min_y-10, max_x+10, max_y+10, outline="yellow", width=2, dash=(2, 2))
                self.canvas.create_rectangle(max_x+3, min_y-3, max_x+17, min_y-17, fill="yellow", width=0)
                self.canvas.create_text(max_x+10, max_y+10, text=str(self.text_objects[i]["font"])+": "+ self.svg_fonts[self.text_objects[i]["font"]] , font=("Arial", 12), fill="yellow", anchor="ne") # show font


    def on_key(self, event):
        print("textobjects:", self.number_textobjects)
        obj = self.text_objects[self.number_textobjects]

        if (event.state & 0x0004) and event.keysym.lower() == "h":
            self.start_homing(1)
        if (event.state & 0x0004) and event.keysym.lower() == "r":
            self.drive_rect()
        if (event.state & 0x0004) and event.keysym.lower() == "k":
            self.calibration_mode = not self.calibration_mode
            self.render()
        
        if event.keysym == "Escape":
            self.abort = 1

        if not self.calibration_mode:
            if event.keysym in ["Left", "Right", "Up", "Down"]:
                if event.state & 0x0001:
                    if event.keysym == "Left":
                        obj["scale"] /= 1.03
                    elif event.keysym == "Right":
                        obj["scale"] *= 1.03
                    if event.keysym == "Up":
                        obj["scale_y"] *= 1.05
                    elif event.keysym == "Down":
                        obj["scale_y"] /= 1.05
                else:
                    if event.keysym == "Left":
                        obj["offset_x"] -= 10
                    elif event.keysym == "Right":
                        obj["offset_x"] += 10
                    elif event.keysym == "Up":
                        obj["offset_y"] -= 10
                    elif event.keysym == "Down":
                        obj["offset_y"] += 10
                self.render()
        else:
            if event.keysym in ["Left", "Right", "Up", "Down"]:
                if event.state & 0x0001:
                    if event.keysym == "Left":
                        self.calib_scale_x /= 1.01
                    elif event.keysym == "Right":
                        self.calib_scale_x *= 1.01
                    elif event.keysym == "Up":
                        self.calib_scale_y /= 1.01
                    elif event.keysym == "Down":
                        self.calib_scale_y *= 1.01
                else:
                    if event.keysym == "Left":
                        self.calib_offset_x -= 2
                    elif event.keysym == "Right":
                        self.calib_offset_x += 2
                    elif event.keysym == "Up":
                        self.calib_offset_y -= 2
                    elif event.keysym == "Down":
                        self.calib_offset_y += 2
                self.render()
        

        if len(event.char) == 1 and (event.char in self.glyphs or event.char == " "):
            obj["text"] += event.char
            self.render()
        elif event.keysym == "BackSpace":
            obj["text"] = obj["text"][:-1]
            self.render()
        elif event.keysym == "Return":
            print("stift gepitzt und los gehts...")
            #self.start_homing(0)
            self.write_with_pen()
        elif event.keysym == "Delete":
            if 0 <= self.number_textobjects < len(self.text_objects):
                del self.text_objects[self.number_textobjects]
                self.number_textobjects = max(0, self.number_textobjects - 1)
                self.render()
        elif event.keysym == "Prior":  # Page Up
            self.text_objects[self.current_index]["font"] = ( self.text_objects[self.current_index]["font"] +1 ) % len(self.svg_fonts)
            self.render()

        elif event.keysym == "Next":  # Page Down
            self.text_objects[self.current_index]["font"] = ( self.text_objects[self.current_index]["font"] -1 ) % len(self.svg_fonts)
            self.render()

    def start_homing(self, drive_to_neutralpos):
        homing_commands = [
            'G0 Z20',
            'M203',
            'G28 XY',
            'G0 X25 Y20',
            'G92 Z100',
            'G28 Z',
            'G0 Z10',
            f'G0 X25 Y{neutralposition*drive_to_neutralpos}',
        ]
        send_commands(homing_commands)

    def drive_rect(self):
        calib_commands = [
            f'G0 X{print_area[0]} Y{print_area[1]}',
            f'G0 X{print_area[2]} Y{print_area[1]}',
            f'G0 X{print_area[2]} Y{print_area[3]}',
            f'G0 X{print_area[0]} Y{print_area[3]}'
        ]
        send_commands(calib_commands)
        send_commands(f'G0 X0 Y{neutralposition}')
    
        time.sleep(2)
        self.reconnect_com()
        

if __name__ == "__main__":
    
    root = tk.Tk()
    root.title("TINKERTANK PEN PLOTTER")
    root.attributes('-fullscreen', True)
    root.update()
    screen_size_x = root.winfo_width()
    screen_size_y = root.winfo_height()
    app = SVGFontApp(root)

    root.mainloop()
