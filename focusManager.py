import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, Toplevel, filedialog
import json
import re

# --- 定数定義 ---
GRID_SIZE = 240  # キャンバス上のグリッドサイズ
NODE_RADIUS = 30 # 国家方針を表す円の半径
ARROW_COLOR = "#333333"
NODE_COLOR = "#CCCCCC"
NODE_HIGHLIGHT_COLOR = "#AADDFF"
TEXT_COLOR = "#000000"

class FocusNode:
    """国家方針のデータを保持するクラス"""
    def __init__(self, data):
        self.id = data.get("id", "")
        self.icon = data.get("icon", "GFX_focus_generic_question_mark")
        # prerequisiteはリストで複数の前提を扱えるようにする
        self.prerequisite = data.get("prerequisite", [])
        self.relative_position_id = data.get("relative_position_id", None)
        self.cost = data.get("cost", 10)
        # x, y は offset の値が加算された最終的な位置
        self.x = data.get("x", 0)
        self.y = data.get("y", 0)
        self.completion_reward = data.get("completion_reward", "{\n\t\t\t\n\t\t}")

        # 描画用の絶対座標
        self.abs_x = 0
        self.abs_y = 0

    def to_dict(self):
        """シリアライズ用の辞書を返す"""
        return {
            "id": self.id,
            "icon": self.icon,
            "prerequisite": self.prerequisite,
            "relative_position_id": self.relative_position_id,
            "cost": self.cost,
            "x": self.x,
            "y": self.y,
            "completion_reward": self.completion_reward,
        }

    def to_hoi4_format(self):
        """Hoi4のスクリプト形式の文字列を生成する"""
        lines = []
        lines.append(f"\tfocus = {{")
        lines.append(f"\t\tid = {self.id}")
        lines.append(f"\t\ticon = {self.icon}")
        lines.append(f"\t\tcost = {self.cost}")

        # 前提条件のフォーマット
        # ここでは、すべての前提条件を単一のprerequisiteブロックにまとめる
        # HoI4のフォーマットでは複数のprerequisiteブロックはAND条件だが、
        # ツール内部ではフラットなリストとして扱い、エクスポート時に単一ブロックにまとめる
        # (これにより、ツールで編集した際にAND/ORの区別が失われる可能性がある点に注意)
        if self.prerequisite:
            if len(self.prerequisite) == 1:
                lines.append(f"\t\tprerequisite = {{ focus = {self.prerequisite[0]} }}")
            else:
                lines.append(f"\t\tprerequisite = {{")
                for prereq in self.prerequisite:
                    lines.append(f"\t\t\tfocus = {prereq}")
                lines.append(f"\t\t}}")

        if self.relative_position_id:
            lines.append(f"\t\trelative_position_id = {self.relative_position_id}")

        # ここでは元のx, yをそのまま出力（offsetは内部で処理済みのため）
        lines.append(f"\t\tx = {self.x}")
        lines.append(f"\t\ty = {self.y}")

        # completion_rewardが空でないことを確認
        reward_str = self.completion_reward.strip()
        if reward_str:
             lines.append(f"\t\tcompletion_reward = {reward_str}")
        else:
             lines.append(f"\t\tcompletion_reward = {{ }}")


        lines.append(f"\t}}")
        return "\n".join(lines)


class FocusEditorWindow(Toplevel):
    """国家方針の情報を編集するためのウィンドウ"""
    def __init__(self, parent, focus_node=None, existing_ids=None, initial_x=0, initial_y=0):
        super().__init__(parent)
        self.parent = parent
        self.focus_node = focus_node
        self.existing_ids = existing_ids if existing_ids else []
        self.original_id = focus_node.id if focus_node else None
        self.initial_x = initial_x
        self.initial_y = initial_y

        self.title("国家方針の編集" if focus_node else "新規国家方針の作成")
        self.geometry("600x700")
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.result = None
        self.prereq_vars = {} # チェックボックスのBooleanVarを格納する辞書

        self.create_widgets()
        if self.focus_node:
            self.load_data()
        else: # 新規作成の場合のみ初期座標をセット
            self.x_var.set(self.initial_x)
            self.y_var.set(self.initial_y)

    def create_widgets(self):
        """ウィジェットを作成し配置する"""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- ID ---
        ttk.Label(main_frame, text="ID:").grid(row=0, column=0, sticky="w", pady=2)
        self.id_var = tk.StringVar()
        self.id_entry = ttk.Entry(main_frame, textvariable=self.id_var)
        self.id_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=2)

        # --- Cost ---
        ttk.Label(main_frame, text="コスト (cost):").grid(row=1, column=0, sticky="w", pady=2)
        self.cost_var = tk.IntVar(value=10)
        self.cost_spinbox = ttk.Spinbox(main_frame, from_=0, to=1000, increment=7, textvariable=self.cost_var)
        self.cost_spinbox.grid(row=1, column=1, columnspan=2, sticky="ew", pady=2)

        # --- Relative Position ID ---
        ttk.Label(main_frame, text="相対位置の基準ID (relative_position_id):").grid(row=2, column=0, sticky="w", pady=2)
        self.relative_id_var = tk.StringVar()
        relative_ids = [""] + [fid for fid in self.existing_ids if fid != self.original_id]
        self.relative_id_combo = ttk.Combobox(main_frame, textvariable=self.relative_id_var, values=relative_ids)
        self.relative_id_combo.grid(row=2, column=1, columnspan=2, sticky="ew", pady=2)

        # --- Position ---
        ttk.Label(main_frame, text="相対位置 (x, y):").grid(row=3, column=0, sticky="w", pady=2)
        pos_frame = ttk.Frame(main_frame)
        pos_frame.grid(row=3, column=1, columnspan=2, sticky="ew")
        self.x_var = tk.IntVar(value=0)
        self.y_var = tk.IntVar(value=0)
        ttk.Label(pos_frame, text="x:").pack(side=tk.LEFT)
        ttk.Spinbox(pos_frame, from_=-50, to=50, textvariable=self.x_var, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Label(pos_frame, text="y:").pack(side=tk.LEFT)
        ttk.Spinbox(pos_frame, from_=-50, to=50, textvariable=self.y_var, width=5).pack(side=tk.LEFT, padx=5)

        # --- Prerequisite (チェックボックス形式に変更) ---
        ttk.Label(main_frame, text="前提条件 (prerequisite):").grid(row=4, column=0, sticky="w", pady=5)
        
        prereq_outer_frame = ttk.Frame(main_frame)
        prereq_outer_frame.grid(row=5, column=0, columnspan=3, sticky="nsew")
        main_frame.rowconfigure(5, weight=1) # この行が拡張できるように設定

        # スクロール可能な領域のためのCanvasを作成
        self.prereq_canvas = tk.Canvas(prereq_outer_frame, borderwidth=1, relief="sunken", background="#ffffff")
        self.prereq_canvas.pack(side="left", fill="both", expand=True)

        # Canvasにスクロールバーを追加
        prereq_scrollbar = ttk.Scrollbar(prereq_outer_frame, orient="vertical", command=self.prereq_canvas.yview)
        prereq_scrollbar.pack(side="right", fill="y")

        # Canvasにスクロールバーを設定
        self.prereq_canvas.configure(yscrollcommand=prereq_scrollbar.set)
        # Canvasのサイズ変更時にスクロール領域を更新
        self.prereq_canvas.bind('<Configure>', lambda e: self.prereq_canvas.configure(scrollregion = self.prereq_canvas.bbox("all")))

        # チェックボックスを保持するためのFrameをCanvas内に作成
        self.prereq_inner_frame = ttk.Frame(self.prereq_canvas)
        # Canvas内にFrameを配置
        self.prereq_canvas.create_window((0, 0), window=self.prereq_inner_frame, anchor="nw")

        prereq_ids = [fid for fid in self.existing_ids if fid != self.original_id]
        prereq_ids.sort() # IDをソートして表示順を安定させる

        for i, fid in enumerate(prereq_ids):
            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(self.prereq_inner_frame, text=fid, variable=var)
            cb.grid(row=i, column=0, sticky="w", padx=2, pady=1)
            self.prereq_vars[fid] = var

        # 全てのウィジェット作成後、スクロール領域を更新
        self.prereq_inner_frame.update_idletasks()
        self.prereq_canvas.config(scrollregion=self.prereq_canvas.bbox("all"))

        # --- Completion Reward ---
        ttk.Label(main_frame, text="達成時効果 (completion_reward):").grid(row=6, column=0, sticky="w", pady=5)
        reward_frame = ttk.Frame(main_frame)
        reward_frame.grid(row=7, column=0, columnspan=3, sticky="nsew")
        self.reward_text = tk.Text(reward_frame, height=10, wrap=tk.WORD)
        self.reward_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        reward_scrollbar = ttk.Scrollbar(reward_frame, orient=tk.VERTICAL, command=self.reward_text.yview)
        reward_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.reward_text.config(yscrollcommand=reward_scrollbar.set)

        main_frame.rowconfigure(7, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # --- Buttons ---
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(button_frame, text="保存", command=self.save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="キャンセル", command=self.cancel).pack(side=tk.RIGHT)

    def load_data(self):
        """既存のノードデータをフォームに読み込む"""
        self.id_var.set(self.focus_node.id)
        self.cost_var.set(self.focus_node.cost)
        self.relative_id_var.set(self.focus_node.relative_position_id or "")
        self.x_var.set(self.focus_node.x)
        self.y_var.set(self.focus_node.y)
        self.reward_text.insert("1.0", self.focus_node.completion_reward)

        # 前提条件の選択状態を復元 (チェックボックス用)
        for fid, var in self.prereq_vars.items():
            if fid in self.focus_node.prerequisite:
                var.set(True)
            else:
                var.set(False) # 明示的にFalseを設定

    def save(self):
        """入力されたデータを検証して保存する"""
        focus_id = self.id_var.get().strip()
        if not focus_id:
            messagebox.showerror("エラー", "IDは必須です。")
            return
        if focus_id != self.original_id and focus_id in self.existing_ids:
            messagebox.showerror("エラー", f"ID '{focus_id}' は既に使用されています。")
            return

        # チェックボックスから前提条件を取得
        prerequisites = []
        for fid, var in self.prereq_vars.items():
            if var.get():
                prerequisites.append(fid)

        data = {
            "id": focus_id,
            "cost": self.cost_var.get(),
            "relative_position_id": self.relative_id_var.get() or None,
            "x": self.x_var.get(),
            "y": self.y_var.get(),
            "prerequisite": prerequisites,
            "completion_reward": self.reward_text.get("1.0", tk.END).strip()
        }
        self.result = data
        self.destroy()

    def cancel(self):
        self.result = None
        self.destroy()

class FocusTreeApp:
    """アプリケーション本体のクラス"""
    def __init__(self, root):
        self.root = root
        self.root.title("HoI4 国家方針ツリー作成ツール")
        self.root.geometry("1024x768")
        # ウィンドウを閉じる際のプロトコルを設定
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.focus_nodes = {}  # {id: FocusNode}
        self.selected_node_id = None
        self.zoom_level = 1.0 # ズームレベルの初期値
        self.last_right_click_canvas_x = 0 # 右クリックされたキャンバスX座標
        self.last_right_click_canvas_y = 0 # 右クリックされたキャンバスY座標
        self.is_dirty = False # 未保存の変更があるかどうかのフラグ

        self.create_menu()
        self.create_widgets()
        self.create_context_menus() # コンテキストメニューを作成
        self.bind_keyboard_events() # キーボードイベントをバインド

        self.draw_tree()

    def on_closing(self):
        """ウィンドウを閉じる際の確認ダイアログを表示する"""
        if self.is_dirty:
            response = messagebox.askyesnocancel("終了の確認", "未保存の変更があります。保存しますか？")
            if response is True:  # はい
                save_successful = self.save_file()
                if save_successful: # 保存が成功した場合のみウィンドウを閉じる
                    self.root.destroy()
                # else: 保存がキャンセルされたかエラーが発生した場合はウィンドウを閉じない
            elif response is False: # いいえ (保存せずに終了)
                self.root.destroy()
            # else: response is None (キャンセル), 何もせずウィンドウを閉じない
        else:
            self.root.destroy() # 未保存の変更がなければ直接閉じる

    def create_menu(self):
        """メニューバーを作成する"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ファイル", menu=file_menu)
        file_menu.add_command(label="新規作成", command=self.new_file)
        file_menu.add_command(label="開く (.json)...", command=self.open_file)
        file_menu.add_command(label="保存 (.json)...", command=self.save_file)
        file_menu.add_separator()
        file_menu.add_command(label="インポート (Hoi4 .txt)...", command=self.import_hoi4_txt)
        file_menu.add_command(label="エクスポート (Hoi4 .txt)...", command=self.export_hoi4_txt)
        file_menu.add_separator()
        file_menu.add_command(label="終了", command=self.root.quit)

        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="編集", menu=edit_menu)
        edit_menu.add_command(label="国家方針を追加", command=self.add_focus_node)
        edit_menu.add_command(label="選択中の国家方針を編集", command=self.edit_selected_node, state=tk.DISABLED)
        edit_menu.add_command(label="選択中の国家方針を削除", command=self.delete_selected_node, state=tk.DISABLED)

        self.edit_menu = edit_menu

    def create_widgets(self):
        """メインウィンドウのウィジェットを作成する"""
        # --- メインフレーム ---
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- ツールバー ---
        toolbar = ttk.Frame(main_frame, padding=5)
        toolbar.pack(fill=tk.X, side=tk.TOP)
        ttk.Button(toolbar, text="国家方針を追加", command=self.add_focus_node).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="スクリプトプレビュー", command=self.preview_script).pack(side=tk.LEFT, padx=5)
        self.status_label = ttk.Label(toolbar, text="準備完了")
        self.status_label.pack(side=tk.RIGHT, padx=10)

        # --- キャンバスフレーム ---
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=5, pady=5)

        self.canvas = tk.Canvas(canvas_frame, bg="white", scrollregion=(-2000, -2000, 2000, 2000))
        
        # スクロールバー
        hbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        vbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas.config(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # --- キャンバスのイベントバインド ---
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click) 
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click) # ダブルクリック
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel) # マウスホイールイベント

        self.drag_data = {"x": 0, "y": 0, "item": None}

    def create_context_menus(self):
        """右クリックメニューを作成する (ノード用とキャンバス用)"""
        # ノード用のコンテキストメニュー
        self.node_context_menu = tk.Menu(self.root, tearoff=0)
        self.node_context_menu.add_command(label="国家方針を編集", command=self.edit_selected_node)
        self.node_context_menu.add_command(label="国家方針を削除", command=self.delete_selected_node)

        # キャンバス空き領域用のコンテキストメニュー
        self.canvas_context_menu = tk.Menu(self.root, tearoff=0)
        self.canvas_context_menu.add_command(label="国家方針を追加", command=self.add_focus_node_at_clicked_position)

    def bind_keyboard_events(self):
        """キーボードイベントをバインドする"""
        self.root.bind("<Left>", self.on_arrow_key_press)
        self.root.bind("<Right>", self.on_arrow_key_press)
        self.root.bind("<Up>", self.on_arrow_key_press)
        self.root.bind("<Down>", self.on_arrow_key_press)

    def on_arrow_key_press(self, event):
        """矢印キーが押されたときの処理"""
        if not self.selected_node_id:
            return # ノードが選択されていない場合は何もしない

        selected_node = self.focus_nodes[self.selected_node_id]
        
        moved = False
        if event.keysym == "Left":
            selected_node.x -= 1
            moved = True
        elif event.keysym == "Right":
            selected_node.x += 1
            moved = True
        elif event.keysym == "Up":
            selected_node.y -= 1
            moved = True
        elif event.keysym == "Down":
            selected_node.y += 1
            moved = True
        
        if moved:
            self.draw_tree()
            self.is_dirty = True # 変更があったことをマーク


    def on_mouse_wheel(self, event):
        """マウスホイールによるズームイン・アウト"""
        # Windows/Linuxではevent.deltaがホイールの回転量を示す
        # macOSではevent.numが4(上)または5(下)を示す
        if event.delta > 0 or event.num == 4: # ホイールアップ (ズームイン)
            self.zoom_level *= 1.1
        elif event.delta < 0 or event.num == 5: # ホイールダウン (ズームアウト)
            self.zoom_level /= 1.1
        
        # ズームレベルの範囲を制限 (例: 0.1から5.0)
        self.zoom_level = max(0.1, min(self.zoom_level, 5.0))
        
        self.draw_tree() # ツリーを再描画

    def on_canvas_click(self, event):
        """キャンバスのクリックイベント"""
        self.canvas.scan_mark(event.x, event.y)
        
        # クリックされたアイテムを特定
        # event.x, event.y はウィンドウ座標なので、canvasx/canvasyで論理座標に変換
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        clicked_items = self.canvas.find_overlapping(canvas_x - 1, canvas_y - 1, canvas_x + 1, canvas_y + 1)
        node_id = None
        for item in clicked_items:
            tags = self.canvas.gettags(item)
            if "node" in tags:
                node_id = tags[1] # "node"タグの次にIDタグがある想定
                break
        
        self.select_node(node_id)


    def on_canvas_drag(self, event):
        """キャンバスのドラッグイベント（画面スクロール）"""
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def on_canvas_release(self, event):
        """ドラッグ終了"""
        pass

    def on_canvas_right_click(self, event):
        """キャンバスの右クリックイベント（ノード選択とコンテキストメニュー表示）"""
        # クリックされたキャンバス座標を論理座標に変換
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        # 検出範囲をNODE_RADIUS程度に広げることで、クリックの精度を向上させる
        # ズームレベルも考慮に入れる
        detection_radius = NODE_RADIUS * self.zoom_level
        clicked_items = self.canvas.find_overlapping(
            canvas_x - detection_radius, canvas_y - detection_radius,
            canvas_x + detection_radius, canvas_y + detection_radius
        )
        node_id = None
        for item in clicked_items:
            tags = self.canvas.gettags(item)
            # タグがタプルであることを確認し、"node"タグとIDタグをチェック
            if isinstance(tags, tuple) and "node" in tags and len(tags) > 1:
                node_id = tags[1] 
                break
        
        # 右クリックされたキャンバス座標（変換後の論理座標）を保存
        self.last_right_click_canvas_x = canvas_x 
        self.last_right_click_canvas_y = canvas_y 

        if node_id:
            self.select_node(node_id) # ノードを選択状態にする
            try:
                self.node_context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.node_context_menu.grab_release()
        else:
            # ノード以外が右クリックされた場合は、キャンバス用のコンテキストメニューを表示
            try:
                self.canvas_context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.canvas_context_menu.grab_release()


    def on_canvas_double_click(self, event):
        """キャンバスのダブルクリックで編集"""
        if self.selected_node_id:
            self.edit_selected_node()

    def select_node(self, node_id):
        """指定されたIDのノードを選択状態にする"""
        # 以前に選択されていたノードのハイライトを解除
        if self.selected_node_id:
            # find_withtagはタプルを返すので、各アイテムIDに対して処理を行う
            items_to_unhighlight = self.canvas.find_withtag(self.selected_node_id)
            for item_id in items_to_unhighlight:
                item_type = self.canvas.type(item_id)
                if item_type == 'oval':
                    self.canvas.itemconfig(item_id, fill=NODE_COLOR)
                elif item_type == 'text':
                    self.canvas.itemconfig(item_id, fill=TEXT_COLOR) # テキストの色を元に戻す

        self.selected_node_id = node_id
        
        # 新しく選択されたノードをハイライト
        if self.selected_node_id:
            items_to_highlight = self.canvas.find_withtag(self.selected_node_id)
            for item_id in items_to_highlight:
                item_type = self.canvas.type(item_id)
                if item_type == 'oval':
                    self.canvas.itemconfig(item_id, fill=NODE_HIGHLIGHT_COLOR)
                elif item_type == 'text':
                    self.canvas.itemconfig(item_id, fill=NODE_HIGHLIGHT_COLOR) # テキストの色もハイライト色にする
            self.status_label.config(text=f"選択中: {self.selected_node_id}")
            self.edit_menu.entryconfig("選択中の国家方針を編集", state=tk.NORMAL)
            self.edit_menu.entryconfig("選択中の国家方針を削除", state=tk.NORMAL)
            # ノード用コンテキストメニューの項目も有効化
            self.node_context_menu.entryconfig("国家方針を編集", state=tk.NORMAL)
            self.node_context_menu.entryconfig("国家方針を削除", state=tk.NORMAL)
        else:
            self.status_label.config(text="準備完了")
            self.edit_menu.entryconfig("選択中の国家方針を編集", state=tk.DISABLED)
            self.edit_menu.entryconfig("選択中の国家方針を削除", state=tk.DISABLED)
            # ノード用コンテキストメニューの項目も無効化
            self.node_context_menu.entryconfig("国家方針を編集", state=tk.DISABLED)
            self.node_context_menu.entryconfig("国家方針を削除", state=tk.DISABLED)


    def add_focus_node(self):
        """国家方針追加ウィンドウを開く (ツールバーボタン用)"""
        # デフォルトのx, yは0で開く
        editor = FocusEditorWindow(self.root, existing_ids=list(self.focus_nodes.keys()))
        self.root.wait_window(editor)

        if editor.result:
            new_node = FocusNode(editor.result)
            self.focus_nodes[new_node.id] = new_node
            self.draw_tree()
            self.status_label.config(text=f"'{new_node.id}' を追加しました。")
            self.select_node(new_node.id) # 新規作成後、選択状態にする
            self.is_dirty = True # 変更があったことをマーク

    def add_focus_node_at_clicked_position(self):
        """右クリックされた座標に新しい国家方針を作成する"""
        # last_right_click_canvas_x/y は既に論理座標なので、そのまま使用
        initial_x = round(self.last_right_click_canvas_x / GRID_SIZE)
        initial_y = round(self.last_right_click_canvas_y / GRID_SIZE)

        editor = FocusEditorWindow(self.root, existing_ids=list(self.focus_nodes.keys()),
                                   initial_x=initial_x, initial_y=initial_y)
        self.root.wait_window(editor)

        if editor.result:
            new_node = FocusNode(editor.result)
            self.focus_nodes[new_node.id] = new_node
            self.draw_tree()
            self.status_label.config(text=f"'{new_node.id}' を追加しました。")
            self.select_node(new_node.id) # 新規作成後、選択状態にする
            self.is_dirty = True # 変更があったことをマーク


    def edit_selected_node(self):
        """選択中のノードを編集する"""
        if not self.selected_node_id:
            return
        
        node_to_edit = self.focus_nodes[self.selected_node_id]
        existing_ids = list(self.focus_nodes.keys())

        # 編集前のノードの絶対座標を保存
        # calculate_positionsを呼び出すことで、最新のabs_x, abs_yが保証される
        self.calculate_positions() 
        original_abs_x = node_to_edit.abs_x
        original_abs_y = node_to_edit.abs_y
        original_relative_position_id = node_to_edit.relative_position_id
        
        editor = FocusEditorWindow(self.root, focus_node=node_to_edit, existing_ids=existing_ids)
        self.root.wait_window(editor)

        if editor.result:
            new_id = editor.result['id']
            new_relative_position_id = editor.result['relative_position_id']
            
            # relative_position_idが変更された場合、x, yを調整
            if new_relative_position_id != original_relative_position_id:
                # 新しい親ノードの絶対座標を取得
                new_parent_abs_x = 0
                new_parent_abs_y = 0
                if new_relative_position_id and new_relative_position_id in self.focus_nodes:
                    # 新しい親のabs_x, abs_yも最新であることを保証するため、再度計算
                    # (editor.resultが返ってきた後、ツリーの状態が変わっている可能性もあるため)
                    self.calculate_positions() 
                    new_parent_node = self.focus_nodes[new_relative_position_id]
                    new_parent_abs_x = new_parent_node.abs_x
                    new_parent_abs_y = new_parent_node.abs_y
                
                # 新しいx, y座標を計算
                # (元の絶対座標 - 新しい親の絶対座標) / GRID_SIZE
                # HoI4のx, yは整数なので、round()で丸める
                adjusted_x = round((original_abs_x - new_parent_abs_x) / GRID_SIZE)
                adjusted_y = round((original_abs_y - new_parent_abs_y) / GRID_SIZE)
                
                editor.result['x'] = adjusted_x
                editor.result['y'] = adjusted_y

            # IDが変更された場合は辞書キーも変更
            if self.selected_node_id != new_id:
                # 他のノードの参照も更新
                old_id = self.selected_node_id
                for node in self.focus_nodes.values():
                    if node.relative_position_id == old_id:
                        node.relative_position_id = new_id
                    if old_id in node.prerequisite:
                        node.prerequisite = [new_id if p == old_id else p for p in node.prerequisite]

                del self.focus_nodes[self.selected_node_id]
                self.selected_node_id = None # 選択を解除 (新しいIDで再選択されるため)

            updated_node = FocusNode(editor.result)
            self.focus_nodes[updated_node.id] = updated_node
            self.draw_tree()
            self.status_label.config(text=f"'{updated_node.id}' を更新しました。")
            self.select_node(updated_node.id) # 編集後に新しいノードが選択状態になるようにする
            self.is_dirty = True # 変更があったことをマーク


    def delete_selected_node(self):
        """選択中のノードを削除する"""
        if not self.selected_node_id:
            return

        if messagebox.askyesno("確認", f"国家方針 '{self.selected_node_id}' を削除しますか？\nこの操作は元に戻せません。"):
            deleted_id = self.selected_node_id
            del self.focus_nodes[deleted_id]
            self.select_node(None)

            # 他のノードからの参照を削除
            for node in self.focus_nodes.values():
                if node.relative_position_id == deleted_id:
                    node.relative_position_id = None
                if deleted_id in node.prerequisite:
                    node.prerequisite.remove(deleted_id)
            
            self.draw_tree()
            self.status_label.config(text=f"'{deleted_id}' を削除しました。")
            self.is_dirty = True # 変更があったことをマーク


    def calculate_positions(self):
        """全ノードの絶対座標を計算する"""
        calculated_nodes = set()
        
        # ルートノード（relative_position_idがない）の位置を確定
        queue = []
        for node in self.focus_nodes.values():
            if not node.relative_position_id or node.relative_position_id not in self.focus_nodes:
                node.abs_x = node.x * GRID_SIZE
                node.abs_y = node.y * GRID_SIZE
                calculated_nodes.add(node.id)
                queue.append(node)

        # 依存関係をたどって位置を計算 (BFS)
        head = 0
        while head < len(queue):
            parent_node = queue[head]
            head += 1
            
            for child_node in self.focus_nodes.values():
                if child_node.relative_position_id == parent_node.id and child_node.id not in calculated_nodes:
                    child_node.abs_x = parent_node.abs_x + child_node.x * GRID_SIZE
                    child_node.abs_y = parent_node.abs_y + child_node.y * GRID_SIZE
                    calculated_nodes.add(child_node.id)
                    queue.append(child_node)
        
        # 未計算のノード（循環参照など）があればデフォルト位置に
        for node in self.focus_nodes.values():
            if node.id not in calculated_nodes:
                 node.abs_x = node.x * GRID_SIZE
                 node.abs_y = node.y * GRID_SIZE

    def draw_tree(self):
        """キャンバスにツリー全体を描画する"""
        self.canvas.delete("all")
        self.calculate_positions()

        # 1. 前提条件の線を描画
        for node in self.focus_nodes.values():
            for prereq_id in node.prerequisite:
                if prereq_id in self.focus_nodes:
                    prereq_node = self.focus_nodes[prereq_id]
                    # ズームレベルを適用して座標を計算
                    x1_scaled = prereq_node.abs_x * self.zoom_level
                    y1_scaled = prereq_node.abs_y * self.zoom_level
                    x2_scaled = node.abs_x * self.zoom_level
                    y2_scaled = node.abs_y * self.zoom_level

                    self.canvas.create_line(
                        x1_scaled, y1_scaled,
                        x2_scaled, y2_scaled,
                        fill=ARROW_COLOR, width=2 * self.zoom_level, arrow=tk.LAST
                    )

        # 2. 国家方針ノードを描画 (線の上に描画するため後から)
        for node_id, node in self.focus_nodes.items():
            # ズームレベルを適用して座標と半径を計算
            scaled_x = node.abs_x * self.zoom_level
            scaled_y = node.abs_y * self.zoom_level
            scaled_radius = NODE_RADIUS * self.zoom_level

            x0 = scaled_x - scaled_radius
            y0 = scaled_y - scaled_radius
            x1 = scaled_x + scaled_radius
            y1 = scaled_y + scaled_radius
            
            fill_color = NODE_HIGHLIGHT_COLOR if node_id == self.selected_node_id else NODE_COLOR
            
            self.canvas.create_oval(x0, y0, x1, y1, fill=fill_color, outline="black", width=2 * self.zoom_level, tags=("node", node_id))
            # テキストのフォントサイズもズームレベルに応じて調整
            font_size = max(6, int(8 * self.zoom_level)) # 最小フォントサイズを設定
            # テキストにも同じタグを付与することで、クリック検出を改善
            self.canvas.create_text(scaled_x, scaled_y + scaled_radius + 10 * self.zoom_level, text=node_id, fill=TEXT_COLOR, font=("Arial", font_size), tags=("node", node_id))

    def _generate_script_string(self):
        """Hoi4スクリプト文字列を生成する内部メソッド"""
        if not self.focus_nodes:
            return None
        
        full_script = "focus_tree = {\n"
        # ここでソートして出力順を安定させる（オプション）
        sorted_nodes = sorted(self.focus_nodes.values(), key=lambda n: (n.y, n.x))
        for node in sorted_nodes:
            full_script += node.to_hoi4_format() + "\n\n"
        full_script += "}"
        return full_script

    def preview_script(self):
        """Hoi4スクリプトを生成して新しいウィンドウに表示する"""
        script_string = self._generate_script_string()
        if not script_string:
            messagebox.showinfo("情報", "国家方針がありません。")
            return

        script_window = Toplevel(self.root)
        script_window.title("生成されたスクリプトのプレビュー")
        script_window.geometry("800x600")

        text_widget = tk.Text(script_window, wrap=tk.WORD, font=("Courier New", 10))
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(text_widget, command=text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.config(yscrollcommand=scrollbar.set)
        
        text_widget.insert("1.0", script_string)
        text_widget.config(state=tk.DISABLED) # 編集不可にする

    def new_file(self):
        """データを初期化する"""
        if self.is_dirty and not messagebox.askyesno("確認", "未保存の変更があります。現在のツリーを破棄して新規作成しますか？"):
            return

        self.focus_nodes.clear()
        self.select_node(None)
        self.draw_tree()
        self.status_label.config(text="新規ファイルを作成しました。")
        self.is_dirty = False # 新規作成で状態をクリーンに

    def save_file(self):
        """現在のツリーをJSONファイルに保存する"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not filepath:
            return False # ユーザーが保存をキャンセルした

        try:
            data_to_save = {node_id: node.to_dict() for node_id, node in self.focus_nodes.items()}
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            self.status_label.config(text=f"ファイルに保存しました: {filepath}")
            self.is_dirty = False # 保存後、状態をクリーンに
            return True # 保存成功
        except Exception as e:
            messagebox.showerror("保存エラー", f"ファイルの保存中にエラーが発生しました:\n{e}")
            return None # エラー発生

    def open_file(self):
        """JSONファイルからツリーを読み込む"""
        if self.is_dirty and not messagebox.askyesno("確認", "未保存の変更があります。現在のツリーを破棄してファイルを開きますか？"):
            return

        filepath = filedialog.askopenfilename(
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not filepath:
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            
            self.focus_nodes.clear()
            for node_id, node_data in loaded_data.items():
                self.focus_nodes[node_id] = FocusNode(node_data)
            
            self.select_node(None)
            self.draw_tree()
            self.status_label.config(text=f"ファイルを開きました: {filepath}")
            self.is_dirty = False # ファイルを開いたので状態をクリーンに
        except Exception as e:
            messagebox.showerror("読み込みエラー", f"ファイルの読み込み中にエラーが発生しました:\n{e}")

    # --- .txt インポート/エクスポート機能 ---

    def _find_matching_brace(self, text, start_index):
        """指定された開始波括弧に対応する閉じ波括弧を見つける"""
        brace_level = 0
        for i in range(start_index, len(text)):
            if text[i] == '{':
                brace_level += 1
            elif text[i] == '}':
                brace_level -= 1
                if brace_level == 0:
                    return i
        return -1

    def _parse_focus_block(self, block_text):
        """単一の focus = { ... } ブロックの内部を解析する"""
        data = {
            'prerequisite': [],
            'x': 0, # Base x
            'y': 0, # Base y
            'completion_reward': '{ }',
            'icon': 'GFX_focus_generic_question_mark' # Default icon
        }

        # ブロック内のコメントを削除
        current_text = re.sub(r'#.*', '', block_text)

        # --- offset ブロックの解析 ---
        offset_x = 0
        offset_y = 0
        offset_match = re.search(r'\boffset\s*=\s*\{([\s\S]*?)\}', current_text)
        if offset_match:
            offset_content = offset_match.group(1)
            offset_x_match = re.search(r'x\s*=\s*(-?\d+)', offset_content)
            offset_y_match = re.search(r'y\s*=\s*(-?\d+)', offset_content)
            offset_x = int(offset_x_match.group(1)) if offset_x_match else 0
            offset_y = int(offset_y_match.group(1)) if offset_y_match else 0
            # Remove the offset block from current_text
            current_text = current_text[:offset_match.start()] + current_text[offset_match.end():]

        # --- completion_reward ブロックの解析 ---
        completion_reward_match = re.search(r'\bcompletion_reward\s*=\s*\{([\s\S]*?)\}', current_text)
        if completion_reward_match:
            data['completion_reward'] = "{\n" + completion_reward_match.group(1).strip() + "\n\t\t}"
            # Remove the completion_reward block from current_text
            current_text = current_text[:completion_reward_match.start()] + current_text[completion_reward_match.end():]

        # --- すべての prerequisite ブロックの解析 ---
        all_prerequisites = []
        # Find all prerequisite blocks and remove them from current_text
        # Iterate in reverse to avoid index issues when removing
        prereq_matches = list(re.finditer(r'\bprerequisite\s*=\s*\{([\s\S]*?)\}', current_text))
        for match in reversed(prereq_matches):
            prereq_content = match.group(1)
            focuses = re.findall(r'focus\s*=\s*(\w+)', prereq_content)
            all_prerequisites.extend(focuses)
            current_text = current_text[:match.start()] + current_text[match.end():]
        data['prerequisite'] = list(set(all_prerequisites)) # 重複を削除

        # --- 単純なキー=値ペアの解析 (id, icon, cost, x, y, relative_position_id) ---
        # Now current_text should only contain top-level key-value pairs
        for line in current_text.split('\n'):
            line = line.strip()
            # Skip empty lines or lines that might contain stray braces from removed blocks
            if not line or '{' in line or '}' in line:
                continue
            
            parts = line.split('=')
            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].strip()
                if key == 'id':
                    data['id'] = value
                elif key == 'icon':
                    data['icon'] = value
                elif key == 'relative_position_id':
                    data['relative_position_id'] = value
                elif key == 'cost':
                    try:
                        data['cost'] = int(value)
                    except ValueError:
                        pass
                elif key == 'x':
                    try:
                        data['x'] = int(value) # This is the base x coordinate
                    except ValueError:
                        pass
                elif key == 'y':
                    try:
                        data['y'] = int(value) # This is the base y coordinate
                    except ValueError:
                        pass
        
        # 基準のx, y座標にoffsetを加算して最終的な座標とする
        data['x'] += offset_x
        data['y'] += offset_y
        
        return data if 'id' in data else None

    def _parse_hoi4_txt(self, text_content):
        """Hoi4の.txtファイルの内容全体を解析する"""
        # ファイル全体のコメントを削除
        text_content = re.sub(r'#.*', '', text_content)
        
        nodes = {}
        cursor = 0
        while True:
            # focus = { ブロックの開始を検索
            match = re.search(r'\bfocus\s*=\s*\{', text_content[cursor:])
            if not match:
                break
            
            start_brace = cursor + match.end() - 1 # '{' の位置
            end_brace = self._find_matching_brace(text_content, start_brace)
            
            if end_brace == -1:
                messagebox.showwarning("解析エラー", "対応する波括弧が見つかりませんでした。ファイルが破損している可能性があります。")
                break
            
            block_content = text_content[start_brace + 1 : end_brace] # focusブロックの中身
            node_data = self._parse_focus_block(block_content)
            if node_data and 'id' in node_data: # idが存在することを確認
                nodes[node_data['id']] = FocusNode(node_data)
            
            cursor = end_brace + 1 # 次の検索開始位置を更新
            
        return nodes

    def import_hoi4_txt(self):
        """Hoi4の.txtファイルをインポートする"""
        if self.is_dirty and not messagebox.askyesno("確認", "未保存の変更があります。現在のツリーを破棄してインポートしますか？"):
            return

        filepath = filedialog.askopenfilename(
            title="Hoi4 国家方針ファイルを開く",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not filepath:
            return

        try:
            with open(filepath, 'r', encoding='utf-8-sig') as f: # utf-8-sigでBOMに対応
                content = f.read()
            
            parsed_nodes = self._parse_hoi4_txt(content)
            if not parsed_nodes:
                messagebox.showinfo("情報", "ファイルから国家方針が見つかりませんでした。")
                return

            self.focus_nodes = parsed_nodes
            self.select_node(None)
            self.draw_tree()
            self.status_label.config(text=f"TXTファイルをインポートしました: {filepath}")
            self.is_dirty = False # インポートしたので状態をクリーンに

        except Exception as e:
            messagebox.showerror("インポートエラー", f"ファイルの読み込みまたは解析中にエラーが発生しました:\n{e}")

    def export_hoi4_txt(self):
        """現在のツリーをHoi4の.txtファイルとしてエクスポートする"""
        script_string = self._generate_script_string()
        if not script_string:
            messagebox.showinfo("情報", "エクスポートする国家方針がありません。")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Hoi4 国家方針ファイルとして保存",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not filepath:
            return

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(script_string)
            self.status_label.config(text=f"TXTファイルにエクスportしました: {filepath}")
            # エクスポートは保存ではないので dirty フラグは変更しない
            # self.is_dirty = False # エクスポートは保存ではないので状態は変更しない
        except Exception as e:
            messagebox.showerror("エクスポートエラー", f"ファイルの保存中にエラーが発生しました:\n{e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = FocusTreeApp(root)
    root.mainloop()
