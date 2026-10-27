from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps, ImageTk

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
INVALID_FILENAME_CHARS = set('<>:"/\\|?*')
RESERVED_NAMES = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def natural_key(value: str):
    return [
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", value)
    ]


def scan_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    files = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(files, key=lambda path: (natural_key(path.name), path.name))


def normalize_filename(raw_name: str, source_suffix: str) -> str:
    if source_suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("不支持该图片格式")

    text = raw_name.strip().rstrip(". ")
    if not text:
        raise ValueError("请输入文件名")
    if "/" in text or "\\" in text:
        raise ValueError("文件名不能包含路径分隔符")
    if any(char in INVALID_FILENAME_CHARS for char in text):
        raise ValueError('文件名不能包含 <>:"/\\|?* 等字符')
    if any(ord(char) < 32 for char in text):
        raise ValueError("文件名包含无效字符")

    lower_text = text.lower()
    for extension in (".jpeg", ".webp", ".jpg", ".png"):
        if lower_text.endswith(extension):
            text = text[: -len(extension)]
            break

    text = text.strip().rstrip(". ")
    if not text:
        raise ValueError("请输入有效的文件名")
    if text.split(".")[0].upper() in RESERVED_NAMES:
        raise ValueError("该文件名是 Windows 保留名称")

    filename = f"{text}{source_suffix}"
    if len(filename) > 255:
        raise ValueError("文件名过长")
    return filename


def save_renamed_image(
    source: Path, output_dir: Path, raw_name: str
) -> tuple[Path, bool]:
    filename = normalize_filename(raw_name, source.suffix)
    if not source.is_file():
        raise FileNotFoundError("源图片不存在")

    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / filename
    if target.resolve(strict=False) == source.resolve(strict=False):
        return target, False

    existed = target.exists()
    shutil.copy2(source, target)
    return target, existed


def resource_path(name: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent
    return base / name


def enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class ImageRenamerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.source_dir: Path | None = None
        self.output_dir: Path | None = None
        self.images: list[Path] = []
        self.index = -1
        self.saved_targets: dict[Path, Path] = {}
        self._preview_job: str | None = None
        self._preview_photo: ImageTk.PhotoImage | None = None
        self._syncing_selection = False
        self._render_attempts = 0
        self._status_kind = "info"

        self.source_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.suffix_var = tk.StringVar()
        self.info_var = tk.StringVar(value="尚未选择图片")
        self.progress_var = tk.StringVar(value="第 0 / 0 张")
        self.count_var = tk.StringVar(value="0 张")
        self.status_var = tk.StringVar(value="请选择源文件夹")

        self._setup_window()
        self._setup_styles()
        self._build_ui()
        self._bind_events()
        self._update_controls()
        self._show_placeholder("请选择源文件夹开始")

    def _setup_window(self) -> None:
        self.root.title("图片重命名工具")
        self.root.geometry("1180x780")
        self.root.minsize(980, 680)
        self.root.configure(bg="#eef2f7")

        icon = resource_path("app.ico")
        if icon.exists():
            try:
                self.root.iconbitmap(default=str(icon))
            except tk.TclError:
                pass

    def _setup_styles(self) -> None:
        font_family = "Microsoft YaHei UI"
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(".", font=(font_family, 10))
        style.configure("App.TFrame", background="#eef2f7")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Card.TLabel", background="#ffffff", foreground="#1f2937")
        style.configure(
            "Section.TLabel",
            background="#ffffff",
            foreground="#111827",
            font=(font_family, 11, "bold"),
        )
        style.configure(
            "FieldLabel.TLabel",
            background="#ffffff",
            foreground="#374151",
            font=(font_family, 10, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background="#ffffff",
            foreground="#6b7280",
            font=(font_family, 9),
        )
        style.configure(
            "Path.TEntry",
            fieldbackground="#f8fafc",
            readonlybackground="#f8fafc",
            foreground="#334155",
            bordercolor="#dbe2ea",
            lightcolor="#dbe2ea",
            darkcolor="#dbe2ea",
            padding=(9, 8),
        )
        style.configure(
            "Name.TEntry",
            fieldbackground="#ffffff",
            foreground="#111827",
            bordercolor="#cbd5e1",
            lightcolor="#cbd5e1",
            darkcolor="#cbd5e1",
            padding=(11, 9),
            font=(font_family, 12),
        )
        style.map(
            "Name.TEntry",
            bordercolor=[("focus", "#2563eb")],
            lightcolor=[("focus", "#2563eb")],
            darkcolor=[("focus", "#2563eb")],
            fieldbackground=[("disabled", "#f1f5f9")],
        )
        style.configure(
            "Accent.TButton",
            background="#2563eb",
            foreground="#ffffff",
            borderwidth=0,
            focusthickness=0,
            padding=(18, 9),
            font=(font_family, 10, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[
                ("pressed", "#1e40af"),
                ("active", "#1d4ed8"),
                ("disabled", "#bfdbfe"),
            ],
            foreground=[("disabled", "#eff6ff")],
        )
        style.configure(
            "Ghost.TButton",
            background="#eef2f7",
            foreground="#334155",
            borderwidth=0,
            focusthickness=0,
            padding=(16, 9),
        )
        style.map(
            "Ghost.TButton",
            background=[
                ("pressed", "#dbeafe"),
                ("active", "#e2e8f0"),
                ("disabled", "#f1f5f9"),
            ],
            foreground=[("disabled", "#94a3b8")],
        )
        style.configure(
            "Treeview",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#374151",
            borderwidth=0,
            rowheight=30,
        )
        style.map(
            "Treeview",
            background=[("selected", "#dbeafe")],
            foreground=[("selected", "#1e3a8a")],
        )
        style.configure(
            "Treeview.Heading",
            background="#f8fafc",
            foreground="#64748b",
            borderwidth=0,
            relief="flat",
            padding=(8, 8),
            font=(font_family, 9, "bold"),
        )
        style.map("Treeview.Heading", background=[("active", "#f1f5f9")])

    def _build_ui(self) -> None:
        font_family = "Microsoft YaHei UI"
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)

        header = tk.Frame(self.root, bg="#0f172a")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title_block = tk.Frame(header, bg="#0f172a")
        title_block.grid(row=0, column=0, sticky="w", padx=26, pady=(16, 14))
        tk.Label(
            title_block,
            text="图片重命名",
            bg="#0f172a",
            fg="#ffffff",
            font=(font_family, 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_block,
            text="选择文件夹，预览图片，快速生成重命名副本",
            bg="#0f172a",
            fg="#94a3b8",
            font=(font_family, 10),
        ).pack(anchor="w", pady=(3, 0))

        tk.Label(
            header,
            text="JPG   PNG   WEBP",
            bg="#1e293b",
            fg="#cbd5e1",
            font=(font_family, 9, "bold"),
            padx=14,
            pady=8,
        ).grid(row=0, column=1, sticky="e", padx=26)

        folder_card = ttk.Frame(
            self.root, style="Card.TFrame", padding=(18, 14)
        )
        folder_card.grid(row=1, column=0, sticky="ew", padx=20, pady=(16, 0))
        folder_card.grid_columnconfigure(1, weight=1)

        ttk.Label(
            folder_card, text="源文件夹", style="FieldLabel.TLabel"
        ).grid(row=0, column=0, sticky="w", padx=(0, 14), pady=(0, 7))
        ttk.Entry(
            folder_card,
            textvariable=self.source_var,
            state="readonly",
            style="Path.TEntry",
        ).grid(row=0, column=1, sticky="ew", pady=(0, 7))
        ttk.Button(
            folder_card,
            text="选择...",
            style="Ghost.TButton",
            command=self._choose_source,
        ).grid(row=0, column=2, padx=(10, 0), pady=(0, 7))

        ttk.Label(
            folder_card, text="输出文件夹", style="FieldLabel.TLabel"
        ).grid(row=1, column=0, sticky="w", padx=(0, 14))
        ttk.Entry(
            folder_card,
            textvariable=self.output_var,
            state="readonly",
            style="Path.TEntry",
        ).grid(row=1, column=1, sticky="ew")
        ttk.Button(
            folder_card,
            text="选择...",
            style="Ghost.TButton",
            command=self._choose_output,
        ).grid(row=1, column=2, padx=(10, 0))

        main_area = ttk.Frame(self.root, style="App.TFrame")
        main_area.grid(
            row=2, column=0, sticky="nsew", padx=20, pady=16
        )
        main_area.grid_rowconfigure(0, weight=1)
        main_area.grid_columnconfigure(0, weight=0, minsize=350)
        main_area.grid_columnconfigure(1, weight=1)

        left = ttk.Frame(main_area, style="Card.TFrame", padding=(14, 14))
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        list_header = ttk.Frame(left, style="Card.TFrame")
        list_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        list_header.grid_columnconfigure(0, weight=1)
        ttk.Label(
            list_header, text="图片列表", style="Section.TLabel"
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            list_header,
            textvariable=self.count_var,
            style="Muted.TLabel",
        ).grid(row=0, column=1, sticky="e")

        tree_wrap = ttk.Frame(left, style="Card.TFrame")
        tree_wrap.grid(row=1, column=0, sticky="nsew")
        tree_wrap.grid_rowconfigure(0, weight=1)
        tree_wrap.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            tree_wrap,
            columns=("source", "target"),
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("source", text="原文件", anchor="w")
        self.tree.heading("target", text="新名称", anchor="w")
        self.tree.column(
            "source", width=190, minwidth=120, stretch=True, anchor="w"
        )
        self.tree.column(
            "target", width=120, minwidth=80, stretch=True, anchor="w"
        )
        self.tree.tag_configure("saved", foreground="#047857")
        self.tree.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(
            tree_wrap, orient="vertical", command=self.tree.yview
        )
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        ttk.Label(
            left,
            text="点击列表可切换图片\n切换时会自动保存当前输入",
            style="Muted.TLabel",
            justify="left",
        ).grid(row=2, column=0, sticky="w", pady=(10, 0))

        right = ttk.Frame(main_area, style="Card.TFrame", padding=(16, 14))
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        top_line = ttk.Frame(right, style="Card.TFrame")
        top_line.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        top_line.grid_columnconfigure(0, weight=1)
        ttk.Label(
            top_line,
            textvariable=self.info_var,
            style="Card.TLabel",
            font=(font_family, 10, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            top_line,
            textvariable=self.progress_var,
            style="Muted.TLabel",
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))

        self.preview_frame = tk.Frame(
            right, bg="#0f172a", highlightthickness=0, bd=0
        )
        self.preview_frame.grid(row=1, column=0, sticky="nsew")
        self.preview_frame.grid_rowconfigure(0, weight=1)
        self.preview_frame.grid_columnconfigure(0, weight=1)

        self.preview_label = tk.Label(
            self.preview_frame,
            bg="#0f172a",
            fg="#94a3b8",
            text="",
            font=(font_family, 12),
            justify="center",
        )
        self.preview_label.grid(row=0, column=0, sticky="nsew")

        form = ttk.Frame(right, style="Card.TFrame")
        form.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        form.grid_columnconfigure(0, weight=1)

        ttk.Label(
            form, text="输出文件名", style="FieldLabel.TLabel"
        ).grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 6))

        self.name_entry = ttk.Entry(
            form, textvariable=self.name_var, style="Name.TEntry"
        )
        self.name_entry.grid(row=1, column=0, sticky="ew")
        ttk.Label(
            form,
            textvariable=self.suffix_var,
            style="Muted.TLabel",
            font=(font_family, 12),
        ).grid(row=1, column=1, padx=(8, 14))

        self.prev_button = ttk.Button(
            form,
            text="上一张",
            style="Ghost.TButton",
            command=self.go_prev,
        )
        self.prev_button.grid(row=1, column=2, padx=(0, 8))
        self.skip_button = ttk.Button(
            form,
            text="跳过",
            style="Ghost.TButton",
            command=self.skip_current,
        )
        self.skip_button.grid(row=1, column=3, padx=(0, 8))
        self.next_button = ttk.Button(
            form,
            text="下一张  Enter",
            style="Accent.TButton",
            command=self.go_next,
        )
        self.next_button.grid(row=1, column=4)

        ttk.Label(
            right,
            text="Enter 保存并进入下一张 · 跳过不写入输出目录 · 扩展名自动保留",
            style="Muted.TLabel",
        ).grid(row=3, column=0, sticky="w", pady=(10, 0))

        bottom_line = ttk.Frame(right, style="Card.TFrame")
        bottom_line.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        bottom_line.grid_columnconfigure(0, weight=1)
        self.status_label = tk.Label(
            bottom_line,
            textvariable=self.status_var,
            bg="#ffffff",
            fg="#6b7280",
            anchor="w",
            font=(font_family, 9),
        )
        self.status_label.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            bottom_line,
            text="仅扫描源文件夹第一层",
            style="Muted.TLabel",
        ).grid(row=0, column=1, sticky="e")

        self.entry_menu = tk.Menu(self.root, tearoff=0)
        self.entry_menu.add_command(
            label="剪切",
            command=lambda: self.name_entry.event_generate("<<Cut>>"),
        )
        self.entry_menu.add_command(
            label="复制",
            command=lambda: self.name_entry.event_generate("<<Copy>>"),
        )
        self.entry_menu.add_command(
            label="粘贴",
            command=lambda: self.name_entry.event_generate("<<Paste>>"),
        )
        self.entry_menu.add_separator()
        self.entry_menu.add_command(
            label="全选",
            command=lambda: self.name_entry.selection_range(0, "end"),
        )

    def _bind_events(self) -> None:
        self.root.bind("<Return>", self._on_return)
        self.root.bind("<KP_Enter>", self._on_return)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.preview_frame.bind("<Configure>", self._on_preview_resize)
        self.name_entry.bind("<Button-3>", self._show_entry_menu)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        self.root.destroy()

    def _on_return(self, event=None):
        focus = self.root.focus_get()
        if isinstance(focus, (ttk.Button, tk.Button)):
            return None
        self.go_next()
        return "break"

    def _show_entry_menu(self, event) -> None:
        self.name_entry.focus_set()
        try:
            self.entry_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.entry_menu.grab_release()

    def _choose_source(self) -> None:
        initial = (
            str(self.source_dir)
            if self.source_dir is not None
            else str(Path.home())
        )
        folder = filedialog.askdirectory(
            parent=self.root,
            title="选择源文件夹",
            initialdir=initial,
        )
        if folder:
            self._load_source_folder(Path(folder))

    def _choose_output(self) -> bool:
        initial = (
            str(self.output_dir)
            if self.output_dir is not None
            else str(self.source_dir or Path.home())
        )
        folder = filedialog.askdirectory(
            parent=self.root,
            title="选择输出文件夹",
            initialdir=initial,
        )
        if not folder:
            return False

        new_output = Path(folder)
        if new_output != self.output_dir:
            self.saved_targets.clear()
            self.output_dir = new_output
            self.output_var.set(str(new_output))
            self._refresh_saved_targets()
            self._update_count()
            if self.index >= 0:
                current_name = self.name_var.get()
                self._apply_current_name()
                if current_name.strip():
                    self.name_var.set(current_name)
                self.root.after_idle(self._focus_name)
        self.set_status(f"输出文件夹：{new_output}", "info")
        return True

    def _load_source_folder(self, folder: Path) -> None:
        self.source_dir = folder
        self.source_var.set(str(folder))
        self.images = scan_images(folder)
        self.saved_targets.clear()
        self.index = -1
        self._populate_tree()
        self._update_count()
        self._update_controls()

        if not self.images:
            self._clear_current_state()
            self.set_status(
                "所选文件夹中没有 JPG / PNG / WEBP 图片", "warn"
            )
            return

        self.index = 0
        self._load_current()
        if self.output_dir is None:
            self.set_status(
                f"已加载 {len(self.images)} 张图片，请选择输出文件夹",
                "info",
            )
        else:
            self.set_status(f"已加载 {len(self.images)} 张图片", "info")

    def _populate_tree(self) -> None:
        self._syncing_selection = True
        self.tree.delete(*self.tree.get_children())
        for index, path in enumerate(self.images):
            target = self.saved_targets.get(path)
            target_name = target.name if target and target.exists() else ""
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(path.name, target_name),
                tags=("saved",) if target_name else (),
            )
        self._syncing_selection = False

    def _refresh_saved_targets(self) -> None:
        for index, path in enumerate(self.images):
            target = self.saved_targets.get(path)
            if target and target.exists():
                self._set_tree_row(
                    index, path.name, target.name, ("saved",)
                )
            else:
                if target is not None:
                    self.saved_targets.pop(path, None)
                self._set_tree_row(index, path.name, "", ())

    def _set_tree_row(
        self, index: int, source_name: str, target_name: str, tags: tuple
    ) -> None:
        iid = str(index)
        if self.tree.exists(iid):
            self.tree.item(
                iid, values=(source_name, target_name), tags=tags
            )

    def _update_tree_row(self, index: int) -> None:
        if not (0 <= index < len(self.images)):
            return
        path = self.images[index]
        target = self.saved_targets.get(path)
        target_name = target.name if target and target.exists() else ""
        self._set_tree_row(
            index,
            path.name,
            target_name,
            ("saved",) if target_name else (),
        )

    def _update_count(self) -> None:
        named = sum(
            1
            for path in self.images
            if path in self.saved_targets
            and self.saved_targets[path].exists()
        )
        text = f"{len(self.images)} 张"
        if named:
            text += f" · 已命名 {named}"
        self.count_var.set(text)

    def _load_current(self) -> None:
        if not (0 <= self.index < len(self.images)):
            self._clear_current_state()
            return

        path = self.images[self.index]
        self.info_var.set(path.name)
        self.progress_var.set(f"第 {self.index + 1} / {len(self.images)} 张")
        self._apply_current_name()
        self._sync_tree_selection()
        self._update_controls()
        self._render_attempts = 0
        self._queue_preview()
        self.root.after_idle(self._focus_name)

    def _apply_current_name(self) -> None:
        if not (0 <= self.index < len(self.images)):
            return
        path = self.images[self.index]
        target = self.saved_targets.get(path)
        if target is not None and target.exists():
            self.name_var.set(target.stem)
        else:
            if target is not None:
                self.saved_targets.pop(path, None)
                self._update_tree_row(self.index)
                self._update_count()
            self.name_var.set(path.stem)
        self.suffix_var.set(path.suffix)

    def _focus_name(self) -> None:
        try:
            self.name_entry.focus_set()
            self.name_entry.selection_range(0, "end")
            self.name_entry.icursor("end")
        except tk.TclError:
            pass

    def _sync_tree_selection(self) -> None:
        if not (0 <= self.index < len(self.images)):
            return
        iid = str(self.index)
        if not self.tree.exists(iid):
            return
        self._syncing_selection = True
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        self.tree.see(iid)
        self._syncing_selection = False

    def _on_tree_select(self, event=None) -> None:
        if self._syncing_selection:
            return
        selection = self.tree.selection()
        if not selection:
            return
        try:
            new_index = int(selection[0])
        except ValueError:
            return
        if new_index == self.index:
            return
        if not self._save_current():
            self._sync_tree_selection()
            return
        self.index = new_index
        self._load_current()

    def _clear_current_state(self) -> None:
        self.index = -1
        self.info_var.set("尚未选择图片")
        self.progress_var.set("第 0 / 0 张")
        self.name_var.set("")
        self.suffix_var.set("")
        self._show_placeholder("请选择源文件夹开始")
        self._update_controls()

    def _update_controls(self) -> None:
        state = "normal" if self.images else "disabled"
        self.name_entry.configure(state=state)
        self.prev_button.configure(state=state)
        self.skip_button.configure(state=state)
        self.next_button.configure(state=state)

    def _save_current(self) -> bool:
        if not (0 <= self.index < len(self.images)):
            return True

        if self.output_dir is None:
            if not self._choose_output():
                self.set_status("请选择输出文件夹后再保存", "warn")
                return False

        source = self.images[self.index]
        try:
            filename = normalize_filename(
                self.name_var.get(), source.suffix
            )
            if self.output_dir is None:
                raise ValueError("请选择输出文件夹")
            self.output_dir.mkdir(parents=True, exist_ok=True)
            target = self.output_dir / filename
            source_resolved = source.resolve(strict=False)
            target_resolved = target.resolve(strict=False)

            if target_resolved != source_resolved:
                for other in self.images:
                    if (
                        other != source
                        and other.resolve(strict=False)
                        == target_resolved
                    ):
                        raise ValueError(
                            "输出名称与源文件夹中的其他图片同名"
                        )

            saved_target, existed = save_renamed_image(
                source, self.output_dir, self.name_var.get()
            )
            self.saved_targets[source] = saved_target
            self._update_tree_row(self.index)
            self._update_count()

            if target_resolved == source_resolved:
                self.set_status(
                    f"名称未改变，未生成副本：{saved_target.name}", "warn"
                )
            elif existed:
                self.set_status(f"已覆盖：{saved_target.name}", "success")
            else:
                self.set_status(f"已保存：{saved_target.name}", "success")
            return True
        except Exception as exc:
            message = str(exc) or "未知错误"
            messagebox.showerror("保存失败", message, parent=self.root)
            self.set_status(message, "error")
            try:
                self.name_entry.focus_set()
                self.name_entry.selection_range(0, "end")
            except tk.TclError:
                pass
            return False

    def skip_current(self) -> None:
        if not self.images:
            self.set_status("请先选择源文件夹", "warn")
            return
        skipped_name = self.images[self.index].name
        if self.index >= len(self.images) - 1:
            self.set_status(
                f"已跳过：{skipped_name}（未保存）· 已是最后一张",
                "info",
            )
            return
        self.index += 1
        self._load_current()
        self.set_status(f"已跳过：{skipped_name}（未保存）", "info")

    def go_next(self) -> None:
        if not self.images:
            self.set_status("请先选择源文件夹", "warn")
            return
        if not self._save_current():
            return
        if self.index >= len(self.images) - 1:
            text = self.status_var.get()
            self.set_status(f"{text} · 已是最后一张", self._status_kind)
            return
        self.index += 1
        self._load_current()

    def go_prev(self) -> None:
        if not self.images:
            self.set_status("请先选择源文件夹", "warn")
            return
        if not self._save_current():
            return
        if self.index <= 0:
            text = self.status_var.get()
            self.set_status(f"{text} · 已是第一张", self._status_kind)
            return
        self.index -= 1
        self._load_current()

    def set_status(self, text: str, kind: str = "info") -> None:
        colors = {
            "info": "#6b7280",
            "success": "#047857",
            "warn": "#b45309",
            "error": "#b91c1c",
        }
        self._status_kind = kind
        self.status_var.set(text)
        self.status_label.configure(foreground=colors.get(kind, "#6b7280"))

    def _show_placeholder(self, text: str) -> None:
        self._preview_photo = None
        self.preview_label.configure(image="", text=text)

    def _on_preview_resize(self, event=None) -> None:
        self._queue_preview()

    def _queue_preview(self) -> None:
        if self._preview_job is not None:
            try:
                self.root.after_cancel(self._preview_job)
            except tk.TclError:
                pass
        self._preview_job = self.root.after(120, self._render_preview)

    def _render_preview(self) -> None:
        self._preview_job = None
        if not (0 <= self.index < len(self.images)):
            self._show_placeholder("请选择源文件夹开始")
            return

        width = self.preview_label.winfo_width()
        height = self.preview_label.winfo_height()
        if width < 20 or height < 20:
            if self._render_attempts < 10:
                self._render_attempts += 1
                self._preview_job = self.root.after(
                    80, self._render_preview
                )
            return
        self._render_attempts = 0

        path = self.images[self.index]
        max_width = max(width - 32, 1)
        max_height = max(height - 32, 1)
        try:
            with Image.open(path) as image:
                image = ImageOps.exif_transpose(image)
                original_width, original_height = image.size
                image.thumbnail(
                    (max_width, max_height), Image.Resampling.LANCZOS
                )
                if image.mode in ("RGBA", "LA") or (
                    image.mode == "P" and "transparency" in image.info
                ):
                    rgba = image.convert("RGBA")
                    background = Image.new(
                        "RGBA", rgba.size, (15, 23, 42, 255)
                    )
                    output = Image.alpha_composite(
                        background, rgba
                    ).convert("RGB")
                else:
                    output = image.convert("RGB")
            photo = ImageTk.PhotoImage(output)
            if (
                not (0 <= self.index < len(self.images))
                or self.images[self.index] != path
            ):
                return
            self._preview_photo = photo
            self.preview_label.configure(image=photo, text="")
            self.info_var.set(
                f"{path.name}  ·  {original_width} × {original_height}"
            )
        except Exception as exc:
            if (
                not (0 <= self.index < len(self.images))
                or self.images[self.index] != path
            ):
                return
            self._show_placeholder("无法预览此图片")
            self.info_var.set(path.name)
            self.set_status(f"预览失败：{exc}", "error")


def main() -> None:
    enable_dpi_awareness()
    root = tk.Tk()
    ImageRenamerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
