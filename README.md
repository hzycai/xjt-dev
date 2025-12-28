
# LiveStream Sensitive Word Filter

本项目实现在直播过程中对音频进行**实时敏感词过滤**。通过采集麦克风和摄像头数据，在固定延迟后同步推流，并自动屏蔽包含敏感词的语音内容。

---

## 📌 功能特点

- 实时采集麦克风音频与摄像头视频
- 使用 **FunASR** 进行流式语音识别（ASR）
- 自动检测并过滤配置文件中的敏感词
- 音频输出至 **VB-CABLE 虚拟麦克风**
- 视频推流至 **OBS Studio**，便于直播使用
- 支持自定义 ASR 模型路径或使用默认模型

---

## ⚙️ 环境依赖

在运行本项目前，请确保已安装以下软件：

- [VB-CABLE Virtual Audio Device](https://vb-audio.com/Cable/)（用于创建虚拟麦克风）
- [OBS Studio](https://obsproject.com/)（用于接收视频推流）

> 💡 请提前配置好 OBS，使其能捕获本程序输出的视频流。

---

## 📦 安装步骤

1. 克隆本仓库：
   ```bash
   git clone https://github.com/hzycai/xjt-dev.git
   cd xjt-dev
安装 Python 依赖：
pip install -r requirements.txt
选择 ASR 模型加载方式（二选一）：
方式一：使用项目内 model/ 目录下的模型
将 FunASR 的 paraformer-zh-streaming 模型（或其他兼容模型）放入 ./model/ 目录
代码中会自动从该路径加载（见 filterprocess.py 中 init_model 函数）
方式二：使用 FunASR 默认模型路径
首次运行前下载模型到默认缓存目录：
 
python download_model.py
此脚本会自动下载 paraformer-zh-streaming 模型（版本 v2.0.4）
🔧 如需更换其他 ASR 模型（如 SenseVoice、Whisper 等），请修改 filterprocess.py 中 AutoModel 的 model 参数。

🛡️ 敏感词配置
敏感词列表位于：
 
config/sensitive_words.txt
格式：每行一个敏感词，支持中文、英文等。

示例：

最便宜
最实惠
超值

▶️ 运行程序
 
python run.py
程序将：

启动摄像头和麦克风采集
实时识别语音并过滤敏感词
将处理后的音频送入 VB-CABLE
将视频帧推送至 OBS（通过共享内存、虚拟摄像头等方式，具体取决于你的实现）
📚 技术栈
ASR 引擎：FunASR（Paraformer 流式模型）
音频路由：VB-CABLE
视频推流：OBS Studio
语言：Python 3.8+
📝 注意事项
推荐使用 GPU（CUDA）以获得更低的识别延迟，确保 device="cuda:0" 可用。
首次运行建议先测试音频/视频是否正常流入 VB-CABLE 和 OBS。
本项目仅做技术演示，请遵守当地法律法规，勿用于非法用途。
📄 许可证
本项目采用 MIT 许可证。详情见 LICENSE。