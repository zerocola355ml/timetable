"""
로깅 설정 모듈
터미널 디버깅 메시지를 제어할 수 있는 로깅 시스템을 제공합니다.
"""
import logging
import os
import sys
from typing import Optional


class LoggerConfig:
    """로깅 설정을 관리하는 클래스"""
    
    # 로그 레벨 매핑
    LOG_LEVELS = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    def __init__(self, 
                 log_level: str = 'INFO',
                 log_format: Optional[str] = None,
                 enable_file_logging: bool = False,
                 log_file_path: Optional[str] = None):
        """
        로거 설정을 초기화합니다.
        
        Args:
            log_level: 로그 레벨 ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
            log_format: 로그 포맷 문자열
            enable_file_logging: 파일 로깅 활성화 여부
            log_file_path: 로그 파일 경로
        """
        self.log_level = log_level.upper()
        self.log_format = log_format or '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        self.enable_file_logging = enable_file_logging
        self.log_file_path = log_file_path or 'timetabling.log'
        
        # 환경변수에서 로그 레벨 읽기
        env_log_level = os.getenv('TIMETABLING_LOG_LEVEL', '').upper()
        if env_log_level in self.LOG_LEVELS:
            self.log_level = env_log_level
        
        self._setup_logging()
    
    def _setup_logging(self):
        """로깅 시스템을 설정합니다."""
        # 루트 로거 설정
        root_logger = logging.getLogger()
        root_logger.setLevel(self.LOG_LEVELS[self.log_level])
        
        # 기존 핸들러 제거
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 콘솔 핸들러 설정
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.LOG_LEVELS[self.log_level])
        
        # 포맷터 설정
        formatter = logging.Formatter(self.log_format)
        console_handler.setFormatter(formatter)
        
        # 핸들러 추가
        root_logger.addHandler(console_handler)
        
        # 파일 로깅 설정 (선택사항)
        if self.enable_file_logging:
            file_handler = logging.FileHandler(self.log_file_path, encoding='utf-8')
            file_handler.setLevel(self.LOG_LEVELS[self.log_level])
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        지정된 이름의 로거를 반환합니다.
        
        Args:
            name: 로거 이름
            
        Returns:
            logging.Logger: 설정된 로거
        """
        return logging.getLogger(name)
    
    def set_log_level(self, level: str):
        """
        로그 레벨을 동적으로 변경합니다.
        
        Args:
            level: 새로운 로그 레벨
        """
        if level.upper() in self.LOG_LEVELS:
            self.log_level = level.upper()
            logging.getLogger().setLevel(self.LOG_LEVELS[self.log_level])
            
            # 모든 핸들러의 레벨도 업데이트
            for handler in logging.getLogger().handlers:
                handler.setLevel(self.LOG_LEVELS[self.log_level])
        else:
            raise ValueError(f"Invalid log level: {level}")
    
    def enable_debug_mode(self):
        """디버그 모드를 활성화합니다."""
        self.set_log_level('DEBUG')
    
    def disable_debug_mode(self):
        """디버그 모드를 비활성화합니다."""
        self.set_log_level('INFO')
    
    def is_debug_enabled(self) -> bool:
        """디버그 모드가 활성화되어 있는지 확인합니다."""
        return self.log_level == 'DEBUG'


# 전역 로거 설정 인스턴스
_logger_config = None


def setup_logging(log_level: str = 'INFO', 
                  enable_file_logging: bool = False,
                  log_file_path: Optional[str] = None) -> LoggerConfig:
    """
    전역 로깅 시스템을 설정합니다.
    
    Args:
        log_level: 로그 레벨
        enable_file_logging: 파일 로깅 활성화 여부
        log_file_path: 로그 파일 경로
        
    Returns:
        LoggerConfig: 설정된 로거 설정 객체
    """
    global _logger_config
    _logger_config = LoggerConfig(
        log_level=log_level,
        enable_file_logging=enable_file_logging,
        log_file_path=log_file_path
    )
    return _logger_config


def get_logger(name: str) -> logging.Logger:
    """
    지정된 이름의 로거를 반환합니다.
    
    Args:
        name: 로거 이름
        
    Returns:
        logging.Logger: 로거
    """
    if _logger_config is None:
        # 기본 설정으로 초기화
        setup_logging()
    
    return _logger_config.get_logger(name)


def set_log_level(level: str):
    """
    전역 로그 레벨을 설정합니다.
    
    Args:
        level: 로그 레벨
    """
    if _logger_config is None:
        setup_logging()
    
    _logger_config.set_log_level(level)


def enable_debug_mode():
    """디버그 모드를 활성화합니다."""
    if _logger_config is None:
        setup_logging()
    
    _logger_config.enable_debug_mode()


def disable_debug_mode():
    """디버그 모드를 비활성화합니다."""
    if _logger_config is None:
        setup_logging()
    
    _logger_config.disable_debug_mode()


def is_debug_enabled() -> bool:
    """디버그 모드가 활성화되어 있는지 확인합니다."""
    if _logger_config is None:
        return False
    
    return _logger_config.is_debug_enabled()


# 편의 함수들
def debug(message: str, logger_name: str = 'timetabling'):
    """디버그 메시지를 출력합니다."""
    logger = get_logger(logger_name)
    logger.debug(message)


def info(message: str, logger_name: str = 'timetabling'):
    """정보 메시지를 출력합니다."""
    logger = get_logger(logger_name)
    logger.info(message)


def warning(message: str, logger_name: str = 'timetabling'):
    """경고 메시지를 출력합니다."""
    logger = get_logger(logger_name)
    logger.warning(message)


def error(message: str, logger_name: str = 'timetabling'):
    """오류 메시지를 출력합니다."""
    logger = get_logger(logger_name)
    logger.error(message)


def critical(message: str, logger_name: str = 'timetabling'):
    """치명적 오류 메시지를 출력합니다."""
    logger = get_logger(logger_name)
    logger.critical(message)


# 환경변수 기반 자동 설정
def auto_setup_from_env():
    """환경변수를 기반으로 자동으로 로깅을 설정합니다."""
    log_level = os.getenv('TIMETABLING_LOG_LEVEL', 'INFO')
    enable_file = os.getenv('TIMETABLING_LOG_FILE', 'false').lower() == 'true'
    log_file = os.getenv('TIMETABLING_LOG_FILE_PATH', 'timetabling.log')
    
    return setup_logging(
        log_level=log_level,
        enable_file_logging=enable_file,
        log_file_path=log_file
    )


if __name__ == "__main__":
    # 테스트 코드
    self.logger.debug("로깅 시스템 테스트")
    
    # 기본 설정
    setup_logging('DEBUG')
    
    # 테스트 로거 생성
    test_logger = get_logger('test')
    
    # 각 레벨별 메시지 출력
    test_logger.debug("이것은 디버그 메시지입니다")
    test_logger.info("이것은 정보 메시지입니다")
    test_logger.warning("이것은 경고 메시지입니다")
    test_logger.error("이것은 오류 메시지입니다")
    
    self.logger.debug("\n로그 레벨을 INFO로 변경")
    set_log_level('INFO')
    
    test_logger.debug("이 디버그 메시지는 보이지 않습니다")
    test_logger.info("이 정보 메시지는 보입니다")
    
    self.logger.debug("\n디버그 모드 활성화")
    enable_debug_mode()
    
    test_logger.debug("이제 디버그 메시지가 보입니다")
