# 負責 AI 模型載入、視覺分析 (VLM) 與 向量 (Embedding) 生成
import base64
import contextlib
import gc
import os
import sys
import threading
import time
os.environ["GGML_QUIET"] = "1"

from llama_cpp import Llama
import config
from config import logger

from llama_cpp.llama_chat_format import Llava15ChatHandler as LlavaChatHandler

class AIEngine:
    def __init__(self):
        self._heavy, self._heavy_lock = None, threading.RLock()
        self._embed, self._embed_lock = None, threading.Lock()
        self._is_ready = False
        self.embedding_dim = None
        self._last_heavy_use = 0
        self._unload_timeout = 60

    @contextlib.contextmanager
    def _suppress_stderr(self):
        try:
            null_file = "nul" if os.name == "nt" else "/dev/null"
            with open(null_file, "w") as devnull:
                old_stderr_fd = os.dup(sys.stderr.fileno())
                os.dup2(devnull.fileno(), sys.stderr.fileno())
                try: yield
                finally:
                    os.dup2(old_stderr_fd, sys.stderr.fileno())
                    os.close(old_stderr_fd)
        except Exception: yield

    # 初始化嵌入模型並檢測維度
    def wait_until_ready(self):
        try:
            if not config.EMBED_MODEL_PATH.exists():
                logger.error(f"❌ Embedding 模型不存在")
                return False
            
            with self._suppress_stderr():
                self._embed = Llama(str(config.EMBED_MODEL_PATH), embedding=True, verbose=False)

            with self._embed_lock:
                probe = self._embed.create_embedding("RECALL probe")['data'][0]['embedding']
            self.embedding_dim = len(probe)
            
            self._is_ready = True
            threading.Thread(target=self._auto_unload_loop, daemon=True).start()
            logger.info("✅ AI Engine (VLM 模式) 就緒")
            return True
        except Exception as e:
            logger.error(f"AI Init Error: {e}")
            return False

    # 每 10 秒檢查一次，若閒置超過 60 秒則自動卸載大模型釋放顯存
    def _auto_unload_loop(self):
        while True:
            time.sleep(10)
            with self._heavy_lock:
                if self._heavy and (time.time() - self._last_heavy_use > self._unload_timeout):
                    logger.info("💤 正在釋放 VLM 大模型資源...")
                    self._heavy = None
                    gc.collect()
                    if os.name == 'nt':
                        try:
                            import ctypes
                            ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
                        except Exception as e:
                            logger.warning(f"釋放記憶體 API 呼叫失敗: {e}")
                    logger.info("✅ 資源已成功歸還系統。")

    # 確保視覺大模型在使用時才載入 (Lazy Loading)
    @contextlib.contextmanager
    def _use_heavy(self):
        with self._heavy_lock:
            self._last_heavy_use = time.time()
            if self._heavy is None:
                if not config.HEAVY_BRAIN_PATH.exists():
                    raise FileNotFoundError(f"Heavy 模型不存在")
                
                logger.info(f"🚀 正在加載 VLM 視覺大腦...")
                
                chat_handler = None
                if config.VLM_PROJ_PATH.exists():
                    chat_handler = LlavaChatHandler(clip_model_path=str(config.VLM_PROJ_PATH))
                
                params = {
                    "model_path": str(config.HEAVY_BRAIN_PATH),
                    "n_gpu_layers": config.AI_GPU_LAYERS,
                    "n_ctx": config.HEAVY_N_CTX,
                    "chat_handler": chat_handler,
                    "chat_format": "gemma",
                    "verbose": False
                }
                with self._suppress_stderr():
                    self._heavy = Llama(**params)
                logger.info("✅ VLM 模型加載完成。")
            
            yield self._heavy
            self._last_heavy_use = time.time()

    # 視覺對話核心：整合 OCR 文字內容與圖片 B64 進行分析
    def ask_with_vision(self, query, image_path=None, context_rows=None, callback=None):
        context_str = ""
        if context_rows:
            lines = []
            for i, row in enumerate(context_rows[:5], 1):
                lines.append(f"[{row['app']}] {row['title']}\n內容：{row['content'][:300]}")
            context_str = "【OCR 文字內容】\n" + "\n\n".join(lines)

        messages = [
            {"role": "system", "content": "你是一位強大的視覺助理，請結合文字內容與提供的截圖來回答。"},
            {"role": "user", "content": [
                {"type": "text", "text": f"{context_str}\n\n任務：{query}"}
            ]}
        ]

        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
                messages[1]["content"].insert(0, {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/avif;base64,{b64}"}
                })

        with self._use_heavy() as llm:
            try:
                res = llm.create_chat_completion(
                    messages=messages,
                    max_tokens=config.HEAVY_MAX_TOKENS,
                    temperature=config.HEAVY_TEMPERATURE,
                    stream=callback is not None
                )
                
                if callback:
                    full_text = ""
                    for chunk in res:
                        delta = chunk["choices"][0]["delta"]
                        if "content" in delta:
                            token = delta["content"]
                            full_text += token
                            callback(token)
                    return full_text.strip()
                else:
                    return res["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.error(f"VLM inference failed: {e}")
                return f"Error: {e}"

    def ask_assistant(self, query, context_rows=None, callback=None):
        return self.ask_with_vision(query, None, context_rows, callback)

    def get_embedding(self, text):
        if not self._is_ready or not text: return None
        with self._embed_lock:
            try: 
                return self._embed.create_embedding(text[:1000].replace("\n"," "))['data'][0]['embedding']
            except Exception as e: 
                logger.error(f"Embedding 生成失敗: {e}", exc_info=True)
                return None

ai_engine = AIEngine()
