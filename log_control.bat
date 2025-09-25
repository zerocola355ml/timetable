@echo off
REM 로깅 제어 배치 파일
REM Windows에서 터미널 디버깅 메시지를 제어할 수 있습니다.

if "%1"=="debug" (
    echo 디버그 모드 활성화
    set TIMETABLING_LOG_LEVEL=DEBUG
    python log_control.py --enable-debug
    goto :end
)

if "%1"=="info" (
    echo 정보 모드로 설정
    set TIMETABLING_LOG_LEVEL=INFO
    python log_control.py --level INFO
    goto :end
)

if "%1"=="warning" (
    echo 경고 모드로 설정
    set TIMETABLING_LOG_LEVEL=WARNING
    python log_control.py --level WARNING
    goto :end
)

if "%1"=="error" (
    echo 오류 모드로 설정
    set TIMETABLING_LOG_LEVEL=ERROR
    python log_control.py --level ERROR
    goto :end
)

if "%1"=="show" (
    echo 현재 로그 레벨 표시
    python log_control.py --show
    goto :end
)

if "%1"=="run-debug" (
    echo 디버그 모드로 애플리케이션 실행
    set TIMETABLING_LOG_LEVEL=DEBUG
    python exam_scheduler_app.py
    goto :end
)

if "%1"=="run-info" (
    echo 정보 모드로 애플리케이션 실행
    set TIMETABLING_LOG_LEVEL=INFO
    python exam_scheduler_app.py
    goto :end
)

if "%1"=="run-web-debug" (
    echo 디버그 모드로 웹 애플리케이션 실행
    set TIMETABLING_LOG_LEVEL=DEBUG
    python web_app.py
    goto :end
)

if "%1"=="run-web-info" (
    echo 정보 모드로 웹 애플리케이션 실행
    set TIMETABLING_LOG_LEVEL=INFO
    python web_app.py
    goto :end
)

echo 사용법:
echo   log_control.bat debug          - 디버그 모드 활성화
echo   log_control.bat info           - 정보 모드로 설정
echo   log_control.bat warning        - 경고 모드로 설정
echo   log_control.bat error          - 오류 모드로 설정
echo   log_control.bat show           - 현재 로그 레벨 표시
echo   log_control.bat run-debug      - 디버그 모드로 애플리케이션 실행
echo   log_control.bat run-info       - 정보 모드로 애플리케이션 실행
echo   log_control.bat run-web-debug  - 디버그 모드로 웹 애플리케이션 실행
echo   log_control.bat run-web-info   - 정보 모드로 웹 애플리케이션 실행

:end
