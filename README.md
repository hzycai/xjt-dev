# 抖音敏感词过滤器 (Whisper版)

这是一个实时语音过滤工具，专门用于在直播或语音通话中自动检测并屏蔽敏感词汇。它使用 OpenAI 的 Whisper 语音识别技术来识别语音内容，并实时过滤预设的敏感词。

## 功能特点

- 实时语音监听和转发
- 基于 Whisper 的高精度语音转文本
- 敏感词自动检测和屏蔽
- 支持 GPU 加速（如果可用）
- 图形用户界面，操作简单

## 系统要求

- Python 3.7 或更高版本
- 麦克风设备
- VB-Cable 或类似虚拟音频设备（用于转发过滤后的音频）

## 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖包括：
- faster-whisper: 用于语音识别
- tkinter: 图形界面
- pyaudio: 音频处理
- numpy: 数值计算

如果需要 GPU 加速，还需要安装相应的包：
```bash
# 对于 NVIDIA GPU 用户
pip install onnxruntime-gpu

# 对于仅 CPU 用户
pip install onnxruntime
```

## 使用方法

1. 确保已安装所有依赖
2. 运行程序：
   ```bash
   python main.py
   ```
3. 在图形界面中：
   - 选择输入设备（通常是你的麦克风）
   - 选择输出设备（通常是 VB-Cable 虚拟音频设备）
   - 选择合适的 Whisper 模型（base 或 small）
   - 点击"启动过滤"开始实时语音过滤
4. 程序会将过滤后的音频输出到指定的输出设备

## 工作原理

1. 程序从选定的输入设备捕获音频
2. 使用 Whisper 模型将音频转换为文本
3. 检查文本中是否包含敏感词
4. 如果检测到敏感词，会在该时间段内静音音频输出
5. 将处理后的音频转发到指定的输出设备

## 敏感词配置

当前版本使用内置的敏感词列表。你可以直接在 [main.py](file:///Users/gushan/Documents/code/yucheng/yucheng-whisper/main.py) 中修改 [load_sensitive_words](file:///Users/gushan/Documents/code/yucheng/yucheng-whisper/main.py#L27-L29) 方法来添加或删除敏感词。

## 注意事项

- 确保 VB-Cable 或类似虚拟音频设备已正确安装和配置
- 根据你的硬件选择合适的 Whisper 模型（GPU 用户可选择 small 模型获得更好效果）
- 程序会自动检测 NVIDIA GPU 并提供相应选项

