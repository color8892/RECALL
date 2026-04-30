# 負責將 Python 專案編譯為獨立的 Windows 執行檔 (.exe)
import shutil, subprocess, sys
from pathlib import Path

def main():
    print("RECALL Build Start...")
    base = Path(__file__).resolve().parent
    
    # 清理舊的編譯目錄
    for folder in ["build", "dist"]:
        if (d := base/folder).exists(): shutil.rmtree(d, ignore_errors=True)
    if (spec := base/"RECALL.spec").exists(): spec.unlink()

    # 設定需要隱含導入的庫
    hidden = [
        "PIL", "psutil", "win32gui", "win32process", 
        "mss", "numpy", "sqlite3"
    ]
    
    # PyInstaller 主要打包參數
    args = [
        "pyinstaller", 
        "--noconfirm", 
        "--onedir", 
        "--windowed", 
        "--name=RECALL",
        "--clean",
        "--collect-all", "llama_cpp",
        "--collect-all", "mss",
        "--collect-all", "pillow_avif",
        "--collect-all", "winsdk",
    ]
    
    # 封裝依賴檔案與 DLL
    data_files = [
        "config.py", "database.py", "ai_engine.py", "monitor.py", 
        "controller.py", "ui_view.py", "vec0.dll", "README.md"
    ]
    for m in data_files:
        if (base/m).exists():
            args += ["--add-data", f"{m}{';' if sys.platform=='win32' else ':'}."]
    
    for h in hidden: args += ["--hidden-import", h]
    args.append("main.py")

    print(f"📦 執行打包指令: {' '.join(args)}")
    
    try:
        subprocess.check_call(args)
        dist_recall = base / "dist" / "RECALL"
        
        # 建立打包後的必要空目錄
        (dist_recall / "models").mkdir(exist_ok=True)
        (dist_recall / "screenshots").mkdir(exist_ok=True)
        (dist_recall / "logs").mkdir(exist_ok=True)
        
        # 複製瀏覽器擴充功能源碼到 dist 目錄
        if (ext := base/"browser_extension").exists():
            shutil.copytree(ext, dist_recall/"browser_extension", dirs_exist_ok=True)
            
        print(f"\n編譯成功: {dist_recall.absolute()}")
    except Exception as e:
        print(f"\n❌ 編譯失敗: {e}")

if __name__ == "__main__":
    main()
