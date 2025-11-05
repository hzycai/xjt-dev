import os
import json
import uuid
from pathlib import Path
import requests

# Define the URL for the HTTP request
AUTH_URL = "https://example.com/auth"  # Replace with actual URL

def read_auth_config(config_path="config/auth.json"):
    """
    Read the auth configuration from JSON file.
    If the file doesn't exist, create it with default values.
    
    Args:
        config_path (str): Path to the auth configuration file
        
    Returns:
        dict: Configuration data
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    # If file doesn't exist, create it with default values
    if not os.path.exists(config_path):
        mac_address = ""
        device_file_path = ""
        
        # Try to get MAC address
        try:
            # 修改为从mac_util.py导入函数
            from utils.mac_util import get_mac_address
            mac_address = get_mac_address()
        except Exception:
            # If MAC address cannot be obtained, create .cache directory and mydevice.json
            # 修改为使用Path获取用户主目录下的.cache路径
            cache_dir = Path.home() / ".cache"
            uuid_dir = cache_dir / str(uuid.uuid4())
            os.makedirs(uuid_dir, exist_ok=True)
            device_file = uuid_dir / 'mydevice.json'
            
            # Create mydevice.json file
            # 修改为{"mac": uuid}格式
            device_info = {"mac": str(uuid.uuid4())}
            with open(device_file, 'w') as f:
                json.dump(device_info, f)
                
            device_file_path = str(device_file)
        
        # 修改默认配置结构为 {"mac":"","key":"","filepath":""}
        default_config = {
            "mac": mac_address,
            "key": "",
            "filepath": device_file_path
        }
        
        # Write default configuration to file
        with open(config_path, "w") as f:
            json.dump(default_config, f, indent=4)
        
        return default_config
    
    # Read existing configuration
    with open(config_path, "r") as f:
        config = json.load(f)
    
    return config


def send_auth_request(config_path="config/auth.json"):
    """
    Read auth configuration and send HTTP request with MAC and key.
    
    Args:
        config_path (str): Path to the auth configuration file
        
    Returns:
        dict: Response from the HTTP request
    """
    # Read the auth configuration
    config = read_auth_config(config_path)
    
    # Get MAC and key from config
    mac = config.get("mac", "")
    key = config.get("key", "")
    
    # If MAC is not in config, try to read it from the filepath JSON
    if not mac and config.get("filepath"):
        try:
            with open(config["filepath"], "r") as f:
                device_info = json.load(f)
                mac = device_info.get("mac", "")
        except Exception:
            pass  # If we can't read the file, mac remains empty
    
    # Create the request body
    body = {
        "mac": mac,
        "key": key
    }
    
    # Send the HTTP request
    try:
        response = requests.post(AUTH_URL, json=body)
        return {
            "status_code": response.status_code,
            "response": response.json() if response.content else {}
        }
    except Exception as e:
        return {
            "error": str(e)
        }
