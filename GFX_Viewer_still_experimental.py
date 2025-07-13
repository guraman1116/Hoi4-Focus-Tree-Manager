import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re
from PIL import Image, ImageTk
# pillow-dds-imagingをインポートすることで、PillowがDDS形式を扱えるようになります。
# この行がないとDDSファイルを開く際にエラーが発生します。
try:
    from PIL import DdsImagePlugin
except ImportError:
    messagebox.showerror(
        "ライブラリが不足しています",
        "Pillow DDS Imagingプラグインが見つかりません。\nコマンドプロンプトで `pip install pillow-dds-imaging` を実行してください。"
    )
    exit()

class GfxParser:
    """
    Hoi4の.gfxファイルを解析し、GFX情報を抽出するクラス。
    """
    def __init__(self, hoi4_path):
        self.hoi4_path = hoi4_path
        # GFXファイルは通常、gfxフォルダを基準としたパスを持っています。
        self.gfx_root_path = os.path.join(hoi4_path, 'gfx')
        self.interface_path = os.path.join(hoi4_path, 'interface')

    def find_gfx_files(self):
        """
        interfaceフォルダ内のすべての.gfxファイルを見つけ出す。
        """
        if not os.path.isdir(self.interface_path):
            return []
        
        gfx_files = []
        for root, _, files in os.walk(self.interface_path):
            for file in files:
                if file.endswith('.gfx'):
                    gfx_files.append(os.path.join(root, file))
        return gfx_files

    def parse_gfx_content(self, content):
        """
        .gfxファイルの内容を解析し、spriteTypeの情報を抽出する。
        """
        # コメント行を削除
        content = re.sub(r'#.*', '', content)
        
        # spriteType = { ... } のブロックをすべて見つける
        # re.DOTALLフラグは '.' が改行にもマッチするようにする
        sprite_type_blocks = re.findall(r'spriteType\s*=\s*{([^}]+)}', content, re.DOTALL)
        
        gfx_data = []
        for block in sprite_type_blocks:
            # ダブルクォーテーションの有無に対応し、値を取得する正規表現
            name_match = re.search(r'name\s*=\s*"?([^"\s}]+)"?', block)
            texture_file_match = re.search(r'texturefile\s*=\s*"?([^"\s}]+)"?', block)

            if name_match and texture_file_match:
                # .strip('"') を使って、値が引用符で囲まれていてもいなくても対応
                name = name_match.group(1).strip('"')
                
                # '_shine'で終わるGFXは無視する
                if name.endswith('_shine'):
                    continue
                
                texture_file = texture_file_match.group(1).strip('"')
                
                # パスの先頭にある "gfx/" または "gfx\" を取り除く
                if texture_file.lower().startswith('gfx/'):
                    texture_file = texture_file[4:]
                elif texture_file.lower().startswith('gfx\\'):
                    texture_file = texture_file[4:]
                
                # パス区切り文字をOS標準に統一
                texture_file_os_path = texture_file.replace('/', os.sep).replace('\\', os.sep)
                
                # gfxフォルダからの絶対パスに変換
                full_texture_path = os.path.join(self.gfx_root_path, texture_file_os_path)

                gfx_data.append({
                    'name': name,
                    'texture_path': full_texture_path
                })
        return gfx_data

    def get_all_gfx(self):
        """
        すべての.gfxファイルを解析し、GFX情報のリストを返す。
        """
        all_gfx = []
        gfx_files = self.find_gfx_files()
        if not gfx_files:
            return None # interfaceフォルダが見つからない場合

        for file_path in gfx_files:
            try:
                # encodingを'utf-8-sig'にするとBOM付きファイルにも対応できる
                with open(file_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
                    content = f.read()
                    all_gfx.extend(self.parse_gfx_content(content))
            except Exception as e:
                print(f"Error parsing file {file_path}: {e}")
        
        return all_gfx


class GfxViewerPage(tk.Frame):
    """
    GFXを一覧表示する画面。
    """
    def __init__(self, parent, controller, hoi4_path):
        super().__init__(parent)
        self.controller = controller
        self.hoi4_path = hoi4_path
        self.gfx_data = []
        self.image_references = [] # PhotoImageオブジェクトへの参照を保持

        # --- UIのセットアップ ---
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- 上部フレーム (検索と戻るボタン) ---
        top_frame = ttk.Frame(self)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        
        back_button = ttk.Button(top_frame, text="< メインメニューに戻る", command=lambda: controller.show_frame("StartPage"))
        back_button.pack(side="left")

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side="left", padx=10, expand=True, fill="x")

        # --- GFX表示エリア (スクロール付き) ---
        canvas_frame = ttk.Frame(self)
        canvas_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_frame)
        self.scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas) # 属性をここで定義

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        # マウスホイールでのスクロールを有効化
        self.bind_all("<MouseWheel>", self._on_mousewheel)

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # --- [修正点] データの読み込みとコールバックの設定を最後に行う ---
        # 1. データを読み込んで表示する
        self.load_gfx()
        
        # 2. 検索ボックスに初期テキストを入れる
        search_entry.insert(0, "GFX名を検索...")
        
        # 3. 最後にコールバックを設定する。これにより、初期化時の不要な呼び出しを防ぐ
        self.search_var.trace_add("write", self.filter_list)

    def _on_mousewheel(self, event):
        # WindowsとmacOS/Linuxでスクロール方向が違うため調整
        # self.canvas.yview_scroll を使うことで、このウィジェットがアクティブでなくてもスクロールできる
        if os.name == 'nt':
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        else:
            self.canvas.yview_scroll(int(event.delta), "units")

    def load_gfx(self):
        """
        GFXを読み込んで表示する。
        """
        parser = GfxParser(self.hoi4_path)
        self.gfx_data = parser.get_all_gfx()

        if self.gfx_data is None:
            messagebox.showerror("エラー", f"指定されたパスに 'interface' フォルダが見つかりません。\nパス: {self.hoi4_path}")
            self.controller.show_frame("StartPage")
            return
        
        if not self.gfx_data:
            messagebox.showinfo("情報", "表示できるGFXが見つかりませんでした。")
            return

        self.display_gfx_list(self.gfx_data)

    def display_gfx_list(self, gfx_list):
        """
        指定されたリストのGFXを画面に表示する。
        """
        # 既存のウィジェットをクリア
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.image_references.clear()

        # GFXをタイル状に表示
        try:
            max_cols = self.winfo_width() // 120 or 5 # ウィンドウ幅に応じて列数を動的に変更
        except tk.TclError:
            max_cols = 5 # ウィンドウがまだ描画されていない場合

        for i, gfx in enumerate(gfx_list):
            row = i // max_cols
            col = i % max_cols
            
            item_frame = ttk.Frame(self.scrollable_frame, padding=5, relief="groove", borderwidth=1)
            item_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

            # 画像の読み込みと表示
            try:
                # DDSファイルをPillowで開く
                with Image.open(gfx['texture_path']) as img:
                    # Tkinterで表示できるようにリサイズして変換
                    img.thumbnail((80, 80))
                    photo_img = ImageTk.PhotoImage(img)
                    self.image_references.append(photo_img) # 参照を保持
                    
                    img_label = ttk.Label(item_frame, image=photo_img)
                    img_label.pack()

            except FileNotFoundError:
                # 画像ファイルが見つからない場合
                img_label = ttk.Label(item_frame, text="画像なし", foreground="red")
                img_label.pack(ipadx=10, ipady=30)
            except Exception as e:
                # その他の画像読み込みエラー
                img_label = ttk.Label(item_frame, text="読込不可", foreground="orange")
                img_label.pack(ipadx=10, ipady=30)
                # print(f"Could not load image {gfx['texture_path']}: {e}")

            # GFX名の表示
            name_label = ttk.Label(item_frame, text=gfx['name'], wraplength=100, justify="center")
            name_label.pack(pady=(5,0))

    def filter_list(self, *args):
        """
        検索ボックスの入力に基づいてGFXリストをフィルタリングする。
        """
        query = self.search_var.get().lower()
        if query == "gfx名を検索...": # 初期値の場合は何もしない
             filtered_list = self.gfx_data
        else:
            filtered_list = [
                gfx for gfx in self.gfx_data if query in gfx['name'].lower()
            ]
        
        self.display_gfx_list(filtered_list)


class StartPage(tk.Frame):
    """
    開始画面。Hoi4のインストールパスを指定する。
    """
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        frame = ttk.Frame(self, padding="20")
        frame.place(relx=0.5, rely=0.5, anchor="center")

        title_label = ttk.Label(frame, text="Hoi4 GFX Viewer", font=("Helvetica", 16, "bold"))
        title_label.pack(pady=(0, 20))

        path_frame = ttk.Frame(frame)
        path_frame.pack(fill="x", expand=True)

        path_label = ttk.Label(path_frame, text="Hoi4インストールパス:")
        path_label.pack(side="left")

        self.path_var = tk.StringVar()
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var, width=60)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=5)

        browse_button = ttk.Button(path_frame, text="参照...", command=self.browse_folder)
        browse_button.pack(side="left")

        start_button = ttk.Button(frame, text="GFXサーチを開始", command=self.start_search)
        start_button.pack(pady=20)

    def browse_folder(self):
        """
        フォルダ選択ダイアログを開き、選択されたパスを入力欄に設定する。
        """
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.path_var.set(folder_selected)

    def start_search(self):
        """
        GFXサーチ画面に遷移する。
        """
        hoi4_path = self.path_var.get()
        if not hoi4_path or not os.path.isdir(hoi4_path):
            messagebox.showerror("エラー", "有効なHoi4インストールパスを指定してください。")
            return
        
        # hoi4.exeがあるか簡易チェック
        if not os.path.exists(os.path.join(hoi4_path, "hoi4.exe")):
            if not messagebox.askyesno("確認", "指定されたフォルダにhoi4.exeが見つかりません。続行しますか？"):
                return

        self.controller.show_frame("GfxViewerPage", hoi4_path)


class MainApp(tk.Tk):
    """
    アプリケーションのメインクラス。画面遷移を管理する。
    """
    def __init__(self):
        super().__init__()
        self.title("Hoi4 Modding Tool")
        self.geometry("800x600")

        container = ttk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        # GfxViewerPageはパスを渡す必要があるため、動的に生成する
        for F in (StartPage,):
            page_name = F.__name__
            frame = F(parent=container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("StartPage")

    def show_frame(self, page_name, *args):
        """
        指定された名前のフレーム（画面）を表示する。
        """
        if page_name == "GfxViewerPage":
            # GfxViewerPageは毎回作り直して最新のパスを渡す
            if "GfxViewerPage" in self.frames:
                self.frames["GfxViewerPage"].destroy()
            
            hoi4_path = args[0]
            frame = GfxViewerPage(parent=self.frames["StartPage"].master, controller=self, hoi4_path=hoi4_path)
            self.frames["GfxViewerPage"] = frame
            frame.grid(row=0, column=0, sticky="nsew")
        
        frame = self.frames[page_name]
        frame.tkraise()


if __name__ == "__main__":
    app = MainApp()
    app.mainloop()

