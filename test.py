from cryptography.fernet import Fernet
import json
import uuid
import hashlib
# 生成密钥（实际应用中应安全存储，不要每次生成）
# key = Fernet.generate_key()
key = b'Ephk5rl57rcgpWohYOzpSU7RM4-7vb0Xdm6m47eU_GU='
print(key.decode())
cipher = Fernet(key)

# 将a1-a5修改成一个dict
uuid_dict = {
    "a1": "ad3ac59e-a475-41c1-ae15-7cb164d2ee6f",
    "a2": "c41bb839-3dd3-41e4-8d84-ddaa278ceb14",
    "a3": "8d59b327-bb12-49f8-95e0-9e554286e73c",
    "a4": "a88dbb3d-1f8c-414c-a9ba-8be157bd9a38",
    "a5": "9b4491b5-4a3d-4d57-acc1-3f4dd99ad756"
}

# 将uuid_dict的值添加到一个List中
uuid_list = list(uuid_dict.values())

# 将uuid_list按照值进行排序后拼接成一个字符串
sorted_uuid_string = ''.join(sorted(uuid_list))

print(hashlib.sha256(sorted_uuid_string.encode('utf-8')).hexdigest())
 

# # 原始数据
# data = {"device_id": "aaaaaaaaaa","key":"123456"}
# data2 = {"key":"123456","device_id": "aaaaaaaaaa"}
# # 序列化为 JSON 字节
# json_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')

# json_bytes2 = json.dumps(data2, ensure_ascii=False).encode('utf-8')


# # 加密
# encrypted_data = cipher.encrypt(json_bytes)
# encrypted_data2 = cipher.encrypt(json_bytes)


# # 写入文件（纯二进制）
# with open("config.bin", "wb") as f:
#     f.write(encrypted_data)

# with open("config2.bin", "wb") as f:
#     f.write(encrypted_data2)

# # ---- 读取时 ----
# with open("config.bin", "rb") as f:
#     encrypted_data = f.read()

# decrypted_bytes = cipher.decrypt(encrypted_data)
# data = json.loads(decrypted_bytes.decode('utf-8'))
# print(data)