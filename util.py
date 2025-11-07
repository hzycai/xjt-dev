# util.py
import sys
import os
from cryptography.fernet import Fernet
import json
import uuid
import hashlib
from enum import Enum
class AuthState(Enum):
    UNREGISTERED = 0
    SUCCESS = 1
    FAILED = 2
    UNBIND = 3


key = b'Ephk5rl57rcgpWohYOzpSU7RM4-7vb0Xdm6m47eU_GU='
def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        # 打包后：使用 exe 所在目录（--onedir）或 _MEIPASS（--onefile）
        base_dir = os.path.dirname(sys.executable) if not hasattr(sys, '_MEIPASS') else sys._MEIPASS
        relative_path = relative_path.replace('/', '\\')
        return f"{base_dir}\\{relative_path}"
    else:
        # 开发环境
        base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    
        return os.path.join(base_dir, relative_path)

def write_bin_file(file_path,data_bytes):
    cipher = Fernet(key)
    # 加密
    encrypted_data = cipher.encrypt(data_bytes)
    # 写入文件（纯二进制）
    with open(file_path, "wb") as f:
        f.write(encrypted_data)

   

def read_bin_file(file_path):
    cipher = Fernet(key)
    if not os.path.exists(file_path):
        return None
    with open(file_path, "rb") as f:
        encrypted_data = f.read()
    decrypted_bytes = cipher.decrypt(encrypted_data)
    return decrypted_bytes.decode('utf-8')

# 新增函数：计算认证哈希值
def calculate_auth_hash(uuid_list, user_key):
    """
    根据UUID列表和用户密钥计算认证哈希值
    
    Args:
        uuid_list (list): UUID列表
        user_key (str): 用户密钥
        
    Returns:
        str: SHA256哈希值
    """
    sorted_uuid_string = ''.join(sorted(uuid_list))
    hash_input = sorted_uuid_string + user_key
    return hashlib.sha256(hash_input.encode('utf-8')).hexdigest()