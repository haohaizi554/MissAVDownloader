from app_core import MissAVDownloaderMixin
from app_ui import MissAVDownloaderAppBase


class MissAVDownloaderApp(MissAVDownloaderMixin, MissAVDownloaderAppBase):
    def get_downloader_exe_path(self):
        return "N_m3u8DL-RE.exe"


if __name__ == "__main__":
    app = MissAVDownloaderApp()
    app.mainloop()
