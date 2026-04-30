# RECALL: 具備視覺大腦的個人數位記憶助理 (Personal Memory Assistant)

RECALL 是一個以「本地優先、視覺驅動」為設計目標的個人記憶系統。它不僅記錄您的螢幕內容，更透過 VLM (視覺大語言模型) 像人一樣「看懂」您的操作脈絡，協助您在海量紀錄中瞬間找回遺忘的細節。

---

## 核心進化：從「記錄」到「理解」

### ✨ VLM 全方位視覺理解
捨棄了傳統且不穩定的 UI Automation (UIA)，RECALL 現在採用多模態視覺分析 (Vision-Language Model)。
- **看圖說故事**：AI 會直接分析螢幕截圖，理解應用程式的實際操作狀態，而不僅僅是讀取標籤。
- **智慧自動命名**：當系統偵測到相關的內容達一定筆數，會自動根據視覺畫面與文字內容，為您的工作階段 (Session) 命名（例如：將一堆雜亂的 Chrome 紀錄自動命名為 `正在研究 2026 歐冠戰術分析`）。
- **AI 互動對話**：您可以針對特定紀錄向 AI 提問：「我那天在看哪一段程式碼？」或「幫我總結這幾封郵件的重點」。

### ⚡ 混合式效能架構 (Hybrid Performance)
為了在維持強大能力的同時不佔用系統資源，我們設計了極致的調度機制：
- **零感背景擷取**：平時僅執行輕量級的 OCR 與截圖，對 CPU 影響微乎其微。
- **按需加載 (Lazy Loading)**：VLM 僅在需要進行深度分析或命名時才載入顯存/記憶體。
- **60秒自動釋放**：任務完成後 60 秒若無後續使用，系統會自動卸載模型資源，歸還所有 VRAM。

---

## 快速開始 (Quick Start)

### 1. 安裝環境
確保您的 Python 版本為 3.10+，然後安裝基礎依賴：
```bash
pip install -r requirements.txt
```

#### 🚀 GPU 硬件加速指南 (強烈推薦)
若要獲得流暢的 AI 對話體驗，建議安裝支援 Vulkan (適用於 AMD/NVIDIA/Intel) 的編譯版本：
```bash
# 移除現有的版本
pip uninstall llama-cpp-python -y
# 安裝支援 Vulkan 的版本 (Windows 下需已安裝 Vulkan SDK 與編譯工具)
$env:CMAKE_ARGS = "-DGGML_VULKAN=on"
pip install llama-cpp-python --upgrade --force-reinstall --no-cache-dir
```

### 2. 放置模型檔案
請將下列模型檔案放入 `models/` 資料夾中（系統會自動識別檔名）：
- **主思考大腦 (GGUF)**: 推薦 `Gemma-4-E4B-Uncensored*.gguf` (約 2-4GB)
- **視覺處理器 (mmproj)**: `mmproj-Gemma*.gguf` (視覺識別用)
- **語意檢索 (Embedding)**: `embeddinggemma*.gguf` (搜尋用)

### 3. 啟動 RECALL
```bash
python main.py
```

### 4. 安裝瀏覽器插件
1. 開啟 Chrome 擴充功能頁面 (`chrome://extensions`)。
2. 開啟右上角「開發者模式」。
3. 點擊「載入解壓縮擴充功能」，選取 `browser_extension/` 資料夾。
4. 點擊插件圖示進入設定頁面，按「測試連線」確認與主程式通訊正常。

---

## 功能導覽

### 🔍 語意向量搜尋
在主介面頂端的搜尋框輸入您的意圖（例如：`上禮拜看的歐冠戰術`），RECALL 會透過嵌入模型 (Embedding) 進行**語意搜尋**，即使標題沒有出現該字眼，只要內容相關就能找到。

### ✨ 工作階段 (Session) 聚合
RECALL 會自動將相同應用程式、且時間接近的操作歸類為一個 Session。
- **自動命名**：當您在同一個 Session 停留較久，AI 會在背景分析畫面，將「Chrome.exe」這種無意義的名字自動改為「正在規劃東京行程」。
- **手動命名**：在右側 AI 聊天框輸入「幫這個 Session 命名」，AI 會立即分析選中的記錄並更新。

### 💬 視覺對話
選中列表中的一筆或多筆記錄後，在右側聊天框輸入問題，AI 會結合當時的**螢幕截圖**與 **OCR 文字**回答您的疑問。

---

## 隱私與安全
- **全本地化**：所有數據與圖片永不上傳雲端。
- **隱私過濾**：系統內建黑名單（如 `1Password`, `Bitwarden`），偵測到這些視窗時會自動停止錄製。
- **安全 RPC**：瀏覽器與主程式通訊需經過 `.recall_token` 鑑權。

---
