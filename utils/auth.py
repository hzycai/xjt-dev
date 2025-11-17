import os
import json
import uuid
from pathlib import Path
import requests
from util import resource_path, write_bin_file, read_bin_file, calculate_auth_hash, AuthState, BASE_URL
from utils import get_logger
 

logger = get_logger()

# Define the URL for the HTTP request
 
default_config_path="config/auth.bin"
# Define authentication states enumeration


def create_userinfo(key):
    """
    Create userinfo directories and files in three specific locations.
    
    Args:
        key (str): The user key to store in the device.bin files
        
    Returns:
        list: List of paths where the device.bin files were created
    """
    # Define the three target directories
    home = Path.home()
    
    # 动态获取系统盘符，而不是硬编码C盘
    windir = Path(os.environ.get('WINDIR', 'C:\\Windows'))
    system_root = windir.parent  # 通常是 C:\
    program_data_path = system_root / "ProgramData" / "cache" / str(uuid.uuid4())

    dirs = [
        home / ".cache" / str(uuid.uuid4()),
        home / ".config"/ str(uuid.uuid4()),
        program_data_path
    ]
    
    # Check and create directories if they don't exist
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)
    
    uuid_list = []
    # Create device.bin in each directory
    file_paths = []
    for directory in dirs:
        # Generate a UUID for the device
        device_uuid = str(uuid.uuid4())
        uuid_list.append(device_uuid)
        file_path = directory / "device.bin"
        file_content = json.dumps({"id": device_uuid, "key": key}).encode("utf-8")
        write_bin_file(str(file_path), file_content)
        file_paths.append(str(file_path))
        
    return file_paths, uuid_list


def check_auth():
     
    """
        实现用户认证的功能
        账户认证流程
        1.如果config/auth.bin文件不存在
            step1:创建一个config/auth.bin文件,生成一个device_id
            step2:将这个device_id作为http请求的参数，发送给服务器进行注册
            step3:弹出一个输入框，要求用户输入一个key
            step4:接收用户输入的key，向服务器进行验证这个key的合法性
            step5:如果验证成功，生成3个文件，分别存储一个json,格式{"id":uuid,"key":key}
            step6:将3个文件的文件路径发送给服务器，服务器进行存储
            step7：读取3个文件中的uuid,将uuid变成列表后进行排序，随后拼接成一个字符串后再拼接上key，进行hash。将结果发送给服务器
        2.如果config/auth.bin文件存在
            step1:读取config/auth.bin文件，取出deivice_id
            step2:将device_id作为http请求的参数，发送给服务器获取文件地址以及hash值
            step3:根据服务器返回的文件地址，读取文件，取出每个文件中的uuid,将uuid变成列表后进行排序，随后拼接成一个字符串后再拼接上key，进行hash
            step4:将step3中获得的hash和step2中获取的hash进行比较，如果一致则验证通过
    """ 
    config_path = resource_path(default_config_path)
    
    if not os.path.exists(config_path):
        logger.info(f"Auth configuration file not found at {config_path}, creating...")
        os.makedirs(resource_path("config"), exist_ok=True)
        
        # Step 1: Create config/auth.bin with a new device_id
        device_id = str(uuid.uuid4())
        write_bin_file(config_path, json.dumps({"device_id": device_id}).encode("utf-8"))
        logger.info(f"Created auth configuration file at {config_path}")

        register_url = BASE_URL + "/register_user"
        # 修改注册请求体，使用mac而不是device_id
        register_body = {"mac": device_id}
        try:
            response = requests.post(register_url, json=register_body)
            if response.status_code != 200:
                logger.error(f"Registration failed with status {response.status_code}")
                return AuthState.FAILED.value
            else:
                regist_data = response.json()
                if regist_data['code'] != 200:
                    logger.error(f"Registration failed with message: {regist_data['msg']}")
                    return AuthState.FAILED.value 
                else:
                    logger.info(f"Registration successful: {regist_data['msg']}")
                    return AuthState.UNREGISTERED.value
        except Exception as e:
            logger.error(f"Registration request failed: {e}")
            return AuthState.FAILED.value
    else:
        device_info = json.loads(read_bin_file(config_path))
        logger.info(f"Reading device_info: {device_info}")

        # Step 2: Request file info and hash from server
        device_id = device_info.get("device_id")
        get_user_file_info_url = BASE_URL + "/get_user_file_info"
        try:
            response = requests.get(get_user_file_info_url, params={"mac": device_id})
            if response.status_code != 200:
                logger.error(f"Failed to get user file info, status: {response.status_code}")
                return AuthState.FAILED.value
            
            file_info_data = response.json()
            if file_info_data['code'] == 500:
                # User does not exist
                logger.error("User does not exist")
                return AuthState.FAILED.value
            elif file_info_data['code'] == 501:
                # User exists but no file_path or hash
                logger.error("User exists but file info is incomplete")
                return AuthState.UNBIND.value
            elif file_info_data['code'] == 502:
                # USER fobbidden
                logger.error("User exists but fobbidden")
                return AuthState.FOBBIDDEN.value
            elif file_info_data['code'] == 200:
                # Successfully retrieved file info and hash
                logger.info(f"Successfully retrieved user file info:{file_info_data}")
                # TODO: Implement steps 3 and 4 from the specification
                # Step 3: Read files, calculate hash and compare with server hash
                # Step 4: Return success if hashes match
                
                # Parse file paths from server response
                file_paths = file_info_data['file_path'].split(',')
                server_hash = file_info_data['hash']
                
                
                # Read UUIDs from each file
                uuid_list = []
                for file_path in file_paths:
                    if not os.path.exists(file_path):
                        logger.error(f"Missing files: {file_path}")
                        return AuthState.FAILED.value
                    try:
                        file_content = read_bin_file(file_path.strip())
                        if file_content:
                            file_data = json.loads(file_content)
                            uuid_list.append(file_data.get('id'))
                        else:
                            logger.error(f"Failed to read file: {file_path}")
                            return AuthState.FAILED.value
                    except Exception as e:
                        logger.error(f"Error reading file {file_path}: {e}")
                        return AuthState.FAILED.value
                
                # Get key from one of the files (assuming all have the same key)
                try:
                    file_content = read_bin_file(file_paths[0].strip())
                    file_data = json.loads(file_content)
                    user_key = file_data.get('key')
                except Exception as e:
                    logger.error(f"Error reading key from file: {e}")
                    return AuthState.FAILED.value
                
                # Calculate hash using the same method as server
                calculated_hash = calculate_auth_hash(uuid_list, user_key)
                
                # Compare hashes
                if calculated_hash == server_hash:
                    logger.info("Authentication hash  successful")
                    return AuthState.SUCCESS.value
                else:
                    logger.error("Hash verification failed. Calculated hash does not match server hash.")
                    return AuthState.FAILED.value
            else:
                logger.error(f"Unexpected response code: {file_info_data['code']}")
                return AuthState.FAILED.value
                
        except Exception as e:
            logger.error(f"Request for user file info failed: {e}")
            return AuthState.FAILED.value
        

def get_device_id():
    config_path = resource_path(default_config_path)
    device_info = json.loads(read_bin_file(config_path))
    return device_info.get("device_id", None)