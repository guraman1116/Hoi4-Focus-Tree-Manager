import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
import json

def generate_hoi4_event_syntax(event_full_id, num_options):
    """
    HOI4イベントの基本構文を生成します。

    Args:
        event_full_id (str): イベントの完全なID (例: FT_JAP_parliament.2)。
        num_options (int): 選択肢の数。

    Returns:
        str: 生成されたHOI4イベントの構文文字列。
    """
    event_syntax = "country_event = {\n"
    event_syntax += f"    id = {event_full_id}\n"
    event_syntax += f"    title = {event_full_id}.t\n"
    event_syntax += f"    desc = {event_full_id}.d\n"
    event_syntax += "    is_triggered_only = yes\n"

    for i in range(num_options):
        option_name_suffix = chr(ord('a') + i)
        event_syntax += "    option = {\n"
        event_syntax += f"        name = {event_full_id}.{option_name_suffix}\n"
        event_syntax += "    }\n"

    event_syntax += "}"
    return event_syntax

def generate_hoi4_localization_json(event_full_id, num_options):
    """
    HOI4イベントのローカライゼーションJSONデータを生成します。

    Args:
        event_full_id (str): イベントの完全なID (例: FT_JAP_parliament.2)。
        num_options (int): 選択肢の数。

    Returns:
        dict: 生成されたローカライゼーションデータ辞書。
    """
    localization_data = {}
    localization_data[f"{event_full_id}.t"] = "イベントタイトル"
    localization_data[f"{event_full_id}.d"] = "イベントの説明文"

    for i in range(num_options):
        option_name_suffix = chr(ord('a') + i)
        localization_data[f"{event_full_id}.{option_name_suffix}"] = f"選択肢 {option_name_suffix.upper()}"

    return localization_data

def generate_hoi4_yml_content(localization_data):
    """
    ローカライゼーションデータ辞書からHOI4の.ymlファイルコンテンツを生成します。

    Args:
        localization_data (dict): ローカライゼーションデータを含む辞書。

    Returns:
        str: HOI4の.ymlファイル形式の文字列。
    """
    yml_content = "l_japanese:\n" # 日本語ローカライゼーションのプレフィックス
    for key, value in localization_data.items():
        # HOI4のローカライゼーション形式: KEY:0 "Value"
        yml_content += f" {key}:0 \"{value}\"\n"
    return yml_content

def create_gui():
    """
    Tkinter GUIを作成し、イベント構文生成機能を提供します。
    """
    window = tk.Tk()
    window.title("Hearts of Iron IV イベント構文ジェネレーター")
    window.geometry("700x550") # ウィンドウサイズを調整
    window.resizable(False, False)

    font_large = ("Arial", 12)
    font_bold = ("Arial", 12, "bold")

    # メニューバーの作成
    menubar = tk.Menu(window)
    window.config(menu=menubar)

    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="ファイル", menu=file_menu)

    def open_localization_tool():
        """
        ローカライゼーションツール用の新しいトップレベルウィンドウを開きます。
        """
        localization_window = tk.Toplevel(window)
        localization_window.title("ローカライゼーションツール")
        localization_window.geometry("800x750") # ウィンドウサイズをさらに大きく
        localization_window.resizable(False, False)

        # 入力フレーム
        input_frame_loc = tk.Frame(localization_window, padx=10, pady=5)
        input_frame_loc.pack(fill='x')

        tk.Label(input_frame_loc, text="名前空間:", font=font_bold).grid(row=0, column=0, sticky='w', pady=2)
        entry_namespace_loc = tk.Entry(input_frame_loc, width=30, font=font_large)
        entry_namespace_loc.grid(row=0, column=1, sticky='ew', pady=2)
        entry_namespace_loc.insert(0, "FT_JAP_parliament")

        tk.Label(input_frame_loc, text="開始ID番号:", font=font_bold).grid(row=1, column=0, sticky='w', pady=2)
        entry_start_id_loc = tk.Entry(input_frame_loc, width=8, font=font_large)
        entry_start_id_loc.grid(row=1, column=1, sticky='w', pady=2)
        entry_start_id_loc.insert(0, "1")

        tk.Label(input_frame_loc, text="終了ID番号:", font=font_bold).grid(row=2, column=0, sticky='w', pady=2)
        entry_end_id_loc = tk.Entry(input_frame_loc, width=8, font=font_large)
        entry_end_id_loc.grid(row=2, column=1, sticky='w', pady=2)
        entry_end_id_loc.insert(0, "1")

        tk.Label(input_frame_loc, text="選択肢の数:", font=font_bold).grid(row=3, column=0, sticky='w', pady=2)
        entry_options_loc = tk.Entry(input_frame_loc, width=10, font=font_large)
        entry_options_loc.grid(row=3, column=1, sticky='w', pady=2)
        entry_options_loc.insert(0, "1")

        def generate_loc_json_and_display():
            """
            入力値に基づいてローカライゼーションJSONを生成し、表示します。
            既存のJSONがある場合はマージします。
            """
            namespace = entry_namespace_loc.get().strip()
            start_id_str = entry_start_id_loc.get().strip()
            end_id_str = entry_end_id_loc.get().strip()
            num_options_str = entry_options_loc.get().strip()

            if not namespace:
                messagebox.showerror("入力エラー", "名前空間は必須です。", parent=localization_window)
                return

            try:
                start_id = int(start_id_str)
                end_id = int(end_id_str)
                num_options = int(num_options_str)

                if start_id <= 0 or end_id <= 0:
                    messagebox.showerror("入力エラー", "ID番号は1以上の数字である必要があります。", parent=localization_window)
                    return
                if start_id > end_id:
                    messagebox.showerror("入力エラー", "開始ID番号は終了ID番号以下である必要があります。", parent=localization_window)
                    return
                if num_options <= 0:
                    messagebox.showerror("入力エラー", "選択肢の数は1以上の数字である必要があります。", parent=localization_window)
                    return
            except ValueError:
                messagebox.showerror("入力エラー", "ID番号と選択肢の数は数字で入力してください。", parent=localization_window)
                return

            # 現在のテキストエリアの内容を読み込み、有効なJSONであれば既存データとして扱う
            current_json_str = output_text_localization_loc.get(1.0, tk.END).strip()
            existing_localization_data = {}
            if current_json_str:
                try:
                    parsed_content = json.loads(current_json_str)
                    if "localization" in parsed_content:
                        existing_localization_data = parsed_content["localization"]
                    else:
                        existing_localization_data = parsed_content # 直接ローカライゼーションデータの場合
                except json.JSONDecodeError:
                    # 無効なJSONの場合は無視して新規生成
                    pass

            all_generated_localization_data = existing_localization_data.copy() # 既存データをコピーして開始

            for i in range(start_id, end_id + 1):
                event_full_id = f"{namespace}.{i}"
                localization_data_for_event = generate_hoi4_localization_json(event_full_id, num_options)
                all_generated_localization_data.update(localization_data_for_event) # 新しいデータをマージ

            # メタデータとローカライゼーションデータを結合
            final_output_data = {
                "event_metadata": {
                    "namespace": namespace,
                    "start_id": start_id,
                    "end_id": end_id,
                    "num_options": num_options
                },
                "localization": all_generated_localization_data
            }

            final_localization_json_string = json.dumps(final_output_data, indent=4, ensure_ascii=False)
            output_text_localization_loc.delete(1.0, tk.END)
            output_text_localization_loc.insert(tk.END, final_localization_json_string)

        def load_json_from_file():
            """
            ファイルからJSONを読み込み、テキストエリアと入力フィールドに表示します。
            """
            filepath = filedialog.askopenfilename(
                parent=localization_window,
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if not filepath:
                return
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    # メタデータを入力フィールドに反映
                    if "event_metadata" in data:
                        metadata = data["event_metadata"]
                        entry_namespace_loc.delete(0, tk.END)
                        entry_namespace_loc.insert(0, metadata.get("namespace", ""))
                        entry_start_id_loc.delete(0, tk.END)
                        entry_start_id_loc.insert(0, str(metadata.get("start_id", "")))
                        entry_end_id_loc.delete(0, tk.END)
                        entry_end_id_loc.insert(0, str(metadata.get("end_id", "")))
                        entry_options_loc.delete(0, tk.END)
                        entry_options_loc.insert(0, str(metadata.get("num_options", "")))

                    # ローカライゼーションデータをテキストエリアに表示
                    localization_to_display = data.get("localization", data) # 'localization'キーがなければ全体を表示
                    output_text_localization_loc.delete(1.0, tk.END)
                    output_text_localization_loc.insert(tk.END, json.dumps(localization_to_display, indent=4, ensure_ascii=False))

                messagebox.showinfo("読み込み完了", "JSONファイルが正常に読み込まれました。", parent=localization_window)
            except json.JSONDecodeError:
                messagebox.showerror("エラー", "無効なJSON形式です。", parent=localization_window)
            except Exception as e:
                messagebox.showerror("エラー", f"ファイルの読み込み中にエラーが発生しました: {e}", parent=localization_window)

        def save_json_to_file():
            """
            テキストエリアの内容と現在の入力フィールドの値をJSONファイルとして保存します。
            """
            filepath = filedialog.asksaveasfilename(
                parent=localization_window,
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if not filepath:
                return
            try:
                content = output_text_localization_loc.get(1.0, tk.END).strip()
                parsed_localization_data = json.loads(content) # テキストエリアのJSONをパース

                # 現在の入力フィールドからメタデータを取得
                namespace = entry_namespace_loc.get().strip()
                start_id = int(entry_start_id_loc.get().strip())
                end_id = int(entry_end_id_loc.get().strip())
                num_options = int(entry_options_loc.get().strip())

                final_output_data = {
                    "event_metadata": {
                        "namespace": namespace,
                        "start_id": start_id,
                        "end_id": end_id,
                        "num_options": num_options
                    },
                    "localization": parsed_localization_data
                }

                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(final_output_data, f, indent=4, ensure_ascii=False)
                messagebox.showinfo("保存完了", "JSONファイルが正常に保存されました。", parent=localization_window)
            except json.JSONDecodeError:
                messagebox.showerror("エラー", "テキストエリアの内容は有効なJSONではありません。", parent=localization_window)
            except ValueError:
                messagebox.showerror("エラー", "入力フィールドに無効な値があります。数字を入力してください。", parent=localization_window)
            except Exception as e:
                messagebox.showerror("エラー", f"ファイルの保存中にエラーが発生しました: {e}", parent=localization_window)

        def copy_to_clipboard_loc(text_widget):
            """
            指定されたテキストウィジェットの内容をクリップボードにコピーします。
            """
            text_to_copy = text_widget.get(1.0, tk.END).strip()
            if text_to_copy:
                localization_window.clipboard_clear()
                localization_window.clipboard_append(text_to_copy)
                messagebox.showinfo("コピー完了", "JSONがクリップボードにコピーされました！", parent=localization_window)
            else:
                messagebox.showwarning("コピー失敗", "コピーするJSONがありません。", parent=localization_window)

        def generate_mod_files_from_json():
            """
            JSONデータからHOI4イベントファイル（.txt）とローカライゼーションファイル（.yml）を生成し、表示します。
            """
            json_content_str = output_text_localization_loc.get(1.0, tk.END).strip()
            if not json_content_str:
                messagebox.showwarning("警告", "生成するJSONデータがありません。", parent=localization_window)
                return

            try:
                parsed_data = json.loads(json_content_str)
                metadata = parsed_data.get("event_metadata", {})
                localization_data = parsed_data.get("localization", {})

                namespace = metadata.get("namespace")
                start_id = metadata.get("start_id")
                end_id = metadata.get("end_id")
                num_options = metadata.get("num_options")

                if not all([namespace, start_id, end_id, num_options is not None]):
                    messagebox.showerror("エラー", "JSONデータにイベントのメタデータが不足しています。", parent=localization_window)
                    return

                # イベントファイル（.txt）の生成
                event_file_content = []
                for i in range(start_id, end_id + 1):
                    event_full_id = f"{namespace}.{i}"
                    event_file_content.append(generate_hoi4_event_syntax(event_full_id, num_options))
                final_event_file_content = "\n\n".join(event_file_content)

                # ローカライゼーションファイル（.yml）の生成
                final_yml_content = generate_hoi4_yml_content(localization_data)

                # 生成された内容を新しいウィンドウで表示
                display_generated_mod_files(final_event_file_content, final_yml_content, localization_window)

            except json.JSONDecodeError:
                messagebox.showerror("エラー", "現在のテキストエリアの内容は有効なJSONではありません。", parent=localization_window)
            except Exception as e:
                messagebox.showerror("エラー", f"ファイルの生成中にエラーが発生しました: {e}", parent=localization_window)

        def display_generated_mod_files(event_content, yml_content, parent_window):
            """
            生成されたイベントファイルとローカライゼーションファイルの内容を表示する新しいウィンドウを作成します。
            """
            display_window = tk.Toplevel(parent_window)
            display_window.title("生成されたModファイル")
            display_window.geometry("900x700")

            # イベントファイル内容
            tk.Label(display_window, text="イベントファイル (.txt):", font=font_bold).pack(pady=(10, 5))
            event_text_area = scrolledtext.ScrolledText(display_window, width=100, height=15, font=("Courier New", 10), wrap=tk.WORD, bg="#f0f0f0", relief="sunken", bd=2)
            event_text_area.pack(padx=10, pady=(0, 5), fill='both', expand=True)
            event_text_area.insert(tk.END, event_content)

            # ローカライゼーションファイル内容
            tk.Label(display_window, text="ローカライゼーションファイル (.yml):", font=font_bold).pack(pady=(10, 5))
            yml_text_area = scrolledtext.ScrolledText(display_window, width=100, height=15, font=("Courier New", 10), wrap=tk.WORD, bg="#f0f0f0", relief="sunken", bd=2)
            yml_text_area.pack(padx=10, pady=(0, 10), fill='both', expand=True)
            yml_text_area.insert(tk.END, yml_content)

            # コピーボタンフレーム
            copy_frame = tk.Frame(display_window, padx=10, pady=5)
            copy_frame.pack(fill='x')

            tk.Button(copy_frame, text="イベント構文をコピー", command=lambda: copy_to_clipboard_loc(event_text_area), font=font_bold, bg="#2196F3", fg="white", relief="raised", bd=3).pack(side='left', expand=True, padx=5)
            tk.Button(copy_frame, text="ローカライゼーションYMLをコピー", command=lambda: copy_to_clipboard_loc(yml_text_area), font=font_bold, bg="#2196F3", fg="white", relief="raised", bd=3).pack(side='right', expand=True, padx=5)


        # ボタンフレーム (ローカライゼーションツール)
        button_frame_loc = tk.Frame(localization_window, padx=10, pady=5)
        button_frame_loc.pack(fill='x')

        tk.Button(button_frame_loc, text="ローカライゼーションJSONを生成/更新", command=generate_loc_json_and_display, font=font_bold, bg="#4CAF50", fg="white", relief="raised", bd=3).pack(side='left', padx=5)
        tk.Button(button_frame_loc, text="ファイルから読み込み", command=load_json_from_file, font=font_bold, bg="#FFC107", fg="black", relief="raised", bd=3).pack(side='left', padx=5)
        tk.Button(button_frame_loc, text="JSONファイルを保存", command=save_json_to_file, font=font_bold, bg="#2196F3", fg="white", relief="raised", bd=3).pack(side='left', padx=5)
        tk.Button(button_frame_loc, text="Modファイル (.txt/.yml) を生成", command=generate_mod_files_from_json, font=font_bold, bg="#8BC34A", fg="white", relief="raised", bd=3).pack(side='left', padx=5)

        # 出力テキストエリア (ローカライゼーションJSON)
        tk.Label(localization_window, text="生成/読み込みされたローカライゼーションJSON:", font=font_bold).pack(pady=(10, 5))
        output_text_localization_loc = scrolledtext.ScrolledText(localization_window, width=90, height=15, font=("Courier New", 10), wrap=tk.WORD, bg="#f0f0f0", relief="sunken", bd=2)
        output_text_localization_loc.pack(padx=10, pady=(0, 10), fill='both', expand=True)

        # JSONコピーボタン (ローカライゼーションツール)
        tk.Button(localization_window, text="JSONをコピー", command=lambda: copy_to_clipboard_loc(output_text_localization_loc), font=font_bold, bg="#2196F3", fg="white", relief="raised", bd=3).pack(pady=(0, 10))

    file_menu.add_command(label="ローカライゼーションツール", command=open_localization_tool)

    # メインウィンドウの入力フレーム
    input_frame_main = tk.Frame(window, padx=10, pady=5)
    input_frame_main.pack(fill='x')

    tk.Label(input_frame_main, text="名前空間 (例: FT_JAP_parliament):", font=font_bold).grid(row=0, column=0, sticky='w', pady=2)
    entry_namespace_main = tk.Entry(input_frame_main, width=30, font=font_large)
    entry_namespace_main.grid(row=0, column=1, sticky='ew', pady=2)
    entry_namespace_main.insert(0, "FT_JAP_parliament")

    tk.Label(input_frame_main, text="開始ID番号:", font=font_bold).grid(row=1, column=0, sticky='w', pady=2)
    entry_start_id_main = tk.Entry(input_frame_main, width=8, font=font_large)
    entry_start_id_main.grid(row=1, column=1, sticky='w', pady=2)
    entry_start_id_main.insert(0, "1")

    tk.Label(input_frame_main, text="終了ID番号:", font=font_bold).grid(row=2, column=0, sticky='w', pady=2)
    entry_end_id_main = tk.Entry(input_frame_main, width=8, font=font_large)
    entry_end_id_main.grid(row=2, column=1, sticky='w', pady=2)
    entry_end_id_main.insert(0, "1")

    tk.Label(input_frame_main, text="選択肢の数:", font=font_bold).grid(row=3, column=0, sticky='w', pady=2)
    entry_options_main = tk.Entry(input_frame_main, width=10, font=font_large)
    entry_options_main.grid(row=3, column=1, sticky='w', pady=2)
    entry_options_main.insert(0, "1")

    def generate_main_event_syntax_and_display():
        """
        メインウィンドウの入力値に基づいてイベント構文を生成し、表示します。
        """
        namespace = entry_namespace_main.get().strip()
        start_id_str = entry_start_id_main.get().strip()
        end_id_str = entry_end_id_main.get().strip()
        num_options_str = entry_options_main.get().strip()

        if not namespace:
            messagebox.showerror("入力エラー", "名前空間は必須です。")
            return

        try:
            start_id = int(start_id_str)
            end_id = int(end_id_str)
            num_options = int(num_options_str)

            if start_id <= 0 or end_id <= 0:
                messagebox.showerror("入力エラー", "ID番号は1以上の数字である必要があります。")
                return
            if start_id > end_id:
                messagebox.showerror("入力エラー", "開始ID番号は終了ID番号以下である必要があります。")
                return
            if num_options <= 0:
                messagebox.showerror("入力エラー", "選択肢の数は1以上の数字である必要があります。")
                return
        except ValueError:
            messagebox.showerror("入力エラー", "ID番号と選択肢の数は数字で入力してください。")
            return

        all_generated_event_code = []
        for i in range(start_id, end_id + 1):
            event_full_id = f"{namespace}.{i}"
            event_code = generate_hoi4_event_syntax(event_full_id, num_options)
            all_generated_event_code.append(event_code)

        output_text_event_main.delete(1.0, tk.END)
        output_text_event_main.insert(tk.END, "\n\n".join(all_generated_event_code))

    def copy_to_clipboard_main(text_widget):
        """
        メインウィンドウのテキストウィジェットの内容をクリップボードにコピーします。
        """
        text_to_copy = text_widget.get(1.0, tk.END).strip()
        if text_to_copy:
            window.clipboard_clear()
            window.clipboard_append(text_to_copy)
            messagebox.showinfo("コピー完了", "構文がクリップボードにコピーされました！")
        else:
            messagebox.showwarning("コピー失敗", "コピーする構文がありません。")

    # 生成ボタン (メインウィンドウ)
    button_generate_main = tk.Button(window, text="イベント構文を生成", command=generate_main_event_syntax_and_display, font=font_bold, bg="#4CAF50", fg="white", relief="raised", bd=3)
    button_generate_main.pack(pady=10)

    # イベント構文出力エリア (メインウィンドウ)
    tk.Label(window, text="生成されたイベント構文:", font=font_bold).pack(pady=(10, 5))
    output_text_event_main = scrolledtext.ScrolledText(window, width=80, height=15, font=("Courier New", 10), wrap=tk.WORD, bg="#f0f0f0", relief="sunken", bd=2)
    output_text_event_main.pack(padx=10, pady=(0, 10), fill='both', expand=True)

    # コピーボタン (メインウィンドウ)
    button_copy_event_main = tk.Button(window, text="イベント構文をコピー", command=lambda: copy_to_clipboard_main(output_text_event_main), font=font_bold, bg="#2196F3", fg="white", relief="raised", bd=3)
    button_copy_event_main.pack(pady=(0, 10))

    window.mainloop()

if __name__ == "__main__":
    create_gui()
