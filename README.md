| MaskPoint | Description |
|---|---|
| Overview | A native Python polygon annotation tool that saves binary PNG masks and editable image-pixel coordinates. |
| Interface | Tkinter desktop window; no browser, server, account, network connection or machine-learning model. |
| Origin | Extracted from the Bladder_AI annotation window and made independent of its paths and datasets. |
| Scope | One polygon per image; no multi-class labels, automatic segmentation or inferred medical diagnosis. |

| Quick start | Command / requirement |
|---|---|
| Python | Python 3.10+ with a working Tcl/Tk installation. |
| Install | `python -m pip install -r requirements.txt` |
| Open the desktop app | `python annotator.py` — opens an empty editor with an editable image-folder field. |
| Specify a folder | `python annotator.py "/path/to/images"` |
| Regression check | `python test_annotation.py` — creates synthetic fixtures only and opens no visible window. |
| Tested locally | macOS with a working Conda Python/Tk environment; other operating systems have not been verified. |
| Tk troubleshooting | Tkinter is part of the Python distribution, not a pip dependency; Linux may need its distribution's `python3-tk` package. |

| Where to set or change the image path | Instructions |
|---|---|
| Recommended: inside the app | Start `python annotator.py`, paste your image directory into **Image folder** at the top, then click **Open** or press **Enter**. |
| Choose instead of typing | Click **Browse…**, select the directory containing your images, and it opens automatically. |
| Change folders later | Replace the text in **Image folder** and click **Open** again; no restart is required. Unsaved polygon edits require confirmation before switching. |
| Folder, not an image file | Enter the directory containing your JPG/PNG images, not the filename of one image and not the `labels/` directory. |
| Path with spaces | Paste the path directly into the app **without surrounding quotes**; for a terminal command, enclose it in double quotes. |
| Command-line alternative | In `python annotator.py "/path/to/images"`, replace **`/path/to/images`** with your own image directory. This preloads the same editable field. |
| Example command | `python annotator.py "/path/to/My Images"` |
| Home and relative paths | `~/Pictures/My Images` expands to your home directory; a relative path is resolved from the terminal's current working directory. |
| Editing Python source | **Not required.** There is no machine-specific dataset path to change in `annotator.py`; use the GUI field or command-line argument. |
| Invalid input | A nonexistent, empty or unsupported image folder shows an error without replacing the previously loaded folder. |
| Where outputs go | A flat folder `/path/to/My Images` gets `/path/to/My Images/labels/<stem>.png` and `<stem>.json`; a group with `images/` gets sibling `labels/`. |

| Input / output | Convention |
|---|---|
| Images | JPG, JPEG, PNG, BMP, TIFF and WebP; decoded by Pillow. |
| Flat layout | Select a directory containing images; outputs go in its `labels/` directory. |
| Grouped layout | Select a parent whose immediate subdirectories contain images; each group gets its own `labels/` directory. |
| Optional images directory | A group may contain `images/` plus sibling `labels/`; the tool uses that group's `images/` directory. |
| Discovery boundary | No recursive dataset scan; hidden files, labels, archives and overlay directories are excluded. |
| Duplicate stems | Images such as `sample.jpg` and `sample.png` in one group are rejected because they would share an output filename. |
| Mask | `labels/<image_stem>.png`; grayscale L mode, 0 = background, 255 = polygon interior; original image dimensions. |
| Points | `labels/<image_stem>.json`; image/mask names, dimensions, `image_pixels` coordinate system and editable `[x, y]` points. |
| Existing annotations | Matching point JSON is reloaded; a PNG without JSON can be displayed but cannot recover its original clicked vertices. |
| Saving edits | Saving intentionally replaces the current image's PNG/JSON pair; source images are never changed. Both outputs are staged first, with rollback on a caught replacement error. |
| Durability limit | The pair is not a database transaction; keep backups, particularly against power loss or failure during rollback. |

| Controls | Action |
|---|---|
| Image folder / Open | Type or paste a directory path; Open or Enter loads it. |
| Browse… | Select and open an image directory using the native folder chooser. |
| Left click | Add a polygon vertex; clicking an existing vertex starts a drag. |
| Drag | Move a vertex; coordinates are clamped to the image. |
| Left / Right | Previous / next image. |
| Z | Undo the last point. |
| C | Clear the editable polygon. |
| S / Save button | Save the binary mask and point JSON. |
| Double click | Save; at least three points are required. |
| Drawing | Green boundary and draggable dots; no filled preview polygon. |
| Reloaded mask | Red overlay over the source image. |
| Keyboard focus | Typing into the path field does not trigger annotation shortcuts. Save before changing images; unsaved edits are not retained by previous/next navigation. |

| Repository | Contents / policy |
|---|---|
| `annotator.py` | Standalone program and annotation file handling. |
| `test_annotation.py` | Editable folder input/switching, discovery, save/reload, rollback, real Tk/ImageTk and coordinate-drag checks. |
| `requirements.txt` | Pillow is the only pip dependency. |
| `.gitignore` | Excludes local datasets, annotations, images, environments and secrets. |
| `LICENSE` | MIT license for the program; it does not grant rights to any external image or dataset. |
| Privacy | No real ultrasound images, patient information, annotations, model weights or account credentials are included. |
| GitHub | [Lumilogoz/MaskPoint](https://github.com/Lumilogoz/MaskPoint) — public source code under the MIT license; datasets and annotations are not included. |
