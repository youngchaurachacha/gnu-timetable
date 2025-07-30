@echo off
REM 이 스크립트는 반드시 프로젝트 최상위 폴더(run_app.bat 파일이 있는 위치)에서 실행해야 합니다.
call .\venv\Scripts\activate.bat
streamlit run app.py