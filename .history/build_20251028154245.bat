@echo off
pyinstaller ^
  --onefile ^
  --windowed ^
  --name="VoiceFilter_Final" ^
  --add-data "models;models" ^
  --add-data "sensitive_words.txt;." ^
  --hidden-import=sklearn.utils._cython_blas ^
  --hidden-import=sklearn.neighbors.typedefs ^
  --hidden-import=sklearn.tree._utils ^
  --collect-all faster-whisper ^
  --exclude-module matplotlib ^
  main.py

echo.
echo ✅ 打包完成！模型已内置，无需联网！
pause