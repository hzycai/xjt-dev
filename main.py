# main.py
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import pyaudio
import numpy as np
import time
import os
import sys

# 尝试导入 faster-whisper（打包后也能工作）
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except Exception as e:
    WHISPER_AVAILABLE = False
    WHISPER_ERROR = str(e)

# 检测 GPU
GPU_AVAILABLE = False
try:
    import onnxruntime
    if 'CUDAExecutionProvider' in onnxruntime.get_available_providers():
        GPU_AVAILABLE = True
except:
    pass

# 获取资源路径（兼容打包后和开发环境）
def resource_path(relative_path):
    """获取 PyInstaller 打包后的资源路径"""
    try:
        # PyInstaller 创建临时文件夹 _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class VoiceFilterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("抖音直播敏感词过滤器")
        self.root.geometry("480x420")
        self.root.resizable(False, False)
        
        self.is_running = False
        self.p = pyaudio.PyAudio()
        self.load_sensitive_words()
        self.model_sizes = self.discover_bundled_models()
        
        self.create_widgets()

    def load_sensitive_words(self):
        """加载内置敏感词库"""
        self.sensitive_set = {"微信", "VX", "赚钱", "最便宜", "稳赚", " guaranteed", "绝对", "第一"}

    def discover_bundled_models(self):
        """自动发现打包进来的模型"""
        models_dir = resource_path("models")
        if not os.path.exists(models_dir):
            return ["base"]  # fallback
        
        available = []
        for model_name in ["base", "small", "medium"]:
            if os.path.isdir(os.path.join(models_dir, model_name)):
                available.append(model_name)
        return available if available else ["base"]

    def get_devices(self, kind='input'):
        devices = []
        for i in range(self.p.get_device_count()):
            dev = self.p.get_device_info_by_index(i)
            if kind == 'input' and dev['maxInputChannels'] > 0:
                devices.append((i, dev['name']))
            elif kind == 'output' and dev['maxOutputChannels'] > 0:
                devices.append((i, dev['name']))
        return devices

    def create_widgets(self):
        # 标题
        title = tk.Label(self.root, text="抖音直播敏感词过滤器", font=("Arial", 14, "bold"))
        title.pack(pady=(10, 5))

        # Whisper 状态
        if not WHISPER_AVAILABLE:
            status = tk.Label(self.root, text=f"❌ Whisper 加载失败: {WHISPER_ERROR}", fg="red")
            status.pack(pady=(0,10))
            return

        gpu_text = "✅ 检测到 NVIDIA GPU" if GPU_AVAILABLE else "⚠️ 未检测到 NVIDIA GPU（使用 CPU）"
        tk.Label(self.root, text=gpu_text, fg="green" if GPU_AVAILABLE else "orange").pack()

        # 输入设备
        tk.Label(self.root, text="输入设备（麦克风）:", anchor='w').pack(fill='x', padx=20, pady=(10,0))
        input_devices = self.get_devices('input')
        self.input_names = [name for _, name in input_devices]
        self.input_idx_map = {name: idx for idx, name in input_devices}
        self.input_combo = ttk.Combobox(self.root, values=self.input_names, state="readonly")
        if self.input_names:
            self.input_combo.current(0)
        self.input_combo.pack(fill='x', padx=20, pady=5)

        # 输出设备（优先 VB-Cable）
        tk.Label(self.root, text="输出设备（推荐 VB-Cable）:", anchor='w').pack(fill='x', padx=20, pady=(10,0))
        output_devices = self.get_devices('output')
        vb_devices = [name for _, name in output_devices if 'CABLE' in name.upper()]
        if not vb_devices:
            vb_devices = [name for _, name in output_devices]
        self.output_names = vb_devices
        self.output_idx_map = {name: idx for idx, name in output_devices}
        self.output_combo = ttk.Combobox(self.root, values=self.output_names, state="readonly")
        if self.output_names:
            self.output_combo.current(0)
        self.output_combo.pack(fill='x', padx=20, pady=5)

        # 模型选择
        tk.Label(self.root, text="Whisper 模型:", anchor='w').pack(fill='x', padx=20, pady=(10,0))
        self.model_var = tk.StringVar(value=self.model_sizes[0])
        model_combo = ttk.Combobox(self.root, textvariable=self.model_var, values=self.model_sizes, state="readonly")
        model_combo.pack(fill='x', padx=20, pady=5)
        model_tip = "• base: 低延迟，适合 CPU\n• small: 更准确，推荐 GPU"
        tk.Label(self.root, text=model_tip, fg="gray", justify='left').pack(anchor='w', padx=20)

        # 启动按钮
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=20)
        self.start_btn = tk.Button(btn_frame, text="▶ 启动过滤", command=self.toggle_process, width=15, height=2)
        self.start_btn.pack()

        # 底部提示
        hint = tk.Label(self.root, text="使用前请安装 VB-Cable\n直播伴侣中选择 'CABLE Input' 作为麦克风", fg="gray")
        hint.pack(side='bottom', pady=(0,10))

    def toggle_process(self):
        if not self.is_running:
            self.start_process()
        else:
            self.stop_process()

    def start_process(self):
        try:
            input_name = self.input_combo.get()
            output_name = self.output_combo.get()
            if not input_name or not output_name:
                messagebox.showerror("错误", "请选择输入和输出设备")
                return

            self.input_idx = self.input_idx_map[input_name]
            self.output_idx = self.output_idx_map[output_name]
            self.selected_model = self.model_var.get()

            self.is_running = True
            self.start_btn.config(text="⏹ 停止过滤", state='disabled')
            self.process_thread = threading.Thread(target=self.run_filter, daemon=True)
            self.process_thread.start()
            
            # 异步启用按钮（避免卡死）
            self.root.after(1000, lambda: self.start_btn.config(state='normal'))
            
        except Exception as e:
            messagebox.showerror("错误", f"启动失败:\n{str(e)}")
            self.is_running = False

    def run_filter(self):
        try:
            # === 加载内置 Whisper 模型 ===
            model_path = resource_path(os.path.join("models", self.selected_model))
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"模型未找到: {model_path}")

            device = "cuda" if GPU_AVAILABLE else "cpu"
            compute_type = "float16" if GPU_AVAILABLE else "int8"
            model = WhisperModel(model_path, device=device, compute_type=compute_type)

            # === 音频参数 ===
            INPUT_RATE = 16000   # Whisper 最佳输入
            OUTPUT_RATE = 48000  # VB-Cable 兼容率
            CHUNK = 1024
            CHANNELS = 1

            # === 打开音频流 ===
            stream_in = self.p.open(
                format=pyaudio.paFloat32,
                channels=CHANNELS,
                rate=INPUT_RATE,
                input=True,
                input_device_index=self.input_idx,
                frames_per_buffer=CHUNK
            )

            stream_out = self.p.open(
                format=pyaudio.paFloat32,
                channels=2,  # 立体声（直播伴侣更兼容）
                rate=OUTPUT_RATE,
                output=True,
                output_device_index=self.output_idx,
                frames_per_buffer=CHUNK * 3  # 16k → 48k
            )

            # === 缓冲与状态 ===
            audio_buffer = np.array([], dtype=np.float32)
            last_process_time = time.time()
            mute_intervals = []  # [(global_start_time, global_end_time), ...]

            while self.is_running:
                try:
                    # 读取音频块
                    data = stream_in.read(CHUNK, exception_on_overflow=False)
                    chunk_audio = np.frombuffer(data, dtype=np.float32)
                    audio_buffer = np.concatenate([audio_buffer, chunk_audio])

                    # 每 1.2 秒处理一次
                    if len(audio_buffer) >= int(1.2 * INPUT_RATE) and (time.time() - last_process_time) > 1.0:
                        # 识别
                        segments, _ = model.transcribe(
                            audio_buffer,
                            language="zh",
                            word_timestamps=True,
                            initial_prompt="中文语音识别"
                        )

                        # 检查敏感词
                        buffer_start_time = time.time() - 1.2
                        for segment in segments:
                            for word in segment.words:
                                clean_word = word.word.strip(" ,.!?，。！？")
                                if clean_word in self.sensitive_set:
                                    global_start = buffer_start_time + word.start
                                    global_end = buffer_start_time + word.end
                                    mute_intervals.append((global_start, global_end))
                                    print(f"🔇 屏蔽: '{clean_word}' [{word.start:.2f}-{word.end:.2f}s]")

                        # 清空缓冲
                        audio_buffer = np.array([], dtype=np.float32)
                        last_process_time = time.time()

                    # === 输出音频（带静音）===
                    current_time = time.time()
                    
                    # 清理过期静音区间
                    mute_intervals = [(s, e) for s, e in mute_intervals if e > current_time]
                    
                    # 检查当前是否需静音
                    should_mute = any(s <= current_time <= e for s, e in mute_intervals)

                    # 简单重采样: 16k → 48k (重复采样)
                    upsampled = np.repeat(chunk_audio, 3)
                    stereo_audio = np.column_stack((upsampled, upsampled))  # 转立体声

                    if should_mute:
                        stereo_audio = np.zeros_like(stereo_audio)

                    stream_out.write(stereo_audio.astype(np.float32).tobytes())

                except Exception as e:
                    print(f"音频处理错误: {e}")
                    break

            # 清理
            stream_in.stop_stream()
            stream_in.close()
            stream_out.stop_stream()
            stream_out.close()

        except Exception as e:
            print(f"主流程错误: {e}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"处理异常:\n{str(e)}"))

        finally:
            self.is_running = False
            self.root.after(0, lambda: self.start_btn.config(text="▶ 启动过滤"))

    def stop_process(self):
        self.is_running = False

    def on_closing(self):
        if self.is_running:
            self.stop_process()
            # 等待线程结束（最多2秒）
            if self.process_thread and self.process_thread.is_alive():
                self.process_thread.join(timeout=2.0)
        self.p.terminate()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = VoiceFilterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()