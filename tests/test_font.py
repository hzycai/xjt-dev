import tkinter as tk
from tkinter import font as tkFont

# 必须先创建 root（即使不显示）
root = tk.Tk()
root.withdraw()  # 隐藏窗口（可选）

# 现在可以安全调用 families()
fonts = tkFont.families()
print("Available fonts:")
for f in sorted(fonts):
        print(f)

# 可选：关闭 root（但不要 destroy 如果后面还要用 Tk）
# root.destroy()