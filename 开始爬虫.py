import os
import time
import subprocess
import re
import threading
from playwright.sync_api import sync_playwright

from hls_local_proxy import HlsLocalProxy, is_curl_cffi_available, should_use_local_hls_proxy
# ================= 配置区域 =================
# 老师的作品列表页
ACTRESS_URL = "https://missav.ai/dm24/cn/actresses/%E5%A4%A9%E9%9F%B3%E5%94%AF"
# 保存路径
SAVE_DIR = "D:/desktop/天音唯合集/"
# 代理
PROXY_SERVER = "http://127.0.0.1:7890" 
MY_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def get_all_video_links():
    """阶段一：爬取所有视频详情页链接 (独立启动浏览器)"""
    print("🚀 阶段一：正在扫描该老师的所有作品...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            proxy={"server": PROXY_SERVER} if PROXY_SERVER else None,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(user_agent=MY_USER_AGENT)
        page = context.new_page()
        video_urls = set()
        current_page = 1
        base_url = ACTRESS_URL.split('?')[0]
        code_pattern = re.compile(r'/cn/.*[a-zA-Z]+-\d+')
        
        try:
            while True:
                target_url = f"{base_url}?page={current_page}"
                print(f"📄 正在扫描第 {current_page} 页: {target_url}")
                
                page.goto(target_url, timeout=60000)
                
                try:
                    page.wait_for_selector("div.grid", timeout=10000)
                except:
                    print("⚠️ 没找到视频列表，可能是最后一页或加载失败。")
                    if current_page > 1: break
                
                links = page.evaluate('''() => {
                    const anchors = Array.from(document.querySelectorAll('div.grid a'));
                    return anchors.map(a => a.href).filter(href => href.includes('/cn/') && !href.includes('actresses'));
                }''')

                if not links:
                    print("✅ 扫描结束（当前页无视频）。")
                    break

                new_count = 0
                for link in links:
                    if link not in video_urls:
                        video_urls.add(link)
                        new_count += 1
                
                print(f"   └── 本页发现 {len(links)} 个视频，新增 {new_count} 个。")
                
                next_btn = page.query_selector("a[rel='next']")
                if not next_btn:
                    print("✅ 已到达最后一页。")
                    break
                
                current_page += 1
                time.sleep(2)

        except Exception as e:
            print(f"❌ 爬取列表出错: {e}")
        finally:
            browser.close()
            # 【关键】这里 with 结束，Playwright 会彻底关闭，释放资源
    
    return list(video_urls)


def _monitor_hls_proxy_progress(hls_proxy, stop_event):
    last_bytes = 0
    while not stop_event.is_set():
        stats = hls_proxy.get_stats()
        bytes_served = stats["bytes_served"]
        if bytes_served > last_bytes:
            mb = bytes_served / (1024 * 1024)
            print(f"   📡 代理转发: {mb:.1f} MB | 分片 {stats['segments_served']}")
            last_bytes = bytes_served
        stop_event.wait(2)


def download_single_video(url, index, total):
    """阶段二：下载单个视频 (独立启动浏览器)"""
    print(f"\n🎬 [{index}/{total}] 正在处理: {url}")

    hls_proxy = None
    progress_stop = threading.Event()
    progress_thread = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                proxy={"server": PROXY_SERVER} if PROXY_SERVER else None,
                args=['--disable-blink-features=AutomationControlled'],
            )
            context = browser.new_context(user_agent=MY_USER_AGENT)
            page = context.new_page()

            def on_new_page(popup):
                if popup != page:
                    try:
                        popup.close()
                    except Exception:
                        pass

            context.on("page", on_new_page)

            final_url = None

            def handle_request(request):
                nonlocal final_url
                if "playlist.m3u8" in request.url:
                    print("   🎯 捕获正片链接!")
                    final_url = request.url

            page.on("request", handle_request)

            page.goto(url, timeout=60000)
            try:
                page.mouse.click(400, 300)
            except Exception:
                pass
            time.sleep(2)
            if not final_url:
                try:
                    page.mouse.click(400, 300)
                except Exception:
                    pass
            for _ in range(20):
                if final_url:
                    break
                time.sleep(1)

            title = page.title().replace("| MissAV", "").strip()
            cookies = {c["name"]: c["value"] for c in context.cookies()}
            browser.close()

            if not final_url:
                print("   ❌ 抓取失败 (超时或无资源)")
                return

            safe_title = "".join([c for c in title if c not in r'\/:*?"<>|']).strip()
            if not safe_title:
                safe_title = f"video_{int(time.time())}"

            download_url = final_url
            use_local_proxy = should_use_local_hls_proxy(final_url)
            if use_local_proxy and is_curl_cffi_available():
                hls_proxy = HlsLocalProxy(
                    referer=url,
                    user_agent=MY_USER_AGENT,
                    cookies=cookies,
                    external_proxy=PROXY_SERVER,
                )
                hls_proxy.start()
                download_url = hls_proxy.wrap(final_url)
                print("   ✅ 启用本地 HLS 代理 (curl_cffi -> N_m3u8DL-RE)")
                print(f"   Trace ID: {hls_proxy.trace_id} | 线程数: 16")
                print(f"   原始 URL: {final_url[:100]}...")
                print(f"   代理 URL: {download_url}")
                progress_thread = threading.Thread(
                    target=_monitor_hls_proxy_progress,
                    args=(hls_proxy, progress_stop),
                    daemon=True,
                )
                progress_thread.start()
            elif use_local_proxy:
                print("   ⚠️ curl_cffi 未安装，回退直连（surrit 可能 403）")
                print(f"   原始 URL: {final_url[:100]}...")
            else:
                print(f"   直连下载: {final_url[:100]}...")

            print(f"   ⚡ 启动下载: {safe_title}")
            if not os.path.exists(SAVE_DIR):
                os.makedirs(SAVE_DIR)

            cmd = [
                "N_m3u8DL-RE.exe",
                download_url,
                "--save-dir", SAVE_DIR,
                "--save-name", safe_title,
                "--thread-count", "16",
                "--download-retry-count", "10",
                "--auto-select", "true",
                "--mux-after-done", "format=mp4",
                "--no-log",
            ]
            if not hls_proxy:
                cmd.extend([
                    "--header", f"User-Agent: {MY_USER_AGENT}",
                    "--header", f"Referer: {url}",
                ])
            result = subprocess.run(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)
            progress_stop.set()
            if progress_thread:
                progress_thread.join(timeout=1)
            if hls_proxy:
                stats = hls_proxy.get_stats()
                mb = stats["bytes_served"] / (1024 * 1024)
                print(f"   📊 代理统计: {mb:.1f} MB 已转发, 分片 {stats['segments_served']}")
            if result.returncode == 0:
                print("   ✅ 下载完成")
            else:
                print("   ❌ 下载失败")
    except Exception as e:
        print(f"   ❌ 处理出错: {e}")
    finally:
        progress_stop.set()
        if hls_proxy:
            hls_proxy.stop()

def main():
    if not os.path.exists("N_m3u8DL-RE.exe"):
        print("❌ 请把 N_m3u8DL-RE.exe 放到脚本旁边！")
        return

    # 【核心修正】
    # 1. 先执行爬取，此时会启动并关闭一次 Playwright
    # 注意：这里不再传入 p 参数
    all_links = get_all_video_links()
    
    print("\n" + "="*50)
    print(f"📊 统计完成：共找到 {len(all_links)} 部作品")
    print("="*50)
    
    if len(all_links) == 0:
        return

    # 2. 再执行循环下载，每次下载都会独立启动并关闭 Playwright
    # 这样就避免了“在循环里套循环”的错误
    for i, link in enumerate(all_links):
        download_single_video(link, i+1, len(all_links))
        print("⏳ 休息 5 秒，准备下一部...")
        time.sleep(5)

    print("\n🎉🎉🎉 所有任务全部完成！")
    input("按回车键退出...")

if __name__ == "__main__":
    main()
