# main.py
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import pyaudio
import numpy as np
import time
import os
import sys
import logging
import queue
from funasr import AutoModel
import pyvirtualcam

# 尝试导入 faster-whisper（打包后也能工作）
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except Exception as e:
    WHISPER_AVAILABLE = False
    WHISPER_ERROR = str(e)

# 检测 GPU
try:
    import torch
    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    CUDA_AVAILABLE = False

# 添加OpenCV导入用于视频处理
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# 如果torch不可用，尝试onnxruntime作为备选

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
        self.root.geometry("480x500")  # 增加窗口高度以容纳视频控件
        self.root.resizable(False, False)
        
        # Setup logging
        self.setup_logging()
        logging.info("Voice Filter App started")
        if CUDA_AVAILABLE:
            logging.info(f"CUDA is available. Using GPU: {torch.cuda.get_device_name(0)}")
        else:
            logging.info("CUDA is not available. Using CPU.")
        
        self.is_running = False
        self.caption_running = False
        self.whisper_running = False
        
       

        self.p = pyaudio.PyAudio()
        self.load_sensitive_words()
        self.model_sizes = self.discover_bundled_models()
        
        self.create_widgets()

    def setup_logging(self):
        """Setup logging configuration"""
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler("log.txt", encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def load_sensitive_words(self):
        """加载内置敏感词库"""
        self.sensitive_set = set()
        try:
            # 尝试从config目录加载敏感词
            config_path = resource_path("config")
            if not os.path.exists(config_path):
                os.makedirs(config_path)
            sensitive_words_file = os.path.join(config_path, "sensitive_words.txt")
            
            # 尝试从外部文件加载敏感词
            with open(sensitive_words_file, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word:  # 忽略空行
                        self.sensitive_set.add(word)
            logging.info(f"Loaded {len(self.sensitive_set)} sensitive words from file")
        except FileNotFoundError:
            # 如果文件不存在，使用默认敏感词库
            logging.warning("sensitive_words.txt not found, using default sensitive words")
            self.sensitive_set = {"微信", "VX", "赚钱", "最便宜", "稳赚", " guaranteed", "绝对", "第一"}
        except Exception as e:
            logging.error(f"Error loading sensitive words: {e}")
            # 出现错误时使用默认敏感词库
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

    # 添加摄像头检测方法
    def get_camera_devices(self):
        """检测可用的摄像头设备"""
        if not CV2_AVAILABLE:
            return []
            
        cameras = []
        for i in range(10):  # 检测前10个摄像头
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    cameras.append((i, f"摄像头 {i}"))
                cap.release()
        return cameras

    def create_widgets(self):
        # 标题
        title = tk.Label(self.root, text="抖音直播敏感词过滤器", font=("Arial", 14, "bold"))
        title.pack(pady=(10, 5))

        # Whisper 状态
        if not WHISPER_AVAILABLE:
            status = tk.Label(self.root, text=f"❌ Whisper 加载失败: {WHISPER_ERROR}", fg="red")
            status.pack(pady=(0,10))
            return

        device_info = "✅ 使用 GPU 进行语音识别" if CUDA_AVAILABLE else "⚠️ 使用 CPU 进行语音识别"
        color = "green" if CUDA_AVAILABLE else "orange"
        tk.Label(self.root, text=device_info, fg=color).pack()

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

        # 视频输入设备选择（新增）
        if CV2_AVAILABLE:
            tk.Label(self.root, text="视频输入设备:", anchor='w').pack(fill='x', padx=20, pady=(10,0))
            camera_devices = self.get_camera_devices()
            self.camera_names = [name for _, name in camera_devices]
            self.camera_idx_map = {name: idx for idx, name in camera_devices}
            self.camera_combo = ttk.Combobox(self.root, values=self.camera_names, state="readonly")
            if self.camera_names:
                self.camera_combo.current(0)
            self.camera_combo.pack(fill='x', padx=20, pady=5)
            
            # 视频输出选项（新增）
            self.video_output_var = tk.BooleanVar()
            video_output_check = tk.Checkbutton(self.root, text="启用视频输出（2秒延迟）", variable=self.video_output_var)
            video_output_check.pack(pady=5)

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

        # 状态栏
        self.status_frame = tk.Frame(self.root)
        self.status_frame.pack(pady=5)
        
        self.mic_status = tk.Label(self.status_frame, text="🎤 麦克风: 未连接", fg="gray")
        self.mic_status.pack(side=tk.LEFT, padx=5)
        
        self.filter_status = tk.Label(self.status_frame, text="🔍 过滤: 未运行", fg="gray")
        self.filter_status.pack(side=tk.LEFT, padx=5)
        
        self.cable_status = tk.Label(self.status_frame, text="🔌 Cable: 未检测", fg="gray")
        self.cable_status.pack(side=tk.LEFT, padx=5)
        
        # 视频状态（新增）
        if CV2_AVAILABLE:
            self.video_status = tk.Label(self.status_frame, text="📹 视频: 未运行", fg="gray")
            self.video_status.pack(side=tk.LEFT, padx=5)

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
                logging.error("Input or output device not selected")
                return

            self.input_idx = self.input_idx_map[input_name]
            self.output_idx = self.output_idx_map[output_name]
            self.selected_model = self.model_var.get()
            
            # Output all selected device indices
            logging.info(f"Selected input device index: {self.input_idx}")
            logging.info(f"Selected output device index: {self.output_idx}")
            
            # If video is available and enabled, log camera device index
            if CV2_AVAILABLE and self.video_output_var.get() and self.camera_names:
                camera_name = self.camera_combo.get()
                if camera_name:
                    self.camera_idx = self.camera_idx_map[camera_name]
                    logging.info(f"Selected camera device index: {self.camera_idx}")
            
            logging.info(f"Starting process with input: {input_name}, output: {output_name}, model: {self.selected_model}")

            # 更新Cable输出状态
            cable_detected = 'CABLE' in output_name.upper()
            self.cable_status.config(text=f"{'✅' if cable_detected else '❌'} Cable: {'已检测' if cable_detected else '未检测'}", 
                                     fg="green" if cable_detected else "red")

            self.is_running = True
            self.start_btn.config(text="⏹ 停止过滤", state='disabled')
            
            # 更新过滤状态
            self.filter_status.config(text="🔍 过滤: 初始化...", fg="orange")
            
            self.process_thread = threading.Thread(target=self.run_filter, daemon=True)
            self.process_thread.start()
            
          
            # 异步启用按钮（避免卡死）
            self.root.after(1000, lambda: self.start_btn.config(state='normal'))
            
        except Exception as e:
            messagebox.showerror("错误", f"启动失败:\n{str(e)}")
            logging.error(f"Failed to start process: {str(e)}")
            self.is_running = False

    def output_audio_to_vb_cable(self, audio_data, vb_cable_stream, input_rate, output_rate):
        """
        将音频数据输出到VB-Cable输出流，并进行重采样
        
        Args:
            audio_data: 需要输出的音频数据
            vb_cable_stream: VB-Cable输出流对象
            input_rate: 输入音频的采样率
            output_rate: 输出音频的采样率
        """
        try:
            # 如果采样率不同，则进行重采样
            if input_rate != output_rate:
                # 将bytes转换为numpy array
                audio_array = np.frombuffer(audio_data, dtype=np.float32)
                
                # 计算重采样后的长度
                new_length = int(len(audio_array) * output_rate / input_rate)
                
                # 重采样 - 简单的线性插值方法
                resampled_audio = np.interp(
                    np.linspace(0, len(audio_array), new_length, endpoint=False),
                    np.arange(len(audio_array)),
                    audio_array
                )
                
                # 转换回bytes
                audio_data = resampled_audio.astype(np.float32).tobytes()
            
            # 输出音频数据
            vb_cable_stream.write(audio_data)
            
        except Exception as e:
            logging.error(f"输出音频到输出设备失败: {e}")
            print(f"输出音频到输出设备失败: {e}")

    # 添加视频输出方法
    def run_video_output(self):
        """运行视频输出功能，实现2秒延迟效果"""
        if not CV2_AVAILABLE:
            return
            
         
       
        cam = None
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Cannot open camera 0")
            exit()
        try:
            # 使用虚拟摄像头上下文管理器
            with pyvirtualcam.Camera(width=1280, height=720, fps=30) as cam:
                print(f'Using virtual camera: {cam.device}')
                
                # 打开摄像头0
                
                
                # 设置摄像头分辨率
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                
                # 计算2秒的帧数
                fps = 30
                delay_frames =int(3 * fps)   # 2秒延迟
                
                # 创建帧缓冲区
                frame_buffer = []
                
                # 记录开始时间，用于手动控制帧率
                start_time = time.time()
                frame_duration = 1.0 / fps
                
                # 或者创建一个动态画面（例如渐变色）
                while self.is_running:
                    # 从摄像头读取帧
                    ret, frame = cap.read()
                    if not ret:
                        print("Can't receive frame from camera 0")
                        break
                        
                    # 调整帧大小以匹配虚拟摄像头分辨率
                    frame = cv2.resize(frame, (cam.width, cam.height))
                    
                    # 将帧添加到缓冲区
                    frame_buffer.append(frame.copy())
                    
                    # 如果缓冲区超过延迟帧数，则移除并发送最旧的帧
                    if len(frame_buffer) > delay_frames:
                        # 移除并获取最旧的帧
                        delayed_frame = frame_buffer.pop(0)
                        
                        # 将BGR格式转换为RGB格式（因为pyvirtualcam期望RGB格式）
                        frame_rgb = cv2.cvtColor(delayed_frame, cv2.COLOR_BGR2RGB)
                        
                        # 将RGB格式的numpy数组发送到虚拟摄像头
                        cam.send(frame_rgb)
                        
                        # 控制帧率，避免 _last_frame_t 为 None 的问题
                        current_time = time.time()
                        elapsed_time = current_time - start_time
                        if elapsed_time < frame_duration:
                            time.sleep(frame_duration - elapsed_time)
                        start_time = time.time()
                        
                    # 等待下一帧
                    # Only call sleep_until_next_frame if we have sent at least one frame
                    if len(frame_buffer) > delay_frames or len(frame_buffer) == delay_frames:
                        try:
                            cam.sleep_until_next_frame()
                        except TypeError:
                            # Fallback if sleep_until_next_frame fails due to _last_frame_t being None
                            time.sleep(frame_duration)
        except Exception as e:
            logging.error(f"视频输出错误: {e}")
        finally:
      
            if cap:
                cap.release()
            # 更新视频状态
            self.root.after(0, lambda: self.video_status.config(text="📹 视频: 未运行", fg="gray"))
            logging.info("视频输出已停止")

    def run_filter(self):
        stream_in = None
        vb_cable_stream = None
        stream_out = None
        
        # Define threads as None initially
        capture_thread = None
        recognition_thread = None
        
        # Record system startup time
        system_startup_time = time.time()
        
        try:
            # === 加载内置 Whisper 模型 ===
            # Replace with simpler model initialization from test_microphone_with_model.py
            # model = AutoModel(model="paraformer-zh-streaming", model_revision="v2.0.4", disable_update=True)
            model = AutoModel(model="paraformer-zh-streaming", model_revision="v2.0.4", disable_update=True)


            # === 音频参数 ===
            INPUT_RATE = 16000   # Whisper 最佳输入
            OUTPUT_RATE = 48000  # VB-Cable 兼容率
            CHUNK = 960          # Changed from 1024 to 960 to match test file
            CHANNELS = 1

            # 更新麦克风状态 - moved here to update immediately when process starts
            self.root.after(0, lambda: self.mic_status.config(text="🎤 麦克风: 已连接", fg="green"))
            print("CHANNELS======>",CHANNELS)
            print("self.input_idx======>",self.input_idx)
            # === 打开音频流 ===
            stream_in = self.p.open(
                format=pyaudio.paFloat32,
                channels=CHANNELS,
                rate=INPUT_RATE,
                input=True,
                input_device_index=self.input_idx,
                frames_per_buffer=CHUNK
            )

            # 打开到选定输出设备的输出流，使用设备支持的采样率
            device_info = self.p.get_device_info_by_index(self.output_idx)
            output_rate = int(device_info['defaultSampleRate'])
            
            vb_cable_stream = self.p.open(
                format=pyaudio.paFloat32,
                channels=1,  # 根据输入音频通道数调整
                rate=output_rate,  # 使用输出设备支持的采样率
                output=True,
                output_device_index=self.output_idx,
                frames_per_buffer=1024
            )
            
            logging.info(f"Audio streams opened - input rate: {INPUT_RATE}, output rate: {OUTPUT_RATE}")

            # 更新过滤状态
            self.root.after(0, lambda: self.filter_status.config(text="✅ 过滤: 运行中", fg="green"))

            # === 缓冲与状态 ===
            audio_queue = queue.Queue()
            last_process_time = time.time()
            mute_intervals = []  # [(global_start_time, global_end_time), ...]
            
            # 使用 tk.Label 选中的输出设备
            selected_output_device_idx = self.output_idx
            
            # Thread 1: Audio capture and queue management
            def capture_audio(vb_cable_stream):
                audio_buffer = np.array([], dtype=np.float32)
                while self.is_running:
                    try:
                        self.caption_running = True
                        # 读取音频块
                        data = stream_in.read(CHUNK, exception_on_overflow=False)
                        chunk_audio = np.frombuffer(data, dtype=np.float32)
                        audio_buffer = np.concatenate([audio_buffer, chunk_audio])
                        
                        # 每 1.2 秒处理一次 (changed from 3 seconds)
                        if len(audio_buffer) >= int(1.2 * INPUT_RATE) and (time.time() - last_process_time) > 1.0:
                            # Put audio data into queue for processing
                            audio_queue.put(audio_buffer.copy())
                            # Log the buffer length
                            logging.info(f"Audio buffer length: {len(audio_buffer)} samples put into queue")
                            audio_buffer = np.array([], dtype=np.float32)
                            
                    except Exception as e:
                        logging.error(f"Audio capture error: {e}")
                        print(f"音频捕获错误: {e}")
                        break
                self.caption_running = False
                logging.info("is_running=false capture_audio threads finished")
                    
                        
            # Thread 2: Speech recognition
            def recognize_speech():
                buffer_start_time = time.time() - 3.0  # Changed from 1.2 to 3.0
                while True:  # Keep thread alive
                    try:
                        if self.is_running:
                            self.whisper_running = True
                            # Get audio data from queue
                            audio_data = audio_queue.get(timeout=0.1)

                            # Simplified recognition like in test_microphone_with_model.py
                            start_time = time.time()
                            res = model.generate(input=audio_data, is_final=self.is_running)
                            end_time = time.time()
                            recognition_time = end_time - start_time
                            logging.info(f"Recognized speech: {res}")
                            
                            # Output recognition time
                            print(f"Recognition result: {res}")
                            print(f"Recognition time: {recognition_time:.4f} seconds")
                            # if recognition_time < 0.5:
                            #     print("⚠️  Warning: Recognition time is less than 0.5 seconds.")
                            #     time.sleep(0.3 - recognition_time)
                            # 检查敏感词
                            found_sensitive_words = []
                            # 记录找到的敏感词
                            # 修改:检查识别结果中的敏感词
                            if isinstance(res, list) and len(res) > 0 and 'text' in res[0]:
                                recognized_text = res[0]['text']
                                for word in self.sensitive_set:
                                    if word in recognized_text:
                                        found_sensitive_words.append(word)
                                        logging.warning(f"Sensitive word detected: {word}")
                                        print(f"⚠️  Warning: Sensitive word detected: {word}")
                                        
                            if found_sensitive_words:
                                logging.info(f"Found sensitive words: {', '.join(found_sensitive_words)}")
                                
                            # 处理音频输出 - 根据敏感词检测结果决定输出原音频还是哔音
                            if selected_output_device_idx is not None:
                                # Calculate time interval from system startup
                                current_time = time.time()
                                time_interval = current_time - system_startup_time
                                print(f"Time since system startup: {time_interval:.4f} seconds")
                                
                                if found_sensitive_words:
                                    # 创建哔音替代音频
                                    beep_duration = len(audio_data) / INPUT_RATE  # 计算音频时长
                                    beep_freq = 800  # 哔音频率 (Hz)
                                    
                                    # 生成哔音样本数
                                    num_samples = int(beep_duration * output_rate)
                                    # 生成时间轴
                                    t = np.linspace(0, beep_duration, num_samples, False)
                                    # 生成哔音信号
                                    beep_signal = np.sin(2 * np.pi * beep_freq * t) * 0.5  # 降低音量避免刺耳
                                    # 转换为float32格式
                                    beep_data = beep_signal.astype(np.float32).tobytes()
                                    
                                    # 输出哔音
                                    self.output_audio_to_vb_cable(beep_data, vb_cable_stream, output_rate, output_rate)
                                else:
                                    # 输出原始音频
                                    audio_bytes = audio_data.astype(np.float32).tobytes()
                                    self.output_audio_to_vb_cable(audio_bytes, vb_cable_stream, INPUT_RATE, output_rate)
                            
                            audio_queue.task_done()
                        else:
                            # When not running, clear the queue
                            while not audio_queue.empty():
                                try:
                                    audio_queue.get_nowait()
                                    audio_queue.task_done()
                                except queue.Empty:
                                    break
                            self.whisper_running = False
                            
                            # Small sleep to prevent busy waiting
                            
                    except queue.Empty:
                        continue
                    except Exception as e:
                        logging.error(f"Speech recognition error: {e}")
                        print(f"语音识别错误: {e}")

                        
            # Start both threads
            capture_thread = threading.Thread(target=capture_audio, args=(vb_cable_stream,), daemon=True)
            recognition_thread = threading.Thread(target=recognize_speech, daemon=True)
            
            capture_thread.start()
            recognition_thread.start()
            print(f"CV2_AVAILABLE:{CV2_AVAILABLE}")
            print(f"self.video_output_var.get():{self.video_output_var.get()}")
            print(f"self.camera_names:{self.camera_names}")

            # 如果启用了视频输出，则启动视频线程
            if CV2_AVAILABLE and self.video_output_var.get() and self.camera_names:
                print("进入视频线程")
                camera_name = self.camera_combo.get()
                if camera_name:
                    self.camera_idx = self.camera_idx_map[camera_name]
                    video_thread = threading.Thread(target=self.run_video_output, daemon=True)
                    video_thread.start()
                    print("视频线程已启动")
                else:
                    print("未选择视频输入设备")
            
            # Wait for threads to finish
            # capture_thread.join()
            recognition_thread.join()

        except Exception as e:
            logging.error(f"Main process error: {e}")
            print(f"主流程错误: {e}")
            self.root.after(0, lambda: messagebox.showerror("错误", f"处理异常:\n{str(e)}"))

        finally:
            # 清理所有打开的音频流
            if stream_in is not None:
                try:
                    stream_in.stop_stream()
                    stream_in.close()
                    logging.info("Input audio stream closed")
                except Exception as e:
                    logging.error(f"Error closing input stream: {e}")
                    
            if vb_cable_stream is not None:
                try:
                    vb_cable_stream.stop_stream()
                    vb_cable_stream.close()
                    logging.info("VB-Cable audio stream closed")
                except Exception as e:
                    logging.error(f"Error closing VB-Cable stream: {e}")
                    
            self.is_running = False
            self.root.after(0, lambda: self.mic_status.config(text="🎤 麦克风: 未连接", fg="gray"))
            self.root.after(0, lambda: self.filter_status.config(text="🔍 过滤: 未运行", fg="gray"))
            # self.root.after(0, lambda: self.start_btn.config(text="▶ 启动过滤", state='normal'))
            logging.info("Processing stopped")

    def find_vb_cable_device(self):
        """
        查找系统中的 VB-Cable 设备
        返回设备索引，如果未找到则返回 None
        """
        try:
            devices = []
            for i in range(self.p.get_device_count()):
                dev = self.p.get_device_info_by_index(i)
                # 查找输出设备且名称包含 CABLE
                if dev['maxOutputChannels'] > 0 and 'CABLE' in dev['name'].upper():
                    logging.info(f"Found VB-Cable device {i}: {dev['name']}")
                    return i
            logging.info("No VB-Cable device found")
            return None
        except Exception as e:
            logging.error(f"Error finding VB-Cable device: {e}")
            return None

    def stop_process(self):
        self.is_running = False
     
        logging.info("Stop process requested")
        
        # Update button to show stopping state
        self.start_btn.config(state='disabled', text="⏹ 停止中...", fg="gray")
        
        while (self.whisper_running or self.caption_running) :
            logging.info("Waiting for threads to finish...")
            self.root.update()  # Keep UI responsive
            time.sleep(0.1)
            
        # Reset button to initial state
        self.start_btn.config(text="▶ 启动过滤", state='normal', fg="black")
        logging.info("Process stopped")

    def on_closing(self):
        if self.is_running:
            self.stop_process()
            # 等待线程结束（最多2秒）
            if self.process_thread and self.process_thread.is_alive():
                self.process_thread.join(timeout=2.0)
          
        self.p.terminate()
        self.root.destroy()
        logging.info("Application closed")

if __name__ == "__main__":
    root = tk.Tk()
    app = VoiceFilterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()