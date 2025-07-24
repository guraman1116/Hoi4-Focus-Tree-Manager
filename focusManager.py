import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, Toplevel, filedialog
import json
import re
import os
import tempfile
import subprocess
import asyncio # 非同期処理のためにasyncioをインポート
import threading # スレッド処理のためにthreadingをインポート
import requests # HTTPリクエストのためにrequestsをインポート

# --- 定数定義 ---
GRID_SIZE = 240
NODE_RADIUS = 30
ARROW_COLOR = "#333333"
NODE_COLOR = "#CCCCCC"
NODE_HIGHLIGHT_COLOR = "#AADDFF"
TEXT_COLOR = "#000000"

# 標準のPython環境でfetch関数をシミュレートするためのダミー関数
# 実際のウェブ環境やaiohttpのようなライブラリとは異なる動作をする可能性があります
async def fetch(url, options):
    """
    requestsを使用してブラウザライクなfetchをシミュレートする非同期関数。
    同期的なrequests呼び出しをasyncio.to_threadで別スレッドで実行し、
    メインのasyncioループをブロックしないようにします。
    """
    method = options.get('method', 'GET')
    headers = options.get('headers', {})
    body = options.get('body', None)

    def _sync_request():
        if method == 'POST':
            # bodyが辞書の場合はjsonとして送信
            if isinstance(body, dict):
                return requests.post(url, headers=headers, json=body)
            else: # その他の場合はdataとして送信
                return requests.post(url, headers=headers, data=body)
        else:
            return requests.get(url, headers=headers)

    # 同期的なリクエストを別スレッドで実行し、asyncioループをブロックしないようにする
    response = await asyncio.to_thread(_sync_request)

    # requestsのresponseオブジェクトに.json()メソッドがあることを想定
    # もしrequestsのresponseオブジェクトが直接awaitableでない場合、
    # aiohttpのような真の非同期HTTPクライアントの使用を検討してください。
    class MockResponse:
        def __init__(self, res):
            self.res = res
        async def json(self):
            return self.res.json()
    
    return MockResponse(response)


class FocusNode:
    """国家方針のデータを保持するクラス"""
    def __init__(self, data):
        self.id = data.get("id", "")
        self.icon = data.get("icon", "GFX_focus_generic_question_mark")
        self.prerequisite = data.get("prerequisite", [])
        self.relative_position_id = data.get("relative_position_id", None)
        self.cost = data.get("cost", 10)
        self.x = data.get("x", 0)
        self.y = data.get("y", 0)
        self.completion_reward = data.get("completion_reward", "{\n\t\t\t\n\t\t}")
        self.name = data.get("name", "")
        self.description = data.get("description", "")

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
            "name": self.name,
            "description": self.description,
        }

    def to_hoi4_format(self):
        """Hoi4のスクリプト形式の文字列を生成する"""
        lines = []
        lines.append(f"\tfocus = {{")
        lines.append(f"\t\tid = {self.id}")
        lines.append(f"\t\ticon = {self.icon}")
        lines.append(f"\t\tcost = {self.cost}")

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

        lines.append(f"\t\tx = {self.x}")
        lines.append(f"\t\ty = {self.y}")

        reward_str = self.completion_reward.strip()
        if reward_str:
             lines.append(f"\t\tcompletion_reward = {reward_str}")
        else:
             lines.append(f"\t\tcompletion_reward = {{ }}")


        lines.append(f"\t}}")
        return "\n".join(lines)


class CanvasIDSelectorWindow(Toplevel):
    """キャンバス上で国家方針IDを選択するためのモーダルウィンドウ"""
    def __init__(self, parent, focus_nodes, current_selected_ids=None, mode='single'):
        super().__init__(parent)
        self.parent = parent
        self.focus_nodes = focus_nodes
        self.mode = mode
        self.result = None

        self.title("国家方針を選択")
        self.geometry("800x600")
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.zoom_level = 1.0
        
        if self.mode == 'single':
            self.selected_node_id_in_selector = current_selected_ids
            self.selected_node_ids_in_selector = []
        else:
            self.selected_node_id_in_selector = None
            self.selected_node_ids_in_selector = list(current_selected_ids) if current_selected_ids else []

        self.create_widgets()
        self.draw_tree()

        self.drag_data = {"x": 0, "y": 0, "item": None}

    def create_widgets(self):
        """ウィジェットを作成し配置する"""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(main_frame, bg="white", scrollregion=(-2000, -2000, 2000, 2000))
        self.canvas.pack(fill=tk.BOTH, expand=True)

        hbar = ttk.Scrollbar(main_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        vbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas.config(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)

        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(button_frame, text="OK", command=self.ok).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="キャンセル", command=self.cancel).pack(side=tk.RIGHT)

    def calculate_positions(self):
        """全ノードの絶対座標を計算する (セレクター用)"""
        calculated_nodes = set()
        
        queue = []
        for node in self.focus_nodes.values():
            if not node.relative_position_id or node.relative_position_id not in self.focus_nodes:
                node.abs_x = node.x * GRID_SIZE
                node.abs_y = node.y * GRID_SIZE
                calculated_nodes.add(node.id)
                queue.append(node)

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
        
        for node in self.focus_nodes.values():
            if node.id not in calculated_nodes:
                 node.abs_x = node.x * GRID_SIZE
                 node.abs_y = node.y * GRID_SIZE

    def draw_tree(self):
        """キャンバスにツリー全体を描画する (セレクター用)"""
        self.canvas.delete("all")
        self.calculate_positions()

        for node in self.focus_nodes.values():
            for prereq_id in node.prerequisite:
                if prereq_id in self.focus_nodes:
                    prereq_node = self.focus_nodes[prereq_id]
                    
                    x1_start = prereq_node.abs_x * self.zoom_level
                    y1_start = (prereq_node.abs_y + NODE_RADIUS) * self.zoom_level

                    x2_end = node.abs_x * self.zoom_level
                    y2_end = (node.abs_y - NODE_RADIUS) * self.zoom_level

                    mid_y_offset = 20 * self.zoom_level
                    mid_y = max(y1_start + mid_y_offset, y2_end)

                    points = [
                        x1_start, y1_start,
                        x1_start, mid_y,
                        x2_end, mid_y,
                        x2_end, y2_end
                    ]

                    self.canvas.create_line(
                        points,
                        fill=ARROW_COLOR, width=2 * self.zoom_level, arrow=tk.LAST, smooth=False
                    )

        for node_id, node in self.focus_nodes.items():
            scaled_x = node.abs_x * self.zoom_level
            scaled_y = node.abs_y * self.zoom_level
            scaled_radius = NODE_RADIUS * self.zoom_level

            x0 = scaled_x - scaled_radius
            y0 = scaled_y - scaled_radius
            x1 = scaled_x + scaled_radius
            y1 = scaled_y + scaled_radius
            
            fill_color = NODE_COLOR
            text_color = TEXT_COLOR

            if self.mode == 'single':
                if node_id == self.selected_node_id_in_selector:
                    fill_color = NODE_HIGHLIGHT_COLOR
                    text_color = NODE_HIGHLIGHT_COLOR
            elif self.mode == 'multiple':
                if node_id in self.selected_node_ids_in_selector:
                    fill_color = NODE_HIGHLIGHT_COLOR
                    text_color = NODE_HIGHLIGHT_COLOR
            
            self.canvas.create_oval(x0, y0, x1, y1, fill=fill_color, outline="black", width=2 * self.zoom_level, tags=("node", node_id))
            font_size = max(6, int(8 * self.zoom_level))
            
            display_text = node.name if node.name else node_id
            self.canvas.create_text(scaled_x, scaled_y + scaled_radius + 10 * self.zoom_level, text=display_text, fill=text_color, font=("Arial", font_size), tags=("node", node_id))

    def on_canvas_click(self, event):
        """キャンバスクリックでノードを選択"""
        self.canvas.scan_mark(event.x, event.y)

        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        clicked_items = self.canvas.find_overlapping(canvas_x - 1, canvas_y - 1, canvas_x + 1, canvas_y + 1)
        node_id = None
        for item in clicked_items:
            tags = self.canvas.gettags(item)
            if "node" in tags:
                node_id = tags[1]
                break
        
        if node_id:
            if self.mode == 'single':
                self.selected_node_id_in_selector = node_id
            elif self.mode == 'multiple':
                if node_id in self.selected_node_ids_in_selector:
                    self.selected_node_ids_in_selector.remove(node_id)
                else:
                    self.selected_node_ids_in_selector.append(node_id)
            self.draw_tree()
        else:
            if self.mode == 'single':
                self.selected_node_id_in_selector = None
            self.draw_tree()


    def on_canvas_drag(self, event):
        """キャンバスのドラッグイベント（画面スクロール）"""
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def on_canvas_release(self, event):
        """ドラッグ終了"""
        pass

    def on_mouse_wheel(self, event):
        """マウスホイールによるズームイン・アウト (セレクター用)"""
        if event.delta > 0 or event.num == 4:
            self.zoom_level *= 1.1
        elif event.delta < 0 or event.num == 5:
            self.zoom_level /= 1.1
        self.zoom_level = max(0.1, min(self.zoom_level, 5.0))
        self.draw_tree()

    def ok(self):
        """選択を確定してウィンドウを閉じる"""
        if self.mode == 'single':
            self.result = self.selected_node_id_in_selector
        elif self.mode == 'multiple':
            self.result = self.selected_node_ids_in_selector
        self.destroy()

    def cancel(self):
        """選択をキャンセルしてウィンドウを閉じる"""
        self.result = None
        self.destroy()


class FocusEditorWindow(Toplevel):
    """国家方針の情報を編集するためのウィンドウ"""
    def __init__(self, parent, app_instance, focus_node=None, initial_x=0, initial_y=0):
        super().__init__(parent)
        self.parent = parent
        self.app_instance = app_instance
        self.focus_node = focus_node
        self.all_focus_nodes = app_instance.focus_nodes
        self.existing_ids = list(self.all_focus_nodes.keys())
        self.original_id = focus_node.id if focus_node else None
        self.initial_x = initial_x
        self.initial_y = initial_y

        self.title("国家方針の編集" if focus_node else "新規国家方針の作成")
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.result = None
        self.prereq_vars = {}
        self.temp_reward_filepath = None
        self.last_mod_time = None

        self.create_widgets()
        if self.focus_node:
            self.load_data()
        else:
            self.x_var.set(self.initial_x)
            self.y_var.set(self.initial_y)
        
        self.protocol("WM_DELETE_WINDOW", self._on_closing_editor_window)

        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth()}x{self.winfo_reqheight()}")


    def create_widgets(self):
        """ウィジェットを作成し配置する"""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="ID:").grid(row=0, column=0, sticky="w", pady=2)
        self.id_var = tk.StringVar()
        self.id_entry = ttk.Entry(main_frame, textvariable=self.id_var)
        self.id_entry.grid(row=0, column=1, columnspan=2, sticky="ew", pady=2)

        ttk.Label(main_frame, text="コスト (cost):").grid(row=1, column=0, sticky="w", pady=2)
        self.cost_var = tk.IntVar(value=10)
        self.cost_spinbox = ttk.Spinbox(main_frame, from_=0, to=1000, increment=7, textvariable=self.cost_var)
        self.cost_spinbox.grid(row=1, column=1, columnspan=2, sticky="ew", pady=2)

        ttk.Label(main_frame, text="相対位置の基準ID (relative_position_id):").grid(row=2, column=0, sticky="w", pady=2)
        self.relative_id_var = tk.StringVar()
        relative_ids_for_combo = [""] + [fid for fid in self.existing_ids if fid != self.original_id]
        self.relative_id_combo = ttk.Combobox(main_frame, textvariable=self.relative_id_var, values=relative_ids_for_combo)
        self.relative_id_combo.grid(row=2, column=1, sticky="ew", pady=2)
        ttk.Button(main_frame, text="キャンバスから選択", command=self.select_relative_id_from_canvas).grid(row=2, column=2, sticky="w", pady=2, padx=5)


        ttk.Label(main_frame, text="相対位置 (x, y):").grid(row=3, column=0, sticky="w", pady=2)
        pos_frame = ttk.Frame(main_frame)
        pos_frame.grid(row=3, column=1, columnspan=2, sticky="ew")
        self.x_var = tk.IntVar(value=0)
        self.y_var = tk.IntVar(value=0)
        ttk.Label(pos_frame, text="x:").pack(side=tk.LEFT)
        ttk.Spinbox(pos_frame, from_=-50, to=50, textvariable=self.x_var, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Label(pos_frame, text="y:").pack(side=tk.LEFT)
        ttk.Spinbox(pos_frame, from_=-50, to=50, textvariable=self.y_var, width=5).pack(side=tk.LEFT, padx=5)

        prereq_label_frame = ttk.Frame(main_frame)
        prereq_label_frame.grid(row=4, column=0, sticky="w", pady=5)
        ttk.Label(prereq_label_frame, text="前提条件 (prerequisite):").pack(side=tk.LEFT)
        ttk.Button(prereq_label_frame, text="キャンバスから選択", command=self.select_prerequisites_from_canvas).pack(side=tk.LEFT, padx=5)
        
        prereq_outer_frame = ttk.Frame(main_frame)
        prereq_outer_frame.grid(row=5, column=0, columnspan=3, sticky="nsew")
        main_frame.rowconfigure(5, weight=1)

        self.prereq_canvas = tk.Canvas(prereq_outer_frame, borderwidth=1, relief="sunken", background="#ffffff")
        self.prereq_canvas.pack(side="left", fill="both", expand=True)

        prereq_scrollbar = ttk.Scrollbar(prereq_outer_frame, orient="vertical", command=self.prereq_canvas.yview)
        prereq_scrollbar.pack(side="right", fill="y")

        self.prereq_canvas.configure(yscrollcommand=prereq_scrollbar.set)
        self.prereq_canvas.bind('<Configure>', lambda e: self.prereq_canvas.configure(scrollregion = self.prereq_canvas.bbox("all")))

        self.prereq_inner_frame = ttk.Frame(self.prereq_canvas)
        self.prereq_canvas.create_window((0, 0), window=self.prereq_inner_frame, anchor="nw")

        prereq_ids = [fid for fid in self.existing_ids if fid != self.original_id]
        prereq_ids.sort()

        for i, fid in enumerate(prereq_ids):
            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(self.prereq_inner_frame, text=fid, variable=var)
            cb.grid(row=i, column=0, sticky="w", padx=2, pady=1)
            self.prereq_vars[fid] = var

        self.prereq_inner_frame.update_idletasks()
        self.prereq_canvas.config(scrollregion=self.prereq_canvas.bbox("all"))

        ttk.Label(main_frame, text="名称 (name):").grid(row=8, column=0, sticky="w", pady=2)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(main_frame, textvariable=self.name_var)
        self.name_entry.grid(row=8, column=1, columnspan=2, sticky="ew", pady=2)

        ttk.Label(main_frame, text="説明 (description):").grid(row=9, column=0, sticky="w", pady=2)
        self.description_text = tk.Text(main_frame, height=5, wrap=tk.WORD)
        self.description_text.grid(row=9, column=1, columnspan=2, sticky="nsew", pady=2)
        desc_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.description_text.yview)
        desc_scrollbar.grid(row=9, column=3, sticky="ns")
        self.description_text.config(yscrollcommand=desc_scrollbar.set)
        main_frame.rowconfigure(9, weight=1)

        reward_label_frame = ttk.Frame(main_frame)
        reward_label_frame.grid(row=10, column=0, sticky="w", pady=5)
        ttk.Label(reward_label_frame, text="達成時効果 (completion_reward):").pack(side=tk.LEFT)
        ttk.Button(reward_label_frame, text="外部エディタで編集", command=self._open_external_editor).pack(side=tk.LEFT, padx=5)

        reward_frame = ttk.Frame(main_frame)
        reward_frame.grid(row=11, column=0, columnspan=3, sticky="nsew")
        self.reward_text = tk.Text(reward_frame, height=10, wrap=tk.WORD)
        self.reward_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        reward_scrollbar = ttk.Scrollbar(reward_frame, orient=tk.VERTICAL, command=self.reward_text.yview)
        reward_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.reward_text.config(yscrollcommand=reward_scrollbar.set)

        main_frame.rowconfigure(11, weight=1)
        main_frame.columnconfigure(1, weight=1)

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
        self.name_var.set(self.focus_node.name)
        self.description_text.insert("1.0", self.focus_node.description)

        for fid, var in self.prereq_vars.items():
            if fid in self.focus_node.prerequisite:
                var.set(True)
            else:
                var.set(False)

    def save(self):
        """入力されたデータを検証して保存する"""
        self._stop_monitoring_temp_file()
        
        focus_id = self.id_var.get().strip()
        if not focus_id:
            messagebox.showerror("エラー", "IDは必須です。")
            return
        if focus_id != self.original_id and focus_id in self.existing_ids:
            messagebox.showerror("エラー", f"ID '{focus_id}' は既に使用されています。")
            return

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
            "completion_reward": self.reward_text.get("1.0", tk.END).strip(),
            "name": self.name_var.get().strip(),
            "description": self.description_text.get("1.0", tk.END).strip()
        }
        self.result = data
        self.destroy()

    def cancel(self):
        self._stop_monitoring_temp_file()
        self.result = None
        self.destroy()

    def _on_closing_editor_window(self):
        """エディタウィンドウが閉じられる際の処理"""
        self._stop_monitoring_temp_file()
        self.destroy()

    def select_relative_id_from_canvas(self):
        """キャンバスからrelative_position_idを選択するモーダルを開く"""
        selector = CanvasIDSelectorWindow(self, self.app_instance.focus_nodes, self.relative_id_var.get(), mode='single')
        self.wait_window(selector)

        if selector.result:
            self.relative_id_var.set(selector.result)

    def select_prerequisites_from_canvas(self):
        """キャンバスから前提条件を選択するモーダルを開く"""
        current_prerequisites = [fid for fid, var in self.prereq_vars.items() if var.get()]
        
        selector = CanvasIDSelectorWindow(self, self.app_instance.focus_nodes, current_prerequisites, mode='multiple')
        self.wait_window(selector)

        if selector.result is not None:
            selected_prerequisites = selector.result
            for fid, var in self.prereq_vars.items():
                var.set(False)
            for fid in selected_prerequisites:
                if fid in self.prereq_vars:
                    self.prereq_vars[fid].set(True)

    def _open_external_editor(self):
        """completion_rewardの内容を一時ファイルに保存し、外部エディタで開く"""
        current_reward_content = self.reward_text.get("1.0", tk.END).strip()

        try:
            fd, self.temp_reward_filepath = tempfile.mkstemp(suffix=".txt", prefix="hoi4_reward_")
            with os.fdopen(fd, 'w', encoding='utf-8') as tmp_file:
                tmp_file.write(current_reward_content)
            
            self.last_mod_time = os.path.getmtime(self.temp_reward_filepath)

            if os.name == 'nt':
                os.startfile(self.temp_reward_filepath)
            elif os.uname().sysname == 'Darwin':
                subprocess.Popen(['open', self.temp_reward_filepath])
            else:
                subprocess.Popen(['xdg-open', self.temp_reward_filepath])
            
            messagebox.showinfo("外部エディタ", f"一時ファイル '{os.path.basename(self.temp_reward_filepath)}' を外部エディタで開きました。\n変更を保存すると自動的に反映されます。")
            
            self.after_id = self.after(1000, self._check_temp_file_for_changes)

        except Exception as e:
            messagebox.showerror("エラー", f"外部エディタを開けませんでした:\n{e}")
            self._stop_monitoring_temp_file()

    def _check_temp_file_for_changes(self):
        """一時ファイルの変更を監視し、変更があれば内容を読み込む"""
        if self.temp_reward_filepath and os.path.exists(self.temp_reward_filepath):
            try:
                new_mod_time = os.path.getmtime(self.temp_reward_filepath)
                if new_mod_time != self.last_mod_time:
                    with open(self.temp_reward_filepath, 'r', encoding='utf-8') as tmp_file:
                        updated_content = tmp_file.read()
                    
                    self.reward_text.delete("1.0", tk.END)
                    self.reward_text.insert("1.0", updated_content)
                    self.last_mod_time = new_mod_time
                    self.app_instance.is_dirty = True
                    self.app_instance.status_label.config(text="外部エディタからの変更を反映しました。")
            except Exception as e:
                print(f"一時ファイルの読み込み中にエラー: {e}")
                self._stop_monitoring_temp_file()
        else:
            self._stop_monitoring_temp_file()
            messagebox.showinfo("外部エディタ", "一時ファイルが見つかりません。外部エディタでの編集を終了します。")

        if hasattr(self, 'after_id') and self.after_id:
             self.after_id = self.after(1000, self._check_temp_file_for_changes)


    def _stop_monitoring_temp_file(self):
        """一時ファイルの監視を停止し、ファイルを削除する"""
        if hasattr(self, 'after_id') and self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        
        if self.temp_reward_filepath and os.path.exists(self.temp_reward_filepath):
            try:
                os.remove(self.temp_reward_filepath)
                print(f"一時ファイル {self.temp_reward_filepath} を削除しました。")
            except Exception as e:
                print(f"一時ファイルの削除中にエラー: {e}")
            finally:
                self.temp_reward_filepath = None
                self.last_mod_time = None

class AIFocusGeneratorWindow(Toplevel):
    """AIで国家方針を生成するためのウィンドウ"""
    def __init__(self, parent, app_instance):
        super().__init__(parent)
        self.parent = parent
        self.app_instance = app_instance
        self.title("AIで国家方針を生成")
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.generated_focus_data = None

        self.create_widgets()
        self.update_idletasks()
        self.geometry(f"{self.winfo_reqwidth()}x{self.winfo_reqheight()}")

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="生成したい国家方針のコンセプトを入力してください:").pack(anchor="w", pady=5)
        self.concept_text = tk.Text(main_frame, height=5, wrap=tk.WORD)
        self.concept_text.pack(fill=tk.X, pady=2)

        # 修正されたコマンド: asyncioタスクをapp_instanceのループにthreadsafeに送信
        self.generate_button = ttk.Button(main_frame, text="生成",
                                           command=lambda: self.app_instance.loop.call_soon_threadsafe(
                                               self.app_instance.loop.create_task, self._generate_focus_with_ai()))
        self.generate_button.pack(pady=10)

        self.loading_label = ttk.Label(main_frame, text="", foreground="blue")
        self.loading_label.pack(pady=5)

        ttk.Label(main_frame, text="生成された国家方針データ (JSON):").pack(anchor="w", pady=5)
        self.generated_json_text = tk.Text(main_frame, height=15, wrap=tk.WORD, state=tk.DISABLED, background="#f0f0f0")
        self.generated_json_text.pack(fill=tk.BOTH, expand=True, pady=2)

        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.add_button = ttk.Button(button_frame, text="国家方針として追加", command=self._add_generated_focus, state=tk.DISABLED)
        self.add_button.pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="キャンセル", command=self.cancel).pack(side=tk.RIGHT)

    def _load_api_key(self):
        """外部ファイルからAPIキーを読み込む"""
        # スクリプトのディレクトリパスを取得
        script_dir = os.path.dirname(os.path.abspath(__file__))
        api_key_file_path = os.path.join(script_dir, "api_key.txt")

        try:
            with open(api_key_file_path, 'r', encoding='utf-8') as f:
                api_key = f.read().strip()
                if not api_key:
                    messagebox.showwarning("APIキーエラー", f"'{api_key_file_path}' が空です。有効なAPIキーを入力してください。")
                    return None
                return api_key
        except FileNotFoundError:
            messagebox.showerror("APIキーエラー", f"'{api_key_file_path}' が見つかりません。\nスクリプトと同じディレクトリにAPIキーを記述したファイルを作成してください。")
            return None
        except Exception as e:
            messagebox.showerror("APIキーエラー", f"'{api_key_file_path}' の読み込み中にエラーが発生しました:\n{e}")
            return None

    async def _generate_focus_with_ai(self):
        """Gemini APIを呼び出して国家方針を生成する"""
        concept = self.concept_text.get("1.0", tk.END).strip()
        if not concept:
            messagebox.showwarning("入力エラー", "コンセプトを入力してください。")
            return

        api_key = self._load_api_key()
        if not api_key:
            return # APIキーがロードできなかった場合、処理を中断

        self.loading_label.config(text="生成中...")
        self.generate_button.config(state=tk.DISABLED)
        self.add_button.config(state=tk.DISABLED)
        self.generated_json_text.config(state=tk.NORMAL)
        self.generated_json_text.delete("1.0", tk.END)
        self.generated_json_text.config(state=tk.DISABLED)
        self.generated_focus_data = None

        try:
            chatHistory = []
            prompt = f"以下のコンセプトに基づいて、Hearts of Iron IVの国家方針データをJSON形式で生成してください。ID、名称、説明は必須です。X, Y座標は-10から10の範囲で整数で指定してください。prerequisiteとrelative_position_idは既存の国家方針IDを参照するか、nullにしてください。completion_rewardはHoI4のスクリプト形式の文字列で、中身は空の`{{ }}`でも構いません。iconは`GFX_focus_generic_question_mark`のような形式で指定してください。\n\nコンセプト: {concept}"
            chatHistory.append({ "role": "user", "parts": [{ "text": prompt }] }) # appendを使用

            payload = {
                "contents": chatHistory,
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": {
                        "type": "OBJECT",
                        "properties": {
                            "id": {"type": "STRING", "description": "国家方針のユニークなID (例: JAP_new_focus)"},
                            "name": {"type": "STRING", "description": "国家方針の表示名"},
                            "description": {"type": "STRING", "description": "国家方針の説明"},
                            "icon": {"type": "STRING", "default": "GFX_focus_generic_question_mark", "description": "国家方針のアイコン (例: GFX_focus_generic_question_mark)"},
                            "cost": {"type": "INTEGER", "default": 10, "description": "国家方針のコスト"},
                            "x": {"type": "INTEGER", "default": 0, "description": "相対X座標 (-10から10)"},
                            "y": {"type": "INTEGER", "default": 0, "description": "相対Y座標 (-10から10)"},
                            "prerequisite": {"type": "ARRAY", "items": {"type": "STRING"}, "default": [], "description": "前提となる国家方針のIDのリスト"},
                            "relative_position_id": {"type": "STRING", "nullable": True, "default": None, "description": "相対位置の基準となる国家方針のID"},
                            "completion_reward": {"type": "STRING", "default": "{\n\t\t\t\n\t\t}", "description": "達成時の効果スクリプト"}
                        },
                        "required": ["id", "name", "description"]
                    }
                }
            }

            apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

            # fetch関数はrequestsをasyncio.to_threadでラップしているため、
            # bodyはjson.dumpsではなく、直接Pythonの辞書として渡す
            response = await fetch(apiUrl, {
                'method': 'POST',
                'headers': {'Content-Type': 'application/json'},
                'body': payload # json.dumpsせずに直接payloadを渡す
            })
            
            result = await response.json()

            if result.candidates and result.candidates[0].content and result.candidates[0].content.parts:
                generated_json_str = result.candidates[0].content.parts[0].text
                self.generated_json_text.config(state=tk.NORMAL)
                self.generated_json_text.insert("1.0", generated_json_str)
                self.generated_json_text.config(state=tk.DISABLED)

                try:
                    self.generated_focus_data = json.loads(generated_json_str)
                    if self.generated_focus_data.get('id') in self.app_instance.focus_nodes:
                        messagebox.showwarning("ID重複", f"生成された国家方針のID '{self.generated_focus_data.get('id')}' は既に存在します。IDを変更してください。")
                        self.add_button.config(state=tk.DISABLED)
                    else:
                        self.add_button.config(state=tk.NORMAL)
                except json.JSONDecodeError:
                    messagebox.showerror("解析エラー", "AIが有効なJSONを生成しませんでした。")
                    self.add_button.config(state=tk.DISABLED)
            else:
                messagebox.showerror("生成失敗", "AIが国家方針を生成できませんでした。")
                self.add_button.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror("通信エラー", f"AIとの通信中にエラーが発生しました:\n{e}")
            self.add_button.config(state=tk.DISABLED)
        finally:
            self.loading_label.config(text="")
            self.generate_button.config(state=tk.NORMAL)

    def _add_generated_focus(self):
        """生成された国家方針をツリーに追加する"""
        if not self.generated_focus_data:
            messagebox.showwarning("データなし", "追加する国家方針データがありません。")
            return

        focus_id = self.generated_focus_data.get('id')
        if focus_id in self.app_instance.focus_nodes:
            messagebox.showerror("ID重複", f"国家方針のID '{focus_id}' は既に存在します。生成されたJSONのIDを修正してください。")
            return

        try:
            new_node = FocusNode(self.generated_focus_data)
            self.app_instance.focus_nodes[new_node.id] = new_node
            self.app_instance.draw_tree()
            self.app_instance.status_label.config(text=f"AIが生成した'{new_node.id}' を追加しました。")
            self.app_instance.select_node(new_node.id)
            self.app_instance.is_dirty = True
            self.destroy()
        except Exception as e:
            messagebox.showerror("追加エラー", f"国家方針の追加中にエラーが発生しました:\n{e}")

    def cancel(self):
        self.destroy()


class FocusTreeApp:
    """アプリケーション本体のクラス"""
    def __init__(self, root):
        self.root = root
        self.root.title("HoI4 国家方針ツリー作成ツール")
        self.root.geometry("1024x768")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.focus_nodes = {}
        self.selected_node_id = None
        self.zoom_level = 1.0
        self.last_right_click_canvas_x = 0
        self.last_right_click_canvas_y = 0
        self.is_dirty = False

        # --- Asyncio setup ---
        # 新しいイベントループを作成し、それをこのスレッドに設定
        self.loop = asyncio.new_event_loop()
        # イベントループを別スレッドで実行
        self.async_thread = threading.Thread(target=self._run_asyncio_loop_in_thread, daemon=True)
        self.async_thread.start()
        # --- End Asyncio setup ---

        self.create_menu()
        self.create_widgets()
        self.create_context_menus()
        self.bind_keyboard_events()

        self.draw_tree()

    def _run_asyncio_loop_in_thread(self):
        """asyncioイベントループを別スレッドで実行する"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def on_closing(self):
        """ウィンドウを閉じる際の確認ダイアログを表示する"""
        if self.is_dirty:
            response = messagebox.askyesnocancel("終了の確認", "未保存の変更があります。保存しますか？")
            if response is True:
                save_successful = self.save_file()
                if save_successful:
                    self._shutdown_asyncio() # Tkinter rootを破棄する前にasyncioをシャットダウン
                    self.root.destroy()
            elif response is False:
                self._shutdown_asyncio() # Tkinter rootを破棄する前にasyncioをシャットダウン
                self.root.destroy()
        else:
            self._shutdown_asyncio() # Tkinter rootを破棄する前にasyncioをシャットダウン
            self.root.destroy()

    def _shutdown_asyncio(self):
        """asyncioイベントループを正常にシャットダウンする"""
        if self.loop.is_running():
            # イベントループに停止をスケジュールし、すぐに実行
            self.loop.call_soon_threadsafe(self.loop.stop)
            # スレッドが終了するのを待つ（タイムアウトを設定してブロックしすぎないようにする）
            self.async_thread.join(timeout=1)
            if self.async_thread.is_alive():
                print("Warning: Asyncio thread did not terminate gracefully.")
        # イベントループを閉じる
        self.loop.close()


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
        file_menu.add_command(label="エクスポート (ローカリゼーション)...", command=self.export_localization_file)
        file_menu.add_separator()
        file_menu.add_command(label="終了", command=self.root.quit)

        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="編集", menu=edit_menu)
        edit_menu.add_command(label="国家方針を追加", command=self.add_focus_node)
        edit_menu.add_command(label="AIで国家方針を生成", command=self.open_ai_focus_generator_window)
        edit_menu.add_command(label="選択中の国家方針を編集", command=self.edit_selected_node, state=tk.DISABLED)
        edit_menu.add_command(label="選択中の国家方針を削除", command=self.delete_selected_node, state=tk.DISABLED)

        self.edit_menu = edit_menu

    def create_widgets(self):
        """メインウィンドウのウィジェットを作成する"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(main_frame, padding=5)
        toolbar.pack(fill=tk.X, side=tk.TOP)
        ttk.Button(toolbar, text="国家方針を追加", command=self.add_focus_node).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="AIで国家方針を生成", command=self.open_ai_focus_generator_window).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="スクリプトプレビュー", command=self.preview_script).pack(side=tk.LEFT, padx=5)
        self.status_label = ttk.Label(toolbar, text="準備完了")
        self.status_label.pack(side=tk.RIGHT, padx=10)

        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=5, pady=5)

        self.canvas = tk.Canvas(canvas_frame, bg="white", scrollregion=(-2000, -2000, 2000, 2000))
        
        hbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        vbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas.config(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click) 
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)

        self.drag_data = {"x": 0, "y": 0, "item": None}

    def create_context_menus(self):
        """右クリックメニューを作成する (ノード用とキャンバス用)"""
        self.node_context_menu = tk.Menu(self.root, tearoff=0)
        self.node_context_menu.add_command(label="国家方針を編集", command=self.edit_selected_node)
        self.node_context_menu.add_command(label="国家方針を削除", command=self.delete_selected_node)

        self.canvas_context_menu = tk.Menu(self.root, tearoff=0)
        self.canvas_context_menu.add_command(label="国家方針を追加", command=self.add_focus_node_at_clicked_position)
        self.canvas_context_menu.add_command(label="AIで国家方針を生成", command=self.open_ai_focus_generator_window)

    def bind_keyboard_events(self):
        """キーボードイベントをバインドする"""
        self.root.bind("<Left>", self.on_arrow_key_press)
        self.root.bind("<Right>", self.on_arrow_key_press)
        self.root.bind("<Up>", self.on_arrow_key_press)
        self.root.bind("<Down>", self.on_arrow_key_press)

    def on_arrow_key_press(self, event):
        """矢印キーが押されたときの処理"""
        if not self.selected_node_id:
            return

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
            self.is_dirty = True


    def on_mouse_wheel(self, event):
        """マウスホイールによるズームイン・アウト"""
        if event.delta > 0 or event.num == 4:
            self.zoom_level *= 1.1
        elif event.delta < 0 or event.num == 5:
            self.zoom_level /= 1.1
        
        self.zoom_level = max(0.1, min(self.zoom_level, 5.0))
        
        self.draw_tree()

    def on_canvas_click(self, event):
        """キャンバスのクリックイベント"""
        self.canvas.scan_mark(event.x, event.y)
        
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        
        clicked_items = self.canvas.find_overlapping(canvas_x - 1, canvas_y - 1, canvas_x + 1, canvas_y + 1)
        node_id = None
        for item in clicked_items:
            tags = self.canvas.gettags(item)
            if "node" in tags:
                node_id = tags[1]
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
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        detection_radius = NODE_RADIUS * self.zoom_level
        clicked_items = self.canvas.find_overlapping(
            canvas_x - detection_radius, canvas_y - detection_radius,
            canvas_x + detection_radius, canvas_y + detection_radius
        )
        node_id = None
        for item in clicked_items:
            tags = self.canvas.gettags(item)
            if isinstance(tags, tuple) and "node" in tags and len(tags) > 1:
                node_id = tags[1] 
                break
        
        self.last_right_click_canvas_x = canvas_x 
        self.last_right_click_canvas_y = canvas_y 

        if node_id:
            self.select_node(node_id)
            try:
                self.node_context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.node_context_menu.grab_release()
        else:
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
        if self.selected_node_id:
            items_to_unhighlight = self.canvas.find_withtag(self.selected_node_id)
            for item_id in items_to_unhighlight:
                item_type = self.canvas.type(item_id)
                if item_type == 'oval':
                    self.canvas.itemconfig(item_id, fill=NODE_COLOR)
                elif item_type == 'text':
                    self.canvas.itemconfig(item_id, fill=TEXT_COLOR)

        self.selected_node_id = node_id
        
        if self.selected_node_id:
            items_to_highlight = self.canvas.find_withtag(self.selected_node_id)
            for item_id in items_to_highlight:
                item_type = self.canvas.type(item_id)
                if item_type == 'oval':
                    self.canvas.itemconfig(item_id, fill=NODE_HIGHLIGHT_COLOR)
                elif item_type == 'text':
                    self.canvas.itemconfig(item_id, fill=NODE_HIGHLIGHT_COLOR)
            
            selected_node = self.focus_nodes[self.selected_node_id]
            display_text = selected_node.name if selected_node.name else selected_node.id
            self.status_label.config(text=f"選択中: {display_text}")

            self.edit_menu.entryconfig("選択中の国家方針を編集", state=tk.NORMAL)
            self.edit_menu.entryconfig("選択中の国家方針を削除", state=tk.NORMAL)
            self.node_context_menu.entryconfig("国家方針を編集", state=tk.NORMAL)
            self.node_context_menu.entryconfig("国家方針を削除", state=tk.NORMAL)
        else:
            self.status_label.config(text="準備完了")
            self.edit_menu.entryconfig("選択中の国家方針を編集", state=tk.DISABLED)
            self.edit_menu.entryconfig("選択中の国家方針を削除", state=tk.DISABLED)
            self.node_context_menu.entryconfig("国家方針を編集", state=tk.DISABLED)
            self.node_context_menu.entryconfig("国家方針を削除", state=tk.DISABLED)


    def add_focus_node(self):
        """国家方針追加ウィンドウを開く (ツールバーボタン用)"""
        editor = FocusEditorWindow(self.root, self, focus_node=None, initial_x=0, initial_y=0)
        self.root.wait_window(editor)

        if editor.result:
            new_node = FocusNode(editor.result)
            self.focus_nodes[new_node.id] = new_node
            self.draw_tree()
            self.status_label.config(text=f"'{new_node.id}' を追加しました。")
            self.select_node(new_node.id)
            self.is_dirty = True

    def add_focus_node_at_clicked_position(self):
        """右クリックされた座標に新しい国家方針を作成する"""
        initial_x = round(self.last_right_click_canvas_x / GRID_SIZE)
        initial_y = round(self.last_right_click_canvas_y / GRID_SIZE)

        editor = FocusEditorWindow(self.root, self, focus_node=None, initial_x=initial_x, initial_y=initial_y)
        self.root.wait_window(editor)

        if editor.result:
            new_node = FocusNode(editor.result)
            self.focus_nodes[new_node.id] = new_node
            self.draw_tree()
            self.status_label.config(text=f"'{new_node.id}' を追加しました。")
            self.select_node(new_node.id)
            self.is_dirty = True


    def edit_selected_node(self):
        """選択中のノードを編集する"""
        if not self.selected_node_id:
            return
        
        node_to_edit = self.focus_nodes[self.selected_node_id]
        
        self.calculate_positions() 
        original_abs_x = node_to_edit.abs_x
        original_abs_y = node_to_edit.abs_y
        original_relative_position_id = node_to_edit.relative_position_id
        
        editor = FocusEditorWindow(self.root, self, focus_node=node_to_edit)
        self.root.wait_window(editor)

        if editor.result:
            new_id = editor.result['id']
            new_relative_position_id = editor.result['relative_position_id']
            
            if new_relative_position_id != original_relative_position_id:
                new_parent_abs_x = 0
                new_parent_abs_y = 0
                if new_relative_position_id and new_relative_position_id in self.focus_nodes:
                    self.calculate_positions() 
                    new_parent_node = self.focus_nodes[new_relative_position_id]
                    new_parent_abs_x = new_parent_node.abs_x
                    new_parent_abs_y = new_parent_node.abs_y
                
                adjusted_x = round((original_abs_x - new_parent_abs_x) / GRID_SIZE)
                adjusted_y = round((original_abs_y - new_parent_abs_y) / GRID_SIZE)
                
                editor.result['x'] = adjusted_x
                editor.result['y'] = adjusted_y

            if self.selected_node_id != new_id:
                old_id = self.selected_node_id
                for node in self.focus_nodes.values():
                    if node.relative_position_id == old_id:
                        node.relative_position_id = new_id
                    if old_id in node.prerequisite:
                        node.prerequisite = [new_id if p == old_id else p for p in node.prerequisite]

                del self.focus_nodes[self.selected_node_id]
                self.selected_node_id = None

            updated_node = FocusNode(editor.result)
            self.focus_nodes[updated_node.id] = updated_node
            self.draw_tree()
            self.status_label.config(text=f"'{updated_node.id}' を更新しました。")
            self.select_node(updated_node.id)
            self.is_dirty = True


    def delete_selected_node(self):
        """選択中のノードを削除する"""
        if not self.selected_node_id:
            return

        if messagebox.askyesno("確認", f"国家方針 '{self.selected_node_id}' を削除しますか？\nこの操作は元に戻せません。"):
            deleted_id = self.selected_node_id
            del self.focus_nodes[deleted_id]
            self.select_node(None)

            for node in self.focus_nodes.values():
                if node.relative_position_id == deleted_id:
                    node.relative_position_id = None
                if deleted_id in node.prerequisite:
                    node.prerequisite.remove(deleted_id)
            
            self.draw_tree()
            self.status_label.config(text=f"'{deleted_id}' を削除しました。")
            self.is_dirty = True


    def calculate_positions(self):
        """全ノードの絶対座標を計算する"""
        calculated_nodes = set()
        
        queue = []
        for node in self.focus_nodes.values():
            if not node.relative_position_id or node.relative_position_id not in self.focus_nodes:
                node.abs_x = node.x * GRID_SIZE
                node.abs_y = node.y * GRID_SIZE
                calculated_nodes.add(node.id)
                queue.append(node)

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
        
        for node in self.focus_nodes.values():
            if node.id not in calculated_nodes:
                 node.abs_x = node.x * GRID_SIZE
                 node.abs_y = node.y * GRID_SIZE

    def draw_tree(self):
        """キャンバスにツリー全体を描画する"""
        self.canvas.delete("all")
        self.calculate_positions()

        for node in self.focus_nodes.values():
            for prereq_id in node.prerequisite:
                if prereq_id in self.focus_nodes:
                    prereq_node = self.focus_nodes[prereq_id]
                    
                    x1_start = prereq_node.abs_x * self.zoom_level
                    y1_start = (prereq_node.abs_y + NODE_RADIUS) * self.zoom_level

                    x2_end = node.abs_x * self.zoom_level
                    y2_end = (node.abs_y - NODE_RADIUS) * self.zoom_level

                    mid_y_offset = 20 * self.zoom_level
                    mid_y = max(y1_start + mid_y_offset, y2_end)

                    points = [
                        x1_start, y1_start,
                        x1_start, mid_y,
                        x2_end, mid_y,
                        x2_end, y2_end
                    ]

                    self.canvas.create_line(
                        points,
                        fill=ARROW_COLOR, width=2 * self.zoom_level, arrow=tk.LAST, smooth=False
                    )

        for node_id, node in self.focus_nodes.items():
            scaled_x = node.abs_x * self.zoom_level
            scaled_y = node.abs_y * self.zoom_level
            scaled_radius = NODE_RADIUS * self.zoom_level

            x0 = scaled_x - scaled_radius
            y0 = scaled_y - scaled_radius
            x1 = scaled_x + scaled_radius
            y1 = scaled_y + scaled_radius
            
            fill_color = NODE_HIGHLIGHT_COLOR if node_id == self.selected_node_id else NODE_COLOR
            
            self.canvas.create_oval(x0, y0, x1, y1, fill=fill_color, outline="black", width=2 * self.zoom_level, tags=("node", node_id))
            font_size = max(6, int(8 * self.zoom_level))
            
            display_text = node.name if node.name else node_id
            self.canvas.create_text(scaled_x, scaled_y + scaled_radius + 10 * self.zoom_level, text=display_text, fill=TEXT_COLOR, font=("Arial", font_size), tags=("node", node_id))

    def _generate_script_string(self):
        """Hoi4スクリプト文字列を生成する内部メソッド"""
        if not self.focus_nodes:
            return None
        
        full_script = "focus_tree = {\n"
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
        text_widget.config(state=tk.DISABLED)

    def new_file(self):
        """データを初期化する"""
        if self.is_dirty and not messagebox.askyesno("確認", "未保存の変更があります。現在のツリーを破棄して新規作成しますか？"):
            return

        self.focus_nodes.clear()
        self.select_node(None)
        self.draw_tree()
        self.status_label.config(text="新規ファイルを作成しました。")
        self.is_dirty = False

    def save_file(self):
        """現在のツリーをJSONファイルに保存する"""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not filepath:
            return False

        try:
            data_to_save = {node_id: node.to_dict() for node_id, node in self.focus_nodes.items()}
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            self.status_label.config(text=f"ファイルに保存しました: {filepath}")
            self.is_dirty = False
            return True
        except Exception as e:
            messagebox.showerror("保存エラー", f"ファイルの保存中にエラーが発生しました:\n{e}")
            return None

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
            self.is_dirty = False
        except Exception as e:
            messagebox.showerror("読み込みエラー", f"ファイルの読み込み中にエラーがいっぱい発生しました:\n{e}")

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
            'x': 0,
            'y': 0,
            'completion_reward': '{ }',
            'icon': 'GFX_focus_generic_question_mark',
            'name': '',
            'description': ''
        }

        current_text = re.sub(r'#.*', '', block_text)

        offset_x = 0
        offset_y = 0
        offset_match = re.search(r'\boffset\s*=\s*\{([\s\S]*?)\}', current_text)
        if offset_match:
            offset_content = offset_match.group(1)
            offset_x_match = re.search(r'x\s*=\s*(-?\d+)', offset_content)
            offset_y_match = re.search(r'y\s*=\s*(-?\d+)', offset_content)
            offset_x = int(offset_x_match.group(1)) if offset_x_match else 0
            offset_y = int(offset_y_match.group(1)) if offset_y_match else 0
            current_text = current_text[:offset_match.start()] + current_text[offset_match.end():]

        completion_reward_match = re.search(r'\bcompletion_reward\s*=\s*\{([\s\S]*?)\}', current_text)
        if completion_reward_match:
            data['completion_reward'] = "{\n" + completion_reward_match.group(1).strip() + "\n\t\t}"
            current_text = current_text[:completion_reward_match.start()] + current_text[completion_reward_match.end():]

        all_prerequisites = []
        prereq_matches = list(re.finditer(r'\bprerequisite\s*=\s*\{([\s\S]*?)\}', current_text))
        for match in reversed(prereq_matches):
            prereq_content = match.group(1)
            focuses = re.findall(r'focus\s*=\s*(\w+)', prereq_content)
            all_prerequisites.extend(focuses)
            current_text = current_text[:match.start()] + current_text[match.end():]
        data['prerequisite'] = list(set(all_prerequisites))

        for line in current_text.split('\n'):
            line = line.strip()
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
                        data['x'] = int(value)
                    except ValueError:
                        pass
                elif key == 'y':
                    try:
                        data['y'] = int(value)
                    except ValueError:
                        pass
        
        data['x'] += offset_x
        data['y'] += offset_y
        
        return data if 'id' in data else None

    def _parse_hoi4_txt(self, text_content):
        """Hoi4の.txtファイルの内容全体を解析する"""
        text_content = re.sub(r'#.*', '', text_content)
        
        nodes = {}
        cursor = 0
        while True:
            match = re.search(r'\bfocus\s*=\s*\{', text_content[cursor:])
            if not match:
                break
            
            start_brace = cursor + match.end() - 1
            end_brace = self._find_matching_brace(text_content, start_brace)
            
            if end_brace == -1:
                messagebox.showwarning("解析エラー", "対応する波括弧が見つかりませんでした。ファイルが破損している可能性があります。")
                break
            
            block_content = text_content[start_brace + 1 : end_brace]
            node_data = self._parse_focus_block(block_content)
            if node_data and 'id' in node_data:
                nodes[node_data['id']] = FocusNode(node_data)
            
            cursor = end_brace + 1
            
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
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            
            parsed_nodes = self._parse_hoi4_txt(content)
            if not parsed_nodes:
                messagebox.showinfo("情報", "ファイルから国家方針が見つかりませんでした。")
                return

            self.focus_nodes = parsed_nodes
            self.select_node(None)
            self.draw_tree()
            self.status_label.config(text=f"TXTファイルをインポートしました: {filepath}")
            self.is_dirty = False

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
        except Exception as e:
            messagebox.showerror("エクスポートエラー", f"ファイルの保存中にエラーが発生しました:\n{e}")

    def export_localization_file(self):
        """現在のツリーからローカリゼーションファイルを生成する"""
        if not self.focus_nodes:
            messagebox.showinfo("情報", "エクスポートする国家方針がありません。")
            return

        filepath = filedialog.asksaveasfilename(
            title="ローカリゼーションファイルを保存",
            defaultextension=".yml",
            filetypes=[("YAML Files", "*.yml"), ("All Files", "*.*")]
        )
        if not filepath:
            return

        localization_content = "l_japanese:\n"
        sorted_nodes = sorted(self.focus_nodes.values(), key=lambda n: n.id)
        for node in sorted_nodes:
            node_name = node.name if node.name else ""
            node_desc = node.description if node.description else ""
            localization_content += f" JAP_{node.id}: \"{node_name}\"\n"
            localization_content += f" JAP_{node.id}_desc: \"{node_desc}\"\n"
        
        try:
            with open(filepath, 'w', encoding='utf-8-sig') as f:
                f.write(localization_content)
            self.status_label.config(text=f"ローカリゼーションファイルをエクスポートしました: {filepath}")
        except Exception as e:
            messagebox.showerror("エクスポートエラー", f"ローカリゼーションファイルの保存中にエラーが発生しました:\n{e}")

    def open_ai_focus_generator_window(self):
        """AI国家方針生成ウィンドウを開く"""
        ai_generator_window = AIFocusGeneratorWindow(self.root, self)
        self.root.wait_window(ai_generator_window)


if __name__ == "__main__":
    root = tk.Tk()
    app = FocusTreeApp(root)
    root.mainloop()
