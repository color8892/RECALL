# downloader.py - 負責自動檢查並從 Hugging Face 下載缺失的模型檔案

import os
import sys
import urllib.request
import config
from config import logger

# 模型下載清單：包含大腦、視覺、語意、過濾共四個模型
MODEL_DOWNLOAD_LIST = {
    "brain.gguf": "https://huggingface.co/HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive/resolve/main/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q4_K_P.gguf",
    "vision.gguf": "https://huggingface.co/HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive/resolve/main/mmproj-Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-f16.gguf",
    "embed.gguf": "https://huggingface.co/unsloth/embeddinggemma-300m-GGUF/resolve/main/embeddinggemma-300m-Q4_0.gguf",
    "lite.gguf": "https://huggingface.co/unsloth/functiongemma-270m-it-GGUF/resolve/main/functiongemma-270m-it-Q8_0.gguf"
}

def check_and_download_models():
    """ 檢查模型資料夾，若缺失檔案則啟動單行進度條下載 """
    if not config.MODELS_DIR.exists():
        config.MODELS_DIR.mkdir(parents=True)

    for filename, url in MODEL_DOWNLOAD_LIST.items():
        target_path = config.MODELS_DIR / filename
        
        if not target_path.exists():
            logger.info(f"⏳ 偵測到缺失模型: {filename}")
            try:
                last_reported_percent = -1

                def progress(count, block_size, total_size):
                    nonlocal last_reported_percent
                    percent = int(count * block_size * 100 / total_size)
                    if percent != last_reported_percent:
                        sys.stdout.write(f"\r📥 下載中: {percent}% [{'#' * (percent // 5)}{'-' * (20 - percent // 5)}]")
                        sys.stdout.flush()
                        last_reported_percent = percent
                
                urllib.request.urlretrieve(url, str(target_path), reporthook=progress)
                print(f"\n✅ {filename} 下載完成")
            except Exception as e:
                logger.error(f"\n❌ {filename} 下載失敗: {e}")

if __name__ == "__main__":
    check_and_download_models()