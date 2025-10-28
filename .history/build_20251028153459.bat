@echo off
pyinstaller ^
  --onefile ^
  --windowed ^
  --name="VoiceFilter_Whisper" ^
  --add-data "sensitive_words.txt;sensitive_words.txt" ^
  --hidden-import=sklearn.utils._cython_blas ^
  --hidden-import=sklearn.neighbors.typedefs ^
  --hidden-import=sklearn.neighbors.quad_tree ^
  --hidden-import=sklearn.tree._utils ^
  --collect-all faster_whisper ^
  --exclude-module matplotlib ^
  main.py

echo.
echo 打包完成！首次运行会自动下载 Whisper 模型（需联网）
pause