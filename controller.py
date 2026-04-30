# 負責處理業務邏輯、協調 Model (DB) 與 View (UI) 的通訊
import threading
import re
from datetime import datetime, timedelta
from tkinter import messagebox, simpledialog
import config

class RecallController:
    def __init__(self, db, monitor, ai, view):
        self.db = db
        self.monitor = monitor
        self.ai = ai
        self.view = view
        self.rows = []
        self._auto_naming_active = False
        self.view.set_controller(self)

    # 程式啟動初始化：綁定回調並載入初始數據
    def init_app(self):
        self.monitor.set_on_save_callback(self.on_new_record_saved)
        self.load_filter_options()
        self.handle_refresh()

    def on_new_record_saved(self):
        if self.view.group_var.get():
            self.view.after(0, self.handle_refresh)
            self.view.after(500, self._check_auto_naming)

    def load_filter_options(self):
        apps, types = self.db.get_filter_options()
        self.view.update_filter_options(apps, types)

    # 讀取 UI 過濾設定並轉換為資料庫參數
    def _filters(self):
        now = datetime.now()
        time_map = {
            "今天": now.replace(hour=0, minute=0, second=0, microsecond=0),
            "近 7 天": now - timedelta(days=7),
            "近 30 天": now - timedelta(days=30),
        }
        since_dt = time_map.get(self.view.time_var.get())
        return {
            "app": self.view.app_var.get(),
            "type": self.view.type_var.get(),
            "since": since_dt.strftime("%Y-%m-%d %H:%M:%S") if since_dt else None,
        }

    def _sort_key(self):
        return {
            "最舊優先": "oldest",
            "應用程式": "app",
            "資料來源": "type",
        }.get(self.view.sort_var.get(), "newest")

    # 處理重新整理動作 (包含搜尋、聚合與排序切換)
    def handle_refresh(self):
        query = self.view.search_var.get().strip()
        filters = self._filters()
        is_grouped = self.view.group_var.get()

        if is_grouped and not query:
            self.rows = self.db.get_sessions(limit=150, filters=filters)
        elif query:
            self.rows = self.db.vector_search(query, limit=150, filters=filters)
        else:
            self.rows = self.db.query_records(limit=150, filters=filters, sort=self._sort_key())

        display_data = []
        for row in self.rows:
            display_data.append(self._display_values(row, query))
        
        self.view.render_treeview(display_data)
        self.load_filter_options()
        self.view.set_status(f"顯示 {len(self.rows)} 筆資料", "#aaa")

    # 處理列表顯示格式：聚合 Session 與單筆資料的不同呈現
    def _display_values(self, row, query):
        is_grouped = "count" in row
        start_ts = row.get("start", row.get("ts"))
        end_ts = row.get("end", row.get("ts"))

        dt = datetime.strptime(start_ts, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        
        if is_grouped:
            if dt.date() == now.date():
                time_str = f"今天 {dt.strftime('%H:%M:%S')} - {end_ts.split(' ')[-1]}"
            else:
                time_str = f"{dt.strftime('%m-%d %H:%M')} - {end_ts.split(' ')[-1]}"
            title = f"{row['title']} ({row['count']} 筆)"
        else:
            time_str = dt.strftime("%H:%M:%S")
            title = row['title']

        icon = self._get_app_icon(row["app"])
        return (time_str, f"{icon} {row['app']}", title)

    # 根據 App 名稱返回對應的表情符號圖標
    def _get_app_icon(self, app_name):
        app_name = app_name.lower()
        mapping = {
            "explorer.exe": "📂", "chrome.exe": "🌐", "msedge.exe": "🌐",
            "firefox.exe": "🦊", "python.exe": "🐍", "code.exe": "💻",
            "windowsterminal.exe": "🐚", "cmd.exe": "🐚", "powershell.exe": "🐚",
            "notepad.exe": "📝", "slack.exe": "💬", "discord.exe": "🎮",
            "spotify.exe": "🎵", "antigravity.exe": "🚀",
        }
        for key, icon in mapping.items():
            if key in app_name: return icon
        return "📄"

    def _row_ids(self, row):
        if "ids" in row: return row["ids"]
        return [row["id"]]

    def _selected_ids(self):
        ids = []
        for item_id in self.view.tree.selection():
            ids.extend(self._row_ids(self.rows[int(item_id)]))
        return ids

    # 處理刪除選定紀錄及其實體截圖
    def handle_delete_selected(self):
        ids = self._selected_ids()
        if not ids:
            self.view.set_status("請先選取要刪除的紀錄", "#ffb74d")
            return
        if not messagebox.askyesno("刪除紀錄", f"確定刪除 {len(ids)} 筆紀錄？相關截圖也會一併刪除。"):
            return
        deleted = self.db.delete_records(ids, delete_screenshots=True)
        self.handle_refresh()
        self.view.set_status(f"已刪除 {deleted} 筆紀錄", "#4caf50")

    # 處理批次清理舊數據
    def handle_purge_old(self):
        days = simpledialog.askinteger("清理舊紀錄", "刪除幾天以前的紀錄？", initialvalue=30, minvalue=1)
        if not days: return
        if not messagebox.askyesno("清理舊紀錄", f"確定刪除 {days} 天以前的紀錄與截圖？"):
            return
        deleted = self.db.purge_records_older_than(days, delete_screenshots=True)
        self.handle_refresh()
        self.view.set_status(f"已清理 {deleted} 筆舊紀錄", "#4caf50")

    # 處理 AI 對話發送與結果串流
    def handle_send_chat(self):
        query = self.view.chat_var.get().strip()
        if not query or not self.ai: return
        
        self.view.chat_var.set("")
        self.view.append_chat("You", query, color="#aaa")
        self.view.append_ai_chat_prefix()

        selection = self.view.tree.selection()
        context_rows = [self.rows[int(i)] for i in selection] if selection else list(self.rows[:15])

        def stream_cb(token):
            self.view.after(0, lambda: self.view.append_token(self.view.chat_history, token))

        def run():
            try:
                final_res = self.ai.ask_assistant(query, context_rows=context_rows, callback=stream_cb)
                if "命名" in query and selection:
                    item_id = selection[0]
                    row = self.rows[int(item_id)]
                    title = final_res.splitlines()[0].strip(" 「」\"'*#").split("：")[-1].strip()
                    self.view.after(0, lambda: self._apply_session_name(item_id, row, title))
            except Exception as e:
                self.view.after(0, lambda: self.view.append_chat("System", f"錯誤: {e}", "#f44336"))
        threading.Thread(target=run, daemon=True).start()

    def _apply_session_name(self, item_id, row, name):
        row["title"] = f"✨ {name}"
        if "ids" in row and row["ids"]:
            self.db.rename_record(row["ids"][0], row["title"])
        values = self._display_values(row, self.view.search_var.get().strip())
        self.view.update_tree_item(item_id, values)

    # 偵測是否有需要自動命名的 Session
    def _check_auto_naming(self):
        if self._auto_naming_active or not self.ai: return
        for i, row in enumerate(self.rows[:20]):
            count = row.get('count', 1) 
            if count >= 3:
                title = row.get('title', '')
                if " / " in title and "✨" not in title:
                    self._run_auto_name(i, row)
                    break

    # 呼叫 VLM 視覺大腦進行自動化任務命名
    def _run_auto_name(self, index, row):
        self._auto_naming_active = True
        def run():
            try:
                query = "請看這張截圖並結合文字內容，給這段工作內容一個簡短的中文命名（5-10個字），直接輸出標題，不要加解釋。"
                img_path = str(config.SCREENSHOT_DIR / row["img"]) if row.get("img") else None
                final_res = self.ai.ask_with_vision(query, image_path=img_path, context_rows=[row])
                title = final_res.splitlines()[0].strip(" 「」\"'*#").split("：")[-1].strip()
                self.view.after(0, lambda: self._finish_auto_name(index, row, title))
            except Exception: self._auto_naming_active = False
        threading.Thread(target=run, daemon=True).start()

    def _finish_auto_name(self, index, row, title):
        self._auto_naming_active = False
        if index < len(self.rows) and self.rows[index] == row:
            self._apply_session_name(str(index), row, title)

    # 將 RPC 安全 Token 複製到剪貼簿
    def handle_copy_token(self):
        self.view.clipboard_clear()
        self.view.clipboard_append(config.RPC_SECRET)
        self.view.set_status("RPC Token 已複製，可貼到瀏覽器擴充功能設定", "#4caf50")

    # 暫停或恢復螢幕擷取監控
    def handle_toggle_pause(self):
        if not self.monitor: return
        paused = not self.monitor.is_paused()
        self.monitor.set_paused(paused)
        self.view.pause_btn.config(text="恢復擷取" if paused else "暫停擷取", bg="#2f6b3b" if paused else "#5c5c5c")
        self.view.set_status("擷取已暫停" if paused else "擷取已恢復", "#ffb74d" if paused else "#4caf50")

    # 處理列表雙擊：彈出詳細內容視窗與關鍵字高亮
    def handle_item_double_click(self):
        selection = self.view.tree.selection()
        if not selection: return
        row = self.rows[int(selection[0])]
        img_path = config.SCREENSHOT_DIR / row["img"] if row["img"] else None
        query_terms = [t for t in re.split(r"\s+", self.view.search_var.get().strip()) if len(t) >= 2]
        self.view.show_detail_window(row["title"], row["url"], img_path, row["content"], query_terms)
