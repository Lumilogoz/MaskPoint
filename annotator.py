#!/usr/bin/env python3
"""MaskPoint: a native polygon editor that saves binary masks and editable points."""
import argparse
import json
import math
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

from PIL import Image, ImageDraw, ImageTk

BG = '#202124'
PANEL = '#2b2d30'
TEXT = '#f1f3f4'
GREEN = '#28d17c'
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}
EXCLUDED_FOLDERS = {'labels', 'images', 'archives', 'overlays', '__pycache__'}


def discover_groups(data_dir):
    """Read a flat image folder or immediate groups; never recurse into datasets."""
    data_dir = Path(data_dir).expanduser().resolve()
    if not data_dir.is_dir():
        raise ValueError('Image folder does not exist: ' + str(data_dir))
    folders = [data_dir]
    for child in sorted(data_dir.iterdir()):
        if child.is_dir() and not child.is_symlink() and not child.name.startswith('.'):
            if child.name not in EXCLUDED_FOLDERS:
                folders.append(child)
    groups = []
    for folder in folders:
        image_folder = folder / 'images'
        if not image_folder.is_dir():
            image_folder = folder
        images = []
        stems = set()
        for path in sorted(image_folder.iterdir()):
            if not path.is_file() or path.name.startswith('.'):
                continue
            if path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            # ponytail: one polygon per image; reject stems that would overwrite each other's labels.
            if path.stem.casefold() in stems:
                raise ValueError('Images share an output stem in ' + str(image_folder) + ': ' + path.stem)
            stems.add(path.stem.casefold())
            images.append(path)
        if images:
            groups.append((folder, images))
    if not groups:
        raise ValueError('No supported images in this folder or its immediate groups')
    return groups


def read_points(json_path, image_path, image_size):
    """Validate saved image-pixel coordinates before allowing edits."""
    if not json_path.exists():
        return []
    annotation = json.loads(json_path.read_text(encoding='utf-8'))
    width, height = image_size
    if (annotation['image'] != image_path.name or annotation['mask'] != image_path.stem + '.png'
            or annotation['coordinate_system'] != 'image_pixels'
            or annotation['image_width'] != width or annotation['image_height'] != height):
        raise ValueError('Point JSON belongs to a different image or coordinate system')
    points = []
    for point in annotation['points']:
        if len(point) != 2:
            raise ValueError('Each point must contain x and y')
        x, y = float(point[0]), float(point[1])
        if not math.isfinite(x) or not math.isfinite(y) or not (0 <= x < width and 0 <= y < height):
            raise ValueError('Point is outside the image or is not finite')
        points.append((x, y))
    if len(points) < 3:
        raise ValueError('A saved polygon needs at least three points')
    return points


def save_pair(folder, image_path, image_size, points):
    """Write PNG/JSON together, restoring replaced outputs if a commit fails."""
    width, height = image_size
    if len(points) < 3:
        raise ValueError('Add at least three points before saving')
    coordinates = []
    for x, y in points:
        if not math.isfinite(x) or not math.isfinite(y) or not (0 <= x < width and 0 <= y < height):
            raise ValueError('Point is outside the image or is not finite')
        coordinates.append([float(x), float(y)])
    labels = folder / 'labels'
    if labels.is_symlink():
        raise ValueError('Refusing to write through a labels folder symlink')
    labels.mkdir(exist_ok=True)
    mask_path = labels / (image_path.stem + '.png')
    json_path = labels / (image_path.stem + '.json')
    previous = {}
    for path in [mask_path, json_path]:
        if path.is_symlink():
            raise ValueError('Refusing to replace an annotation symlink')
        previous[path] = path.read_bytes() if path.exists() else None
    mask = Image.new('L', image_size, 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    annotation = {'image': image_path.name, 'mask': mask_path.name,
                  'coordinate_system': 'image_pixels', 'image_width': width,
                  'image_height': height, 'points': coordinates}
    # Stage both outputs before touching existing annotations.
    with tempfile.TemporaryDirectory(prefix='.maskpoint-', dir=labels) as directory:
        temporary = Path(directory)
        mask.save(temporary / mask_path.name)
        (temporary / json_path.name).write_text(json.dumps(annotation, indent=2) + '\n', encoding='utf-8')
        committed = []
        try:
            for path in [mask_path, json_path]:
                (temporary / path.name).replace(path)
                committed.append(path)
        except OSError:
            for path in committed:
                if previous[path] is None:
                    path.unlink()  # Only remove this failed save's newly created output.
                else:
                    path.write_bytes(previous[path])
            raise
    return mask_path, json_path


class App:
    def __init__(self, master, data_dir=None):
        self.master = master
        self.data_dir = None
        self.groups = []
        self.items = []
        self.current = -1
        self.points = []
        self.saved_points = []
        self.drag_point = None
        self.image = None
        self.tk_image = None
        self.saved_mask = None
        self.scale = 1.0
        master.title('MaskPoint · Binary mask annotation')
        master.geometry('1200x800')
        master.minsize(900, 600)
        master.configure(bg=BG)

        paths = tk.Frame(master, bg=PANEL)
        paths.pack(side='top', fill='x', padx=12, pady=(10, 0))
        tk.Label(paths, text='Image folder', bg=PANEL, fg=TEXT).pack(side='left', padx=(8, 10))
        self.folder_var = tk.StringVar(master)
        self.path_entry = tk.Entry(paths, textvariable=self.folder_var, bg='#18191b',
                                   fg=TEXT, insertbackground=TEXT, relief='flat')
        self.path_entry.pack(side='left', fill='x', expand=True, padx=(0, 8), ipady=5)
        self.path_entry.bind('<Return>', self.load_folder)
        self.browse_button = self.button(paths, 'Browse…', self.browse_folder)
        self.browse_button.pack(side='left', padx=(0, 6))
        self.open_button = self.button(paths, 'Open', self.load_folder, primary=True)
        self.open_button.pack(side='left', padx=(0, 8), pady=5)

        left = tk.Frame(master, bg=PANEL, width=285)
        left.pack(side='left', fill='y')
        left.pack_propagate(False)
        tk.Label(left, text='MaskPoint', bg=PANEL, fg=TEXT,
                 font=('Helvetica', 16, 'bold')).pack(anchor='w', padx=14, pady=(14, 4))
        tk.Label(left, text='Click a boundary · Drag points · Save', bg=PANEL,
                 fg='#aeb4bb', font=('Helvetica', 10)).pack(anchor='w', padx=14, pady=(0, 10))
        self.listbox = tk.Listbox(left, bg='#18191b', fg=TEXT, selectbackground='#315f9e',
                                  selectforeground='white', relief='flat', borderwidth=0,
                                  font=('Helvetica', 10), activestyle='none')
        self.listbox.pack(fill='both', expand=True, padx=8, pady=4)
        self.listbox.bind('<<ListboxSelect>>', self.choose)
        self.progress = tk.Label(left, bg=PANEL, fg='#aeb4bb', font=('Helvetica', 10))
        self.progress.pack(anchor='w', padx=14, pady=(5, 12))

        main = tk.Frame(master, bg=BG)
        main.pack(side='right', fill='both', expand=True)
        bar = tk.Frame(main, bg=BG)
        bar.pack(fill='x', padx=12, pady=10)
        for text, command in [('Previous', self.previous), ('Next', self.next),
                              ('Undo point', self.undo), ('Clear', self.clear)]:
            self.button(bar, text, command).pack(side='left', padx=(0, 6))
        self.button(bar, 'Save mask + points', self.save, primary=True).pack(side='left')
        self.status = tk.Label(main, bg=BG, fg='#aeb4bb', font=('Helvetica', 10), anchor='w')
        self.status.pack(fill='x', padx=12, pady=(0, 6))
        self.canvas = tk.Canvas(main, bg='#0b0c0d', highlightthickness=0, cursor='crosshair')
        self.canvas.pack(fill='both', expand=True, padx=12, pady=(0, 12))
        self.canvas.bind('<ButtonPress-1>', self.press_point)
        self.canvas.bind('<B1-Motion>', self.move_point)
        self.canvas.bind('<ButtonRelease-1>', self.release_point)
        self.canvas.bind('<Configure>', self.display)
        self.canvas.bind('<Double-Button-1>', self.save)
        master.bind('<KeyPress>', self.shortcut)
        self.refresh_items()
        self.status.config(text='Paste an image folder above, then click Open or press Enter.')
        if data_dir is not None:
            self.set_folder(data_dir)

    def set_folder(self, folder):
        """Validate a new folder before replacing the current editing session."""
        groups = discover_groups(folder)
        if self.points != self.saved_points:
            discard = messagebox.askyesno('Unsaved polygon',
                'Discard unsaved points and open another folder?', parent=self.master)
            if not discard:
                self.folder_var.set(str(self.data_dir))
                return
        self.data_dir = Path(folder).expanduser().resolve()
        self.folder_var.set(str(self.data_dir))
        self.groups = groups
        self.items = []
        for group_folder, images in groups:
            for image in images:
                self.items.append((group_folder, image))
        self.current = -1
        self.image = None
        self.tk_image = None
        self.saved_mask = None
        self.points = []
        self.saved_points = []
        self.drag_point = None
        self.canvas.delete('all')
        self.refresh_items()
        self.select_item(0)

    def load_folder(self, _event=None):
        value = self.folder_var.get()
        try:
            if not value.strip():
                raise ValueError('Enter the folder containing your images, not a single image filename')
            self.set_folder(value)
        except (OSError, ValueError) as error:
            messagebox.showerror('Cannot open image folder', str(error), parent=self.master)
            if self.data_dir is not None:
                self.folder_var.set(str(self.data_dir))

    def browse_folder(self):
        selected = filedialog.askdirectory(parent=self.master, title='Choose your image folder', mustexist=True)
        if selected:
            self.folder_var.set(selected)
            self.load_folder()

    def shortcut(self, event):
        # Typing a path must never trigger Save/Clear/Undo or image navigation.
        if event.widget == self.path_entry:
            return
        commands = {'left': self.previous, 'right': self.next,
                    'z': self.undo, 'c': self.clear, 's': self.save}
        action = commands.get(event.keysym.lower())
        if action is not None:
            action()

    def button(self, parent, text, command, primary=False):
        background = '#e8eaed'
        foreground = '#202124'
        if primary:
            background = '#376fc4'
            foreground = 'white'
        return tk.Button(parent, text=text, command=command, bg=background, fg=foreground,
                         activebackground='#4a82dc', activeforeground='white', relief='flat',
                         borderwidth=0, padx=12, pady=7, font=('Helvetica', 10))

    def done_count(self, folder):
        count = 0
        for item_folder, image in self.items:
            if item_folder == folder:
                labels = folder / 'labels'
                if (labels / (image.stem + '.png')).is_file() and (labels / (image.stem + '.json')).is_file():
                    count += 1
        return count

    def refresh_items(self):
        self.listbox.delete(0, tk.END)
        completed = 0
        for folder, images in self.groups:
            done = self.done_count(folder)
            completed += done
            self.listbox.insert(tk.END, f'── {folder.name} ({done}/{len(images)})')
            for image in images:
                labels = folder / 'labels'
                mark = '  '
                if (labels / (image.stem + '.png')).is_file() and (labels / (image.stem + '.json')).is_file():
                    mark = '✓ '
                self.listbox.insert(tk.END, mark + image.name)
        self.progress.config(text=f'Completed {completed} / {len(self.items)}')

    def list_index(self, item_index):
        row = 0
        for _, images in self.groups:
            row += 1
            if item_index < len(images):
                return row + item_index
            item_index -= len(images)
            row += len(images)
        return 0

    def choose(self, _event=None):
        selection = self.listbox.curselection()
        if not selection:
            return
        row = 0
        item_index = 0
        for _, images in self.groups:
            if selection[0] == row:
                return
            row += 1
            for _ in images:
                if selection[0] == row:
                    self.select_item(item_index)
                    return
                row += 1
                item_index += 1

    def select_item(self, index):
        if not self.items:
            return
        index %= len(self.items)
        folder, path = self.items[index]
        try:
            with Image.open(path) as source:
                image = source.convert('RGB')
            mask = None
            mask_path = folder / 'labels' / (path.stem + '.png')
            if mask_path.exists():
                with Image.open(mask_path) as source:
                    if source.size != image.size:
                        raise ValueError('Saved mask dimensions differ from the image')
                    mask = source.convert('L')
            points = read_points(folder / 'labels' / (path.stem + '.json'), path, image.size)
        except (OSError, ValueError, KeyError, TypeError) as error:
            messagebox.showerror('Cannot open annotation', str(error), parent=self.master)
            return
        self.current = index
        self.image = image
        self.saved_mask = mask
        self.points = points
        self.saved_points = list(points)
        self.drag_point = None
        self.display()
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(self.list_index(index))
        self.listbox.see(self.list_index(index))
        self.status.config(text=f'{index + 1} / {len(self.items)} · {path.name}')

    def display(self, _event=None):
        if self.image is None:
            return
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width < 20 or height < 20:
            return
        self.scale = min(width / self.image.width, height / self.image.height, 1.0)
        size = (round(self.image.width * self.scale), round(self.image.height * self.scale))
        shown = self.image.resize(size, Image.Resampling.LANCZOS)
        if self.saved_mask is not None:
            mask = self.saved_mask.resize(size, Image.Resampling.NEAREST)
            red = Image.new('RGB', size, (255, 70, 70))
            shown = Image.blend(shown, Image.composite(red, shown, mask), 0.45)
        self.tk_image = ImageTk.PhotoImage(shown)
        self.canvas.delete('all')
        self.x0 = (width - shown.width) // 2
        self.y0 = (height - shown.height) // 2
        self.canvas.create_image(self.x0, self.y0, image=self.tk_image, anchor='nw')
        canvas_points = []
        for x, y in self.points:
            canvas_points.extend([self.x0 + x * self.scale, self.y0 + y * self.scale])
        if len(self.points) >= 3:
            self.canvas.create_polygon(canvas_points, outline=GREEN, width=2, fill='')
        elif len(self.points) == 2:
            self.canvas.create_line(canvas_points, fill=GREEN, width=2)
        for x, y in self.points:
            x, y = self.x0 + x * self.scale, self.y0 + y * self.scale
            self.canvas.create_oval(x - 4, y - 4, x + 4, y + 4, fill=GREEN, outline='white')

    def image_point(self, event):
        return (event.x - self.x0) / self.scale, (event.y - self.y0) / self.scale

    def press_point(self, event):
        if self.image is None or self.tk_image is None:
            return
        x, y = self.image_point(event)
        if not (0 <= x < self.image.width and 0 <= y < self.image.height):
            return
        self.drag_point = None
        radius = max(8 / self.scale, 3)
        for index, (px, py) in enumerate(self.points):
            if (px - x) ** 2 + (py - y) ** 2 <= radius ** 2:
                self.drag_point = index
                break
        if self.drag_point is None:
            self.points.append((x, y))
            self.display()

    def move_point(self, event):
        if self.drag_point is None:
            return
        x, y = self.image_point(event)
        x = min(max(x, 0), self.image.width - 1)
        y = min(max(y, 0), self.image.height - 1)
        self.points[self.drag_point] = (x, y)
        self.display()

    def release_point(self, _event=None):
        self.drag_point = None

    def undo(self, _event=None):
        if self.points:
            self.points.pop()
            self.display()

    def clear(self, _event=None):
        self.points = []
        self.drag_point = None
        self.display()

    def save(self, _event=None):
        if self.current < 0 or self.image is None:
            return
        folder, path = self.items[self.current]
        try:
            save_pair(folder, path, self.image.size, self.points)
        except (OSError, ValueError) as error:
            messagebox.showerror('Cannot save annotation', str(error), parent=self.master)
            return
        self.refresh_items()
        self.select_item(self.current)
        self.status.config(text='Saved mask + points: ' + path.name)

    def previous(self, _event=None):
        self.select_item(self.current - 1)

    def next(self, _event=None):
        self.select_item(self.current + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', nargs='?', type=Path, help='Image folder or a parent containing groups')
    args = parser.parse_args()
    root = tk.Tk()
    root.withdraw()
    try:
        App(root, args.folder)
    except (OSError, ValueError) as error:
        root.destroy()
        parser.error(str(error))
    root.deiconify()
    root.mainloop()


if __name__ == '__main__':
    main()
