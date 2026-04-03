import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import time
import subprocess
import re
import threading
import shutil
import urllib.parse
from collections import defaultdict
from playwright.sync_api import sync_playwright

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
# ================= 🎨 UI 主题配置 =================
THEME = {
    "bg": "#1A1A1A", "card_bg": "#252525", "accent": "#3B8ED0", 
    "text": "#E0E0E0", "text_sub": "#AAAAAA", 
    "success": "#2CC985", "danger": "#C92C2C", 
    "input_bg": "#181818", "list_item": "#333333", "list_item_hover": "#3E3E3E"
}
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")
# ================= 弹窗：预浏览清单 =================
class PreviewDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, info_text, on_confirm, on_cancel):
        super().__init__(parent)
        self.title(title)
        self.geometry("900x700")
        self.resizable(True, True)
        self.attributes("-topmost", True)
        self.configure(fg_color=THEME["bg"])
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self, text="📋 下载清单确认", font=("微软雅黑", 18, "bold"), text_color=THEME["text"]).grid(row=0, column=0, pady=(20, 10))  
        self.textbox = ctk.CTkTextbox(self, font=("Consolas", 11), fg_color=THEME["input_bg"], text_color=THEME["text"], corner_radius=10)
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=20, pady=5)
        self.textbox.insert("1.0", info_text)
        self.textbox.configure(state="disabled")
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=20)
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(btn_frame, text="取消任务", fg_color=THEME["danger"], hover_color="#992222", height=45, command=self.cancel).grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(btn_frame, text="确认下载", fg_color=THEME["success"], hover_color="#229964", height=45, command=self.confirm).grid(row=0, column=1, sticky="ew", padx=(10, 0))
    def confirm(self):
        self.on_confirm()
        self.destroy()
    def cancel(self):
        self.on_cancel()
        self.destroy()
# ================= 拖拽列表项 =================
class DraggableList(ctk.CTkFrame):
    def __init__(self, master, items, update_callback, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.items = items 
        self.update_callback = update_callback
        self.buttons = []
        self.drag_start_idx = None
        self.render_items()
    def render_items(self):
        for btn in self.buttons: btn.destroy()
        self.buttons = []
        for idx, text in enumerate(self.items):
            btn = ctk.CTkButton(
                self, text=f" :: {text}", anchor="w", height=45, corner_radius=8,
                fg_color=THEME["list_item"], hover_color=THEME["list_item_hover"], 
                border_width=1, border_color="#404040", font=("微软雅黑", 13), text_color=THEME["text"]
            )
            btn.pack(fill="x", pady=4)
            btn.bind("<Button-1>", lambda e, b=btn: self.on_start(e, b))
            btn.bind("<B1-Motion>", lambda e, b=btn: self.on_drag(e, b))
            btn.bind("<ButtonRelease-1>", lambda e, b=btn: self.on_stop(e, b))
            btn.configure(cursor="hand2")
            self.buttons.append(btn)
    def on_start(self, event, widget):
        self.drag_start_idx = self.buttons.index(widget)
        widget.configure(fg_color="#202020", border_color=THEME["accent"], border_width=2)
    def on_drag(self, event, widget):
        if self.drag_start_idx is None: return
        root_y = widget.winfo_rooty() + event.y
        target_idx = -1
        for idx, btn in enumerate(self.buttons):
            if btn.winfo_rooty() <= root_y <= btn.winfo_rooty() + btn.winfo_height():
                target_idx = idx
                break
        if target_idx != -1 and target_idx != self.drag_start_idx:
            self.items[self.drag_start_idx], self.items[target_idx] = self.items[target_idx], self.items[self.drag_start_idx]
            self.buttons[self.drag_start_idx].configure(text=f" :: {self.items[self.drag_start_idx]}")
            self.buttons[target_idx].configure(text=f" :: {self.items[target_idx]}")
            self.buttons[self.drag_start_idx].configure(fg_color=THEME["list_item"], border_color="#404040", border_width=1)
            self.buttons[target_idx].configure(fg_color="#202020", border_color=THEME["accent"], border_width=2)
            self.drag_start_idx = target_idx
            if self.update_callback: self.update_callback()
    def on_stop(self, event, widget):
        if self.drag_start_idx is not None:
            for btn in self.buttons: 
                btn.configure(fg_color=THEME["list_item"], border_color="#404040", border_width=1)
            self.drag_start_idx = None
# ================= 主应用程序 =================
class MissAVDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MissAV 智能下载终端")
        self.geometry("1200x900")
        self.configure(fg_color=THEME["bg"])
        self.is_running = False
        self.stop_event = threading.Event()
        self.user_action_event = threading.Event()
        self.preview_confirm_event = threading.Event()
        self.preview_result = False
        self.priority_data = ["中文字幕", "英文字幕", "无码流出", "普通版"]
        self.grid_columnconfigure(0, weight=4, minsize=450)
        self.grid_columnconfigure(1, weight=6, minsize=500)
        self.grid_rowconfigure(0, weight=1)
        self.build_ui()
        self.check_tools()
    def build_ui(self):
        left_panel = ctk.CTkFrame(self, fg_color="transparent")
        left_panel.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)        
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(1, weight=1)
        left_panel.grid_rowconfigure(2, weight=0)
        left_panel.grid_rowconfigure(3, weight=0)
        ctk.CTkLabel(left_panel, text="MissAV Downloader", font=("微软雅黑", 24, "bold"), text_color=THEME["text"]).grid(row=0, column=0, sticky="w", pady=(0, 15))
        self.config_card = ctk.CTkFrame(left_panel, fg_color=THEME["card_bg"], corner_radius=12)
        self.config_card.grid(row=1, column=0, sticky="nsew", pady=(0, 15))
        self.setup_config_ui()
        self.priority_card = ctk.CTkFrame(left_panel, fg_color=THEME["card_bg"], corner_radius=12)
        self.priority_card.grid(row=2, column=0, sticky="ew", pady=(0, 15))
        self.setup_priority_ui()
        self.action_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        self.action_frame.grid(row=3, column=0, sticky="ew")
        self.action_frame.grid_columnconfigure(0, weight=1)
        self.action_frame.grid_columnconfigure(1, weight=1) 
        self.btn_start = ctk.CTkButton(self.action_frame, text="🚀 立即执行", font=("微软雅黑", 16, "bold"), height=55, corner_radius=8, fg_color=THEME["success"], hover_color="#229964", command=self.start_thread)
        self.btn_start.grid(row=0, column=0, sticky="ew", padx=(0, 5))      
        self.btn_stop = ctk.CTkButton(self.action_frame, text="🛑 强制停止", font=("微软雅黑", 16, "bold"), height=55, corner_radius=8, fg_color=THEME["danger"], hover_color="#992222", state="disabled", command=self.stop_task)
        self.btn_stop.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        right_panel = ctk.CTkFrame(self, fg_color=THEME["card_bg"], corner_radius=12)
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(0, 20), pady=20)
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=1)   
        ctk.CTkLabel(right_panel, text=">_ 系统终端", font=("Consolas", 14, "bold"), text_color=THEME["accent"]).grid(row=0, column=0, sticky="w", padx=20, pady=15)        
        self.textbox = ctk.CTkTextbox(right_panel, font=("Consolas", 10), fg_color="#111111", text_color="#00FF00", activate_scrollbars=True, corner_radius=8)
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.textbox.configure(state="disabled")
    def setup_config_ui(self):
        self.config_card.grid_columnconfigure(0, weight=1)
        pad = ctk.CTkFrame(self.config_card, fg_color="transparent")
        pad.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        pad.grid_columnconfigure(0, weight=1)
        self.mode_tabs = ctk.CTkTabview(pad, height=140, corner_radius=8, fg_color=THEME["input_bg"], segmented_button_selected_color=THEME["accent"])
        self.mode_tabs.grid(row=0, column=0, sticky="ew", pady=(0, 15))        
        self.tab_url = self.mode_tabs.add("🔗 链接模式")
        self.tab_search = self.mode_tabs.add("🔍 搜索模式")
        self.tab_url.grid_columnconfigure(0, weight=1)
        self.entry_url = ctk.CTkEntry(self.tab_url, placeholder_text="粘贴链接...", height=45, border_width=0, fg_color="#252525", font=("Consolas", 12))
        self.entry_url.insert(0, "https://missav.ai/dm24/cn/actresses/%E5%A4%A9%E9%9F%B3%E5%94%AF")
        self.entry_url.grid(row=0, column=0, sticky="ew", padx=10, pady=15)
        self.tab_search.grid_columnconfigure(0, weight=1)
        self.entry_code = ctk.CTkEntry(self.tab_search, placeholder_text="输入番号/名字...", height=45, border_width=0, fg_color="#252525", font=("Consolas", 12))
        self.entry_code.grid(row=0, column=0, sticky="ew", padx=10, pady=15)
        bottom_box = ctk.CTkFrame(pad, fg_color="transparent")
        bottom_box.grid(row=1, column=0, sticky="ew")
        bottom_box.grid_columnconfigure(0, weight=1)
        self.switch_individual = ctk.CTkSwitch(bottom_box, text="仅下载单体作品", font=("微软雅黑", 13), text_color=THEME["accent"], progress_color=THEME["accent"])
        self.switch_individual.grid(row=0, column=0, sticky="w", pady=(0, 15))
        grid_box = ctk.CTkFrame(bottom_box, fg_color="transparent")
        grid_box.grid(row=1, column=0, sticky="ew")
        grid_box.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(grid_box, text="保存:", text_color=THEME["text_sub"], width=40, anchor="w").grid(row=0, column=0, sticky="w")
        path_box = ctk.CTkFrame(grid_box, fg_color="transparent")
        path_box.grid(row=0, column=1, sticky="ew", padx=5)
        path_box.grid_columnconfigure(0, weight=1)
        self.entry_save = ctk.CTkEntry(path_box, height=38, border_width=0, fg_color=THEME["input_bg"], font=("Consolas", 11))
        self.entry_save.insert(0, os.path.join(os.path.expanduser("~"), "Desktop", "MissAV_Download"))
        self.entry_save.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(path_box, text="📂", width=38, height=38, fg_color=THEME["input_bg"], hover_color="#404040", command=self.select_folder).grid(row=0, column=1, padx=(5,0))
        ctk.CTkLabel(grid_box, text="代理:", text_color=THEME["text_sub"], width=40, anchor="w").grid(row=1, column=0, sticky="w", pady=(10, 0))
        proxy_box = ctk.CTkFrame(grid_box, fg_color="transparent")
        proxy_box.grid(row=1, column=1, sticky="w", padx=5, pady=(10, 0))
        self.entry_proxy = ctk.CTkEntry(proxy_box, width=90, height=38, border_width=0, fg_color=THEME["input_bg"], font=("Consolas", 11))
        self.entry_proxy.insert(0, "7890")
        self.entry_proxy.pack(side="left")
        ctk.CTkLabel(proxy_box, text="HTTP 127.0.0.1", text_color="gray", font=("Arial", 11)).pack(side="left", padx=10)
    def setup_priority_ui(self):
        self.priority_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.priority_card, text="智能筛选优先级", font=("微软雅黑", 14, "bold"), text_color=THEME["text"]).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))
        self.drag_list = DraggableList(self.priority_card, self.priority_data, self.on_priority_change)
        self.drag_list.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
    def on_priority_change(self):
        self.log(f"🔁 优先级更新: {self.priority_data}")
    def log(self, msg):
        self.textbox.configure(state="normal")
        if msg.strip():
            self.textbox.insert("end", f"[{time.strftime('%H:%M:%S')}] {msg}\n")
            self.textbox.see("end")
        self.textbox.configure(state="disabled")
        self.update_idletasks()
    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.entry_save.delete(0, "end")
            self.entry_save.insert(0, folder)
    def check_tools(self):
        n_m3u8dl_re_path = get_resource_path("N_m3u8DL-RE.exe")
        if not os.path.exists(n_m3u8dl_re_path):
            self.log(f"❌ 缺失 N_m3u8DL-RE.exe 或路径不正确: {n_m3u8dl_re_path}")
            self.btn_start.configure(state="disabled")
        else:
            self.log(f"✅ N_m3u8DL-RE.exe 已找到: {n_m3u8dl_re_path}")
    def stop_task(self):
        if self.is_running:
            self.stop_event.set()
            self.log("🛑 正在停止...")
            self.user_action_event.set()
            self.preview_confirm_event.set()
    def check_disk_space(self, path):
        try:
            drive = os.path.splitdrive(os.path.abspath(path))[0]
            if not drive: drive = path
            total, used, free = shutil.disk_usage(drive)
            free_gb = free / (1024**3)
            if free_gb < 5:
                self.log(f"⚠️ 磁盘 {drive} 空间不足 (<5GB)！")
                self.after(0, self.show_disk_full_dialog, drive, free_gb)
                self.user_action_event.clear()
                self.user_action_event.wait()
                if self.stop_event.is_set(): return False
                return True
            return True
        except: return True
    def show_disk_full_dialog(self, drive, free_gb):
        if messagebox.askyesno("空间不足", f"磁盘 {drive} 剩余 {free_gb:.2f}GB。\n是否更换路径继续？"):
            new_dir = filedialog.askdirectory()
            if new_dir:
                self.entry_save.delete(0, "end")
                self.entry_save.insert(0, new_dir)
                self.user_action_event.set()
            else:
                self.stop_event.set()
                self.user_action_event.set()
        else:
            self.stop_event.set()
            self.user_action_event.set()
    def show_preview_dialog_on_main_thread(self, info_text):
        PreviewDialog(self, "下载清单确认", info_text, on_confirm=self.on_preview_confirm, on_cancel=self.on_preview_cancel)
    def on_preview_confirm(self):
        self.preview_result = True
        self.preview_confirm_event.set()
    def on_preview_cancel(self):
        self.preview_result = False
        self.preview_confirm_event.set()
    def start_thread(self):
        if self.is_running: return
        current_tab = self.mode_tabs.get()
        target_url = ""
        is_search_mode = False
        enable_individual = bool(self.switch_individual.get())
        if current_tab == "🔗 链接模式":
            target_url = self.entry_url.get().strip()
            if not target_url:
                messagebox.showerror("提示", "请输入链接！")
                return
        else:
            code = self.entry_code.get().strip()
            if not code:
                messagebox.showerror("提示", "请输入番号或名字！")
                return
            target_url = f"https://missav.ai/cn/search/{code}"
            is_search_mode = True
            self.log(f"🔍 搜索: {code}")
        self.is_running = True
        self.stop_event.clear()
        self.btn_start.configure(state="disabled", text="⚡ 运行中...", fg_color="#225544")
        self.btn_stop.configure(state="normal")
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")        
        t = threading.Thread(target=self.run_process, args=(target_url, is_search_mode, enable_individual), daemon=True)
        t.start()
    # === 核心逻辑：打分 ===
    def get_score(self, url, title, verified_chinese_urls):
        url_lower = url.lower()
        title_lower = title.lower()        
        is_uncensored = "uncensored" in url_lower or "leak" in url_lower or "无码" in title_lower
        is_english = "english" in url_lower or "英文字幕" in title_lower
        is_chinese = (url in verified_chinese_urls) or ("chinese" in url_lower) or ("中文字幕" in title_lower)        
        # 互斥锁
        if is_uncensored: is_chinese = False 
        feature_map = {
            "中文": is_chinese,
            "英文": is_english,
            "无码": is_uncensored,
            "普通": (not is_chinese and not is_english and not is_uncensored)
        }
        total = len(self.priority_data)
        for idx, name in enumerate(self.priority_data):
            score = (total - idx) * 20 
            for key, satisfies in feature_map.items():
                if key in name and satisfies:
                    return score
        return 0
    def clean_code(self, url):
        try:
            match = re.search(r'/cn/.*?([a-zA-Z]+-\d+)', url)
            if match: return match.group(1).upper()
        except: pass
        return None

    def scrape_page_videos(self, page):
        return page.evaluate('''() => {
            return Array.from(document.querySelectorAll('div.grid a')).map(a => {
                const img = a.querySelector('img');
                const title = img ? img.getAttribute('alt') : a.textContent.trim();
                return {
                    url: a.href,
                    title: title || "" 
                };
            });
        }''')
    def run_process(self, target_url, is_search_mode, enable_individual):
        proxy_port = self.entry_proxy.get().strip()
        proxy_server = f"http://127.0.0.1:{proxy_port}" if proxy_port else None
        my_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.log(f"🚀 启动: {target_url}")
        if enable_individual: self.log("⚙️ 启用单体筛选")
        scraped_data = {} 
        verified_chinese_urls = set()
        playwright_browsers_dir = get_resource_path("playwright")
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = playwright_browsers_dir
        self.log(f"Playwright 浏览器路径设置为: {playwright_browsers_dir}")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False, proxy={"server": proxy_server} if proxy_server else None, args=['--disable-blink-features=AutomationControlled'])
                context = browser.new_context(user_agent=my_ua)
                page = context.new_page()                
                page.goto(target_url, timeout=60000)                
                # 1. 智能导航
                if is_search_mode:
                    self.log("⏳ 等待搜索结果...")
                    time.sleep(3) 
                    try:
                        links = page.query_selector_all('a[href*="/actresses/"]')
                        valid_actress_link = None
                        for link in links:
                            href = link.get_attribute("href")
                            if "ranking" not in href and "search" not in href:
                                if link.is_visible():
                                    valid_actress_link = link
                                    break
                        if valid_actress_link:
                            actress_href = valid_actress_link.get_attribute("href")
                            self.log(f"✨ 跳转演员主页: {actress_href}")
                            valid_actress_link.click()
                            page.wait_for_load_state('domcontentloaded')
                            target_url = page.url 
                        else:
                            self.log("ℹ️ 未发现演员头像，按视频列表处理。")
                    except Exception as e: self.log(f"⚠️ 导航检测出错: {e}")
                # 2. 单体筛选 (主线)
                if enable_individual and "/actresses/" in page.url:
                    current_url = page.url
                    if "filters=individual" not in current_url:
                        sep = "&" if "?" in current_url else "?"
                        target_url = f"{current_url}{sep}filters=individual"
                        self.log(f"🔄 切换单体模式: {target_url}")
                        page.goto(target_url, timeout=60000)
                    else:
                        target_url = page.url                
                base_url_main = target_url
                # 3. 第一遍遍历 (抓取所有)
                self.log("--- 🏁 第一遍遍历 (获取视频) ---")
                current_page = 1
                code_pattern = re.compile(r'/cn/.*[a-zA-Z]+-\d+')                
                while not self.stop_event.is_set():
                    if "page=" in base_url_main:
                        page_url = re.sub(r'page=\d+', f'page={current_page}', base_url_main)
                    else:
                        sep = "&" if "?" in base_url_main else "?"
                        page_url = f"{base_url_main}{sep}page={current_page}"
                    self.log(f"📄 扫描第 {current_page} 页...")
                    try:
                        if current_page > 1: page.goto(page_url, timeout=60000)
                        page.wait_for_selector("div.grid", timeout=10000)
                    except:
                        self.log("⚠️ 主列表扫描结束。")
                        break                    
                    items = self.scrape_page_videos(page)
                    count = 0
                    for item in items:
                        link = item['url']
                        title = item['title']
                        if "/cn/" in link and code_pattern.search(link):
                            if not any(x in link for x in ['contact', 'dmca']):
                                if link not in scraped_data:
                                    scraped_data[link] = title
                                    count += 1
                    self.log(f"   └── 新增 {count} 个")
                    if not page.query_selector("a[rel='next']"): break
                    current_page += 1
                    time.sleep(1)
                # 4. 第二遍遍历 (中文校验) - 无差别执行
                self.log("\n--- 🇨🇳 第二遍遍历 (中文校验) ---")                
                chinese_base_url = ""
                search_keyword = ""                
                # 情况A: 演员页/分类页 (URL含 filters 或 actresses)
                if "/actresses/" in base_url_main or "filters=" in base_url_main:
                    if "filters=" in base_url_main:
                        if "chinese-subtitle" not in base_url_main:
                            # 叠加 filter
                            chinese_base_url = base_url_main.replace("filters=", "filters=chinese-subtitle,")
                            chinese_base_url = chinese_base_url.replace("individual,", "individual,") 
                        else:
                            chinese_base_url = base_url_main
                    else:
                        sep = "&" if "?" in base_url_main else "?"
                        chinese_base_url = f"{base_url_main}{sep}filters=chinese-subtitle"                
                # 情况B: 搜索页 (URL含 search)
                elif "/search/" in base_url_main:
                    try:
                        # 提取原始关键词
                        raw_keyword = base_url_main.split("/search/")[1].split("?")[0]
                        search_keyword = urllib.parse.unquote(raw_keyword)
                        # 构造新关键词
                        new_keyword = f"{search_keyword} 中文字幕"
                        self.log(f"🔍 尝试搜索中文关键词: {new_keyword}")
                        chinese_base_url = f"https://missav.ai/cn/search/{new_keyword}"
                    except: pass
                if chinese_base_url:
                    chinese_base_url = re.sub(r'[?&]page=\d+', '', chinese_base_url)
                    self.log(f"🔍 校验链接: {chinese_base_url}")                    
                    current_page = 1
                    while not self.stop_event.is_set():
                        # 搜索页翻页逻辑特殊 (直接拼page)
                        if "/search/" in chinese_base_url:
                             # MissAV 搜索页翻页通常是 url?page=2
                             sep = "&" if "?" in chinese_base_url else "?"
                             page_url = f"{chinese_base_url}{sep}page={current_page}"
                        else:
                             sep = "&" if "?" in chinese_base_url else "?"
                             page_url = f"{chinese_base_url}{sep}page={current_page}"
                        
                        self.log(f"📄 校验第 {current_page} 页...")
                        try:
                            page.goto(page_url, timeout=60000)
                            page.wait_for_selector("div.grid", timeout=10000)
                        except:
                            self.log("⚠️ 中文列表扫描结束。")
                            break
                        items = self.scrape_page_videos(page)
                        new_cn = 0
                        for item in items:
                            # 【核心】直接信任第二遍抓到的 URL
                            verified_chinese_urls.add(item['url'])
                            # 补录第一遍漏掉的
                            if item['url'] not in scraped_data:
                                scraped_data[item['url']] = item['title']
                            new_cn += 1
                        self.log(f"   └── 记录 {new_cn} 个中文链接")
                        if not page.query_selector("a[rel='next']"): break
                        current_page += 1
                        time.sleep(1)
                browser.close()
        except Exception as e:
            self.log(f"❌ 爬取错误: {e}")
            self.reset_ui()
            return
        if self.stop_event.is_set():
            self.log("🛑 任务已停止。")
            self.reset_ui()
            return
        # === 智能筛选 ===
        self.log(f"\n🧠 智能筛选中 ({len(scraped_data)} 个)...")
        grouped = defaultdict(list)
        for link, title in scraped_data.items():
            code = self.clean_code(link)
            if code: grouped[code].append((link, title))        
        final_list = []
        preview_text = ""
        for i, (code, item_list) in enumerate(grouped.items()):
            sorted_items = sorted(item_list, key=lambda x: self.get_score(x[0], x[1], verified_chinese_urls), reverse=True)
            best_url, best_title = sorted_items[0]
            final_list.append((best_url, best_title))            
            score = self.get_score(best_url, best_title, verified_chinese_urls)
            tag = "普通"           
            is_uncensored = "uncensored" in best_url.lower() or "leak" in best_url.lower() or "无码" in best_title.lower()
            is_chinese = (best_url in verified_chinese_urls) or ("chinese" in best_url.lower()) or ("中文字幕" in best_title.lower())
            if is_uncensored: is_chinese = False
            is_english = "english" in best_url.lower() or "英文字幕" in best_title.lower()
            if is_chinese: tag = "中文字幕"
            elif is_english: tag = "英文字幕"
            elif is_uncensored: tag = "无码流出"            
            title_str = f"   🎬 {best_title}\n" if best_title else ""
            preview_text += f"{i+1}. [{code}] {tag}\n{title_str}   🔗 {best_url}\n\n"
        self.log(f"✅ 筛选完成，共 {len(final_list)} 部")
        # === 预浏览 ===
        if len(final_list) > 0:
            self.log("⏸️ 等待确认...")
            self.preview_result = False
            self.preview_confirm_event.clear()
            self.after(0, self.show_preview_dialog_on_main_thread, preview_text)
            self.preview_confirm_event.wait()
            if not self.preview_result:
                self.log("❌ 用户取消。")
                self.reset_ui()
                return
            self.log("✅ 开始下载...")
        else:
            self.log("❌ 无有效视频。")
            self.reset_ui()
            return
        # === 下载 ===
        for i, (url, title_text) in enumerate(final_list):
            if self.stop_event.is_set(): break
            current_save_dir = self.entry_save.get().strip()
            if not os.path.exists(current_save_dir):
                try: os.makedirs(current_save_dir)
                except: pass
            if not self.check_disk_space(current_save_dir): break
            current_save_dir = self.entry_save.get().strip()            
            self.log(f"\n🎬 [{i+1}/{len(final_list)}] 处理: {self.clean_code(url)}")
            self.download_single(url, title_text, current_save_dir, proxy_server, my_ua, verified_chinese_urls)
            for _ in range(3):
                if self.stop_event.is_set(): break
                time.sleep(1)
        self.log("\n🎉 任务结束！")
        self.reset_ui()
    def download_single(self, url, original_title, save_dir, proxy, ua, verified_chinese_urls):
        code_name = self.clean_code(url) or "UNKNOWN"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False, proxy={"server": proxy} if proxy else None, args=['--disable-blink-features=AutomationControlled'])
                context = browser.new_context(user_agent=ua)
                page = context.new_page()
                
                final_url = None
                def handle_request(req):
                    nonlocal final_url
                    if "playlist.m3u8" in req.url:
                        final_url = req.url
                        self.log("   ✨ 捕获正片链接")
                def on_popup(popup):
                    if popup != page:
                        try: popup.close()
                        except: pass
                context.on("page", on_popup)
                page.on("request", handle_request)
                page.goto(url, timeout=60000)                
                page_title = page.title().replace("| MissAV", "").strip()
                if not page_title: page_title = original_title
                safe_title = "".join([c for c in page_title if c not in r'\/:*?"<>|']).strip()
                if "Just a moment" in page.title():
                    self.log("   ⚠️ 触发验证，等待 10s...")
                    time.sleep(10)                
                try:
                    page.wait_for_selector(".plyr", timeout=5000)
                    page.mouse.click(400, 300)
                    time.sleep(2)
                    if not final_url: page.mouse.click(400, 300)
                except: pass                
                for _ in range(15):
                    if final_url: break
                    time.sleep(1)                
                browser.close()               
                if final_url:
                    is_uncensored = "uncensored" in url.lower() or "leak" in url.lower() or "无码" in original_title.lower()
                    is_chinese = (url in verified_chinese_urls) or ("chinese" in url.lower()) or ("中文字幕" in original_title.lower())
                    if is_uncensored: is_chinese = False
                    is_english = "english" in url.lower() or "英文字幕" in original_title.lower()
                    suffix = ""
                    if is_chinese: suffix = " [中文字幕]"
                    elif is_english: suffix = " [英文字幕]"
                    elif is_uncensored: suffix = " [无码]"                    
                    if code_name in safe_title.upper():
                        file_name = f"{safe_title}{suffix}"
                    else:
                        file_name = f"{code_name} {safe_title}{suffix}"
                    if len(file_name) > 220: file_name = file_name[:220]                    
                    self.log(f"   ⚡ 启动外部下载器: {file_name}")                   
                    n_m3u8dl_re_exe_path = get_resource_path("N_m3u8DL-RE.exe")
                    cmd = [n_m3u8dl_re_exe_path, final_url, "--save-dir", save_dir, "--save-name", file_name, "--thread-count", "16", "--download-retry-count", "10", "--auto-select", "true", "--header", f"User-Agent: {ua}", "--header", f"Referer: {url}", "--mux-after-done", "format=mp4", "--no-log"]                   
                    process = subprocess.run(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    if process.returncode == 0: self.log("   ✅ 下载成功")
                    else: self.log("   ❌ 下载失败")
                else: self.log("   ❌ 无法获取视频链接")
        except Exception as e: self.log(f"   ❌ 异常: {e}")
    def reset_ui(self):
        self.is_running = False
        self.btn_start.configure(state="normal", text="🚀 立即执行", fg_color=THEME["success"])
        self.btn_stop.configure(state="disabled")
if __name__ == "__main__":
    app = MissAVDownloaderApp()
    app.mainloop()