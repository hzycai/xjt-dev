import cv2
import time

def get_camera_fps(camera_index=0, warmup_frames=30, test_frames=120):
    """
    获取指定摄像头的实际帧率 (FPS)。

    :param camera_index: 摄像头索引，默认为 0 (通常代表默认摄像头)。
    :param warmup_frames: 启动摄像头后丢弃的初始帧数，用于让摄像头适应环境光等。
    :param test_frames: 用于计算 FPS 的帧数。
    :return: 计算出的平均 FPS (浮点数)，如果失败则返回 None。
    """
    # 打开摄像头
    cap = cv2.VideoCapture(camera_index)

    # 检查摄像头是否成功打开
    if not cap.isOpened():
        print(f"错误：无法打开摄像头 {camera_index}")
        return None

    print(f"正在测试摄像头 {camera_index} 的帧率...")
    print("预热中...")

    # --- 预热阶段 ---
    # 读取并丢弃前 warmup_frames 帧，让摄像头初始化稳定
    for i in range(warmup_frames):
        ret, frame = cap.read()
        if not ret:
            print(f"警告：预热阶段读取第 {i+1} 帧失败。")
            cap.release()
            return None
        # 可选：在此处添加小延时，避免 CPU 占用过高（如果需要）
        # time.sleep(0.01) 

    print("开始计时计算 FPS...")

    # --- 测试阶段 ---
    start_time = time.time()  # 记录开始时间

    frames_captured = 0
    first_frame_saved = False
    while frames_captured < test_frames:
        ret, frame = cap.read()
        if not ret:
            print(f"错误：测试阶段读取第 {frames_captured + 1} 帧失败。")
            break  # 如果读取失败，则提前结束循环

        # --- 在此处可以对帧进行处理 ---
        # 例如：显示画面、保存图像、进行图像识别等
        # 注意：任何处理都会影响最终测得的 FPS
        # 显示画面会显著降低 FPS 并增加延迟
        # cv2.imshow('Camera Feed', frame)
        # if cv2.waitKey(1) & 0xFF == ord('q'): # 按 'q' 键退出 (如果显示画面)
        #     break
        
        # 保存第一帧到当前目录
        if not first_frame_saved:
            cv2.imwrite('first_frame.jpg', frame)
            print("第一帧已保存为 first_frame.jpg")
            first_frame_saved = True

        frames_captured += 1

    end_time = time.time()  # 记录结束时间

    # --- 清理资源 ---
    cap.release()
    # cv2.destroyAllWindows() # 如果之前调用了 cv2.imshow()

    # --- 计算并输出结果 ---
    elapsed_time = end_time - start_time
    if elapsed_time > 0 and frames_captured > 0:
        measured_fps = frames_captured / elapsed_time
        print(f"\n测试完成！")
        print(f"捕获帧数: {frames_captured}")
        print(f"耗时: {elapsed_time:.4f} 秒")
        print(f"计算得出的实际平均帧率: {measured_fps:.2f} FPS")
        return measured_fps
    else:
        print("\n错误：测试过程中出现问题，无法计算 FPS。")
        return None

# --- 主程序入口 ---
if __name__ == "__main__":
    # 调用函数测试默认摄像头 (索引 0)
    fps = get_camera_fps(camera_index=0, warmup_frames=30, test_frames=120)
    
    # 如果你想测试其他摄像头或调整参数，可以修改下面这行：
    # fps = get_camera_fps(camera_index=1, warmup_frames=20, test_frames=100)

    if fps is not None:
        print(f"\n最终结果：摄像头的实测平均帧率为 {fps:.2f} FPS。")
    else:
        print("\n未能成功测量摄像头帧率。")