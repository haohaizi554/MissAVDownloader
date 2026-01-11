import os
import time
import subprocess
import re  # 引入正则模块
from playwright.sync_api import sync_playwright
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

def download_single_video(url, index, total):
    """阶段二：下载单个视频 (独立启动浏览器)"""
    print(f"\n🎬 [{index}/{total}] 正在处理: {url}")
    
    # 【修正】每次下载都重新启动一个新的 Playwright 实例，互不干扰
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, 
            proxy={"server": PROXY_SERVER} if PROXY_SERVER else None,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(user_agent=MY_USER_AGENT)
        page = context.new_page()
        
        # 广告杀手
        def on_new_page(popup):
            if popup != page:
                try: popup.close()
                except: pass
        context.on("page", on_new_page)

        final_url = None

        def handle_request(request):
            nonlocal final_url
            req_url = request.url
            # 只抓 playlist.m3u8
            if "playlist.m3u8" in req_url:
                print(f"   🎯 捕获正片链接!")
                final_url = req_url

        page.on("request", handle_request)

        try:
            page.goto(url, timeout=60000)
            
            # 尝试点击播放
            try: page.mouse.click(400, 300) 
            except: pass
            time.sleep(2)
            if not final_url:
                try: page.mouse.click(400, 300)
                except: pass

            # 等待捕获
            for i in range(20):
                if final_url: break
                time.sleep(1)

            if final_url:
                title = page.title().replace("| MissAV", "").strip()
                safe_title = "".join([c for c in title if c not in r'\/:*?"<>|']).strip()
                if not safe_title: safe_title = f"video_{int(time.time())}"

                print(f"   ⚡ 启动下载: {safe_title}")
                
                if not os.path.exists(SAVE_DIR):
                    os.makedirs(SAVE_DIR)

                cmd = [
                    "N_m3u8DL-RE.exe",
                    final_url,
                    "--save-dir", SAVE_DIR,
                    "--save-name", safe_title,
                    "--thread-count", "16",
                    "--download-retry-count", "10",
                    "--auto-select", "true",
                    "--header", f"User-Agent: {MY_USER_AGENT}",
                    "--header", f"Referer: {url}",
                    "--mux-after-done", "format=mp4",
                    "--no-log"
                ]
                subprocess.run(cmd)
                print(f"   ✅ 下载完成")
            else:
                print("   ❌ 抓取失败 (超时或无资源)")

        except Exception as e:
            print(f"   ❌ 处理出错: {e}")
        finally:
            browser.close()

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
