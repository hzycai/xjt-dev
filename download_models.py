# download_models.py
from faster_whisper import WhisperModel
import os

def download_model(size):
    print(f"正在下载 {size} 模型...")
    model = WhisperModel(size, device="cpu", compute_type="int8")
    print(f"✅ {size} 模型已缓存到: {model.model_path}")

if __name__ == "__main__":
    # 下载 base 模型（必选）
    download_model("base")
    # 下载 small 模型（可选，有 GPU 时推荐）
    download_model("small")