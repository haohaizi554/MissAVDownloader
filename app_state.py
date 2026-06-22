import json

import os

import threading

import uuid

from copy import deepcopy

from datetime import date, datetime





def _default_state():

    default_save = os.path.join(os.path.expanduser("~"), "Desktop", "MissAV_Download")

    return {

        "stats": {

            "date": date.today().isoformat(),

            "today_total": 0,

            "completed": 0,

            "failed": 0,

        },

        "history": [],

        "settings": {

            "save_dir": default_save,

            "proxy_enabled": True,

            "proxy_host": "127.0.0.1",

            "proxy_port": "7890",

            "theme": "dark",

        },

        "active_batch": None,

        "batches_today": [],

        "queue": [],

    }





class AppStateStore:

    def __init__(self, state_dir=None):

        if state_dir is None:

            state_dir = os.path.join(os.path.expanduser("~"), ".missav_downloader")

        self.state_dir = state_dir

        self.state_path = os.path.join(state_dir, "state.json")

        self._lock = threading.Lock()

        self._data = _default_state()

        self._load()



    def _load(self):

        os.makedirs(self.state_dir, exist_ok=True)

        if os.path.exists(self.state_path):

            try:

                with open(self.state_path, "r", encoding="utf-8") as f:

                    loaded = json.load(f)

                self._data = self._merge_defaults(loaded)

            except Exception:

                self._data = _default_state()

        self._ensure_today_stats()

        self._save_unlocked()



    def _merge_defaults(self, loaded):

        base = _default_state()

        for key in base:

            if key not in loaded:

                loaded[key] = base[key]

        if "settings" in loaded:

            for k, v in base["settings"].items():

                loaded["settings"].setdefault(k, v)

        if "stats" in loaded:

            for k, v in base["stats"].items():

                loaded["stats"].setdefault(k, v)

        loaded.setdefault("batches_today", [])

        loaded.setdefault("queue", [])

        return loaded



    def _ensure_today_stats(self):

        today = date.today().isoformat()

        if self._data["stats"].get("date") != today:

            self._data["stats"] = {

                "date": today,

                "today_total": 0,

                "completed": 0,

                "failed": 0,

            }

            self._data["batches_today"] = []

            self._data["queue"] = []

            self._data["active_batch"] = None



    def _save_unlocked(self):

        os.makedirs(self.state_dir, exist_ok=True)

        with open(self.state_path, "w", encoding="utf-8") as f:

            json.dump(self._data, f, ensure_ascii=False, indent=2)



    def save(self):

        with self._lock:

            self._ensure_today_stats()

            self._save_unlocked()



    def get_snapshot(self):

        with self._lock:

            self._ensure_today_stats()

            return deepcopy(self._data)



    def get_today_stats(self):

        with self._lock:

            self._ensure_today_stats()

            return deepcopy(self._data["stats"])



    def get_history(self, limit=200):

        with self._lock:

            items = list(self._data.get("history", []))

            items.reverse()

            return items[:limit]



    def get_queue(self):

        with self._lock:

            return deepcopy(self._data.get("queue", []))



    def get_batches_today(self):

        with self._lock:

            self._ensure_today_stats()

            return deepcopy(self._data.get("batches_today", []))



    def get_active_batch(self):

        with self._lock:

            batch = self._data.get("active_batch")

            return deepcopy(batch) if batch else None



    def load_settings(self):

        with self._lock:

            return deepcopy(self._data["settings"])



    def save_settings(self, settings):

        with self._lock:

            self._data["settings"].update(settings)

            self._save_unlocked()



    def record_batch_start(self, target_url, is_search_mode, enable_individual):

        with self._lock:

            self._ensure_today_stats()

            batch_id = str(uuid.uuid4())[:8]

            batch = {

                "id": batch_id,

                "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

                "target_url": target_url,

                "mode": "搜索模式" if is_search_mode else "链接模式",

                "individual": enable_individual,

                "status": "crawling",

                "progress": 0,

                "total": 0,

            }

            self._data["active_batch"] = batch

            self._data["stats"]["today_total"] += 1

            self._data["batches_today"].append(deepcopy(batch))

            self._save_unlocked()

            return batch_id



    def _find_batch_ref(self, batch_id=None):

        batch = self._data.get("active_batch")

        if batch:

            return batch

        if not batch_id:

            return None

        for b in self._data.get("batches_today", []):

            if b.get("id") == batch_id:

                return b

        return None



    def set_batch_status(self, status, progress=None, total=None, batch_id=None):

        with self._lock:

            batch = self._find_batch_ref(batch_id)

            if not batch:

                return

            batch["status"] = status

            if progress is not None:

                batch["progress"] = progress

            if total is not None:

                batch["total"] = total

            if self._data.get("active_batch") and self._data["active_batch"].get("id") == batch.get("id"):

                self._data["active_batch"] = batch

            self._sync_batch_to_today(batch)

            self._save_unlocked()



    def _sync_batch_to_today(self, batch):

        for i, b in enumerate(self._data["batches_today"]):

            if b.get("id") == batch.get("id"):

                self._data["batches_today"][i] = deepcopy(batch)

                break



    def set_queue(self, items):

        with self._lock:

            queue = []

            for item in items:

                queue.append({

                    "code": item.get("code", ""),

                    "title": item.get("title", ""),

                    "url": item.get("url", ""),

                    "status": item.get("status", "pending"),

                })

            self._data["queue"] = queue

            batch = self._data.get("active_batch")

            if batch:

                batch["total"] = len(queue)

                batch["status"] = "preview"

                self._sync_batch_to_today(batch)

            self._save_unlocked()



    def update_queue_item(self, code, status, batch_id=None):

        with self._lock:

            for item in self._data.get("queue", []):

                if item.get("code") == code:

                    item["status"] = status

                    break

            batch = self._find_batch_ref(batch_id)

            if batch:

                done = sum(1 for q in self._data["queue"] if q["status"] in ("done", "failed"))

                batch["progress"] = done

                if self._data.get("active_batch") and self._data["active_batch"].get("id") == batch.get("id"):

                    self._data["active_batch"] = batch

                self._sync_batch_to_today(batch)

            self._save_unlocked()



    def clear_queue(self):

        with self._lock:

            self._data["queue"] = []

            self._save_unlocked()



    def record_download_success(self, code, title, url, save_dir):

        with self._lock:

            self._ensure_today_stats()

            self._data["stats"]["completed"] += 1

            self._append_history(code, title, url, save_dir, "success")

            self._save_unlocked()



    def record_download_fail(self, code, title, url, save_dir, reason=""):

        with self._lock:

            self._ensure_today_stats()

            self._data["stats"]["failed"] += 1

            self._append_history(code, title, url, save_dir, "failed", reason)

            self._save_unlocked()



    def _append_history(self, code, title, url, save_dir, status, reason=""):

        entry = {

            "id": str(uuid.uuid4())[:12],

            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

            "code": code,

            "title": title,

            "url": url,

            "save_dir": save_dir,

            "status": status,

            "reason": reason,

        }

        self._data.setdefault("history", []).append(entry)

        if len(self._data["history"]) > 500:

            self._data["history"] = self._data["history"][-500:]



    def finish_batch(self, status, batch_id=None, clear_queue=None):

        with self._lock:

            batch = self._data.get("active_batch")

            if batch:

                batch["status"] = status

                batch["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                self._sync_batch_to_today(batch)

                batch_id = batch_id or batch.get("id")

            elif batch_id:

                for i, b in enumerate(self._data.get("batches_today", [])):

                    if b.get("id") == batch_id:

                        b["status"] = status

                        b["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        self._data["batches_today"][i] = deepcopy(b)

                        break

            self._data["active_batch"] = None

            if clear_queue is None:

                clear_queue = status in ("done", "stopped", "failed")

            if clear_queue:

                self._data["queue"] = []

            self._save_unlocked()


