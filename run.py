# run.py
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import pyaudio
from multiprocessing import Process, Queue, Event 
from utils.logger import get_logger
import time
import os
import sys
from faster_whisper import WhisperModel
import torch 
import cv2
from filterprocess import (
    process_capture_audio,
    process_send_audio_frames,
    # 新增导入视频相关的函数
    process_capture_video_frames,
    process_send_video_frames
)

# 导入认证相关模块
from utils.auth import read_auth_config, send_auth_request
import requests
import json

# 尝试导入 faster-whisper（打包后也能工作）
try:
    WHISPER_AVAILABLE = True
except Exception as e:
    WHISPER_AVAILABLE = False
    WHISPER_ERROR = str(e)

# 检测 GPU
try:
    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    CUDA_AVAILABLE = False

# 添加OpenCV导入用于视频处理
try:
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
 
logger = get_logger()

stop_event =  Event() 


# 获取资源路径（兼容打包后和开发环境）
def resource_path(relative_path):
    """获取 PyInstaller 打包后的资源路径"""
    try:
        # PyInstaller 创建临时文件夹 _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class AuthDialog:
    def __init__(self, parent, mac):
        self.top = tk.Toplevel(parent)
        self.top.title("产品认证")
        self.top.geometry("400x200")
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.grab_set()
        
        # 居中显示
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.top.winfo_screenheight() // 2) - (200 // 2)
        self.top.geometry(f"400x200+{x}+{y}")
        
        # 显示MAC地址
        mac_frame = tk.Frame(self.top)
        mac_frame.pack(pady=10)
        tk.Label(mac_frame, text="设备MAC地址:", font=("Arial", 10)).pack()
        tk.Label(mac_frame, text=mac, font=("Arial", 10, "bold"), fg="blue").pack()
        
        # 输入KEY
        key_frame = tk.Frame(self.top)
        key_frame.pack(pady=10)
        tk.Label(key_frame, text="请输入您的产品密钥:", font=("Arial", 10)).pack(pady=(0, 5))
        self.key_entry = tk.Entry(key_frame, width=30, show="*")
        self.key_entry.pack()
        self.key_entry.focus()
        
        # 提交按钮
        button_frame = tk.Frame(self.top)
        button_frame.pack(pady=20)
        self.submit_btn = tk.Button(button_frame, text="提交认证", command=self.submit_auth, width=15)
        self.submit_btn.pack()
        
        # 绑定回车键
        self.key_entry.bind('<Return>', lambda event: self.submit_auth())
        
        self.result = None
        
    def submit_auth(self):
        key = self.key_entry.get().strip()
        if not key:
            messagebox.showwarning("警告", "请输入产品密钥")
            return
            
        # 发送认证请求
        self.submit_btn.config(state='disabled', text="认证中...")
        self.top.update()
        
        try:
            # 读取配置获取MAC地址
            config = read_auth_config()
            mac = config.get("mac", "")
            
            # 发送认证请求
            auth_url = "https://example.com/xjt_auth"  # 实际使用时替换为正确的URL
            response = requests.post(auth_url, json={"key": key, "mac": mac})
            
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 200:
                    # 认证成功，更新配置文件
                    config["key"] = key
                    with open("config/auth.json", "w") as f:
                        json.dump(config, f, indent=4)
                    
                    self.result = True
                    messagebox.showinfo("认证成功", "产品认证成功，点击确定开始使用")
                    self.top.destroy()
                else:
                    messagebox.showerror("认证失败", result.get("msg", "认证失败"))
                    self.submit_btn.config(state='normal', text="提交认证")
            else:
                messagebox.showerror("网络错误", f"认证请求失败: {response.status_code}")
                self.submit_btn.config(state='normal', text="提交认证")
        except Exception as e:
            messagebox.showerror("错误", f"认证过程中发生错误: {str(e)}")
            self.submit_btn.config(state='normal', text="提交认证")

class VoiceFilterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("抖音直播敏感词过滤器")
        self.root.geometry("480x500")  # 增加窗口高度以容纳视频控件
        self.root.resizable(False, False)
        
        # 检查认证状态
        self.check_auth()
        
        logger.info("Voice Filter App started")
        if CUDA_AVAILABLE:
            logger.info(f"CUDA is available. Using GPU: {torch.cuda.get_device_name(0)}")
        else:
            logger.info("CUDA is not available. Using CPU.")
        
        self.is_running = False
        self.caption_running = False
        self.whisper_running = False

        self.audio_processes = None
        self.video_processes = None
        self.process_thread = None

        self.p = pyaudio.PyAudio()
     
        self.model_sizes = self.discover_bundled_models()
        
        self.create_widgets()

    def check_auth(self):
        """检查认证状态"""
        try:
            config = read_auth_config()
            mac = config.get("mac", "")
            
            # 如果没有MAC地址，显示系统错误
            if not mac:
                messagebox.showerror("系统错误", "无法获取设备标识，程序无法使用")
                self.root.destroy()
                return
                
            key = config.get("key", "")
            # 如果没有KEY，显示认证对话框
            if not key:
                auth_dialog = AuthDialog(self.root, mac)
                self.root.wait_window(auth_dialog.top)
                if not auth_dialog.result:
                    self.root.destroy()
                    return
        except Exception as e:
            logger.error(f"Auth check failed: {e}")
            messagebox.showerror("系统错误", f"认证检查失败: {str(e)}")
            self.root.destroy()
            return

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

        # # 模型选择
        # tk.Label(self.root, text="Whisper 模型:", anchor='w').pack(fill='x', padx=20, pady=(10,0))
        # self.model_var = tk.StringVar(value=self.model_sizes[0])
        # model_combo = ttk.Combobox(self.root, textvariable=self.model_var, values=self.model_sizes, state="readonly")
        # model_combo.pack(fill='x', padx=20, pady=5)
        # model_tip = "• base: 低延迟，适合 CPU\n• small: 更准确，推荐 GPU"
        # tk.Label(self.root, text=model_tip, fg="gray", justify='left').pack(anchor='w', padx=20)

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
        # 占位函数：启动处理流程
        try:
            input_name = self.input_combo.get()
            output_name = self.output_combo.get()
            if not input_name or not output_name:
                messagebox.showerror("错误", "请选择输入和输出设备")
                logger.error("Input or output device not selected")
                return

            self.input_idx = self.input_idx_map[input_name]
            self.output_idx = self.output_idx_map[output_name]
           
            
            # Output all selected device indices
            logger.info(f"Selected input device index: {self.input_idx}")
            logger.info(f"Selected output device index: {self.output_idx}")
            
            # If video is available and enabled, log camera device index
            if CV2_AVAILABLE and self.video_output_var.get() and self.camera_names:
                camera_name = self.camera_combo.get()
                if camera_name:
                    self.camera_idx = self.camera_idx_map[camera_name]
                    logger.info(f"Selected camera device index: {self.camera_idx}")
            
            logger.info(f"Starting process with input: {input_name}, output: {output_name},  ")

            # 更新Cable输出状态
            cable_detected = 'CABLE' in output_name.upper()
            self.cable_status.config(text=f"{'✅' if cable_detected else '❌'} Cable: {'已检测' if cable_detected else '未检测'}", 
                                     fg="green" if cable_detected else "red")

            self.is_running = True
            stop_event.clear()
            self.start_btn.config(text="⏹ 停止过滤", state='disabled')
            
            # 更新过滤状态
            self.filter_status.config(text="🔍 过滤: 初始化...", fg="orange")
            
            # 启动处理线程
            self.process_thread = threading.Thread(target=self.run_filter, daemon=True)
            self.process_thread.start()
            
            # 异步启用按钮（避免卡死）
            self.root.after(1000, lambda: self.start_btn.config(state='normal'))
            
        except Exception as e:
            messagebox.showerror("错误", f"启动失败:\n{str(e)}")
            logger.error(f"Failed to start process: {str(e)}")
            self.is_running = False
            stop_event.set()

    def stop_process(self):
        # 占位函数：停止处理流程
        self.is_running = False
        # Also update the is_running flag in claude_plan module
        claude_plan.is_running = False
        stop_event.set()
        logger.info("Stop process requested")
        
        # Update button to show stopping state
        self.start_btn.config(state='disabled', text="⏹ 停止中...", fg="gray")
        
        while (self.whisper_running or self.caption_running) :
            logger.info("Waiting for threads to finish...")
            self.root.update()  # Keep UI responsive
            time.sleep(0.1)
            
        # Reset button to initial state
        self.start_btn.config(text="▶ 启动过滤", state='normal', fg="black")
        logger.info("Process stopped")

    def run_filter(self):
        # 初始化队列
        self.audio_queue = Queue()
        video_queue = Queue()  # Changed to PriorityQueue for better ordering
        audio_queue = Queue()
        
        # Reset the is_running flag in claude_plan before starting threads
        claude_plan.is_running = True
        stop_event.clear()
 
        start_time = time.time() + 10.0
        # 创建音频处理进程，使用从claude_plan导入的函数
        self.audio_processes = []
        capture_audio_process = Process(target=process_capture_audio, name="AudioCapture" ,args=(audio_queue, start_time, stop_event))
        send_audio_process = Process(target=process_send_audio_frames, name="AudioProcessor",args=(audio_queue, start_time, stop_event) )
        self.audio_processes.extend([capture_audio_process, send_audio_process])
        # 启动视频进程（如果启用）
        for process in self.audio_processes:
            logger.info(f"Starting audio process: {process.name}")
            process.start()
        # 如果启用了视频功能，则创建视频处理进程
        self.video_processes = []
        if CV2_AVAILABLE and self.video_output_var.get():
            capture_video_process = Process(target=process_capture_video_frames, name="VideoCapture",args=(video_queue, start_time, stop_event))
            send_video_process = Process(target=process_send_video_frames, name="VideoSender",args=(video_queue, start_time, stop_event))
            self.video_processes.extend([capture_video_process, send_video_process])
            # 更新视频状态
            self.video_status.config(text="📹 视频: 运行中", fg="green")
        
        # 更新状态
        self.mic_status.config(text="🎤 麦克风: 运行中", fg="green")
        self.filter_status.config(text="🔍 过滤: 运行中", fg="green")
        
        
        # 启动视频进程（如果启用）
        for process in self.video_processes:
            logger.info(f"Starting video process: {process.name}")
            process.start()
        
        # 等待进程完成
        try:
            while self.is_running  :
                time.sleep(0.1)
            for process in self.video_processes:
                logger.warning(f"Terminating stuck process: {process.name}")
                if process is not None and  process.is_alive():  # 确保进程已启动
                    process.terminate()
                    process.join(timeout=1.0)
                    if process.is_alive():  # 确保进程已终止
                        logger.error(f"Failed to terminate process: {process.name}")
            for process in self.audio_processes:
                logger.warning(f"Terminating stuck process: {process.name}")
                if process is not None and  process.is_alive():  # 确保进程已启动
                    process.terminate()
                    process.join(timeout=1.0)
                    if process.is_alive():  # 确保进程已终止
                        logger.error(f"Failed to terminate process: {process.name}")
        except Exception as e:
            logger.info("Interrupted by user, stopping processes...")
            self.is_running = False
            claude_plan.is_running = False
            # 等待进程结束
            capture_audio_process.join()
            send_audio_process.join()
            for process in self.video_processes:
                process.join()
        
        # 更新状态
        self.mic_status.config(text="🎤 麦克风: 已停止", fg="gray")
        self.filter_status.config(text="🔍 过滤: 已停止", fg="gray")
        if CV2_AVAILABLE:
            self.video_status.config(text="📹 视频: 已停止", fg="gray")
        
        logger.info("Audio processing shutdown complete")


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
                    logger.info(f"Found VB-Cable device {i}: {dev['name']}")
                    return i
            logger.info("No VB-Cable device found")
            return None
        except Exception as e:
            logger.error(f"Error finding VB-Cable device: {e}")
            return None

    def on_closing(self):
        # 占位函数：关闭应用时的清理操作
        if self.is_running:
            self.stop_process()
            # 等待线程结束（最多2秒）
        if self.process_thread and self.process_thread.is_alive():
            self.process_thread.join(timeout=2.0)
        for process in self.video_processes:
            logger.warning(f"Terminating stuck process: {process.name}")
            if process is not None and  process.is_alive():  # 确保进程已启动
                process.terminate()
                process.join(timeout=1.0)
                if process.is_alive():  # 确保进程已终止
                    logger.error(f"Failed to terminate process: {process.name}")
        for process in self.audio_processes:
            logger.warning(f"Terminating stuck process: {process.name}")
            if process is not None and  process.is_alive():  # 确保进程已启动
                process.terminate()
                process.join(timeout=1.0)
                if process.is_alive():  # 确保进程已终止
                    logger.error(f"Failed to terminate process: {process.name}")
          
        self.p.terminate()
        self.root.destroy()
        logger.info("Application closed")

if __name__ == "__main__":
    root = tk.Tk()
    app = VoiceFilterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()