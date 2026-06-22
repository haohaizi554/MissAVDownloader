import customtkinter as ctk
import os
import socket
import time
import threading
from tkinter import filedialog, messagebox

from app_state import AppStateStore

THEME = {
    "sidebar_bg": "#0C1220",
    "main_bg": "#0A101C",
    "card_bg": "#131B2E",
    "card_border": "#1E2A3F",
    "accent": "#3B82F6",
    "accent_hover": "#2563EB",
    "accent_soft": "#1E3A5F",
    "text": "#E2E8F0",
    "text_sub": "#64748B",
    "success": "#22C55E",
    "success_soft": "#14532D",
    "danger": "#EF4444",
    "danger_hover": "#DC2626",
    "warning": "#F59E0B",
    "warning_soft": "#78350F",
    "input_bg": "#0F1729",
    "input_border": "#243047",
    "list_item": "#182236",
    "list_item_hover": "#1F2B42",
    "list_drag": "#1A2740",
    "terminal_bg": "#060B14",
    "terminal_text": "#86EFAC",
    "terminal_error": "#FCA5A5",
    "terminal_warn": "#FDE68A",
    "terminal_success": "#6EE7B7",
    "pill_bg": "#132038",
    "stat_blue": "#3B82F6",
    "stat_green": "#22C55E",
    "stat_red": "#EF4444",
    "stat_teal": "#14B8A6",
    "radius": 12,
    "sidebar_w": 240,
}

THEME_LIGHT = {
    **THEME,
    "sidebar_bg": "#F1F5F9",
    "main_bg": "#F8FAFC",
    "card_bg": "#FFFFFF",
    "card_border": "#E2E8F0",
    "text": "#0F172A",
    "text_sub": "#64748B",
    "input_bg": "#F8FAFC",
    "input_border": "#CBD5E1",
    "list_item": "#F1F5F9",
    "list_item_hover": "#E2E8F0",
    "terminal_bg": "#0F172A",
    "pill_bg": "#E2E8F0",
}

APP_VERSION = "v1.0.0"
SIDEBAR_NAV = [
    ("home", "首页", "⌂"),
    ("tasks", "下载任务", "▣"),
    ("queue", "队列", "☰"),
    ("history", "历史", "◷"),
    ("settings", "设置", "⚙"),
]
PAGE_TITLES = {
    "home": "首页",
    "tasks": "下载任务",
    "queue": "队列",
    "history": "历史",
    "settings": "设置",
}

STATUS_ZH = {
    "pending": "等待中",
    "running": "下载中",
    "done": "已完成",
    "failed": "失败",
    "crawling": "爬取中",
    "preview": "待确认",
    "downloading": "下载中",
    "stopped": "已停止",
    "success": "成功",
}

FONT_UI = ("微软雅黑", 13)
FONT_UI_SM = ("微软雅黑", 11)
FONT_TITLE = ("微软雅黑", 18, "bold")
FONT_CARD = ("微软雅黑", 14, "bold")
FONT_MONO = ("Consolas", 11)
FONT_MONO_SM = ("Consolas", 10)

_active_theme = THEME


def get_theme():
    return _active_theme


def apply_theme_mode(mode):
    global _active_theme
    if mode == "light":
        _active_theme = THEME_LIGHT
        ctk.set_appearance_mode("Light")
    else:
        _active_theme = THEME
        ctk.set_appearance_mode("Dark")


ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def check_proxy_status(host, port, enabled):
    if not enabled:
        return "未启用", get_theme()["text_sub"]
    host = (host or "127.0.0.1").strip()
    port = (port or "").strip()
    if not port:
        return "未连接", get_theme()["warning"]
    try:
        port_num = int(port)
        with socket.create_connection((host, port_num), timeout=1.5):
            return "代理已连接", get_theme()["success"]
    except Exception:
        return "未连接", get_theme()["danger"]


def proxy_quality_label(status_text):
    if status_text == "代理已连接":
        return "在线 优"
    if status_text == "未启用":
        return "未启用"
    return "离线"


class PreviewDialog(ctk.CTkToplevel):
    T = property(lambda self: get_theme())

    def __init__(self, parent, title, summary_text, info_text, on_confirm, on_cancel):
        super().__init__(parent)
        t = get_theme()
        self.title(title)
        self.geometry("920x720")
        self.minsize(640, 480)
        self.configure(fg_color=t["main_bg"])
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self._closed = False
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 8))
        ctk.CTkLabel(header, text="下载清单确认", font=("微软雅黑", 18, "bold"), text_color=t["text"]).pack(anchor="w")
        ctk.CTkLabel(header, text=summary_text, font=FONT_UI_SM, text_color=t["text_sub"], justify="left").pack(
            anchor="w", pady=(6, 0),
        )

        self.textbox = ctk.CTkTextbox(
            self, font=FONT_MONO, fg_color=t["input_bg"], text_color=t["text"], corner_radius=10,
            border_width=1, border_color=t["card_border"],
        )
        self.textbox.grid(row=2, column=0, sticky="nsew", padx=24, pady=8)
        self.textbox.insert("1.0", info_text)
        self.textbox.configure(state="disabled")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, sticky="ew", padx=24, pady=(8, 24))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(
            btn_frame, text="取消任务", fg_color=t["danger"], hover_color=t["danger_hover"],
            height=44, font=FONT_UI, command=self.cancel,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            btn_frame, text="确认下载", fg_color=t["accent"], hover_color=t["accent_hover"],
            height=44, font=FONT_UI, command=self.confirm,
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

    def _finish(self, callback):
        if self._closed:
            return
        self._closed = True
        try:
            self.grab_release()
        except Exception:
            pass
        callback()
        self.destroy()

    def confirm(self):
        self._finish(self.on_confirm)

    def cancel(self):
        self._finish(self.on_cancel)


class DraggableList(ctk.CTkFrame):
    def __init__(self, master, items, update_callback, **kwargs):
        t = get_theme()
        super().__init__(master, fg_color="transparent", **kwargs)
        self.items = items
        self.update_callback = update_callback
        self.row_frames = []
        self.drag_start_idx = None
        self._enabled = True
        self.render_items()

    def set_enabled(self, enabled):
        self._enabled = enabled
        for row in self.row_frames:
            for w in row.winfo_children():
                try:
                    w.configure(state="normal" if enabled else "disabled")
                except Exception:
                    pass

    def _make_row(self, idx, text):
        t = get_theme()
        row = ctk.CTkFrame(self, fg_color=t["list_item"], corner_radius=8, height=44, border_width=1, border_color=t["input_border"])
        row.pack(fill="x", pady=4)
        row.pack_propagate(False)
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=8, pady=6)

        grip = ctk.CTkLabel(inner, text="☰", width=20, text_color=t["text_sub"], font=FONT_UI)
        grip.pack(side="left")

        badge = ctk.CTkFrame(inner, width=26, height=26, fg_color=t["accent"], corner_radius=13)
        badge.pack(side="left", padx=(6, 10))
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text=str(idx + 1), font=("微软雅黑", 11, "bold"), text_color="#FFFFFF").place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(inner, text=text, font=FONT_UI, text_color=t["text"], anchor="w").pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(inner, text="⋮", width=16, text_color=t["text_sub"], font=FONT_UI).pack(side="right")

        row.bind("<Button-1>", lambda e, r=row: self.on_start(e, r))
        row.bind("<B1-Motion>", lambda e, r=row: self.on_drag(e, r))
        row.bind("<ButtonRelease-1>", lambda e, r=row: self.on_stop(e, r))
        for child in row.winfo_children():
            child.bind("<Button-1>", lambda e, r=row: self.on_start(e, r))
            child.bind("<B1-Motion>", lambda e, r=row: self.on_drag(e, r))
            child.bind("<ButtonRelease-1>", lambda e, r=row: self.on_stop(e, r))
        row.configure(cursor="hand2")
        return row

    def render_items(self):
        for row in self.row_frames:
            row.destroy()
        self.row_frames = []
        for idx, text in enumerate(self.items):
            self.row_frames.append(self._make_row(idx, text))
        self.set_enabled(self._enabled)

    def _highlight(self, row, active):
        t = get_theme()
        row.configure(
            fg_color=t["list_drag"] if active else t["list_item"],
            border_color=t["accent"] if active else t["input_border"],
            border_width=2 if active else 1,
        )

    def on_start(self, event, widget):
        if not self._enabled:
            return
        self.drag_start_idx = self.row_frames.index(widget)
        self._highlight(widget, True)

    def on_drag(self, event, widget):
        if not self._enabled or self.drag_start_idx is None:
            return
        root_y = widget.winfo_rooty() + event.y
        target_idx = -1
        for idx, row in enumerate(self.row_frames):
            if row.winfo_rooty() <= root_y <= row.winfo_rooty() + row.winfo_height():
                target_idx = idx
                break
        if target_idx != -1 and target_idx != self.drag_start_idx:
            self.items[self.drag_start_idx], self.items[target_idx] = (
                self.items[target_idx], self.items[self.drag_start_idx],
            )
            self.row_frames[self.drag_start_idx], self.row_frames[target_idx] = (
                self.row_frames[target_idx], self.row_frames[self.drag_start_idx],
            )
            self._highlight(self.row_frames[self.drag_start_idx], False)
            self._highlight(self.row_frames[target_idx], True)
            self.drag_start_idx = target_idx

    def on_stop(self, event, widget):
        if self.drag_start_idx is not None:
            changed = self.drag_start_idx is not None
            self.drag_start_idx = None
            self.render_items()
            if changed and self.update_callback:
                self.update_callback()


class MissAVDownloaderAppBase(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.store = AppStateStore()
        settings = self.store.load_settings()
        apply_theme_mode(settings.get("theme", "dark"))

        self.title("MissAV 智能下载终端")
        self.geometry("1400x900")
        self.minsize(1200, 760)

        self.is_running = False
        self.stop_event = threading.Event()
        self.user_action_event = threading.Event()
        self.preview_confirm_event = threading.Event()
        self.preview_result = False
        self.priority_data = ["中文字幕", "英文字幕", "无码流出", "普通版"]
        self.runtime_save_dir = settings.get("save_dir", os.path.join(os.path.expanduser("~"), "Desktop", "MissAV_Download"))
        self._tools_ok = True
        self._current_page = "home"
        self._current_mode = "link"
        self._theme_mode = settings.get("theme", "dark")
        self._proxy_check_job = None
        self._proxy_check_generation = 0
        self._proxy_status_text = "未启用"
        self._proxy_status_color = get_theme()["text_sub"]
        self._status_text = "就绪"
        self._nav_buttons = {}

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.configure(fg_color=get_theme()["main_bg"])

        self._build_sidebar()
        self._build_main_shell()
        self._build_pages()
        self.show_page("home")
        self.center_window()
        self._apply_settings_to_form(settings)
        self.check_tools()
        self.refresh_all_ui()
        self._schedule_proxy_check()
        self.set_status("就绪", get_theme()["success"])

    def get_downloader_exe_path(self):
        return "N_m3u8DL-RE.exe"

    def center_window(self):
        self.update_idletasks()
        w, h = 1400, 900
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _card(self, master, **kw):
        t = get_theme()
        return ctk.CTkFrame(
            master, fg_color=t["card_bg"], corner_radius=t["radius"],
            border_width=1, border_color=t["card_border"], **kw,
        )

    def _build_sidebar(self):
        t = get_theme()
        self.sidebar = ctk.CTkFrame(self, width=THEME["sidebar_w"], fg_color=t["sidebar_bg"], corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=16, pady=(20, 24))
        logo = ctk.CTkFrame(brand, width=36, height=36, fg_color=t["accent"], corner_radius=8)
        logo.pack(side="left")
        logo.pack_propagate(False)
        ctk.CTkLabel(logo, text="M", font=("微软雅黑", 16, "bold"), text_color="#FFF").place(relx=0.5, rely=0.5, anchor="center")
        text_box = ctk.CTkFrame(brand, fg_color="transparent")
        text_box.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(text_box, text="MissAV Downloader", font=("微软雅黑", 13, "bold"), text_color=t["text"]).pack(anchor="w")
        ctk.CTkLabel(text_box, text="智能下载终端", font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w")

        nav = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav.pack(fill="x", padx=8)
        for page_id, label, icon in SIDEBAR_NAV:
            btn = ctk.CTkButton(
                nav, text=f"  {icon}   {label}", anchor="w", height=42, corner_radius=8,
                fg_color="transparent", hover_color=t["list_item_hover"],
                text_color=t["text_sub"], font=FONT_UI,
                command=lambda p=page_id: self.show_page(p),
            )
            btn.pack(fill="x", pady=2)
            btn._page_id = page_id
            self._nav_buttons[page_id] = btn

        footer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=16, pady=16)
        ctk.CTkLabel(footer, text=f"© MissAV Downloader {APP_VERSION}", font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w")
        ctk.CTkLabel(footer, text="● 已是最新版本", font=FONT_UI_SM, text_color=t["success"]).pack(anchor="w", pady=(4, 12))

        theme_row = ctk.CTkFrame(footer, fg_color=t["input_bg"], corner_radius=8)
        theme_row.pack(fill="x")
        self.btn_theme_light = ctk.CTkButton(
            theme_row, text="☀", width=50, height=32, fg_color="transparent",
            hover_color=t["list_item_hover"], command=lambda: self.set_theme("light"),
        )
        self.btn_theme_light.pack(side="left", padx=4, pady=4)
        self.btn_theme_dark = ctk.CTkButton(
            theme_row, text="☾", width=50, height=32, fg_color=t["accent_soft"],
            hover_color=t["accent"], command=lambda: self.set_theme("dark"),
        )
        self.btn_theme_dark.pack(side="left", padx=4, pady=4)
        self._update_theme_buttons()

    def _update_theme_buttons(self):
        t = get_theme()
        if self._theme_mode == "dark":
            self.btn_theme_dark.configure(fg_color=t["accent_soft"])
            self.btn_theme_light.configure(fg_color="transparent")
        else:
            self.btn_theme_light.configure(fg_color=t["accent_soft"])
            self.btn_theme_dark.configure(fg_color="transparent")

    def _build_main_shell(self):
        t = get_theme()
        self.main = ctk.CTkFrame(self, fg_color=t["main_bg"], corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        topbar = ctk.CTkFrame(self.main, fg_color=t["main_bg"], height=56)
        topbar.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        topbar.grid_columnconfigure(0, weight=1)
        self.page_title_label = ctk.CTkLabel(topbar, text="首页", font=FONT_TITLE, text_color=t["text"])
        self.page_title_label.grid(row=0, column=0, sticky="w")

        self.status_chip = ctk.CTkFrame(topbar, fg_color=t["pill_bg"], corner_radius=12, border_width=1, border_color=t["card_border"])
        self.status_chip.grid(row=0, column=1, sticky="w", padx=(16, 0))
        chip_inner = ctk.CTkFrame(self.status_chip, fg_color="transparent")
        chip_inner.pack(padx=10, pady=4)
        self.status_chip_dot = ctk.CTkLabel(chip_inner, text="●", text_color=t["success"], font=FONT_UI_SM)
        self.status_chip_dot.pack(side="left")
        self.status_chip_label = ctk.CTkLabel(chip_inner, text="就绪", font=FONT_UI_SM, text_color=t["text"])
        self.status_chip_label.pack(side="left", padx=(4, 0))

        self.proxy_pill = ctk.CTkFrame(topbar, fg_color=t["pill_bg"], corner_radius=16, border_width=1, border_color=t["card_border"])
        self.proxy_pill.grid(row=0, column=2, sticky="e")
        pill_inner = ctk.CTkFrame(self.proxy_pill, fg_color="transparent")
        pill_inner.pack(padx=12, pady=6)
        self.proxy_pill_dot = ctk.CTkLabel(pill_inner, text="●", text_color=t["success"], font=FONT_UI_SM)
        self.proxy_pill_dot.pack(side="left")
        self.proxy_pill_label = ctk.CTkLabel(pill_inner, text="代理已连接", font=FONT_UI_SM, text_color=t["text"])
        self.proxy_pill_label.pack(side="left", padx=(4, 0))

        self.page_container = ctk.CTkFrame(self.main, fg_color="transparent")
        self.page_container.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 16))
        self.page_container.grid_columnconfigure(0, weight=1)
        self.page_container.grid_rowconfigure(0, weight=1)
        self.pages = {}

    def _build_pages(self):
        self.pages["home"] = self._build_home_page()
        self.pages["tasks"] = self._build_tasks_page()
        self.pages["queue"] = self._build_queue_page()
        self.pages["history"] = self._build_history_page()
        self.pages["settings"] = self._build_settings_page()

    def _build_home_page(self):
        t = get_theme()
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_columnconfigure(1, weight=1)
        page.grid_rowconfigure(0, weight=3)
        page.grid_rowconfigure(1, weight=2)

        left = ctk.CTkFrame(page, fg_color="transparent")
        left.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(0, weight=3)
        left.grid_rowconfigure(1, weight=2)
        left.grid_rowconfigure(2, weight=0)
        left.grid_rowconfigure(3, weight=0)

        config = self._card(left)
        config.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        self._setup_config_card(config)

        priority = self._card(left)
        priority.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self._setup_priority_card(priority)

        actions = ctk.CTkFrame(left, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)
        self.btn_start = ctk.CTkButton(
            actions, text="▶  立即执行", font=("微软雅黑", 14, "bold"), height=48,
            fg_color=t["accent"], hover_color=t["accent_hover"], command=self.start_thread,
        )
        self.btn_start.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_stop = ctk.CTkButton(
            actions, text="■  强制停止", font=("微软雅黑", 14, "bold"), height=48,
            fg_color=t["danger"], hover_color=t["danger_hover"], state="disabled",
            command=self.stop_task,
        )
        self.btn_stop.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.progress_bar = ctk.CTkProgressBar(
            left, height=5, mode="indeterminate", fg_color=t["input_bg"], progress_color=t["accent"],
        )
        self.progress_bar.grid(row=3, column=0, sticky="ew")
        self.progress_bar.grid_remove()

        right_top = self._card(page)
        right_top.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 10))
        self._setup_terminal_card(right_top)

        right_bottom = self._card(page)
        right_bottom.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        self._setup_overview_card(right_bottom)

        return page

    def _setup_config_card(self, card):
        t = get_theme()
        card.grid_columnconfigure(0, weight=1)
        pad = ctk.CTkFrame(card, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(pad, text="▣  任务配置", font=FONT_CARD, text_color=t["text"]).pack(anchor="w", pady=(0, 12))

        self.tool_warning_frame = ctk.CTkFrame(pad, fg_color="#3D1F1F", corner_radius=8)
        self.tool_warning_label = ctk.CTkLabel(
            self.tool_warning_frame, text="", font=FONT_UI_SM, text_color="#FF9999", wraplength=420, justify="left",
        )
        self.tool_warning_label.pack(anchor="w", padx=12, pady=10)

        tab_row = ctk.CTkFrame(pad, fg_color=t["input_bg"], corner_radius=8)
        tab_row.pack(fill="x", pady=(0, 12))
        self.btn_mode_link = ctk.CTkButton(
            tab_row, text="链接模式", height=36, corner_radius=6, font=FONT_UI,
            fg_color=t["accent"], hover_color=t["accent_hover"], command=lambda: self._set_mode("link"),
        )
        self.btn_mode_link.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        self.btn_mode_search = ctk.CTkButton(
            tab_row, text="搜索模式", height=36, corner_radius=6, font=FONT_UI,
            fg_color="transparent", hover_color=t["list_item_hover"], command=lambda: self._set_mode("search"),
        )
        self.btn_mode_search.pack(side="left", fill="x", expand=True, padx=4, pady=4)

        self.link_panel = ctk.CTkFrame(pad, fg_color="transparent")
        self.link_panel.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(self.link_panel, text="视频或演员主页链接", font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w", pady=(0, 4))
        url_row = ctk.CTkFrame(self.link_panel, fg_color=t["input_bg"], corner_radius=8, border_width=1, border_color=t["input_border"])
        url_row.pack(fill="x")
        ctk.CTkLabel(url_row, text="🔗", width=30, text_color=t["text_sub"]).pack(side="left", padx=(8, 0))
        self.entry_url = ctk.CTkEntry(
            url_row, placeholder_text="https://missav.ai/...", height=40, border_width=0,
            fg_color=t["input_bg"], font=FONT_MONO,
        )
        self.entry_url.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=4)

        self.search_panel = ctk.CTkFrame(pad, fg_color="transparent")
        ctk.CTkLabel(self.search_panel, text="番号或演员名字", font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w", pady=(0, 4))
        self.entry_code = ctk.CTkEntry(
            self.search_panel, placeholder_text="例如 SSIS-001", height=40, border_width=1,
            border_color=t["input_border"], fg_color=t["input_bg"], font=FONT_MONO,
        )
        self.entry_code.pack(fill="x")

        sw_box = ctk.CTkFrame(pad, fg_color="transparent")
        sw_box.pack(fill="x", pady=(12, 0))
        self.switch_individual = ctk.CTkSwitch(
            sw_box, text="仅下载单体作品", font=FONT_UI, text_color=t["text"], progress_color=t["accent"],
        )
        self.switch_individual.pack(anchor="w")
        ctk.CTkLabel(sw_box, text="开启后仅抓取单体作品列表", font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w", padx=(36, 0))

        ctk.CTkLabel(pad, text="保存路径", font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w", pady=(12, 4))
        path_row = ctk.CTkFrame(pad, fg_color="transparent")
        path_row.pack(fill="x", pady=(0, 12))
        path_row.grid_columnconfigure(0, weight=1)
        self.entry_save = ctk.CTkEntry(
            path_row, height=38, border_width=1, border_color=t["input_border"],
            fg_color=t["input_bg"], font=FONT_MONO,
        )
        self.entry_save.grid(row=0, column=0, sticky="ew")
        self.btn_folder = ctk.CTkButton(
            path_row, text="浏览", width=64, height=38, font=FONT_UI_SM,
            fg_color=t["input_bg"], hover_color=t["list_item_hover"], command=self.select_folder,
        )
        self.btn_folder.grid(row=0, column=1, padx=(8, 0))

        ctk.CTkLabel(pad, text="网络代理", font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w", pady=(0, 4))
        self.switch_proxy = ctk.CTkSwitch(
            pad, text="启用 HTTP 代理", font=FONT_UI, text_color=t["text"],
            progress_color=t["accent"], command=self._on_proxy_settings_change,
        )
        self.switch_proxy.pack(anchor="w", pady=(0, 8))

        proxy_grid = ctk.CTkFrame(pad, fg_color="transparent")
        proxy_grid.pack(fill="x")
        proxy_grid.grid_columnconfigure(0, weight=1)
        proxy_grid.grid_columnconfigure(1, weight=1)
        proxy_grid.grid_columnconfigure(2, weight=1)

        host_box = ctk.CTkFrame(proxy_grid, fg_color=t["input_bg"], corner_radius=8, border_width=1, border_color=t["input_border"])
        host_box.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkLabel(host_box, text="主机", font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w", padx=10, pady=(8, 0))
        self.entry_proxy_host = ctk.CTkEntry(host_box, height=32, border_width=0, fg_color=t["input_bg"], font=FONT_MONO)
        self.entry_proxy_host.pack(fill="x", padx=10, pady=(0, 8))
        self.entry_proxy_host.bind("<KeyRelease>", lambda e: self._on_proxy_settings_change())

        port_box = ctk.CTkFrame(proxy_grid, fg_color=t["input_bg"], corner_radius=8, border_width=1, border_color=t["input_border"])
        port_box.grid(row=0, column=1, sticky="ew", padx=6)
        ctk.CTkLabel(port_box, text="端口", font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w", padx=10, pady=(8, 0))
        self.entry_proxy_port = ctk.CTkEntry(port_box, height=32, border_width=0, fg_color=t["input_bg"], font=FONT_MONO)
        self.entry_proxy_port.pack(fill="x", padx=10, pady=(0, 8))
        self.entry_proxy_port.bind("<KeyRelease>", lambda e: self._on_proxy_settings_change())

        status_box = ctk.CTkFrame(proxy_grid, fg_color=t["success_soft"], corner_radius=8, border_width=1, border_color=t["success"])
        status_box.grid(row=0, column=2, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(status_box, text="状态", font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w", padx=10, pady=(8, 0))
        self.proxy_status_badge = ctk.CTkLabel(status_box, text="代理已连接", font=FONT_UI, text_color=t["success"])
        self.proxy_status_badge.pack(anchor="w", padx=10, pady=(0, 8))

        self._input_widgets = [
            self.entry_url, self.entry_code, self.switch_individual,
            self.entry_save, self.btn_folder, self.switch_proxy,
            self.entry_proxy_host, self.entry_proxy_port,
            self.btn_mode_link, self.btn_mode_search,
        ]
        self._set_mode("link")

    def _setup_priority_card(self, card):
        t = get_theme()
        pad = ctk.CTkFrame(card, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=16, pady=16)
        ctk.CTkLabel(pad, text="☰  智能筛选优先级", font=FONT_CARD, text_color=t["text"]).pack(anchor="w")
        ctk.CTkLabel(pad, text="拖拽调整优先级（越靠上越优先）", font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w", pady=(4, 10))
        self.drag_list = DraggableList(pad, self.priority_data, self.on_priority_change)
        self.drag_list.pack(fill="both", expand=True)

    def _setup_terminal_card(self, card):
        t = get_theme()
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="▸  实时终端", font=FONT_CARD, text_color=t["text"]).grid(row=0, column=0, sticky="w")
        dots = ctk.CTkFrame(header, fg_color="transparent")
        dots.grid(row=0, column=1, sticky="e", padx=8)
        for c in ("#FF5F57", "#FFBD2E", "#28CA41"):
            ctk.CTkFrame(dots, width=10, height=10, fg_color=c, corner_radius=5).pack(side="left", padx=2)
        ctk.CTkButton(
            header, text="清空", width=56, height=28, font=FONT_UI_SM,
            fg_color=t["input_bg"], hover_color=t["list_item_hover"], command=self.clear_log,
        ).grid(row=0, column=2, sticky="e")

        self.textbox = ctk.CTkTextbox(
            card, font=FONT_MONO_SM, fg_color=t["terminal_bg"], text_color=t["terminal_text"],
            corner_radius=8, border_width=1, border_color=t["card_border"],
        )
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.textbox.configure(state="disabled")
        self._setup_log_tags()

    def _setup_overview_card(self, card):
        t = get_theme()
        pad = ctk.CTkFrame(card, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=16, pady=16)
        ctk.CTkLabel(pad, text="▣  任务概览", font=FONT_CARD, text_color=t["text"]).pack(anchor="w", pady=(0, 10))

        stats = ctk.CTkFrame(pad, fg_color="transparent")
        stats.pack(fill="x", pady=(0, 10))
        stats.grid_columnconfigure((0, 1), weight=1)
        self.stat_labels = {}
        stat_defs = [
            ("today", "今日任务", "0 个", t["stat_blue"]),
            ("completed", "已完成", "0 个", t["stat_green"]),
            ("failed", "失败", "0 个", t["stat_red"]),
            ("proxy", "代理状态", "未启用", t["stat_teal"]),
        ]
        for i, (key, title, default, color) in enumerate(stat_defs):
            box = ctk.CTkFrame(stats, fg_color=t["input_bg"], corner_radius=10, border_width=1, border_color=t["card_border"])
            box.grid(row=i // 2, column=i % 2, sticky="nsew", padx=4, pady=4)
            ctk.CTkLabel(box, text=title, font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w", padx=12, pady=(10, 0))
            val = ctk.CTkLabel(box, text=default, font=("微软雅黑", 16, "bold"), text_color=color)
            val.pack(anchor="w", padx=12, pady=(0, 10))
            self.stat_labels[key] = val

        queue_header = ctk.CTkFrame(pad, fg_color=t["input_bg"], corner_radius=8)
        queue_header.pack(fill="x", pady=(4, 6))
        qh = ctk.CTkFrame(queue_header, fg_color="transparent")
        qh.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(qh, text="当前队列", font=FONT_UI, text_color=t["text"]).pack(side="left")
        self.home_queue_count = ctk.CTkLabel(qh, text="0", font=FONT_UI, text_color=t["text_sub"])
        self.home_queue_count.pack(side="right")

        self.home_queue_frame = ctk.CTkScrollableFrame(pad, fg_color="transparent", height=100)
        self.home_queue_frame.pack(fill="both", expand=True)
        ctk.CTkButton(
            pad, text="查看全部队列 →", height=28, font=FONT_UI_SM,
            fg_color="transparent", hover_color=t["list_item_hover"], text_color=t["accent"],
            command=lambda: self.show_page("queue"),
        ).pack(anchor="e", pady=(6, 0))

    def _build_tasks_page(self):
        t = get_theme()
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(page, text="今日下载批次", font=FONT_CARD, text_color=t["text"]).grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.tasks_scroll = ctk.CTkScrollableFrame(page, fg_color=t["card_bg"], corner_radius=t["radius"], border_width=1, border_color=t["card_border"])
        self.tasks_scroll.grid(row=1, column=0, sticky="nsew")
        return page

    def _build_queue_page(self):
        t = get_theme()
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        hdr = ctk.CTkFrame(page, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="下载队列", font=FONT_CARD, text_color=t["text"]).grid(row=0, column=0, sticky="w")
        self.queue_count_label = ctk.CTkLabel(hdr, text="共 0 项", font=FONT_UI_SM, text_color=t["text_sub"])
        self.queue_count_label.grid(row=0, column=1, sticky="e")
        self.queue_scroll = ctk.CTkScrollableFrame(page, fg_color=t["card_bg"], corner_radius=t["radius"], border_width=1, border_color=t["card_border"])
        self.queue_scroll.grid(row=1, column=0, sticky="nsew")
        return page

    def _build_history_page(self):
        t = get_theme()
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(page, text="下载历史", font=FONT_CARD, text_color=t["text"]).grid(row=0, column=0, sticky="w", pady=(0, 10))
        self.history_scroll = ctk.CTkScrollableFrame(page, fg_color=t["card_bg"], corner_radius=t["radius"], border_width=1, border_color=t["card_border"])
        self.history_scroll.grid(row=1, column=0, sticky="nsew")
        return page

    def _build_settings_page(self):
        t = get_theme()
        page = ctk.CTkFrame(self.page_container, fg_color="transparent")
        card = self._card(page)
        card.pack(fill="both", expand=True)
        pad = ctk.CTkFrame(card, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(pad, text="应用设置", font=FONT_CARD, text_color=t["text"]).pack(anchor="w", pady=(0, 16))

        ctk.CTkLabel(pad, text="默认保存路径", font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w")
        sp = ctk.CTkFrame(pad, fg_color="transparent")
        sp.pack(fill="x", pady=(4, 12))
        sp.grid_columnconfigure(0, weight=1)
        self.settings_save_entry = ctk.CTkEntry(sp, height=38, fg_color=t["input_bg"], border_width=1, border_color=t["input_border"], font=FONT_MONO)
        self.settings_save_entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(sp, text="浏览", width=64, command=self._settings_browse).grid(row=0, column=1, padx=(8, 0))

        self.settings_proxy_switch = ctk.CTkSwitch(pad, text="启用 HTTP 代理", font=FONT_UI, progress_color=t["accent"])
        self.settings_proxy_switch.pack(anchor="w", pady=(8, 4))

        ph = ctk.CTkFrame(pad, fg_color="transparent")
        ph.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(ph, text="主机", font=FONT_UI_SM, text_color=t["text_sub"]).pack(side="left")
        self.settings_proxy_host = ctk.CTkEntry(ph, width=140, height=36, fg_color=t["input_bg"], border_width=1, border_color=t["input_border"])
        self.settings_proxy_host.pack(side="left", padx=(8, 16))
        ctk.CTkLabel(ph, text="端口", font=FONT_UI_SM, text_color=t["text_sub"]).pack(side="left")
        self.settings_proxy_port = ctk.CTkEntry(ph, width=80, height=36, fg_color=t["input_bg"], border_width=1, border_color=t["input_border"])
        self.settings_proxy_port.pack(side="left", padx=8)

        ctk.CTkLabel(pad, text="外观主题", font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w", pady=(8, 4))
        theme_btns = ctk.CTkFrame(pad, fg_color="transparent")
        theme_btns.pack(anchor="w", pady=(0, 12))
        ctk.CTkButton(theme_btns, text="深色", width=80, command=lambda: self.set_theme("dark")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(theme_btns, text="浅色", width=80, command=lambda: self.set_theme("light")).pack(side="left")

        self.settings_tool_label = ctk.CTkLabel(pad, text="", font=FONT_UI_SM, text_color=t["text_sub"], justify="left")
        self.settings_tool_label.pack(anchor="w", pady=(8, 12))

        ctk.CTkLabel(pad, text=f"状态文件: {self.store.state_path}", font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w", pady=(0, 12))

        ctk.CTkButton(pad, text="保存设置", height=40, fg_color=t["accent"], hover_color=t["accent_hover"], command=self._save_settings_from_page).pack(anchor="w")
        return page

    def show_page(self, page_id):
        t = get_theme()
        self._current_page = page_id
        for pid, frame in self.pages.items():
            if pid == page_id:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_remove()
        self.page_title_label.configure(text=PAGE_TITLES.get(page_id, page_id))
        for pid, btn in self._nav_buttons.items():
            if pid == page_id:
                btn.configure(fg_color=t["accent_soft"], text_color=t["text"], border_width=0)
            else:
                btn.configure(fg_color="transparent", text_color=t["text_sub"])
        if page_id == "tasks":
            self.refresh_tasks_page()
        elif page_id == "queue":
            self.refresh_queue_page(full=True)
        elif page_id == "history":
            self.refresh_history_page()
        elif page_id == "settings":
            self._load_settings_page()

    def _set_mode(self, mode):
        t = get_theme()
        self._current_mode = mode
        if mode == "link":
            self.link_panel.pack(fill="x", pady=(0, 10))
            self.search_panel.pack_forget()
            self.btn_mode_link.configure(fg_color=t["accent"])
            self.btn_mode_search.configure(fg_color="transparent")
        else:
            self.search_panel.pack(fill="x", pady=(0, 10))
            self.link_panel.pack_forget()
            self.btn_mode_search.configure(fg_color=t["accent"])
            self.btn_mode_link.configure(fg_color="transparent")

    def _apply_settings_to_form(self, settings):
        self.entry_save.delete(0, "end")
        self.entry_save.insert(0, settings.get("save_dir", self.runtime_save_dir))
        self.runtime_save_dir = settings.get("save_dir", self.runtime_save_dir)
        if settings.get("proxy_enabled", True):
            self.switch_proxy.select()
        else:
            self.switch_proxy.deselect()
        self.entry_proxy_host.delete(0, "end")
        self.entry_proxy_host.insert(0, settings.get("proxy_host", "127.0.0.1"))
        self.entry_proxy_port.delete(0, "end")
        self.entry_proxy_port.insert(0, settings.get("proxy_port", "7890"))
        self._on_proxy_toggle_fields()

    def _on_proxy_toggle_fields(self):
        if self.switch_proxy.get():
            self.entry_proxy_host.configure(state="normal")
            self.entry_proxy_port.configure(state="normal")
        else:
            self.entry_proxy_host.configure(state="disabled")
            self.entry_proxy_port.configure(state="disabled")

    def _on_proxy_settings_change(self):
        self._on_proxy_toggle_fields()
        self._persist_settings_from_home()
        self._schedule_proxy_check()

    def _persist_settings_from_home(self):
        self.store.save_settings({
            "save_dir": self.entry_save.get().strip(),
            "proxy_enabled": bool(self.switch_proxy.get()),
            "proxy_host": self.entry_proxy_host.get().strip(),
            "proxy_port": self.entry_proxy_port.get().strip(),
        })

    def _schedule_proxy_check(self):
        if self._proxy_check_job:
            self.after_cancel(self._proxy_check_job)
        self._apply_proxy_status("检测中...", get_theme()["text_sub"])
        self._proxy_check_job = self.after(500, self._start_proxy_check)

    def _start_proxy_check(self):
        self._proxy_check_job = None
        enabled = bool(self.switch_proxy.get())
        host = self.entry_proxy_host.get().strip()
        port = self.entry_proxy_port.get().strip()
        self._proxy_check_generation += 1
        generation = self._proxy_check_generation
        threading.Thread(
            target=self._proxy_check_worker,
            args=(host, port, enabled, generation),
            daemon=True,
        ).start()

    def _proxy_check_worker(self, host, port, enabled, generation):
        text, color = check_proxy_status(host, port, enabled)
        self.after(0, self._on_proxy_check_done, generation, text, color)

    def _on_proxy_check_done(self, generation, text, color):
        if generation != self._proxy_check_generation:
            return
        self._apply_proxy_status(text, color)

    def _apply_proxy_status(self, text, color):
        self._proxy_status_text = text
        self._proxy_status_color = color
        self._update_proxy_badges(text, color)

    def _run_proxy_check(self):
        self._schedule_proxy_check()

    def _update_proxy_badges(self, text, color):
        t = get_theme()
        self.proxy_pill_label.configure(text=text)
        self.proxy_pill_dot.configure(text_color=color)
        self.proxy_status_badge.configure(text=text, text_color=color)
        if text == "代理已连接":
            self.proxy_status_badge.master.configure(fg_color=t["success_soft"], border_color=t["success"])
        elif text == "未启用":
            self.proxy_status_badge.master.configure(fg_color=t["input_bg"], border_color=t["input_border"])
        else:
            self.proxy_status_badge.master.configure(fg_color=t["warning_soft"], border_color=t["warning"])
        quality = proxy_quality_label(text)
        self.stat_labels["proxy"].configure(text=quality)

    def get_proxy_server(self):
        if not self.switch_proxy.get():
            return None
        host = self.entry_proxy_host.get().strip() or "127.0.0.1"
        port = self.entry_proxy_port.get().strip()
        return f"http://{host}:{port}" if port else None

    def refresh_all_ui(self):
        self.refresh_stats_ui()
        self.refresh_queue_page(full=False)
        self._schedule_proxy_check()

    def refresh_stats_ui(self):
        stats = self.store.get_today_stats()
        self.stat_labels["today"].configure(text=f"{stats.get('today_total', 0)} 个")
        self.stat_labels["completed"].configure(text=f"{stats.get('completed', 0)} 个")
        self.stat_labels["failed"].configure(text=f"{stats.get('failed', 0)} 个")

    def refresh_queue_page(self, full=False):
        t = get_theme()
        queue = self.store.get_queue()
        pending = [q for q in queue if q.get("status") in ("pending", "running")]
        self.home_queue_count.configure(text=str(len(pending)))
        if hasattr(self, "queue_count_label"):
            self.queue_count_label.configure(text=f"共 {len(queue)} 项")

        for w in self.home_queue_frame.winfo_children():
            w.destroy()
        home_display = pending[:5]
        if not home_display:
            ctk.CTkLabel(
                self.home_queue_frame, text="当前无任务排队",
                font=FONT_UI_SM, text_color=t["text_sub"],
            ).pack(anchor="w", pady=4)
        else:
            for item in home_display:
                self._render_queue_row(self.home_queue_frame, item)

        if full:
            for w in self.queue_scroll.winfo_children():
                w.destroy()
            if not queue:
                ctk.CTkLabel(self.queue_scroll, text="当前无任务排队", font=FONT_UI, text_color=t["text_sub"]).pack(pady=20)
            else:
                for i, item in enumerate(queue, 1):
                    self._render_queue_row(self.queue_scroll, item, index=i)

    def _render_queue_row(self, parent, item, index=None):
        t = get_theme()
        status = item.get("status", "pending")
        status_zh = STATUS_ZH.get(status, status)
        colors = {"pending": t["text_sub"], "running": t["accent"], "done": t["success"], "failed": t["danger"]}
        row = ctk.CTkFrame(parent, fg_color=t["input_bg"], corner_radius=8)
        row.pack(fill="x", pady=3, padx=2 if parent == self.queue_scroll else 0)
        prefix = f"{index}. " if index else ""
        text = f"{prefix}[{item.get('code', '?')}] {item.get('title', '')[:40]}"
        ctk.CTkLabel(row, text=text, font=FONT_UI_SM, text_color=t["text"], anchor="w").pack(side="left", padx=10, pady=8)
        ctk.CTkLabel(row, text=status_zh, font=FONT_UI_SM, text_color=colors.get(status, t["text_sub"])).pack(side="right", padx=10)

    def refresh_tasks_page(self):
        t = get_theme()
        for w in self.tasks_scroll.winfo_children():
            w.destroy()
        batches = self.store.get_batches_today()
        active = self.store.get_active_batch()
        if active and not any(b.get("id") == active.get("id") for b in batches):
            batches = [active] + batches
        if not batches:
            ctk.CTkLabel(self.tasks_scroll, text="今日暂无下载任务", font=FONT_UI, text_color=t["text_sub"]).pack(pady=20)
            return
        for batch in reversed(batches):
            row = ctk.CTkFrame(self.tasks_scroll, fg_color=t["input_bg"], corner_radius=8, border_width=1, border_color=t["card_border"])
            row.pack(fill="x", pady=6, padx=8)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=12, pady=(10, 4))
            ctk.CTkLabel(top, text=f"批次 {batch.get('id', '?')}", font=FONT_UI, text_color=t["text"]).pack(side="left")
            status_zh = STATUS_ZH.get(batch.get("status", ""), batch.get("status", ""))
            ctk.CTkLabel(top, text=status_zh, font=FONT_UI_SM, text_color=t["accent"]).pack(side="right")
            progress = batch.get("progress", 0)
            total = batch.get("total", 0)
            progress_text = f"进度: {progress}/{total}" if total else "进度: --"
            ctk.CTkLabel(
                row,
                text=f"开始: {batch.get('started_at', '')}  |  模式: {batch.get('mode', '')}  |  {progress_text}",
                font=FONT_UI_SM, text_color=t["text_sub"], anchor="w",
            ).pack(fill="x", padx=12)
            ctk.CTkLabel(row, text=batch.get("target_url", "")[:80], font=FONT_MONO_SM, text_color=t["text_sub"], anchor="w").pack(fill="x", padx=12, pady=(0, 10))

    def refresh_history_page(self):
        t = get_theme()
        for w in self.history_scroll.winfo_children():
            w.destroy()
        history = self.store.get_history()
        if not history:
            ctk.CTkLabel(self.history_scroll, text="暂无历史记录", font=FONT_UI, text_color=t["text_sub"]).pack(pady=20)
            return
        for item in history:
            row = ctk.CTkFrame(self.history_scroll, fg_color=t["input_bg"], corner_radius=8)
            row.pack(fill="x", pady=4, padx=8)
            status = item.get("status", "")
            status_zh = "成功" if status == "success" else "失败"
            color = t["success"] if status == "success" else t["danger"]
            ctk.CTkLabel(row, text=f"[{item.get('time', '')}] {item.get('code', '')}", font=FONT_UI, text_color=t["text"]).pack(anchor="w", padx=12, pady=(8, 0))
            ctk.CTkLabel(row, text=item.get("title", "")[:60], font=FONT_UI_SM, text_color=t["text_sub"]).pack(anchor="w", padx=12)
            ctk.CTkLabel(row, text=f"结果: {status_zh}  |  {item.get('save_dir', '')}", font=FONT_UI_SM, text_color=color).pack(anchor="w", padx=12, pady=(0, 8))

    def _load_settings_page(self):
        s = self.store.load_settings()
        self.settings_save_entry.delete(0, "end")
        self.settings_save_entry.insert(0, s.get("save_dir", ""))
        if s.get("proxy_enabled", True):
            self.settings_proxy_switch.select()
        else:
            self.settings_proxy_switch.deselect()
        self.settings_proxy_host.delete(0, "end")
        self.settings_proxy_host.insert(0, s.get("proxy_host", "127.0.0.1"))
        self.settings_proxy_port.delete(0, "end")
        self.settings_proxy_port.insert(0, s.get("proxy_port", "7890"))
        exe = self.get_downloader_exe_path()
        ok = os.path.exists(exe)
        self.settings_tool_label.configure(
            text=f"N_m3u8DL-RE: {'已就绪' if ok else '未找到'}\n路径: {exe}",
            text_color=get_theme()["success"] if ok else get_theme()["danger"],
        )

    def _settings_browse(self):
        folder = filedialog.askdirectory()
        if folder:
            self.settings_save_entry.delete(0, "end")
            self.settings_save_entry.insert(0, folder)

    def _save_settings_from_page(self):
        settings = {
            "save_dir": self.settings_save_entry.get().strip(),
            "proxy_enabled": bool(self.settings_proxy_switch.get()),
            "proxy_host": self.settings_proxy_host.get().strip(),
            "proxy_port": self.settings_proxy_port.get().strip(),
            "theme": self._theme_mode,
        }
        self.store.save_settings(settings)
        self._apply_settings_to_form(settings)
        self.runtime_save_dir = settings["save_dir"]
        self._schedule_proxy_check()
        messagebox.showinfo("设置", "设置已保存")

    def set_theme(self, mode):
        self._theme_mode = mode
        apply_theme_mode(mode)
        self.store.save_settings({"theme": mode})
        self._update_theme_buttons()
        self.apply_theme_colors()

    def apply_theme_colors(self):
        t = get_theme()
        self.configure(fg_color=t["main_bg"])
        self.sidebar.configure(fg_color=t["sidebar_bg"])
        self.main.configure(fg_color=t["main_bg"])
        self.page_title_label.configure(text_color=t["text"])
        self.status_chip.configure(fg_color=t["pill_bg"], border_color=t["card_border"])
        self.proxy_pill.configure(fg_color=t["pill_bg"], border_color=t["card_border"])
        self.textbox.configure(fg_color=t["terminal_bg"], text_color=t["terminal_text"], border_color=t["card_border"])
        self._setup_log_tags()
        self.set_status(self._status_text)
        self._update_proxy_badges(self._proxy_status_text, self._proxy_status_color)
        self.show_page(self._current_page)

    def set_inputs_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for widget in self._input_widgets:
            try:
                widget.configure(state=state)
            except Exception:
                pass
        self.drag_list.set_enabled(enabled)
        if enabled:
            self._on_proxy_toggle_fields()
        else:
            self.entry_proxy_host.configure(state="disabled")
            self.entry_proxy_port.configure(state="disabled")

    def on_priority_change(self):
        self.log(f"优先级更新: {self.priority_data}")

    def _setup_log_tags(self):
        tw = self.textbox._textbox
        t = get_theme()
        tw.tag_config("info", foreground=t["terminal_text"])
        tw.tag_config("success", foreground=t["terminal_success"])
        tw.tag_config("warning", foreground=t["terminal_warn"])
        tw.tag_config("error", foreground=t["terminal_error"])

    def _detect_log_level(self, msg):
        if any(x in msg for x in ("错误", "失败", "异常", "缺失")):
            return "error"
        if any(x in msg for x in ("警告", "不足", "停止")):
            return "warning"
        if any(x in msg for x in ("成功", "完成", "就绪")):
            return "success"
        return "info"

    def log(self, msg, level=None):
        if threading.current_thread() is threading.main_thread():
            self._log_impl(msg, level)
        else:
            self.after(0, self._log_impl, msg, level)

    def _log_impl(self, msg, level=None):
        if not msg.strip():
            return
        if level is None:
            level = self._detect_log_level(msg)
        self.textbox.configure(state="normal")
        line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
        self.textbox._textbox.insert("end", line, level)
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def clear_log(self):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_save.delete(0, "end")
            self.entry_save.insert(0, folder)
            self.runtime_save_dir = folder
            self._persist_settings_from_home()

    def check_tools(self):
        exe_path = self.get_downloader_exe_path()
        if not os.path.exists(exe_path):
            self._tools_ok = False
            msg = f"未找到 N_m3u8DL-RE.exe，请将下载器放入程序目录。\n路径: {exe_path}"
            self.tool_warning_label.configure(text=msg)
            self.tool_warning_frame.pack(fill="x", pady=(0, 12))
            self.log(f"缺失 N_m3u8DL-RE.exe: {exe_path}", "error")
            self.btn_start.configure(state="disabled")
        else:
            self._tools_ok = True
            self.tool_warning_frame.pack_forget()
            self.log("N_m3u8DL-RE.exe 就绪", "success")

    def stop_task(self):
        if self.is_running:
            self.stop_event.set()
            self.preview_result = False
            self.set_status("停止中", get_theme()["warning"])
            self.log("正在停止...", "warning")
            self.user_action_event.set()
            self.preview_confirm_event.set()

    def set_status(self, text, color=None):
        t = get_theme()
        self._status_text = text
        if color is None:
            color_map = {
                "就绪": t["success"],
                "运行中": t["accent"],
                "等待确认": t["warning"],
                "停止中": t["warning"],
                "检测中...": t["text_sub"],
            }
            color = color_map.get(text, t["text_sub"])
        if hasattr(self, "status_chip_label"):
            self.status_chip_dot.configure(text_color=color)
            self.status_chip_label.configure(text=text, text_color=t["text"])

    def check_disk_space(self, path):
        import shutil
        try:
            drive = os.path.splitdrive(os.path.abspath(path))[0] or path
            total, used, free = shutil.disk_usage(drive)
            free_gb = free / (1024 ** 3)
            if free_gb < 5:
                self.log(f"磁盘 {drive} 空间不足 (<5GB)，剩余 {free_gb:.2f}GB", "warning")
                self.after(0, self.show_disk_full_dialog, drive, free_gb)
                self.user_action_event.clear()
                self.user_action_event.wait()
                return not self.stop_event.is_set()
            return True
        except Exception:
            return True

    def show_disk_full_dialog(self, drive, free_gb):
        if messagebox.askyesno("空间不足", f"磁盘 {drive} 剩余 {free_gb:.2f}GB。\n是否更换路径继续？"):
            new_dir = filedialog.askdirectory()
            if new_dir:
                self.entry_save.delete(0, "end")
                self.entry_save.insert(0, new_dir)
                self.runtime_save_dir = new_dir
                self.user_action_event.set()
            else:
                self.stop_event.set()
                self.user_action_event.set()
        else:
            self.stop_event.set()
            self.user_action_event.set()

    def show_preview_dialog_on_main_thread(self, summary_text, info_text):
        self.set_status("等待确认", get_theme()["warning"])
        PreviewDialog(
            self, "下载清单确认", summary_text, info_text,
            on_confirm=self.on_preview_confirm, on_cancel=self.on_preview_cancel,
        )

    def on_preview_confirm(self):
        self.preview_result = not self.stop_event.is_set()
        self.preview_confirm_event.set()

    def on_preview_cancel(self):
        self.preview_result = False
        self.preview_confirm_event.set()

    def _set_running_ui_impl(self):
        self.set_status("运行中", get_theme()["accent"])
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal", border_width=2, border_color=get_theme()["danger"])
        self.progress_bar.grid()
        self.progress_bar.start()
        self.set_inputs_enabled(False)
        self.clear_log()

    def _reset_ui_impl(self):
        self.is_running = False
        self.set_status("就绪", get_theme()["success"])
        self.btn_start.configure(state="normal" if self._tools_ok else "disabled")
        self.btn_stop.configure(state="disabled", border_width=0)
        try:
            self.progress_bar.stop()
        except Exception:
            pass
        self.progress_bar.grid_remove()
        self.set_inputs_enabled(True)
        self.refresh_all_ui()

    def reset_ui(self):
        if threading.current_thread() is threading.main_thread():
            self._reset_ui_impl()
        else:
            self.after(0, self._reset_ui_impl)

    def start_thread(self):
        if self.is_running:
            return
        enable_individual = bool(self.switch_individual.get())
        if self._current_mode == "link":
            target_url = self.entry_url.get().strip()
            if not target_url:
                messagebox.showerror("提示", "请输入链接！")
                return
            is_search_mode = False
        else:
            code = self.entry_code.get().strip()
            if not code:
                messagebox.showerror("提示", "请输入番号或名字！")
                return
            target_url = f"https://missav.ai/cn/search/{code}"
            is_search_mode = True
            self.log(f"搜索: {code}")

        self.runtime_save_dir = self.entry_save.get().strip()
        proxy_server = self.get_proxy_server()
        self._persist_settings_from_home()
        self._schedule_proxy_check()

        self.is_running = True
        self.stop_event.clear()
        batch_id = self.store.record_batch_start(target_url, is_search_mode, enable_individual)
        self.after(0, self.refresh_all_ui)
        self._set_running_ui_impl()

        t = threading.Thread(
            target=self.run_process,
            args=(target_url, is_search_mode, enable_individual, proxy_server, self.runtime_save_dir, batch_id),
            daemon=True,
        )
        t.start()

    def run_process(self, target_url, is_search_mode, enable_individual, proxy_server, save_dir, batch_id):
        raise NotImplementedError
