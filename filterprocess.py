import time
import queue
import threading
from dataclasses import dataclass
from funasr import AutoModel
import pyaudio
import sys
import cv2
import pyvirtualcam
import numpy as np
import os
import signal
from utils.logger import get_logger
from multiprocessing import  Queue
from util import resource_path 
logger = get_logger()
 

@dataclass
class MediaFrame:
    data: any
    target_t: float  # Presentation TimeStamp
    end_t: float

def now_sec() -> float:
    return time.monotonic()

# video_queue = queue.Queue()  # Changed to PriorityQueue for better ordering
# audio_queue = queue.Queue()

# video_queue = Queue()  # Changed to PriorityQueue for better ordering
# audio_queue = Queue()
is_running = True
start_time = None  # Unified start time reference
delay_t = 2.0
delay_threshold = 0.15

def init_model():
    # Initialize the speech recognition model like in main.py
    logger.info("Initializing speech recognition model")
    model_dir =resource_path("model") 
    
    logger.info(f"Model directory: {model_dir}")
    # model = AutoModel(model="paraformer-zh-streaming", model_revision="v2.0.4", disable_update=True,device="cuda:0")
    # model = AutoModel(model="./model", model_revision="v2.0.4", disable_update=True,device="cuda:0")
    try:
        model = AutoModel(model=model_dir, model_revision="v2.0.4", disable_update=True,device="cuda:0",disable_pbar=False)
    except Exception as e:
        logger.error(f"Failed to initialize speech recognition model: {e}")

   
    logger.info("Speech recognition model initialized successfully")
    return model

def init_video_cam(camera_index):
    try:    
        logger.info("Initializing video capture device")
        # cap = cv2.VideoCapture(0)
        # if not cap.isOpened():
        #     logger.error("Cannot open camera 0")
        
        # # 设置摄像头分辨率
        # cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        # cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)

        # 设置常见分辨率（先试 1080p30）
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FPS, 30)

        # 关键：设置像素格式为 YUY2（大多数 UVC 采集设备默认格式）
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('Y', 'U', 'Y', '2'))
        logger.info("Video capture device initialized successfully with resolution 1280x720")
        return cap
    except Exception as e:
        logger.error(f"Failed to initialize video capture: {e}")
       
                
def init_audio_mic(audio_input_device_index):
    # Initialize audio input stream similar to main.py
    logger.info("Initializing audio input stream")
    p = pyaudio.PyAudio()
    INPUT_RATE = 16000
    CHUNK = 960
    CHANNELS = 1
    input_idx = audio_input_device_index
    try:
        audio_stream_in = p.open(
            format=pyaudio.paFloat32,
            channels=CHANNELS,
            rate=INPUT_RATE,
            input=True,
            input_device_index=input_idx,
            frames_per_buffer=CHUNK
        )
        logger.info(f"Audio input stream initialized successfully with rate={INPUT_RATE}, chunk={CHUNK}")
        return audio_stream_in
    except Exception as e:
        logger.error(f"Failed to initialize audio input stream: {e}")
       

def init_audio_output():
    # Initialize audio output stream
    logger.info("Initializing audio output stream")
    p = pyaudio.PyAudio()
    try:
        # Find VB-Cable device like in main.py
        output_idx = None
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            # Look for output device with CABLE in name
            if dev['maxOutputChannels'] > 0 and 'CABLE' in dev['name'].upper():
                output_idx = i
                logger.info(f"Found VB-Cable output device: {dev['name']} (index {i})")
                break
        
        # If no VB-Cable device found, use first available output device
        if output_idx is None:
            logger.warning("VB-Cable device not found, searching for alternative output device")
            for i in range(p.get_device_count()):
                dev = p.get_device_info_by_index(i)
                if dev['maxOutputChannels'] > 0:
                    output_idx = i
                    logger.info(f"Using alternative output device: {dev['name']} (index {i})")
                    break
        
        if output_idx is None:
            raise Exception("No output device found")
        
        device_info = p.get_device_info_by_index(output_idx)
        output_rate = int(device_info['defaultSampleRate'])

        audio_stream_out = p.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=output_rate,
                output=True,
                output_device_index=output_idx,
                frames_per_buffer=1024
            )
        logger.info(f"Audio output stream initialized successfully with rate={output_rate}")
        return audio_stream_out
    except Exception as e:
        logger.error(f"Failed to initialize audio output stream: {e}")
        
def process_capture_video_frames(video_queue, start_time, stop_event, camera_index):
    # Thread 1: Process video frames
    # TODO: Add video processing logic here
    logger.info("Starting video capture thread")
    logger.info(f"Camera index: {camera_index}")
    cap = init_video_cam(camera_index)  # Get the video capture object
    while time.time() < start_time :
        time.sleep(0.01)
    try:
        # while is_running:
        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                logger.warning("Can't receive frame from camera")
                break
             
            # Create MediaFrame with frame data and timestamp based on unified clock
            
            timestamp =  now_sec() + delay_t
            video_queue.put((timestamp,frame))   # Priority based on timestamp
            
    except Exception as e:
        logger.error(f"Error capturing video frames: {e}")
    finally:
        if cap.isOpened():  # Check if the video capture is open
            cap.release()
        logger.info(f"Video capture thread stopped. ")

def process_send_video_frames(video_queue, start_time, stop_event):
    # Thread 1: Process video frames
    # TODO: Add video processing logic here
    logger.info("Starting video sending thread")
    target_t = None
    frame_count = 0
    while time.time() < start_time :
        time.sleep(0.01)
 
    try:
        with pyvirtualcam.Camera(width=1280, height=720, fps=30) as cam:
            logger.info("Virtual camera initialized successfully")
            # while is_running:
            while not stop_event.is_set():
                try:
                    # Get next frame from queue
                    if target_t is None:
                        target_t, media_frame = video_queue.get(timeout=0.01)
                        # print(f"取出frame，queue size:{video_queue.qsize()}")
                    current_time = now_sec()
                    # Send frame if it's time to display it
                    if current_time - delay_threshold <=  target_t <= current_time:
                        # 调整帧大小以匹配虚拟摄像头分辨率
                        frame = cv2.resize(media_frame, (cam.width, cam.height))
                        # 将BGR格式转换为RGB格式（因为pyvirtualcam期望RGB格式）
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        # 将RGB格式的numpy数组发送到虚拟摄像头
                        cam.send(frame_rgb)
                        # Log the target_t when sending video frame
                        # logger.debug(f"Sent video frame with timestamp: {target_t}")
                        frame_count += 1
                        target_t = None  # Ready for next frame
                        if frame_count % 30 == 0:  # Log every 30 frames sent
                            logger.debug(f"Sent {frame_count} video frames so far")
                    elif target_t <= current_time - delay_threshold:
                        # Too early for this frame, put it back
                        target_t = None
                except queue.Empty:
                    # No frames available, send last frame or blank frame
                    time.sleep(0.001)
                    continue
                except Exception as e:
                    logger.error(f"Error sending video frames: {e}")
        logger.info(f"Video sending thread stopped. Total frames sent: {frame_count}")
    except Exception as e:
        logger.error(f"Error initializing or using virtual camera: {e}")
    finally:
        logger.info("stop video sending thread")

def load_sensitive_words():
    """Load sensitive words from file"""
    sensitive_set = set()
    try:
        # Try to load sensitive words from config directory
        config_path = "config"
        if not os.path.exists(config_path):
            os.makedirs(config_path)
            logger.info(f"Created config directory: {config_path}")
        # sensitive_words_file = os.path.join(config_path, "sensitive_words.txt")
        sensitive_words_file =  resource_path("config/sensitive_words.txt")

        
        # Try to load sensitive words from external file
        with open(sensitive_words_file, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word:  # Ignore empty lines
                    sensitive_set.add(word)
        logger.info(f"Loaded {len(sensitive_set)} sensitive words from file: {sensitive_words_file}")
    except FileNotFoundError:
        # If file doesn't exist, use default sensitive words
        logger.warning("sensitive_words.txt not found, using default sensitive words")
        sensitive_set = {"微信", "VX", "赚钱", "最便宜", "稳赚", " guaranteed", "绝对", "第一"}
    except Exception as e:
        logger.error(f"Error loading sensitive words: {e}")
        # Use default sensitive words in case of error
        sensitive_set = {"微信", "VX", "赚钱", "最便宜", "稳赚", " guaranteed", "绝对", "第一"}
    logger.info("loaded sensitive words successfully")
    return sensitive_set
def output_audio_to_vb_cable(audio_data, vb_cable_stream, input_rate, output_rate):
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
            logger.error(f"输出音频到输出设备失败: {e}")
            print(f"输出音频到输出设备失败: {e}")
def process_send_audio_frames(audio_queue, start_time, stop_event):
    # Thread 2: Process audio frames
    logger.info("Starting audio processing and sending thread")
    # Initialize audio output stream
    audio_stream_out = init_audio_output()
    audio_frame = None
    while time.time() < start_time :
        time.sleep(0.01)
    # while is_running:
    try:
        while not stop_event.is_set():
            try:
                if audio_frame is None:            
                    # Get audio data from the audio queue
                    _,audio_frame ,input_rate,output_rate= audio_queue.get(timeout=0.01)
                current_time = now_sec() 
                if current_time - delay_threshold <= audio_frame.target_t <= current_time  :
                    # audio_stream_out.write(audio_frame.data.astype(np.float32).tobytes())
                    output_audio_to_vb_cable(audio_frame.data.astype(np.float32).tobytes(),audio_stream_out, input_rate,output_rate )
                    logger.debug(f"Sent audio frame with timestamp: {audio_frame.target_t}")
                    audio_frame = None
                elif audio_frame.target_t < current_time - delay_threshold:
                    logger.debug(f"Audio frame 已过期,current_time:{current_time},audio_frame.target_t:{audio_frame.target_t},{(current_time - audio_frame.target_t):.3f}")
                    audio_frame = None
            
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error sending audio frames: {e}")
    finally:
        logger.info("Stopping audio send thread")
    

def process_capture_audio(audio_queue, start_time, stop_event, audio_input_device_index ):
    # Initialize audio input stream
    logger.info("Starting audio capture thread")
    INPUT_RATE = 16000
    CHUNK = 960
    audio_stream_in = init_audio_mic(audio_input_device_index)
    model = init_model()
    audio_stream_out = init_audio_output()
    sensitive_set = load_sensitive_words()
    # Buffer to accumulate audio data
    audio_buffer = np.array([], dtype=np.float32)
    # Target duration in seconds
    target_duration = 1.2
    chunk_count = 0
    while time.time() < start_time :
        time.sleep(0.01)
   
    timestamp = None
    try:
        # while is_running:
        while not stop_event.is_set():
             
            if timestamp is None:
                timestamp = now_sec()
                print(f"开始音频采集{timestamp}")

            # Read audio chunk
            try:
                data = audio_stream_in.read(CHUNK, exception_on_overflow=False)
            except Exception as e:
                logger.error(f"Audio read error: {e}")
                break
            audio_data = np.frombuffer(data, dtype=np.float32)
            chunk_count += 1
            # Accumulate audio data in buffer
            audio_buffer = np.concatenate([audio_buffer, audio_data])
            
            # Check if we have enough data (1.2 seconds)
            if len(audio_buffer) >= int(target_duration * INPUT_RATE):
                # Create MediaFrame with accumulated audio data and timestamp
                now_t = now_sec()
                print(f"音频采集结束，结束时间：{now_t}，采集时间长度：{(now_t - timestamp):.3f}")

                duration = len(audio_buffer) / INPUT_RATE
                audio_frame = MediaFrame(audio_buffer.copy(), timestamp + delay_t, duration)
                res = model.generate(input=audio_buffer, is_final=is_running)
                logger.debug(f"Recognized speech: {res}")
                print(f"音频推理完毕，推理时长{now_sec() - now_t}")
                # Check for sensitive words
                found_sensitive_words = []
                if isinstance(res, list) and len(res) > 0 and 'text' in res[0]:
                    recognized_text = res[0]['text'].replace(' ', '')
                    for word in sensitive_set:
                        if word in recognized_text:
                            found_sensitive_words.append(word)
                            logger.warning(f"Sensitive word detected: {word}")
                            print(f"⚠️  Warning: Sensitive word detected: {word}")
                             
                if found_sensitive_words:
                    # Create beep sound with same duration as original audio                                      
                    output_rate = audio_stream_out._rate  # Get output stream rate                    
                    # Generate beep signal
                    num_samples = int(duration * output_rate)
                    beep_freq = 800  # Beep frequency in Hz
                    t = np.linspace(0, duration, num_samples, False)
                    # beep_signal = np.sin(2 * np.pi * beep_freq * t) * 0.5  # Generate sine wave with reduced volume
                    audio_frame.data = np.sin(2 * np.pi * beep_freq * t) * 0.5  # Generate sine wave with reduced volume

                    # audio_frame.data = beep_signal.astype(np.float32).tobytes()
                    logger.info(f"Replaced audio with beep due to sensitive words: {', '.join(found_sensitive_words)}")
                    # Log timestamp when beep data is sent
                    logger.debug(f"Sent beep audio frame with timestamp: {audio_frame.target_t}")
                     
                    audio_queue.put((timestamp + delay_t, audio_frame,output_rate,output_rate))
                else:
                    audio_queue.put((timestamp + delay_t, audio_frame,INPUT_RATE,audio_stream_out._rate))
                now_t = now_sec()
                print(f"音频处理完毕，发送时间:{now_t}")
                timestamp = None
                # Reset buffer
                audio_buffer = np.array([], dtype=np.float32)
                
    except Exception as e:
        logger.error(f"Error capturing audio frames: {e}")
        logger.exception(e)
    finally:
        logger.info("Stopping audio capture thread")
        audio_stream_in.stop_stream()
        audio_stream_in.close()

 