# 負責系統視窗監控、螢幕截圖、OCR 辨識與 接收擴充功能 RPC
import asyncio
import ctypes
import ctypes.wintypes
import io
import json
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional
from urllib.parse import urlparse

import mss
import psutil
import pythoncom
import win32gui
import win32process
from PIL import Image

import config

try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
except: ctypes.windll.user32.SetProcessDPIAware()

class RecallMonitor:
    def __init__(self, db, ai):
        self.db, self.ai = db, ai
        self.sct = mss.mss()
        self._last_hwnd = 0
        self._lock = threading.Lock()
        self._last_event_time = 0
        self._paused = False
        self._app_blocklist = {p.lower() for p in config.PRIVATE_APPS}
        self._domain_blocklist = {"gemini.google.com", "chatgpt.com", "claude.ai", "127.0.0.1", "localhost"}
        self.on_save_callback: Optional[Callable] = None

    def set_on_save_callback(self, callback: Callable) -> None:
        self.on_save_callback = callback

    def set_paused(self, paused):
        self._paused = bool(paused)

    def is_paused(self): return self._paused

    def _should_capture_app(self, app):
        return (app or "").lower() not in self._app_blocklist

    def _should_capture_url(self, url):
        try:
            domain = urlparse(url).hostname or ""
            return domain.lower() not in self._domain_blocklist
        except: return True

    # 啟動 Windows 事件鉤子與 RPC 伺服器
    def start(self):
        def _hook_callback(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
            if hwnd != self._last_hwnd:
                self._last_hwnd = hwnd
                threading.Thread(target=self._capture_task, args=(hwnd,), daemon=True).start()

        WinEventProc = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_long, ctypes.c_long, ctypes.c_uint, ctypes.c_uint)
        self._callback = WinEventProc(_hook_callback)
        self._hhook = ctypes.windll.user32.SetWinEventHook(0x0003, 0x0003, 0, self._callback, 0, 0, 0)
        
        threading.Thread(target=self._start_rpc, daemon=True).start()
        threading.Thread(target=self._msg_loop, daemon=True).start()

    # 建立本地 HTTP 服務以接收瀏覽器插件傳來的網頁資料
    def _start_rpc(self):
        monitor_self = self
        class RPCHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                if self.path != "/capture":
                    self.send_response(404); self.end_headers(); return
                try:
                    if monitor_self.is_paused():
                        self.send_response(204); self.end_headers(); return
                    content_len = int(self.headers.get('Content-Length', 0))
                    raw_body = self.rfile.read(content_len)
                    data = json.loads(raw_body.decode('utf-8'))
                    if self.headers.get('X-RECALL-Token') != config.RPC_SECRET:
                        self.send_response(403); self.end_headers(); return
                    
                    title = str(data.get("title", ""))[:300]
                    content = str(data.get("content", ""))[:3000]
                    url = str(data.get("url", ""))[:2000]
                    if not monitor_self._should_capture_url(url):
                        self.send_response(204); self.end_headers(); return
                    monitor_self.db.save("browser", "Browser", title, content, "", url)
                    self.send_response(200); self.end_headers()
                except Exception as e:
                    config.logger.error(f"RPC Error: {e}", exc_info=True)
                    self.send_response(500)
                    self.end_headers()
            def log_message(self, format, *args): pass

        try:
            self.srv = ThreadingHTTPServer(('127.0.0.1', config.BROWSER_EXT_PORT), RPCHandler)
            self.srv.serve_forever()
        except Exception as e: 
            config.logger.error(f"RPC Server start error: {e}", exc_info=True)

    def _msg_loop(self):
        try:
            msg = ctypes.wintypes.MSG()
            while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as e: 
            config.logger.error(f"Message loop error: {e}", exc_info=True)

    # 執行擷取任務：檢查視窗穩定性、獲取進程資訊、執行截圖與 OCR
    def _capture_task(self, hwnd: int) -> None:
        if self._paused: 
            return
            
        try:
            time.sleep(2.5)
            if win32gui.GetForegroundWindow() != hwnd: 
                return

            now = time.time()
            if now - self._last_event_time < 2.0: 
                return
            self._last_event_time = now

            coinited = False
            try:
                pythoncom.CoInitialize()
                coinited = True
                with self._lock:
                    if not win32gui.IsWindow(hwnd): 
                        return
                    app, title = self._get_info(hwnd)
                    if not self._should_capture_app(app): 
                        return

                    img, ocr_text = None, ""
                    if config.CAPTURE_SCREENSHOT:
                        shot = self.sct.grab(self.sct.monitors[1])
                        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                        if config.CAPTURE_OCR: 
                            ocr_text = self._win_ocr(img)
                    
                if not img: 
                    return
                
                def save_and_log(target_img, target_app, target_title, target_content):
                    try:
                        fname = f"{int(time.time())}.avif"
                        target_img.save(config.SCREENSHOT_DIR / fname, "AVIF", quality=70)
                        self.db.save("snapshot", target_app, target_title, target_content, fname)
                        if self.on_save_callback:
                            self.on_save_callback()
                    except Exception as e: 
                        config.logger.error(f"Save Error: {e}", exc_info=True)
                
                threading.Thread(target=save_and_log, args=(img, app, title, ocr_text), daemon=True).start()
            except Exception as e: 
                config.logger.error(f"內部擷取發生未預期錯誤 (HWND: {hwnd}): {e}", exc_info=True)
            finally:
                if coinited: 
                    pythoncom.CoUninitialize()
        except Exception as e: 
            config.logger.error(f"擷取任務發生未預期錯誤 (HWND: {hwnd}): {e}", exc_info=True)

    # 調用 Windows Runtime API 執行非同步 OCR
    def _win_ocr(self, pil_img: Image.Image) -> str:
        try:
            from winsdk.windows.media.ocr import OcrEngine
            from winsdk.windows.graphics.imaging import BitmapDecoder
            from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
        except Exception as e: 
            config.logger.warning(f"Windows SDK 載入失敗，OCR 無法使用: {e}")
            return ""

        async def _run_ocr():
            try:
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                stream = InMemoryRandomAccessStream()
                writer = DataWriter(stream)
                writer.write_bytes(buf.getvalue())
                await writer.store_async()
                await writer.flush_async()
                stream.seek(0)
                decoder = await BitmapDecoder.create_async(stream)
                bitmap = await decoder.get_software_bitmap_async()
                engine = OcrEngine.try_create_from_user_profile_languages()
                if not engine: 
                    return ""
                result = await engine.recognize_async(bitmap)
                return "\n".join([line.text for line in result.lines])
            except Exception as e: 
                config.logger.warning(f"非同步 OCR 辨識失敗: {e}")
                return ""
                
        try: 
            return asyncio.run(_run_ocr())
        except Exception as e: 
            config.logger.warning(f"OCR 辨識失敗: {e}")
            return ""

    def _get_info(self, hwnd):
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            p = psutil.Process(pid)
            return p.name(), win32gui.GetWindowText(hwnd)
        except: return "Unknown", win32gui.GetWindowText(hwnd)
