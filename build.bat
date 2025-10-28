@echo off
pyinstaller ^
  --onefile ^
  --windowed ^
  --name="VoiceFilter_Final" ^
  --add-data "models;models" ^
  --hidden-import=sklearn.utils._cython_blas ^
  --hidden-import=sklearn.neighbors.typedefs ^
  --hidden-import=sklearn.tree._utils ^
  --collect-all faster_whisper ^
  --exclude-module matplotlib ^
  main.py

echo.
echo ✅ 打包成功！模型已内置，无需联网。
echo 生成文件: dist\VoiceFilter_Final.exe
pause