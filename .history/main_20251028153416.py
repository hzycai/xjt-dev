# main.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import pyaudio
import numpy as np
import time
import os
import queue

# 检测 GPU
try:
    import onnxruntime
    GPU_AVAILABLE = 'CUDAExecutionProvider' in onnxruntime.get_available_providers()
except:
    GPU_AVAILABLE = False

from faster_whisper import WhisperModel

class VoiceFilterWithWhisper:
    def __init__(self, root):
        self.root = root
        self.root.title("抖音敏感词过滤器 (Whisper版)")
        self.root.geometry("450x400")
        
        self.is_running = False
        self.p = pyaudio.PyAudio()
        self.load_sensitive_words()
        
        self.create_widgets()

    def load_sensitive_words(self):
        # 内置默认词库
        self.sensitive_set = {"微信", "VX", "赚钱", "最便宜", "稳赚"}

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
        # 输入设备
        tk.Label(self.root, text="输入设备（麦克风）:").pack(pady=(10,0))
        input_devices = self.get_devices('input')
        self.input_names = [name for _, name in input_devices]
        self.input_idx_map = {name: idx for idx, name in input_devices}
        self.input_combo = ttk.Combobox(self.root, values=self.input_names)
        if self.input_names:
            self.input_combo.current(0)
        self.input_combo.pack(fill='x', padx=20, pady=5)

        # 输出设备
        tk.Label(self.root, text="输出设备（VB-Cable）:").pack(pady=(10,0))
        output_devices = self.get_devices('output')
        vb_devices = [name for _, name in output_devices if 'CABLE' in name.upper()]
        if not vb_devices:
            vb_devices = [name for _, name in output_devices]
        self.output_names = vb_devices
        self.output_idx_map = {name: idx for idx, name in output_devices}
        self.output_combo = ttk.Combobox(self.root, values=self.output_names)
        if self.output_names:
            self.output_combo.current(0)
        self.output_combo.pack(fill='x', padx=20, pady=5)

        # Whisper 模型
        tk.Label(self.root, text="Whisper 模型:").pack(pady=(10,0))
        models = ["base"]  # base always works
        if GPU_AVAILABLE:
            models = ["base", "small"]
        self.model_var = tk.StringVar(value=models[0])
        ttk.Combobox(self.root, textvariable=self.model_var, values=models).pack(fill='x', padx=20, pady=5)
        if GPU_AVAILABLE:
            tk.Label(self.root, text="✅ 检测到 NVIDIA GPU，推荐使用 small 模型", fg="green").pack()

        # 启动按钮
        self.start_btn = tk.Button(self.root, text="▶ 启动过滤", command=self.toggle_process, height=2)
        self.start_btn.pack(fill='x', padx=50, pady=20)

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
            self.model_size = self.model_var.get()

            self.is_running = True
            self.start_btn.config(text="⏹ 停止过滤")
            self.process_thread = threading.Thread(target=self.run_filter, daemon=True)
            self.process_thread.start()
            messagebox.showinfo("提示", f"过滤已启动！\n模型: {self.model_size} {'(GPU)' if GPU_AVAILABLE else '(CPU)'}")
        except Exception as e:
            messagebox.showerror("错误", f"启动失败: {e}")

    def run_filter(self):
        # 初始化 Whisper
        device = "cuda" if GPU_AVAILABLE else "cpu"
        compute_type = "float16" if GPU_AVAILABLE else "int8"
        model = WhisperModel(self.model_size, device=device, compute_type=compute_type)

        # 音频参数
        RATE = 16000  # Whisper 最佳采样率
        CHUNK = 1024
        CHANNELS = 1

        # 音频缓冲区（环形）
        audio_buffer = np.array([], dtype=np.float32)
        last_process_time = time.time()
        mute_intervals = []  # [(start_time, end_time), ...]

        # 打开输入流（16kHz 单声道）
        stream_in = self.p.open(
            format=pyaudio.paFloat32,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=self.input_idx,
            frames_per_buffer=CHUNK
        )

        # 打开输出流（48kHz 立体声，VB-Cable 兼容）
        stream_out = self.p.open(
            format=pyaudio.paFloat32,
            channels=2,
            rate=48000,
            output=True,
            output_device_index=self.output_idx,
            frames_per_buffer=CHUNK*3  # 48k/16k = 3x
        )

        while self.is_running:
            try:
                # 读取音频
                data = stream_in.read(CHUNK, exception_on_overflow=False)
                chunk_audio = np.frombuffer(data, dtype=np.float32)
                audio_buffer = np.concatenate([audio_buffer, chunk_audio])

                # 每 1.2 秒处理一次
                if len(audio_buffer) >= int(1.2 * RATE) and time.time() - last_process_time > 1.0:
                    # 识别
                    segments, _ = model.transcribe(
                        audio_buffer,
                        language="zh",
                        word_timestamps=True
                    )

                    # 检查敏感词
                    current_time = time.time()
                    for segment in segments:
                        for word in segment.words:
                            word_text = word.word.strip(" ,.!?")
                            if word_text in self.sensitive_set:
                                # 转换为全局静音时间（基于当前）
                                start_global = current_time - 1.2 + word.start
                                end_global = current_time - 1.2 + word.end
                                mute_intervals.append((start_global, end_global))
                                print(f"🔇 屏蔽: {word_text} [{word.start:.2f}-{word.end:.2f}s]")

                    # 清空缓冲区
                    audio_buffer = np.array([], dtype=np.float32)
                    last_process_time = time.time()

                # 输出原始音频（48kHz 立体声）
                # 简化：直接复制单声道到立体声，并检查是否需静音
                current_global_time = time.time()
                should_mute = any(start <= current_global_time <= end for start, end in mute_intervals)
                
                # 清理过期区间
                mute_intervals = [(s, e) for s, e in mute_intervals if e > current_global_time]

                # 转换为 48kHz 立体声（简单重复采样）
                out_audio = np.repeat(chunk_audio, 3)  # 16k → 48k
                out_audio = np.tile(out_audio[:, np.newaxis], (1, 2))  # 单声道 → 立体声

                if should_mute:
                    out_audio = np.zeros_like(out_audio)

                stream_out.write(out_audio.astype(np.float32).tobytes())

            except Exception as e:
                print(f"Error: {e}")
                break

        # 清理
        stream_in.stop_stream()
        stream_in.close()
        stream_out.stop_stream()
        stream_out.close()

    def stop_process(self):
        self.is_running = False
        self.start_btn.config(text="▶ 启动过滤")

if __name__ == "__main__":
    root = tk.Tk()
    app = VoiceFilterWithWhisper(root)
    root.protocol("WM_DELETE_WINDOW", lambda: [app.stop_process(), root.destroy()])
    root.mainloop()