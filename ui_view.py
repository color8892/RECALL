# 負責 GUI 介面佈局、樣式設定與視窗元件管理 (Tkinter)
import ctypes
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import config

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

class RecallView(tk.Tk):
    def __init__(self):
        super().__init__()
        self.controller = None
        self.title("RECALL")
        self.geometry("1180x720")
        self.minsize(980, 580)
        self.configure(bg=config.THEME_DARK)
        self._setup_ui()

    def set_controller(self, controller):
        self.controller = controller

    # 建立主介面元件：工具欄、過濾器、列表與 AI 對話框
    def _setup_ui(self):
        self._setup_style()

        toolbar = tk.Frame(self, bg=config.THEME_DARK)
        toolbar.pack(fill="x", padx=16, pady=(12, 6))

        self.search_var = tk.StringVar()
        entry = tk.Entry(toolbar, textvariable=self.search_var, font=("Segoe UI", 12))
        entry.pack(side=tk.LEFT, fill="x", expand=True)
        entry.bind("<Return>", lambda _: self.controller.handle_refresh())

        tk.Button(toolbar, text="搜尋", command=lambda: self.controller.handle_refresh(), bg=config.ACCENT_COLOR, fg="#fff", relief=tk.FLAT, padx=14).pack(side=tk.LEFT, padx=(8, 0))
        tk.Button(toolbar, text="重整", command=lambda: self.controller.handle_refresh(), bg="#3a3a3a", fg="#fff", relief=tk.FLAT, padx=12).pack(side=tk.LEFT, padx=(8, 0))

        self.pause_btn = tk.Button(toolbar, text="暫停擷取", command=lambda: self.controller.handle_toggle_pause(), bg="#5c5c5c", fg="#fff", relief=tk.FLAT, padx=12)
        self.pause_btn.pack(side=tk.RIGHT, padx=(8, 0))
        tk.Button(toolbar, text="複製 Token", command=lambda: self.controller.handle_copy_token(), bg="#3a3a3a", fg="#fff", relief=tk.FLAT, padx=12).pack(side=tk.RIGHT)

        filters = tk.Frame(self, bg=config.THEME_DARK)
        filters.pack(fill="x", padx=16, pady=(0, 8))

        self.app_var = tk.StringVar(value="全部")
        self.type_var = tk.StringVar(value="全部")
        self.time_var = tk.StringVar(value="全部")
        self.sort_var = tk.StringVar(value="最新優先")
        self.group_var = tk.BooleanVar(value=True)

        self.app_combo = self._combo(filters, self.app_var, ["全部"], 13)
        self.type_combo = self._combo(filters, self.type_var, ["全部"], 10)
        self._combo(filters, self.time_var, ["全部", "今天", "近 7 天", "近 30 天"], 10)
        self._combo(filters, self.sort_var, ["最新優先", "最舊優先", "應用程式", "資料來源"], 11)

        tk.Checkbutton(filters, text="時間軸聚合", variable=self.group_var, command=lambda: self.controller.handle_refresh(), bg=config.THEME_DARK, fg="#ddd", selectcolor="#2b2b2b", activebackground=config.THEME_DARK).pack(side=tk.LEFT, padx=(12, 0))

        actions = tk.Frame(self, bg=config.THEME_DARK)
        actions.pack(fill="x", padx=16, pady=(0, 8))
        tk.Button(actions, text="刪除選取", command=lambda: self.controller.handle_delete_selected(), bg="#8b2f2f", fg="#fff", relief=tk.FLAT, padx=12).pack(side=tk.LEFT)
        tk.Button(actions, text="清理舊紀錄", command=lambda: self.controller.handle_purge_old(), bg="#5c3d1f", fg="#fff", relief=tk.FLAT, padx=12).pack(side=tk.LEFT, padx=(8, 0))

        self.paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg="#1e1e1e", sashwidth=4, bd=0)
        self.paned.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        list_frame = tk.Frame(self.paned, bg=config.THEME_DARK)
        self.paned.add(list_frame, width=750)

        columns = ("Time", "App", "Title")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.tag_configure("odd", background="#2a2a2a")
        self.tree.tag_configure("even", background="#252525")
        
        headings = {"Time": "時間軸 (Session)", "App": "應用程式", "Title": "摘要內容"}
        widths = {"Time": 180, "App": 150, "Title": 420}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor=tk.W)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self.controller.handle_item_double_click())

        self.chat_frame = tk.Frame(self.paned, bg="#252525", bd=0)
        self.paned.add(self.chat_frame, width=400)

        tk.Label(self.chat_frame, text="✨ AI 記憶助理", bg="#252525", fg="#4caf50", font=("Segoe UI", 11, "bold")).pack(fill="x", pady=8)
        
        self.chat_history = tk.Text(self.chat_frame, bg="#2d2d2d", fg="#eee", font=("Segoe UI", 10), state="disabled", wrap="word", bd=0, padx=8, pady=8)
        self.chat_history.pack(fill="both", expand=True, padx=8)
        
        chat_input_frame = tk.Frame(self.chat_frame, bg="#252525")
        chat_input_frame.pack(fill="x", side=tk.BOTTOM, padx=8, pady=8)

        self.chat_var = tk.StringVar()
        self.chat_entry = tk.Entry(chat_input_frame, textvariable=self.chat_var, bg="#333", fg="#fff", insertbackground="#fff", font=("Segoe UI", 11), bd=0)
        self.chat_entry.pack(side=tk.LEFT, fill="x", expand=True, ipady=4)
        self.chat_entry.bind("<Return>", lambda _: self.controller.handle_send_chat())
        
        tk.Button(chat_input_frame, text="發送", command=lambda: self.controller.handle_send_chat(), bg="#4caf50", fg="#fff", relief=tk.FLAT, padx=12).pack(side=tk.RIGHT, padx=(6, 0))

        self.status_bar = tk.Label(self, text="AI 引擎載入中...", bd=1, relief=tk.SUNKEN, anchor=tk.W, bg=config.THEME_DARK, fg="#888")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # 設定自定義元件樣式 (Treeview 顏色與間距)
    def _setup_style(self):
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Treeview", 
                        background="#252525", 
                        foreground="#ddd", 
                        fieldbackground="#252525", 
                        rowheight=35,
                        font=("Segoe UI", 10))
        style.configure("Treeview.Heading", 
                        background="#333", 
                        foreground="#eee", 
                        font=("Segoe UI", 10, "bold"))
        style.map("Treeview", 
                  background=[("selected", config.ACCENT_COLOR)],
                  foreground=[("selected", "#ffffff")])

    def _combo(self, parent, variable, values, width):
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=width)
        combo.pack(side=tk.LEFT, padx=(0, 8))
        combo.bind("<<ComboboxSelected>>", lambda _: self.controller.handle_refresh())
        return combo

    def update_filter_options(self, apps, types):
        self.app_combo["values"] = ["全部", *apps]
        self.type_combo["values"] = ["全部", *types]

    def set_status(self, text, fg="#aaa"):
        self.status_bar.config(text=text, fg=fg)

    # 渲染主列表資料
    def render_treeview(self, display_data):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for index, values in enumerate(display_data):
            tag = "odd" if index % 2 else "even"
            self.tree.insert("", "end", iid=str(index), values=values, tags=(tag,))

    def update_tree_item(self, item_id, values):
        self.tree.item(item_id, values=values)

    # 在對話框中顯示 AI 或使用者的訊息
    def append_chat(self, sender, text, color="#4caf50"):
        self.chat_history.config(state="normal")
        self.chat_history.insert("end", f"\n{sender}: ", f"sender_{sender}")
        self.chat_history.insert("end", text)
        self.chat_history.tag_config(f"sender_{sender}", foreground=color, font=("Segoe UI", 10, "bold"))
        self.chat_history.see("end")
        self.chat_history.config(state="disabled")
        
    def append_ai_chat_prefix(self):
        self.chat_history.config(state="normal")
        self.chat_history.insert("end", f"\nAI: ", "ai_sender")
        self.chat_history.tag_config("ai_sender", foreground="#4caf50", font=("Segoe UI", 10, "bold"))
        self.chat_history.config(state="disabled")

    # 處理 AI 串流輸出 (Streaming) 元件更新
    def append_token(self, widget, token):
        if not widget.winfo_exists():
            return
        try:
            widget.config(state="normal")
            widget.insert("end", token)
            widget.see("end")
            widget.config(state="disabled")
        except Exception:
            pass

    # 彈出詳細視窗 (包含圖片、文字與關鍵字高亮)
    def show_detail_window(self, title, url, img_path, content, query_terms):
        detail = tk.Toplevel(self)
        detail.title(f"詳情: {title}")
        detail.geometry("760x620")
        detail.configure(bg=config.THEME_DARK)

        meta = tk.Label(detail, text=url or title, bg=config.THEME_DARK, fg="#aaa", anchor="w", wraplength=700)
        meta.pack(fill="x", padx=16, pady=(12, 6))

        if img_path and img_path.exists():
            from PIL import Image, ImageTk
            try:
                image = Image.open(img_path)
                image.thumbnail((700, 260))
                tk_img = ImageTk.PhotoImage(image)
                lbl = tk.Label(detail, image=tk_img, bg=config.THEME_DARK)
                lbl.image = tk_img
                lbl.pack(pady=8)
            except Exception:
                pass

        txt = tk.Text(detail, bg="#252525", fg="#ddd", insertbackground="#fff", font=("Segoe UI", 10), padx=10, pady=10, wrap="word")
        txt.insert("1.0", content or "無內容")
        txt.tag_config("hit", background="#735c1d", foreground="#fff")
        
        # 對搜尋關鍵字進行黃底亮顯
        for term in query_terms:
            start = "1.0"
            while True:
                pos = txt.search(term, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = f"{pos}+{len(term)}c"
                txt.tag_add("hit", pos, end)
                start = end
                
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True, padx=16, pady=(0, 16))
