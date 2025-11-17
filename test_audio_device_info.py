import pyaudio

def is_device_compatible(device_index, rate=16000, channels=1, chunk=960):
    p = pyaudio.PyAudio()
    
    try:
        # 获取设备信息
        device_info = p.get_device_info_by_index(device_index)
        max_input_channels = device_info['maxInputChannels']

        print(max_input_channels)
        supported_rates = []

        # 检查通道数是否满足
        if max_input_channels < channels:
            print(f"Device {device_index} only supports {max_input_channels} input channel(s).")
            return False

        # 尝试测试采样率是否被支持（PyAudio 不直接列出所有支持的采样率）
        # 所以我们尝试打开一个流来验证
        try:
            test_stream = p.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=chunk
            )
            test_stream.close()
            print(f"Device {device_index} supports rate={rate}, channels={channels}, chunk={chunk}")
            return True
        except Exception as e:
            print(f"Device {device_index} does NOT support rate={rate}: {e}")
            return False

    finally:
        p.terminate()

is_device_compatible(1,rate=166200,channels=2)