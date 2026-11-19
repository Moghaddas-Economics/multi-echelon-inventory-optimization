@echo off
cd /d "%~dp0"
call "C:\Users\asus\Desktop\lecturesinwinter\DSS_data decisin\project\.venv\Scripts\activate.bat"
python -m streamlit run app.py --theme.base dark
pause