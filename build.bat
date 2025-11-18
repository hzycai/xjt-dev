@echo off
:: 设置代码页为 UTF-8
chcp 65001 > nul
call C:\Users\Win11\anaconda3\Scripts\activate.bat venv

pyinstaller ^
  --onedir ^
  --windowed ^
  --name="VoiceFilter_Final" ^
  --add-data "model;model" ^
  --add-data "res;res" ^
  --add-data "config;config" ^
  --add-data "funasr;funasr" ^
  --hidden-import=sklearn.utils._cython_blas ^
  --hidden-import=sklearn.neighbors.typedefs ^
  --hidden-import=sklearn.tree._utils ^
  --collect-all faster_whisper ^
  --exclude-module matplotlib ^
  --exclude-module torch.utils.tensorboard ^ 
  run.py

echo.
echo ✅ 打包成功！模型已内置，无需联网。
echo 生成文件: dist\VoiceFilter_Final.exe
pause