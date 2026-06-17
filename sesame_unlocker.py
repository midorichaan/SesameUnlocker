import json
import os
import requests
import time
import threading
import tkinter as tk
from tkinter import ttk # プログレスバー用
from datetime import datetime
from Crypto.Hash import CMAC
from Crypto.Cipher import AES
from dotenv import load_dotenv

# 映像ストリーミング用ライブラリ
try:
    import cv2
    from PIL import Image, ImageTk
    HAS_VIDEO_LIBS = True
except ImportError:
    HAS_VIDEO_LIBS = False

# Load .env
load_dotenv()

# =====================================================================
API_KEY = os.environ.get("API_KEY")
UUID = os.environ.get("DEVICE_UUID")
SECRET_KEY = os.environ.get("SECRET_KEY_HEX")
STREAM_URL = "http://172.18.135.26:5000/cam_stream"
# =====================================================================

def generate_sign(secret_key_hex):
    timestamp = int(time.time())
    timestamp_bytes = timestamp.to_bytes(4, byteorder='little')
    message_bytes = timestamp_bytes[1:4]
    secret_bytes = bytes.fromhex(secret_key_hex)
    cmac = CMAC.new(secret_bytes, ciphermod=AES)
    cmac.update(message_bytes)
    return cmac.hexdigest()

def log_message(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_text.config(state=tk.NORMAL)
    
    tag = "info"
    if level == "ERROR":
        tag = "error"
    elif level == "SUCCESS":
        tag = "success"
        
    log_line = f"[{timestamp}] [{level}] {message}\n"
    log_text.insert(tk.END, log_line, tag)
    log_text.see(tk.END)
    log_text.config(state=tk.DISABLED)
    root.update_idletasks()

def unlock_sesame():
    url = f"{os.environ.get('ENDPOINT_URL')}/{UUID}/cmd"
    headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}
    history_base64 = os.environ.get("CLIENT_NAME", "BMS_CLIENT").encode('utf-8').hex()

    log_message("解錠シーケンスを開始します...", "INFO")
    try:
        sign = generate_sign(SECRET_KEY)
    except Exception as e:
        log_message(f"署名の生成に失敗しました: {e}", "ERROR")
        return

    payload = {"cmd": 83, "history": history_base64, "sign": sign}
    unlock_button.config(state=tk.DISABLED, bg="#9E9E9E", fg="#FFFFFF")
    root.update()

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        if response.status_code == 200:
            log_message("ドアを解錠しました。 (アクセス許可)", "SUCCESS")
        else:
            log_message(f"解錠コマンド失敗 Status: {response.status_code}", "ERROR")
    except requests.exceptions.RequestException as e:
        log_message(f"通信エラー: {e}", "ERROR")
    finally:
        unlock_button.config(state=tk.NORMAL, bg="#28A745", fg="#FFFFFF")

def lock_sesame():
    url = f"{os.environ.get('ENDPOINT_URL')}/{UUID}/cmd"
    headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}
    history_base64 = os.environ.get("CLIENT_NAME", "BMS_CLIENT").encode('utf-8').hex()

    log_message("施錠シーケンスを開始します...", "INFO")
    try:
        sign = generate_sign(SECRET_KEY)
    except Exception as e:
        log_message(f"署名の生成に失敗しました: {e}", "ERROR")
        return

    payload = {"cmd": 82, "history": history_base64, "sign": sign}
    lock_button.config(state=tk.DISABLED, bg="#9E9E9E", fg="#FFFFFF")
    root.update()

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        if response.status_code == 200:
            log_message("ドアを施錠しました。 (セキュリティ有効)", "SUCCESS")
        else:
            log_message(f"施錠コマンド失敗 Status: {response.status_code}", "ERROR")
    except requests.exceptions.RequestException as e:
        log_message(f"通信エラー: {e}", "ERROR")
    finally:
        lock_button.config(state=tk.NORMAL, bg="#DC3545", fg="#FFFFFF")


# =====================================================================
# Video Streaming Thread
# =====================================================================
class VideoCaptureThread(threading.Thread):
    def __init__(self, url):
        super().__init__(daemon=True)
        self.url = url
        self.cap = cv2.VideoCapture(self.url) if HAS_VIDEO_LIBS else None
        self.current_frame = None
        self.running = HAS_VIDEO_LIBS

    def run(self):
        while self.running:
            if not self.cap.isOpened():
                time.sleep(1)
                self.cap.open(self.url)
                continue
            
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                self.cap.release()
                time.sleep(1) # 再接続待機

def update_video_frame():
    """定期的に呼び出され、UIの画像ラベルを更新する"""
    if HAS_VIDEO_LIBS and video_thread.current_frame is not None:
        try:
            # 映像の枠（video_label）の現在の実際のピクセルサイズを取得
            w = video_label.winfo_width()
            h = video_label.winfo_height()
            
            if w < 10 or h < 10:
                w, h = 640, 480

            img = Image.fromarray(video_thread.current_frame)
            img = img.resize((w, h), Image.Resampling.LANCZOS)
            imgtk = ImageTk.PhotoImage(image=img)
            
            video_label.imgtk = imgtk
            video_label.configure(image=imgtk, text="")
        except Exception as e:
            pass 
            
    # 30ミリ秒ごとに再帰的に呼び出し（約33fps）
    root.after(30, update_video_frame)


# =====================================================================
# Splash Screen (起動画面) の処理
# =====================================================================
def show_splash():
    splash = tk.Toplevel(root)
    # ウィンドウの枠（タイトルバーなど）を消す
    splash.overrideredirect(True)
    
    # 画面の中央に配置
    splash_w, splash_h = 450, 250
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    x = int((screen_w / 2) - (splash_w / 2))
    y = int((screen_h / 2) - (splash_h / 2))
    splash.geometry(f"{splash_w}x{splash_h}+{x}+{y}")
    
    splash.configure(bg="#2C3E50") # ヘッダーと同じダークブルーグレー

    # タイトル
    title = tk.Label(splash, text="施設管理コンソール", font=("Segoe UI", 20, "bold"), bg="#2C3E50", fg="#FFFFFF")
    title.pack(pady=(50, 5))
    
    subtitle = tk.Label(splash, text="H602 EV側", font=("Segoe UI", 12), bg="#2C3E50", fg="#CCCCCC")
    subtitle.pack(pady=(0, 30))

    # プログレスバー
    style = ttk.Style()
    style.theme_use('clam')
    style.configure("TProgressbar", thickness=5)
    progress = ttk.Progressbar(splash, style="TProgressbar", orient=tk.HORIZONTAL, length=300, mode='determinate')
    progress.pack(pady=10)

    # ステータステキスト
    status_label = tk.Label(splash, text="システムを初期化中...", font=("Segoe UI", 9), bg="#2C3E50", fg="#AAAAAA")
    status_label.pack()

    # 疑似的なロード処理
    def update_progress(val, text):
        progress['value'] = val
        status_label.config(text=text)
        splash.update()

    def finish_splash():
        splash.destroy()
        root.deiconify() # メインウィンドウを表示
        
        # 画面表示後に境界線を初期位置にセット
        root.update_idletasks()
        main_paned_window.sash_place(0, 850, 0)
        left_paned_window.sash_place(0, 0, 600)

    # ロードアニメーション (約2.5秒)
    root.after(500, lambda: update_progress(30, "モジュールをロード中..."))
    root.after(1000, lambda: update_progress(60, "ライブカメラストリームに接続中..."))
    root.after(1800, lambda: update_progress(90, "UIを構築中..."))
    root.after(2500, finish_splash)


# =====================================================================
# GUIの構築 (Tkinter)
# =====================================================================
root = tk.Tk()
root.withdraw() # 起動時はメインウィンドウを隠す

root.title("入退室管理システム - H602")
root.geometry("1300x850") 

# ユーザーがウィンドウのサイズを変更できるようにする
root.resizable(True, True) 
root.minsize(900, 600) 

BG_COLOR = "#F4F6F9"
root.configure(bg=BG_COLOR)

# ヘッダー領域
header_frame = tk.Frame(root, bg="#2C3E50", height=60)
header_frame.pack(fill=tk.X)
header_frame.pack_propagate(False)

header_label = tk.Label(
    header_frame,
    text="施設管理コンソール - H602 EV側",
    font=("Segoe UI", 16, "bold"),
    bg="#2C3E50",
    fg="#FFFFFF"
)
header_label.pack(side=tk.LEFT, padx=20, pady=15)

# ドラッグで左右の比率を変更できる PanedWindow (水平方向)
main_paned_window = tk.PanedWindow(
    root, 
    orient=tk.HORIZONTAL, 
    sashrelief=tk.RAISED, 
    sashwidth=8, 
    bg="#CCCCCC"
)
main_paned_window.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

# --- 左側エリア: ドラッグで上下の比率を変更できる PanedWindow (垂直方向) ---
left_paned_window = tk.PanedWindow(
    main_paned_window,
    orient=tk.VERTICAL,
    sashrelief=tk.RAISED,
    sashwidth=8,
    bg="#CCCCCC"
)
main_paned_window.add(left_paned_window, minsize=500, stretch="always")

# 左上: カメラモニター領域
cam_frame = tk.Frame(left_paned_window, bg=BG_COLOR)
left_paned_window.add(cam_frame, minsize=300, stretch="always")

cam_title_label = tk.Label(
    cam_frame,
    text="ライブカメラモニター (上下左右の枠をドラッグしてサイズ変更可)",
    font=("Segoe UI", 12, "bold"),
    bg=BG_COLOR,
    fg="#333333"
)
cam_title_label.pack(anchor="w", pady=(0, 5))

# 映像を表示するラベル
video_label = tk.Label(cam_frame, bg="#000000")
video_label.pack(expand=True, fill=tk.BOTH, pady=(0, 10))

if not HAS_VIDEO_LIBS:
    video_label.config(
        text="映像を表示するには\n'pip install opencv-python Pillow'\nを実行してください。",
        fg="#FFFFFF", font=("Segoe UI", 12)
    )

# 左下: デバイス操作領域
control_frame = tk.Frame(left_paned_window, bg=BG_COLOR)
left_paned_window.add(control_frame, minsize=100, stretch="never")

control_label = tk.Label(
    control_frame,
    text="デバイス操作",
    font=("Segoe UI", 12, "bold"),
    bg=BG_COLOR,
    fg="#333333"
)
control_label.pack(anchor="w", pady=(10, 5))

button_frame = tk.Frame(control_frame, bg=BG_COLOR)
button_frame.pack(fill=tk.X)

unlock_button = tk.Button(
    button_frame, text="🔓 解 錠 (UNLOCK)", font=("Segoe UI", 12, "bold"),
    bg="#28A745", fg="#FFFFFF", activebackground="#218838", activeforeground="#FFFFFF",
    width=18, pady=10, cursor="hand2", command=unlock_sesame, relief=tk.FLAT, borderwidth=0
)
unlock_button.pack(side=tk.LEFT, padx=(0, 20))

lock_button = tk.Button(
    button_frame, text="🔒 施 錠 (LOCK)", font=("Segoe UI", 12, "bold"),
    bg="#DC3545", fg="#FFFFFF", activebackground="#C82333", activeforeground="#FFFFFF",
    width=18, pady=10, cursor="hand2", command=lock_sesame, relief=tk.FLAT, borderwidth=0
)
lock_button.pack(side=tk.LEFT)

# --- 右側エリア (システムログ) ---
right_frame = tk.Frame(main_paned_window, bg=BG_COLOR)
main_paned_window.add(right_frame, minsize=300, stretch="always")

log_label = tk.Label(
    right_frame,
    text="システムログ",
    font=("Segoe UI", 12, "bold"),
    bg=BG_COLOR,
    fg="#333333"
)
log_label.pack(anchor="w", pady=(0, 5))

log_frame = tk.Frame(right_frame, bg="#FFFFFF", bd=1, relief=tk.SOLID)
log_frame.pack(fill=tk.BOTH, expand=True)

scrollbar = tk.Scrollbar(log_frame)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

log_text = tk.Text(
    log_frame, bg="#FFFFFF", fg="#333333", font=("Consolas", 10),
    state=tk.DISABLED, wrap=tk.WORD, yscrollcommand=scrollbar.set,
    padx=10, pady=10, relief=tk.FLAT, borderwidth=0
)
log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.config(command=log_text.yview)

log_text.tag_config("info", foreground="#555555")
log_text.tag_config("error", foreground="#DC3545")
log_text.tag_config("success", foreground="#28A745")

log_message("システムが起動しました。待機中です。", "INFO")

# 映像スレッドの開始とUI更新ループの設定
if HAS_VIDEO_LIBS:
    video_thread = VideoCaptureThread(STREAM_URL)
    video_thread.start()
    update_video_frame()

# 起動画面を表示
show_splash()

# アプリ起動
root.mainloop()
