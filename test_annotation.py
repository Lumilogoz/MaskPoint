#!/usr/bin/env python3
"""Run real Tk/Pillow checks with synthetic fixtures and no visible window."""
import hashlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tkinter as tk

from PIL import Image, ImageChops, ImageDraw

from annotator import App, discover_groups, read_points, save_pair


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def check():
    with tempfile.TemporaryDirectory(prefix='maskpoint-test-') as temporary:
        directory = Path(temporary)
        data = directory / 'input images'
        data.mkdir()
        fixture = Image.new('RGB', (420, 300), '#30363d')
        drawing = ImageDraw.Draw(fixture)
        drawing.ellipse((80, 55, 345, 255), fill='#78838e')
        drawing.text((12, 12), 'SYNTHETIC TEST IMAGE', fill='white')
        image_path = data / 'synthetic.png'
        fixture.save(image_path)
        nested = data / 'group_b' / 'images'
        nested.mkdir(parents=True)
        fixture.save(nested / 'second.jpg')
        archives = data / 'archives'
        archives.mkdir()
        fixture.save(archives / 'ignored.jpg')
        original = hashlib.sha256(image_path.read_bytes()).hexdigest()
        groups = discover_groups(data)
        count = 0
        for _, images in groups:
            count += len(images)
        require(count == 2, 'Flat/grouped discovery or archive exclusion failed')

        root = tk.Tk()
        root.withdraw()
        try:
            app = App(root)
            require(app.current == -1 and not app.items, 'Empty startup failed')
            app.previous()
            app.next()
            app.save()
            with patch('annotator.messagebox.showerror') as popup:
                app.open_button.invoke()
                require(popup.call_count == 1, 'Empty path did not report an error')
            app.path_entry.insert(0, str(data))
            app.open_button.invoke()
            require(app.data_dir == data.resolve() and len(app.items) == 2, 'Typed path with spaces did not load')
            # Withdrawn Tk canvases report 1x1; render into their requested dimensions.
            app.canvas.winfo_width = app.canvas.winfo_reqwidth
            app.canvas.winfo_height = app.canvas.winfo_reqheight
            app.display()
            require(app.tk_image is not None, 'Actual ImageTk rendering failed')
            vertices = [(65.0, 65.0), (340.0, 70.0), (325.0, 235.0), (75.0, 240.0)]
            for x, y in vertices:
                event = SimpleNamespace(x=app.x0 + x * app.scale, y=app.y0 + y * app.scale)
                app.press_point(event)
                app.release_point()
            require(len(app.points) == 4, 'Point insertion failed')
            before_points = list(app.points)
            for key in ['c', 's', 'z', 'Left', 'Right']:
                app.shortcut(SimpleNamespace(widget=app.path_entry, keysym=key))
            require(app.points == before_points and app.current == 0, 'Path editing triggered a shortcut')
            require(not (data / 'labels').exists(), 'Typing a path triggered Save')
            event = SimpleNamespace(x=app.x0 + 65 * app.scale, y=app.y0 + 65 * app.scale)
            app.press_point(event)
            target = (68.125, 74.25)
            app.move_point(SimpleNamespace(x=app.x0 + target[0] * app.scale,
                                          y=app.y0 + target[1] * app.scale))
            app.release_point()
            app.save()
            root.update_idletasks()
            mask_path = data / 'labels/synthetic.png'
            json_path = data / 'labels/synthetic.json'
            annotation = json.loads(json_path.read_text())
            require(abs(annotation['points'][0][0] - target[0]) < 1e-6, 'Dragged x was not saved')
            require(abs(annotation['points'][0][1] - target[1]) < 1e-6, 'Dragged y was not saved')
            require(app.saved_mask is not None and len(app.points) == 4, 'Saved annotation was not reloaded')
            require(app.progress.cget('text') == 'Completed 1 / 2', 'Pair progress is incorrect')
            with Image.open(mask_path) as mask:
                require(mask.mode == 'L' and mask.size == fixture.size, 'Mask mode/size changed')
                histogram = mask.histogram()
                require(histogram[0] > 0 and histogram[255] > 0 and sum(histogram[1:255]) == 0,
                        'Mask is not binary')
                expected = Image.new('L', fixture.size, 0)
                ImageDraw.Draw(expected).polygon(app.points, fill=255)
                require(ImageChops.difference(mask, expected).getbbox() is None, 'Polygon rasterization changed')
            app.next()
            app.previous()
            require(len(app.points) == 4, 'Navigation did not restore editable points')
            app.clear()
            require(not app.points, 'Clear failed')
            app.select_item(0)
            app.undo()
            require(len(app.points) == 3, 'Undo failed')
            app.select_item(0)
            before_mask = mask_path.read_bytes()
            before_json = json_path.read_bytes()
            original_replace = Path.replace

            def fail_json_commit(path, target_path):
                if path.parent.name.startswith('.maskpoint-') and path.suffix == '.json':
                    raise OSError('Synthetic second-file commit failure')
                return original_replace(path, target_path)

            with patch.object(Path, 'replace', fail_json_commit):
                try:
                    save_pair(data, image_path, fixture.size, vertices)
                except OSError:
                    pass
                else:
                    raise RuntimeError('Failure injection did not run')
            require(mask_path.read_bytes() == before_mask and json_path.read_bytes() == before_json,
                    'Failed save did not preserve the existing pair')
            invalid = json.loads(before_json)
            invalid['points'][0][0] = -1
            json_path.write_text(json.dumps(invalid))
            try:
                read_points(json_path, image_path, fixture.size)
            except ValueError:
                pass
            else:
                raise RuntimeError('Invalid coordinates were accepted')
            json_path.write_bytes(before_json)
            require(hashlib.sha256(image_path.read_bytes()).hexdigest() == original, 'Source image changed')
            previous_items = list(app.items)
            for invalid_folder in [directory / 'missing', image_path]:
                app.folder_var.set(str(invalid_folder))
                with patch('annotator.messagebox.showerror') as popup:
                    app.open_button.invoke()
                    require(popup.call_count == 1, 'Invalid directory did not report an error')
                require(app.items == previous_items and app.folder_var.get() == str(data.resolve()),
                        'Invalid path changed the active folder')
            other = directory / 'other images'
            other.mkdir()
            fixture.save(other / 'different.png')
            app.points.append((100.0, 100.0))
            unsaved = list(app.points)
            app.folder_var.set(str(other))
            with patch('annotator.messagebox.askyesno', return_value=False):
                app.open_button.invoke()
            require(app.items == previous_items and app.points == unsaved,
                    'Canceled folder switch discarded edits')
            with patch('annotator.filedialog.askdirectory', return_value=''):
                app.browse_button.invoke()
            require(app.items == previous_items and app.points == unsaved, 'Canceled Browse changed the session')
            with patch('annotator.filedialog.askdirectory', return_value=str(other)):
                with patch('annotator.messagebox.askyesno', return_value=True):
                    app.browse_button.invoke()
            require(app.data_dir == other.resolve() and len(app.items) == 1 and not app.points,
                    'Browse did not switch image folders')
            require(mask_path.read_bytes() == before_mask and json_path.read_bytes() == before_json,
                    'Folder switching modified saved annotations')
        finally:
            root.destroy()

        collision = directory / 'collision'
        collision.mkdir()
        fixture.save(collision / 'same.jpg')
        fixture.save(collision / 'same.png')
        try:
            discover_groups(collision)
        except ValueError:
            pass
        else:
            raise RuntimeError('Colliding mask filenames were accepted')
    print('PASS: editable paths with spaces, empty startup, Open/Browse, canceled/invalid switches,')
    print('      unsaved-edit protection, path-field shortcut isolation, real Tk/ImageTk,')
    print('      discovery, click/drag, binary PNG + point JSON, reload/navigation,')
    print('      clear/undo, progress, invalid-coordinate and duplicate-stem rejection,')
    print('      failed-save rollback and unchanged source image. No real dataset writes.')


if __name__ == '__main__':
    check()
