#!/usr/bin/env python3
"""
로깅 제어 스크립트
환경변수를 통해 터미널 디버깅 메시지를 제어할 수 있습니다.
"""
import os
import sys
import argparse
from logger_config import setup_logging, set_log_level, enable_debug_mode, disable_debug_mode, is_debug_enabled


def set_environment_log_level(level: str):
    """환경변수로 로그 레벨을 설정합니다."""
    os.environ['TIMETABLING_LOG_LEVEL'] = level.upper()
    print(f"환경변수 TIMETABLING_LOG_LEVEL을 {level.upper()}로 설정했습니다.")


def show_current_log_level():
    """현재 로그 레벨을 표시합니다."""
    current_level = os.getenv('TIMETABLING_LOG_LEVEL', 'INFO')
    print(f"현재 로그 레벨: {current_level}")
    
    # 로깅 시스템 초기화 후 실제 설정 확인
    setup_logging()
    if is_debug_enabled():
        print("디버그 모드: 활성화")
    else:
        print("디버그 모드: 비활성화")


def run_with_log_level(level: str, command: str):
    """지정된 로그 레벨로 명령을 실행합니다."""
    set_environment_log_level(level)
    
    print(f"로그 레벨 {level.upper()}로 실행: {command}")
    
    # 환경변수 설정 후 명령 실행
    import subprocess
    result = subprocess.run(command, shell=True, env=os.environ.copy())
    return result.returncode


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='터미널 디버깅 메시지 제어 도구',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python log_control.py --level DEBUG                    # 디버그 모드 활성화
  python log_control.py --level INFO                     # 정보 모드로 설정
  python log_control.py --level WARNING                  # 경고 모드로 설정
  python log_control.py --level ERROR                    # 오류 모드로 설정
  python log_control.py --show                           # 현재 로그 레벨 표시
  python log_control.py --run "python exam_scheduler_app.py" --level DEBUG  # 디버그 모드로 실행
  python log_control.py --enable-debug                   # 디버그 모드 활성화
  python log_control.py --disable-debug                  # 디버그 모드 비활성화

환경변수:
  TIMETABLING_LOG_LEVEL: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  TIMETABLING_LOG_FILE: 파일 로깅 활성화 (true/false)
  TIMETABLING_LOG_FILE_PATH: 로그 파일 경로
        """
    )
    
    parser.add_argument('--level', '-l', 
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                       help='로그 레벨 설정')
    
    parser.add_argument('--show', '-s', 
                       action='store_true',
                       help='현재 로그 레벨 표시')
    
    parser.add_argument('--run', '-r',
                       help='지정된 로그 레벨로 명령 실행')
    
    parser.add_argument('--enable-debug', '-d',
                       action='store_true',
                       help='디버그 모드 활성화')
    
    parser.add_argument('--disable-debug',
                       action='store_true',
                       help='디버그 모드 비활성화')
    
    parser.add_argument('--file-logging',
                       choices=['true', 'false'],
                       help='파일 로깅 활성화/비활성화')
    
    parser.add_argument('--log-file',
                       help='로그 파일 경로 설정')
    
    args = parser.parse_args()
    
    # 로깅 시스템 초기화
    setup_logging()
    
    if args.show:
        show_current_log_level()
        return 0
    
    if args.level:
        set_environment_log_level(args.level)
        set_log_level(args.level)
        print(f"로그 레벨이 {args.level}로 설정되었습니다.")
    
    if args.enable_debug:
        set_environment_log_level('DEBUG')
        enable_debug_mode()
        print("디버그 모드가 활성화되었습니다.")
    
    if args.disable_debug:
        set_environment_log_level('INFO')
        disable_debug_mode()
        print("디버그 모드가 비활성화되었습니다.")
    
    if args.file_logging:
        os.environ['TIMETABLING_LOG_FILE'] = args.file_logging
        print(f"파일 로깅이 {args.file_logging}로 설정되었습니다.")
    
    if args.log_file:
        os.environ['TIMETABLING_LOG_FILE_PATH'] = args.log_file
        print(f"로그 파일 경로가 {args.log_file}로 설정되었습니다.")
    
    if args.run:
        if not args.level:
            print("--run 옵션을 사용할 때는 --level 옵션도 함께 지정해야 합니다.")
            return 1
        
        return run_with_log_level(args.level, args.run)
    
    # 설정된 환경변수 표시
    print("\n현재 환경변수 설정:")
    print(f"TIMETABLING_LOG_LEVEL: {os.getenv('TIMETABLING_LOG_LEVEL', 'INFO')}")
    print(f"TIMETABLING_LOG_FILE: {os.getenv('TIMETABLING_LOG_FILE', 'false')}")
    print(f"TIMETABLING_LOG_FILE_PATH: {os.getenv('TIMETABLING_LOG_FILE_PATH', 'timetabling.log')}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
