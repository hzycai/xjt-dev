# util.py
import sys
import os
from cryptography.fernet import Fernet
import json
import hashlib
from enum import Enum
from utils.download_file import download_file

class AuthState(Enum):
    UNREGISTERED = 0
    SUCCESS = 1
    FAILED = 2
    UNBIND = 3
    FOBBIDDEN = 4   

class AudioReplaceType(Enum):
    SILENCE = 0
    BEEP = 1

# BASE_URL = "http://127.0.0.1:5000"
BASE_URL = "https://cfapi.bdhome360.com"
sen_words_version_file_path="config/version.json"
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


def load_sensitive_words(mac):
    
    """
        version.json内容格式：{"version": 1}
    """
    file_path = resource_path(sen_words_version_file_path)
    # Check if the directory of the file path exists, create it if not
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    # If the file exists, load JSON data from it
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            data  =  json.loads(content)
            version = int(data['version'])
        except (json.JSONDecodeError, IOError):
            # Return None or handle error appropriately if JSON is invalid or file can't be read
            version = -1
    else:
        version = -1

    # Request sensitive words and version information from server
    import requests
    try:
        response = requests.get(f"{BASE_URL}/get_words_and_version", params={
            "version": version,
            "mac": mac
        })
        response.raise_for_status()
        result = response.json()
        
        if result.get("code") == 200:
            data = result.get("data", {})
            remote_version = data.get("version", -1)
            words = data.get("words", [])
            file_url = data.get("file_url")
            
            # Save sensitive words to file
            sensitive_words_path = resource_path("config/sensitive_words.txt")
            
            # If versions match, load local file
            if version == remote_version:
                if os.path.exists(sensitive_words_path):
                    return load_sensitive_words_file(sensitive_words_path, words)
            # If versions don't match and we have a file URL, download new file
            elif file_url:
                try:
                    if download_file(file_url,sensitive_words_path):
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(json.dumps({"version": remote_version}))
                        return load_sensitive_words_file(sensitive_words_path, words)
                except Exception as e:
                    print(f"Failed to download sensitive words file: {e}")
            else:
                 return None
        else:
            print(f"Server returned error: {result.get('msg', 'Unknown error')}")
            return None
            
    except requests.RequestException as e:
        print(f"Failed to request sensitive words: {e}")
        return None
    

def load_sensitive_words_file(sensitive_words_file, words):
    """Load sensitive words from file"""
    sensitive_set = set()
    try:
        # Try to load sensitive words from external file
        with open(sensitive_words_file, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word:  # Ignore empty lines
                    sensitive_set.add(word)
        print(f"Loaded {len(sensitive_set)} sensitive words from file: {sensitive_words_file}")
    except FileNotFoundError:
        # If file doesn't exist, use default sensitive words
        print("sensitive_words.txt not found, using default sensitive words")
        return None
    except Exception as e:
        print(f"Error loading sensitive words: {e}")
        # Use default sensitive words in case of error
        return None
    
    sensitive_set.update(words)
         
    return sensitive_set
