# download_models.py
from faster_whisper import WhisperModel
import os
import sys

def resource_path(relative_path):
    """获取资源路径（兼容打包后和开发环境）"""
    try:
        # PyInstaller 创建临时文件夹 _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def download_model(size):
    print(f"正在下载 {size} 模型...")
    model = WhisperModel(size, device="cpu", compute_type="int8")
    
    # 创建目标目录
    models_dir = resource_path("models")
    os.makedirs(models_dir, exist_ok=True)
    
    target_dir = os.path.join(models_dir, size)
    os.makedirs(target_dir, exist_ok=True)
    
    # 获取源模型路径 - 使用正确的属性
    
    # 改为使用模型下载和保存的正确方法
    from faster_whisper.utils import download_model
    source_model_path = download_model(size, ".cache")
    
    # 复制模型文件到目标目录
    import shutil
    for file in os.listdir(source_model_path):
        source_file = os.path.join(source_model_path, file)
        target_file = os.path.join(target_dir, file)
        if os.path.isfile(source_file):
            shutil.copy2(source_file, target_file)
            print(f"复制文件: {file}")
    
    print(f"✅ {size} 模型已保存到: {target_dir}")

if __name__ == "__main__":
    # 确保models目录存在
    models_dir = resource_path("models")
    os.makedirs(models_dir, exist_ok=True)
    
    # 下载 base 模型（必选）
    # download_model("base")
    
    # 下载 small 模型（可选，有 GPU 时推荐）
    download_model("small")
    download_model("medium")
