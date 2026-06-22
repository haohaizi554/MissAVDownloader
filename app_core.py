import os
import time
import subprocess
import re
import threading
import urllib.parse
from collections import defaultdict

from playwright.sync_api import sync_playwright

from hls_local_proxy import HlsLocalProxy, is_curl_cffi_available, should_use_local_hls_proxy


class MissAVDownloaderMixin:
    """Shared crawl/download logic; mixed into AppBase subclasses."""

    def setup_playwright_env(self):
        """Override in packaged build to set PLAYWRIGHT_BROWSERS_PATH."""
        pass

    def _refresh_state_ui(self):
        self.after(0, self.refresh_all_ui)

    def get_score(self, url, title, verified_chinese_urls):
        url_lower = url.lower()
        is_uncensored = "uncensored" in url_lower or "leak" in url_lower or "无码" in title.lower()
        is_english = "english" in url_lower or "英文字幕" in title.lower()
        is_chinese = (
            (url in verified_chinese_urls) or ("chinese" in url_lower) or ("中文字幕" in title.lower())
        )
        if is_uncensored:
            is_chinese = False
        feature_map = {
            "中文": is_chinese,
            "英文": is_english,
            "无码": is_uncensored,
            "普通": (not is_chinese and not is_english and not is_uncensored),
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
            if match:
                return match.group(1).upper()
        except Exception:
            pass
        return None

    def classify_tag(self, url, title, verified_chinese_urls):
        is_uncensored = "uncensored" in url.lower() or "leak" in url.lower() or "无码" in title.lower()
        is_chinese = (
            (url in verified_chinese_urls) or ("chinese" in url.lower()) or ("中文字幕" in title.lower())
        )
        if is_uncensored:
            is_chinese = False
        is_english = "english" in url.lower() or "英文字幕" in title.lower()
        if is_chinese:
            return "中文字幕"
        if is_english:
            return "英文字幕"
        if is_uncensored:
            return "无码流出"
        return "普通"

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

    def run_process(self, target_url, is_search_mode, enable_individual, proxy_server, save_dir, batch_id):
        my_ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.setup_playwright_env()
        self.store.set_batch_status("crawling", batch_id=batch_id)
        self._refresh_state_ui()
        self.log(f"启动: {target_url}")
        if enable_individual:
            self.log("启用单体筛选")
        scraped_data = {}
        verified_chinese_urls = set()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
                    proxy={"server": proxy_server} if proxy_server else None,
                    args=['--disable-blink-features=AutomationControlled'],
                )
                context = browser.new_context(user_agent=my_ua)
                page = context.new_page()
                page.goto(target_url, timeout=60000)

                if is_search_mode:
                    self.log("等待搜索结果...")
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
                            self.log(f"跳转演员主页: {actress_href}")
                            valid_actress_link.click()
                            page.wait_for_load_state('domcontentloaded')
                            target_url = page.url
                        else:
                            self.log("未发现演员头像，按视频列表处理。")
                    except Exception as e:
                        self.log(f"导航检测出错: {e}", "warning")

                if enable_individual and "/actresses/" in page.url:
                    current_url = page.url
                    if "filters=individual" not in current_url:
                        sep = "&" if "?" in current_url else "?"
                        target_url = f"{current_url}{sep}filters=individual"
                        self.log(f"切换单体模式: {target_url}")
                        page.goto(target_url, timeout=60000)
                    else:
                        target_url = page.url

                base_url_main = target_url
                self.log("--- 第一遍遍历 (获取视频) ---")
                current_page = 1
                code_pattern = re.compile(r'/cn/.*[a-zA-Z]+-\d+')
                while not self.stop_event.is_set():
                    if "page=" in base_url_main:
                        page_url = re.sub(r'page=\d+', f'page={current_page}', base_url_main)
                    else:
                        sep = "&" if "?" in base_url_main else "?"
                        page_url = f"{base_url_main}{sep}page={current_page}"
                    self.log(f"扫描第 {current_page} 页...")
                    try:
                        if current_page > 1:
                            page.goto(page_url, timeout=60000)
                        page.wait_for_selector("div.grid", timeout=10000)
                    except Exception:
                        self.log("主列表扫描结束。", "warning")
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
                    self.log(f"   新增 {count} 个")
                    if not page.query_selector("a[rel='next']"):
                        break
                    current_page += 1
                    time.sleep(1)

                self.log("\n--- 第二遍遍历 (中文校验) ---")
                chinese_base_url = ""
                if "/actresses/" in base_url_main or "filters=" in base_url_main:
                    if "filters=" in base_url_main:
                        if "chinese-subtitle" not in base_url_main:
                            chinese_base_url = base_url_main.replace("filters=", "filters=chinese-subtitle,")
                            chinese_base_url = chinese_base_url.replace("individual,", "individual,")
                        else:
                            chinese_base_url = base_url_main
                    else:
                        sep = "&" if "?" in base_url_main else "?"
                        chinese_base_url = f"{base_url_main}{sep}filters=chinese-subtitle"
                elif "/search/" in base_url_main:
                    try:
                        raw_keyword = base_url_main.split("/search/")[1].split("?")[0]
                        search_keyword = urllib.parse.unquote(raw_keyword)
                        new_keyword = f"{search_keyword} 中文字幕"
                        self.log(f"尝试搜索中文关键词: {new_keyword}")
                        chinese_base_url = f"https://missav.ai/cn/search/{new_keyword}"
                    except Exception:
                        pass

                if chinese_base_url:
                    chinese_base_url = re.sub(r'[?&]page=\d+', '', chinese_base_url)
                    self.log(f"校验链接: {chinese_base_url}")
                    current_page = 1
                    while not self.stop_event.is_set():
                        sep = "&" if "?" in chinese_base_url else "?"
                        page_url = f"{chinese_base_url}{sep}page={current_page}"
                        self.log(f"校验第 {current_page} 页...")
                        try:
                            page.goto(page_url, timeout=60000)
                            page.wait_for_selector("div.grid", timeout=10000)
                        except Exception:
                            self.log("中文列表扫描结束。", "warning")
                            break
                        items = self.scrape_page_videos(page)
                        new_cn = 0
                        for item in items:
                            verified_chinese_urls.add(item['url'])
                            if item['url'] not in scraped_data:
                                scraped_data[item['url']] = item['title']
                            new_cn += 1
                        self.log(f"   记录 {new_cn} 个中文链接")
                        if not page.query_selector("a[rel='next']"):
                            break
                        current_page += 1
                        time.sleep(1)
                browser.close()
        except Exception as e:
            self.log(f"爬取错误: {e}", "error")
            self.store.finish_batch("failed", batch_id=batch_id)
            self._refresh_state_ui()
            self.reset_ui()
            return

        if self.stop_event.is_set():
            self.log("任务已停止。", "warning")
            self.store.finish_batch("stopped", batch_id=batch_id)
            self._refresh_state_ui()
            self.reset_ui()
            return

        self.log(f"\n智能筛选中 ({len(scraped_data)} 个)...")
        grouped = defaultdict(list)
        for link, title in scraped_data.items():
            code = self.clean_code(link)
            if code:
                grouped[code].append((link, title))

        final_list = []
        preview_text = ""
        tag_counts = defaultdict(int)
        for i, (code, item_list) in enumerate(grouped.items()):
            sorted_items = sorted(
                item_list,
                key=lambda x: self.get_score(x[0], x[1], verified_chinese_urls),
                reverse=True,
            )
            best_url, best_title = sorted_items[0]
            final_list.append((best_url, best_title))
            tag = self.classify_tag(best_url, best_title, verified_chinese_urls)
            tag_counts[tag] += 1
            title_str = f"   {best_title}\n" if best_title else ""
            preview_text += f"{i + 1}. [{code}] {tag}\n{title_str}   {best_url}\n\n"

        self.log(f"筛选完成，共 {len(final_list)} 部", "success")

        if len(final_list) > 0:
            queue_items = []
            for url, title in final_list:
                code = self.clean_code(url) or "UNKNOWN"
                queue_items.append({"code": code, "title": title, "url": url, "status": "pending"})
            self.store.set_queue(queue_items)
            self._refresh_state_ui()

            summary_parts = [f"共 {len(final_list)} 部待下载"]
            for tag in ("中文字幕", "英文字幕", "无码流出", "普通"):
                if tag_counts[tag]:
                    summary_parts.append(f"{tag} {tag_counts[tag]}")
            summary_text = "  ·  ".join(summary_parts)

            self.log("等待确认...")
            self.preview_result = False
            self.preview_confirm_event.clear()
            self.after(0, self.show_preview_dialog_on_main_thread, summary_text, preview_text)
            self.preview_confirm_event.wait()

            if self.stop_event.is_set() or not self.preview_result:
                self.log("用户取消或已停止。", "warning")
                self.store.finish_batch("stopped", batch_id=batch_id)
                self._refresh_state_ui()
                self.reset_ui()
                return
            self.log("开始下载...", "success")
            self.store.set_batch_status("downloading", batch_id=batch_id)
            self._refresh_state_ui()
        else:
            self.log("无有效视频。", "error")
            self.store.finish_batch("failed", batch_id=batch_id)
            self._refresh_state_ui()
            self.reset_ui()
            return

        for i, (url, title_text) in enumerate(final_list):
            if self.stop_event.is_set():
                break
            code = self.clean_code(url) or "UNKNOWN"
            current_save_dir = self.runtime_save_dir
            if not os.path.exists(current_save_dir):
                try:
                    os.makedirs(current_save_dir)
                except Exception:
                    pass
            if not self.check_disk_space(current_save_dir):
                break
            current_save_dir = self.runtime_save_dir
            self.store.update_queue_item(code, "running", batch_id=batch_id)
            self._refresh_state_ui()
            self.log(f"\n[{i + 1}/{len(final_list)}] 处理: {code}")
            success = self.download_single(url, title_text, current_save_dir, proxy_server, my_ua, verified_chinese_urls)
            if success:
                self.store.update_queue_item(code, "done", batch_id=batch_id)
                self.store.record_download_success(code, title_text, url, current_save_dir)
            else:
                self.store.update_queue_item(code, "failed", batch_id=batch_id)
                self.store.record_download_fail(code, title_text, url, current_save_dir)
            self._refresh_state_ui()
            for _ in range(3):
                if self.stop_event.is_set():
                    break
                time.sleep(1)

        if self.stop_event.is_set():
            self.store.finish_batch("stopped", batch_id=batch_id)
        else:
            self.store.finish_batch("done", batch_id=batch_id)
        self.log("\n任务结束！", "success")
        self._refresh_state_ui()
        self.reset_ui()

    def download_single(self, url, original_title, save_dir, proxy, ua, verified_chinese_urls):
        code_name = self.clean_code(url) or "UNKNOWN"
        hls_proxy = None
        progress_stop = threading.Event()
        progress_thread = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=False,
                    proxy={"server": proxy} if proxy else None,
                    args=['--disable-blink-features=AutomationControlled'],
                )
                context = browser.new_context(user_agent=ua)
                page = context.new_page()

                final_url = None

                def handle_request(req):
                    nonlocal final_url
                    if "playlist.m3u8" in req.url:
                        final_url = req.url
                        self.log("   捕获正片链接", "success")

                def on_popup(popup):
                    if popup != page:
                        try:
                            popup.close()
                        except Exception:
                            pass

                context.on("page", on_popup)
                page.on("request", handle_request)
                page.goto(url, timeout=60000)
                page_title = page.title().replace("| MissAV", "").strip()
                if not page_title:
                    page_title = original_title
                safe_title = "".join([c for c in page_title if c not in r'\/:*?"<>|']).strip()
                if "Just a moment" in page.title():
                    self.log("   触发验证，等待 10s...", "warning")
                    time.sleep(10)
                try:
                    page.wait_for_selector(".plyr", timeout=5000)
                    page.mouse.click(400, 300)
                    time.sleep(2)
                    if not final_url:
                        page.mouse.click(400, 300)
                except Exception:
                    pass
                for _ in range(15):
                    if final_url:
                        break
                    time.sleep(1)

                cookies = {c["name"]: c["value"] for c in context.cookies()}
                browser.close()

                if not final_url:
                    self.log("   无法获取视频链接", "error")
                    return False

                tag = self.classify_tag(url, original_title, verified_chinese_urls)
                suffix_map = {
                    "中文字幕": " [中文字幕]",
                    "英文字幕": " [英文字幕]",
                    "无码流出": " [无码]",
                }
                suffix = suffix_map.get(tag, "")
                if code_name in safe_title.upper():
                    file_name = f"{safe_title}{suffix}"
                else:
                    file_name = f"{code_name} {safe_title}{suffix}"
                if len(file_name) > 220:
                    file_name = file_name[:220]

                download_url = final_url
                use_local_proxy = should_use_local_hls_proxy(final_url)
                if use_local_proxy and is_curl_cffi_available():
                    hls_proxy = HlsLocalProxy(
                        referer=url,
                        user_agent=ua,
                        cookies=cookies,
                        external_proxy=proxy,
                    )
                    hls_proxy.start()
                    download_url = hls_proxy.wrap(final_url)
                    self.log("   启用本地 HLS 代理 (curl_cffi -> N_m3u8DL-RE)", "success")
                    self.log(f"   Trace ID: {hls_proxy.trace_id} | 线程数: 16", "info")
                    self.log(f"   原始 URL: {final_url[:100]}...", "info")
                    self.log(f"   代理 URL: {download_url}", "info")
                    progress_thread = threading.Thread(
                        target=self._monitor_hls_proxy_progress,
                        args=(hls_proxy, progress_stop),
                        daemon=True,
                    )
                    progress_thread.start()
                elif use_local_proxy:
                    self.log("   curl_cffi 未安装，回退直连（surrit 可能 403）", "warning")
                    self.log(f"   原始 URL: {final_url[:100]}...", "info")
                else:
                    self.log(f"   直连下载: {final_url[:100]}...", "info")

                self.log(f"   启动外部下载器: {file_name}")
                cmd = [
                    self.get_downloader_exe_path(), download_url,
                    "--save-dir", save_dir, "--save-name", file_name,
                    "--thread-count", "16", "--download-retry-count", "10",
                    "--auto-select", "true",
                    "--mux-after-done", "format=mp4", "--no-log",
                ]
                if not hls_proxy:
                    cmd.extend([
                        "--header", f"User-Agent: {ua}",
                        "--header", f"Referer: {url}",
                    ])
                process = subprocess.run(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
                progress_stop.set()
                if progress_thread:
                    progress_thread.join(timeout=1)
                if hls_proxy:
                    stats = hls_proxy.get_stats()
                    mb = stats["bytes_served"] / (1024 * 1024)
                    self.log(
                        f"   代理统计: {mb:.1f} MB 已转发, 分片 {stats['segments_served']}",
                        "info",
                    )
                if process.returncode == 0:
                    self.log("   下载成功", "success")
                    return True
                self.log("   下载失败", "error")
                return False
        except Exception as e:
            self.log(f"   异常: {e}", "error")
            return False
        finally:
            progress_stop.set()
            if hls_proxy:
                hls_proxy.stop()

    def _monitor_hls_proxy_progress(self, hls_proxy, stop_event):
        last_bytes = 0
        while not stop_event.is_set():
            stats = hls_proxy.get_stats()
            bytes_served = stats["bytes_served"]
            if bytes_served > last_bytes:
                mb = bytes_served / (1024 * 1024)
                self.log(
                    f"   代理转发: {mb:.1f} MB | 分片 {stats['segments_served']}",
                    "info",
                )
                last_bytes = bytes_served
            stop_event.wait(2)
