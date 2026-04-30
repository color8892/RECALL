# 專案啟動器：負責初始化各模組並協調整合
import threading
import logging
import tkinter as tk
import tkinter.messagebox as mbox
from ai_engine import ai_engine
from database import RecallDB
from monitor import RecallMonitor
from ui_view import RecallView
from controller import RecallController
from downloader import check_and_download_models
if __name__ == "__main__":
    try:

        # 0. 優先檢查模型完整性，確保初次執行也能成功
        check_and_download_models()

        # 1. 初始化資料庫並清理過期快取
        db = RecallDB(ai_engine.get_embedding)
        db.purge_old_cache()

        # 2. 啟動背景監控與 RPC 服務
        monitor = RecallMonitor(db, ai_engine)
        monitor.start()

        # 3. 建立 UI 視窗與控制器
        app_view = RecallView()
        controller = RecallController(db, monitor, ai_engine, app_view)
        
        # 4. 非同步加載 AI 模型避免卡住介面
        def start_ai_loading():
            def _load_task():
                is_ready = ai_engine.wait_until_ready()
                if is_ready:
                    app_view.after(0, lambda: app_view.set_status("AI 引擎就緒", "#4caf50"))
                else:
                    app_view.after(0, lambda: app_view.set_status("AI 引擎載入失敗，搜尋會先使用關鍵字模式", "#f44336"))
            
            threading.Thread(target=_load_task, daemon=True).start()

        # 5. 啟動應用程式業務邏輯
        controller.init_app()
        app_view.after(100, start_ai_loading) 

        # 6. 進入 Tkinter 主事件迴圈
        app_view.mainloop()

    except Exception as e:
        # 處理啟動階段的致命錯誤
        logging.error(f"FATAL STARTUP ERROR: {e}", exc_info=True)
        root = tk.Tk()
        root.withdraw()
        mbox.showerror("啟動錯誤", f"程式啟動失敗：\n{e}\n\n請檢查 models/ 目錄下是否有模型檔案。")
        root.destroy()
