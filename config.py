# config.py - 全域配置：定義路徑、AI 參數與隱私設定

import logging
import secrets
import sys
from pathlib import Path

# 判斷是否為打包環境 (EXE) 並設定根目錄
IS_FROZEN = getattr(sys, 'frozen', False)
BASE_DIR = Path(sys.executable).parent if IS_FROZEN else Path(__file__).resolve().parent

# 定義模型、日誌、截圖與資料庫路徑
MODELS_DIR, LOG_DIR = BASE_DIR/"models", BASE_DIR/"logs"
SCREENSHOT_DIR, DB_PATH = BASE_DIR/"screenshots", BASE_DIR/"recall.db"
VEC_DLL_PATH = BASE_DIR / "vec0.dll"

# 自動建立必要資料夾
for d in [MODELS_DIR, LOG_DIR, SCREENSHOT_DIR]: d.mkdir(parents=True, exist_ok=True)

# 偵測並設定模型路徑 (若檔名符合規則則自動抓取)
HEAVY_BRAIN_PATH = next(MODELS_DIR.glob("Gemma-4-E4B-Uncensored*.gguf"), MODELS_DIR/"brain.gguf")
EMBED_MODEL_PATH = next(MODELS_DIR.glob("embeddinggemma*.gguf"), MODELS_DIR/"embed.gguf")
LITE_FILTER_PATH = next(MODELS_DIR.glob("functiongemma*.gguf"), MODELS_DIR/"lite.gguf")
VLM_PROJ_PATH    = next(MODELS_DIR.glob("mmproj-Gemma*.gguf"), MODELS_DIR/"vision.gguf")

# 產生或讀取瀏覽器插件鑑權用的 Token
def _load_or_create_token():
    token_path = BASE_DIR / ".recall_token"
    if token_path.exists():
        with open(token_path, "r") as f: return f.read().strip()
    token = secrets.token_hex(16)
    with open(token_path, "w") as f: f.write(token)
    return token

# 系統運行參數
CAPTURE_INTERVAL = 5        # 截圖間隔 (秒)
BROWSER_EXT_PORT = 8085     # 瀏覽器插件通訊埠
RPC_SECRET = _load_or_create_token()

# AI 模型推理參數
EMBED_DIM = 768             # 向量維度
AI_GPU_LAYERS = 33          # 卸載至 GPU 的層數
HEAVY_N_CTX = 8192          # 上下文視窗大小
HEAVY_MAX_TOKENS = 2048     # 最大生成長度
HEAVY_TEMPERATURE = 0.2     # 生成溫度 (隨機性)

# 隱私與 UI 設定
CAPTURE_SCREENSHOT = True
CAPTURE_OCR = True
PRIVATE_APPS = ["1Password.exe", "KeePass.exe", "Bitwarden.exe", "Lockwise.exe"] # 黑名單
SESSION_TIMEOUT_SECS = 300  # Session 聚合超時 (5分鐘)
THEME_DARK = "#1e1e1e"
ACCENT_COLOR = "#2196f3"

# 日誌配置
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RECALL")