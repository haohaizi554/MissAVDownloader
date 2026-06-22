import os
import sys

from app_core import MissAVDownloaderMixin
from app_ui import MissAVDownloaderAppBase


def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class MissAVDownloaderApp(MissAVDownloaderMixin, MissAVDownloaderAppBase):
    def get_downloader_exe_path(self):
        return get_resource_path("N_m3u8DL-RE.exe")

    def setup_playwright_env(self):
        playwright_browsers_dir = get_resource_path("playwright")
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = playwright_browsers_dir
        self.log(f"Playwright 浏览器路径: {playwright_browsers_dir}")


if __name__ == "__main__":
    app = MissAVDownloaderApp()
    app.mainloop()
