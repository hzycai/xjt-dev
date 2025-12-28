# run.py
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkFont
import threading
import pyaudio
from multiprocessing import Process, Queue, Event 
from utils.logger import get_logger
import time
import os
import sys
import torch 
import cv2
from utils.auth import check_auth, get_device_id, create_userinfo, calculate_auth_hash
from filterprocess import (
    process_capture_audio,
    process_send_audio_frames,
    # 新增导入视频相关的函数
    process_capture_video_frames,
    process_send_video_frames,
    init_audio_mic,
    init_audio_output,
    init_video_cam,
    init_model,
    upload_user_detect_record
)
from util import AuthState, BASE_URL, load_sensitive_words, AudioReplaceType

# 导入认证相关模块
# from utils.auth import read_auth_config, send_auth_request
import requests
 

 
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
font_name = None

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
        
        # Set window icon
        try:
            icon_path = resource_path("res/favicon.ico")
            if os.path.exists(icon_path):
                self.top.iconbitmap(icon_path)
        except Exception as e:
            logger.warning(f"Failed to load icon for AuthDialog: {e}")
        
        # 居中显示
        self.top.update_idletasks()
        x = (self.top.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.top.winfo_screenheight() // 2) - (200 // 2)
        self.top.geometry(f"400x200+{x}+{y}")
        
        # 显示MAC地址
        mac_frame = tk.Frame(self.top)
        mac_frame.pack(pady=10)
        tk.Label(mac_frame, text="设备号:", font=(font_name, 10)).pack()
        tk.Label(mac_frame, text=mac, font=(font_name, 10, "bold"), fg="blue").pack()
        
        # 输入KEY
        key_frame = tk.Frame(self.top)
        key_frame.pack(pady=10)
        tk.Label(key_frame, text="请输入您的产品密钥:", font=(font_name, 10)).pack(pady=(0, 5))
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
            
            mac = get_device_id()
            
            # 发送认证请求
            auth_url = f"{BASE_URL}/update_user_info"  # 实际使用时替换为正确的URL
            response = requests.post(auth_url, json={"key": key, "mac": mac})
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Auth result: {result}")
                if result.get("code") == 200:
                    # 认证成功，创建密钥文件
                    file_path_list, uuid_list = create_userinfo(key)
                    user_hash = calculate_auth_hash(uuid_list, key)
                    
                    # Send request to update user file info
                    file_info_url = f"{BASE_URL}/update_user_file_info"
                    file_paths_str = ','.join(file_path_list)
                    file_info_data = {
                        "mac": mac,
                        "file_path": file_paths_str,
                        "hash": user_hash
                    }
                    file_info_response = requests.post(file_info_url, json=file_info_data)
                    if file_info_response.status_code != 200:
                        logger.error(f"Failed to update user file info: {file_info_response.status_code}")
                    else:
                        file_info_response_data = file_info_response.json()
                        if file_info_response_data['code'] == 200:
                            self.result = True
                            logger.info("Auth success")
                        else:
                            logger.error(f"Failed to update user file info: {file_info_response_data}")
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
        self.root.title("消禁腾")

        # Calculate new dimensions: increase height by 20%
        original_height = 550
        new_height = int(original_height * 1.2)  # 660 pixels
        x = (self.root.winfo_screenwidth() // 2) - (480 // 2)
        y = (self.root.winfo_screenheight() // 2) - (new_height // 2)  # Adjusted for new height
        self.root.geometry(f"480x{new_height}+{x}+{y}")  # Updated geometry
        
        # self.root.geometry(f"480x{new_height}")  # Changed from 480x550 to 480x660
        self.root.resizable(False, False)
        
        # Set window icon
        try:
            icon_path = resource_path("res/favicon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception as e:
            logger.warning(f"Failed to load icon: {e}")
        
        # Show loading message immediately
        self.loading_label = tk.Label(root, text="系统初始化中...", font=("", 14))
        self.loading_label.pack(expand=True)
        self.root.update_idletasks()
        self.root.update()  # Force the window to display the loading message
        
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
     
        # Add mute option variable
        self.mute_option = tk.StringVar(value="silence")  # Default to silence
        
        check_res = check_auth()
        # Check authentication before creating widgets
        if check_res==AuthState.SUCCESS.value:
            # Remove loading label and create widgets after auth check
            self.loading_label.destroy()
            self.create_widgets()
        elif check_res == AuthState.UNBIND.value:
            # Show key input dialog when in UNBIND state
            self.loading_label.destroy()
            
            auth_dialog = AuthDialog(self.root, get_device_id())
            self.root.wait_window(auth_dialog.top)
            if auth_dialog.result:
                self.create_widgets()
            else:
                self.root.destroy()
        elif check_res == AuthState.FAILED.value:
            # Show error message and prompt for re-authentication
            self.loading_label.destroy()
            messagebox.showerror("认证失败", "认证信息错误，请重新认证")
            auth_dialog = AuthDialog(self.root, get_device_id())
            self.root.wait_window(auth_dialog.top)
            if auth_dialog.result:
                self.create_widgets()
            else:
                self.root.destroy()
        elif check_res == AuthState.FOBBIDDEN.value:
            # Show error message and exit when user is disabled
            self.loading_label.destroy()
            messagebox.showerror("账户禁用", "您的账户已被禁用，程序将退出")
            self.root.destroy()
            return
        else:
            # Close the application if authentication fails
            # Show error message and prompt for re-authentication
            self.loading_label.destroy()
            auth_dialog = AuthDialog(self.root, get_device_id())
            self.root.wait_window(auth_dialog.top)
            if auth_dialog.result:
                self.create_widgets()
            else:
                self.root.destroy()

    def get_devices(self, kind='input'):
        devices = []
        for i in range(self.p.get_device_count()):
            dev = self.p.get_device_info_by_index(i)
      
            if kind == 'input' and dev['maxInputChannels'] > 0:
                tmp_d = init_audio_mic(i,self.p)
                if tmp_d:
                    tmp_d.close()
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
        cameras = self.get_camera_devices_windows()
        if cameras:  # 如果有摄像头，则返回
            return cameras
        for i in range(10):  # 检测前10个摄像头
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    cameras.append((i, f"摄像头 {i}"))
                cap.release()
        return cameras
    
    def get_camera_devices_windows(self):
        # 1. 用 pygrabber 获取真实名称列表（基于 DirectShow）
        try:
            from pygrabber.dshow_graph import FilterGraph
            device_names = FilterGraph().get_input_devices()
        except Exception as e:
            print("Failed to get camera names:", e)
            device_names = []

        cameras = []
        # 2. 用 CAP_DSHOW 后端逐个测试
        for i in range(len(device_names)):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, frame = cap.read()
                name = device_names[i] if i < len(device_names) else f"Unknown Camera {i}"
                if ret and frame is not None and frame.size > 0:
                    cameras.append((i, name))
                cap.release()
        return cameras

    # 新增函数：获取摄像头支持的分辨率和FPS
    def get_camera_formats(self, device_index):
        """获取指定摄像头支持的分辨率和FPS"""
        try:
            from pygrabber.dshow_graph import FilterGraph
            graph = FilterGraph()
            devices = graph.get_input_devices()
            
            if device_index >= len(devices):
                return []
                
            # 设置该设备为当前输入源
            graph.add_video_input_device(device_index)
            
            # 获取该设备支持的所有格式
            formats = graph.get_input_device().get_formats()
            # 提取唯一的分辨率和FPS组合
            device_info = set()
            fps = 0
            for fmt in formats:
                width = fmt.get('width', 0)
                height = fmt.get('height', 0)
                fps = fmt.get('max_framerate', 30)
                device_info.add( 
                        f"{width}x{height}"
                     )
            # 返回去重后的格式列表
            # 修改:按分辨率从大到小排序
            sorted_resolutions = sorted(list(device_info), key=lambda x: int(x.split('x')[0]) * int(x.split('x')[1]), reverse=True)
            return sorted_resolutions, int(fps)
        except Exception as e:
            print(f"Failed to get camera formats: {e}")
            return []

    def create_widgets(self):
        # Clear any existing widgets (in case of reload)
        for widget in self.root.winfo_children():
            widget.destroy()
        text = "\u2009".join("消禁腾")    
        # Title
        title = tk.Label(self.root, text=text, font=(font_name, 14 ))
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
        # tmp_input_devices = []
        # for item in input_devices:
        #     tmp_d = init_audio_mic(item[0],self.p)
        #     if tmp_d:
        #         tmp_input_devices.append(item)
        #         tmp_d.close()
        # input_devices = tmp_input_devices
        print(f"input_devices=]==>{input_devices}")
        self.input_names = [f"{i}_{name}" for i, name in input_devices]
        self.input_idx_map = {f"{idx}_{name}": idx for idx, name in input_devices}
        print(f"input_idx_map----------->{self.input_idx_map}")
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
                # 绑定选择事件，当选中摄像头时更新分辨率选项
                self.camera_combo.bind('<<ComboboxSelected>>', self.on_camera_selected)
            self.camera_combo.pack(fill='x', padx=20, pady=5)
            
            # 视频分辨率和FPS选择（拆分为两个独立的下拉框）
            tk.Label(self.root, text="视频分辨率:", anchor='w').pack(fill='x', padx=20, pady=(10,0))
            self.resolution_combo = ttk.Combobox(self.root, state="readonly")
            self.resolution_combo.pack(fill='x', padx=20, pady=5)
            
            tk.Label(self.root, text="视频FPS:", anchor='w').pack(fill='x', padx=20, pady=(10,0))
            self.fps_combo = ttk.Combobox(self.root, state="readonly")
            self.fps_combo.pack(fill='x', padx=20, pady=5)
            
            # 初始化分辨率和FPS选项
            if self.camera_names:
                self.update_resolution_options(0)
            
            # 视频输出选项（新增）
            # self.video_output_var = tk.BooleanVar()
            # video_output_check = tk.Checkbutton(self.root, text="启用视频输出（2秒延迟）", variable=self.video_output_var)
            # video_output_check.pack(pady=5)

        # 添加消音选项区域
        tk.Label(self.root, text="消音选项:", anchor='w').pack(fill='x', padx=20, pady=(10, 0))
       
        # 修改为下拉框选择方式，使用更友好的显示文字
        mute_options_display = ["使用静音代替", "使用'哔'代替"]
        mute_options_values = [AudioReplaceType.SILENCE.value, AudioReplaceType.BEEP.value]
        # self.mute_option_combo = ttk.Combobox(mute_frame, values=mute_options_display, state="readonly")
        self.mute_option_combo = ttk.Combobox(self.root, values=mute_options_display, state="readonly")

        self.mute_option_combo.set("使用静音代替")  # 默认值
        self.mute_option_combo.pack(fill='x', padx=20, pady=5)
        
        # 创建映射字典，用于获取实际值
        self.mute_option_map = dict(zip(mute_options_display, mute_options_values))
        
        # 添加导入敏感词按钮和启动过滤按钮，水平排列
        buttons_frame = tk.Frame(self.root)
        buttons_frame.pack(pady=10)
        
        self.import_words_btn = tk.Button(buttons_frame, text="📥 导入敏感词", command=self.import_sensitive_words, width=15, height=2)
        self.import_words_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.start_btn = tk.Button(buttons_frame, text="▶ 启动过滤", command=self.toggle_process, width=15, height=2)
        self.start_btn.pack(side=tk.LEFT, padx=(5, 0))

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
        hint = tk.Label(self.root, text="使用前请安装 VB-Cable\n直播软件中选择 'CABLE Input' 作为麦克风", fg="gray")
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
            if CV2_AVAILABLE  and self.camera_names:
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

    def check_device_available(self,audio_input_device_index, camera_idx,w,h,fps):
        audio_input = init_audio_mic(audio_input_device_index,self.p)
        audio_output = init_audio_output(self.p)
        cam = init_video_cam(camera_idx,w,h,fps)
        msg = None
        ret = True
        if audio_input is None:
            msg = '音频输入设备检测失败'
            ret = False
            logger.error(msg)
        else:
            logger.info("音频输入设备检测成功")
            audio_input.close()
        if audio_output is None:
            msg = '音频输出设备检测失败'
            ret = False
            logger.error(msg)
        else:
            logger.info("音频输出设备检测成功")
            audio_output.close()
        if cam is None:
            msg = '视频输入设备检测失败'
            ret = False
            logger.error("视频输入设备检测失败")
        else:
            logger.info("视频输入设备检测成功")
            if cam.isOpened():  # Check if the video capture is open
                cam.release()
      
        return ret, msg

    def run_filter(self):
        
        
        
        logger.info(f"self.input_idx_map : {self.input_idx_map}")
        audio_input_device_index = self.input_idx_map[self.input_combo.get()]
        logger.info(f"audio_input_device_index：{self.input_idx_map[self.input_combo.get()]}")
        # 获取选中的分辨率字符串 (例如: "640x480")
        selected_resolution = self.resolution_combo.get()
        logger.info(f"selected_resolution: {selected_resolution}")
        if 'x' in selected_resolution:
            width, height = map(int, selected_resolution.split('x'))
        else:
            width, height = 640, 480
        # 获取选中的FPS字符串 (例如: "30")
        selected_fps = self.fps_combo.get()
        logger.info(f"selected_fps: {selected_fps}")
        
        # check device available
        ret, msg = self.check_device_available(audio_input_device_index, self.camera_idx_map[self.camera_combo.get()], width, height ,int(selected_fps))
        if not ret:
            messagebox.showerror("错误", msg)
            # Update UI status
            self.start_btn.config(text="▶ 启动过滤", state='normal')
            self.mic_status.config(text="🎤 麦克风: 未连接", fg="gray")
            self.filter_status.config(text="🔍 过滤: 未运行", fg="gray")
            if CV2_AVAILABLE:
                self.video_status.config(text="📹 视频: 未运行", fg="gray")
            self.is_running = False
            return
        # Check authentication before starting the filter

        check_res = check_auth()
        if check_res == AuthState.FOBBIDDEN.value:
            # Show error message and exit when user is disabled
            self.loading_label.destroy()
            messagebox.showerror("账户禁用", "您的账户已被禁用，程序将退出")
            self.root.destroy()
            return
        if check_res is not AuthState.SUCCESS.value:
            logger.info("认证失败")
   
            self.loading_label.destroy()
            messagebox.showerror("认证失败", "认证信息错误，请重新认证")
            auth_dialog = AuthDialog(self.root, get_device_id())
            self.root.wait_window(auth_dialog.top)
            if auth_dialog.result:
                self.create_widgets()
            else:
                self.root.destroy()
        else:                
            # 初始化队列
            self.audio_queue = Queue()
            video_queue = Queue()  # Changed to PriorityQueue for better ordering
            audio_queue = Queue()
            record_queue = Queue()
            # Reset the is_running flag in claude_plan before starting threads
            stop_event.clear()
            start_time = time.time() + 10.0
            # 创建敏感词集合
            sensitive_set = load_sensitive_words(get_device_id())
            logger.info(f"load sensitive words success,words size : {len(sensitive_set)}")
            # 创建音频处理进程，使用从claude_plan导入的函数
            self.audio_processes = []
            # 获取选中的消音选项
            selected_mute_display = self.mute_option_combo.get()
            selected_mute_option = self.mute_option_map.get(selected_mute_display, "silence")
            logger.info(f"Selected mute option: {selected_mute_option}")
            
            # 在创建进程时传递消音选项参数
            capture_audio_process = Process(target=process_capture_audio, name="AudioCapture",
                                           args=(audio_queue,record_queue, start_time, stop_event, audio_input_device_index, 
                                                 sensitive_set, self.mute_option_map[self.mute_option_combo.get()] ))
            send_audio_process = Process(target=process_send_audio_frames, name="AudioProcessor",args=(audio_queue, start_time, stop_event ) )
            upload_record_process = Process(target=upload_user_detect_record, name="UploadProcessor",args=(record_queue, get_device_id(), stop_event) )

            self.audio_processes.extend([capture_audio_process, send_audio_process,upload_record_process])
            # 启动视频进程（如果启用）
            for process in self.audio_processes:
                logger.info(f"Starting audio process: {process.name}")
                process.start()
            # 如果启用了视频功能，则创建视频处理进程
            self.video_processes = []
            if CV2_AVAILABLE :
                capture_video_process = Process(target=process_capture_video_frames, name="VideoCapture",args=(video_queue, start_time, stop_event,self.camera_idx_map[self.camera_combo.get()], width, height,int(selected_fps)))
                send_video_process = Process(target=process_send_video_frames, name="VideoSender",args=(video_queue, start_time, stop_event, width, height,int(selected_fps)))
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
                
                # 等待进程结束
                capture_audio_process.join()
                send_audio_process.join()
                upload_record_process.join()
                for process in self.video_processes:
                    process.join()
            
            # 更新状态
            self.mic_status.config(text="🎤 麦克风: 已停止", fg="gray")
            self.filter_status.config(text="🔍 过滤: 已停止", fg="gray")
            if CV2_AVAILABLE:
                self.video_status.config(text="📹 视频: 已停止", fg="gray")
            
            logger.info("Audio processing shutdown complete")

 
    def on_closing(self):
        # 占位函数：关闭应用时的清理操作
        if self.is_running:
            self.stop_process()
            # 等待线程结束（最多2秒）
        if self.process_thread and self.process_thread.is_alive():
            self.process_thread.join(timeout=2.0)
        if self.video_processes:
            for process in self.video_processes:
                logger.warning(f"Terminating stuck process: {process.name}")
                if process is not None and  process.is_alive():  # 确保进程已启动
                    process.terminate()
                    process.join(timeout=1.0)
                    if process.is_alive():  # 确保进程已终止
                        logger.error(f"Failed to terminate process: {process.name}")
        if self.audio_processes:
            for process in self.audio_processes:
                logger.warning(f"Terminating stuck process: {process.name}")
                if process is not None and  process.is_alive():  # 确保进程已启动
                    process.terminate()
                    process.join(timeout=1.0)
                    if process.is_alive():  # 确保进程已终止
                        logger.error(f"Failed to terminate process: {process.name}")
            
        if self.p:
            self.p.terminate()
        self.root.destroy()
        logger.info("Application closed")

    def on_camera_selected(self, event=None):
        """当选择摄像头时更新分辨率和FPS选项"""
        camera_name = self.camera_combo.get()
        if camera_name in self.camera_idx_map:
            camera_index = self.camera_idx_map[camera_name]
            self.update_resolution_options(camera_index)
    
    def update_resolution_options(self, camera_index):
        """更新指定摄像头的分辨率和FPS选项"""
        formats ,fps = self.get_camera_formats(camera_index)
        # 提取唯一分辨率和FPS选项
        resolutions = [item  for item in list(formats) ] if formats else ["默认"] 
        fps_values = [fps]  if formats else ["默认"]
        # 更新下拉框选项
        self.resolution_combo['values'] = resolutions
        self.fps_combo['values'] = fps_values
        # 设置默认选项
        if resolutions:
            self.resolution_combo.current(0)
        if fps_values:
            self.fps_combo.current(0)
        
        # 存储格式信息以便后续使用
        self.camera_formats = formats

    def import_sensitive_words(self):
        """导入敏感词文件"""
        try:
            from tkinter import filedialog
            file_path = filedialog.askopenfilename(
                title="选择敏感词文件",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            
            if not file_path:
                return
                
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # 处理敏感词，去除空白行和注释行
            sensitive_words = []
            for line in lines:
                word = line.strip()
                if word and not word.startswith('#'):  # 忽略空行和注释行
                    sensitive_words.append(word)
                    
            if not sensitive_words:
                messagebox.showwarning("导入失败", "文件中没有有效的敏感词")
                return
                
            # 发送敏感词到服务器
            try:
                update_url = f"{BASE_URL}/update_user_words"
                payload = {
                    "mac": get_device_id(),  # 修复:使用get_device_id()而不是device_id变量
                    "words": sensitive_words
                }
                response = requests.post(update_url, json=payload)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("code") == 200:
                        messagebox.showinfo("导入成功", f"成功导入 {len(sensitive_words)} 个敏感词并同步到服务器")
                        logger.info(f"Imported {len(sensitive_words)} sensitive words from {file_path} and synced to server")
                    else:
                        messagebox.showwarning("导入部分成功", f"本地导入成功 ({len(sensitive_words)} 个敏感词)，但服务器同步失败: {result.get('msg')}")
                        logger.warning(f"Imported {len(sensitive_words)} sensitive words locally but failed to sync to server: {result.get('msg')}")
                else:
                    messagebox.showwarning("导入部分成功", f"本地导入成功 ({len(sensitive_words)} 个敏感词)，但服务器同步失败: HTTP {response.status_code}")
                    logger.warning(f"Imported {len(sensitive_words)} sensitive words locally but failed to sync to server: HTTP {response.status_code}")
            except Exception as e:
                messagebox.showwarning("导入部分成功", f"本地导入成功 ({len(sensitive_words)} 个敏感词)，但服务器同步失败: {str(e)}")
                logger.warning(f"Imported {len(sensitive_words)} sensitive words locally but failed to sync to server: {str(e)}")
                
        except Exception as e:
            messagebox.showerror("导入失败", f"导入敏感词时出错:\n{str(e)}")
            logger.error(f"Failed to import sensitive words: {str(e)}")

if __name__ == "__main__":
    # Add freeze support check to prevent multiple windows on startup
    from multiprocessing import freeze_support
    freeze_support()
    
    root = tk.Tk()
    fonts = tkFont.families()
    for itm in fonts:
        if "阿里巴巴普惠" in itm:
            font_name = itm
            break
        elif "Microsoft YaHei" in itm:
            font_name = itm
            break

    if font_name is None:
        font_name = font_name
    app = VoiceFilterApp(root)
    # Only set the protocol if the root window still exists (not destroyed during auth)
    try:
        if root.winfo_exists():
            root.protocol("WM_DELETE_WINDOW", app.on_closing)
            root.mainloop()
    except tk.TclError:
        # Application was destroyed during authentication, exit gracefully
        pass
