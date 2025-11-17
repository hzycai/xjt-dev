import requests
import traceback


def download(url, file_path):
    """
    下载文件根据url下载文件，保存路径为file_path
    """
    try:
        # Send GET request to download the file
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Write content to file in chunks to handle large files
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print(f"文件下载成功: {file_path}")
    except requests.RequestException as e:
        print(f"下载请求失败: {e}")
        raise
    except IOError as e:
        print(f"文件写入失败: {e}")
        raise
    except Exception as e:
        print(f"下载过程中发生未知错误: {e}")
        raise


def download_file(url, file_path):
    print(f"开始下载文件：{url}")

    try:
        download(url, file_path)
        return True
    except Exception as e:
        print(f"下载失败,{e}")
        traceback.print_exc()
        return False