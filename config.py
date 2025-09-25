"""
시험 시간표 배정 시스템 설정 관리
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import os


@dataclass
class ExamInfoConfig:
    """시험 정보 기본 설정"""
    
    # 교시별 기본 시작 시간
    default_start_times: Dict[int, str] = None
    
    # 기본 교시 지속 시간 (분)
    default_duration: int = 50
    
    # 기본 쉬는 시간 (분)
    default_break_time: int = 10
    
    # 기본 교시 수
    default_periods: int = 4
    
    # 기본 날짜 라벨
    default_day_labels: Dict[int, str] = None
    
    def __post_init__(self):
        if self.default_start_times is None:
            self.default_start_times = {
                1: '08:30',  # 1교시: 8:30
                2: '09:30',  # 2교시: 9:30
                3: '10:30',  # 3교시: 10:30
                4: '11:30'   # 4교시: 11:30
            }
        
        if self.default_day_labels is None:
            self.default_day_labels = {
                1: '제1일',
                2: '제2일',
                3: '제3일',
                4: '제4일',
                5: '제5일'
            }
    
    def get_start_time(self, period: int) -> str:
        """특정 교시의 시작 시간 반환"""
        return self.default_start_times.get(period, '09:00')
    
    def get_day_label(self, day: int) -> str:
        """특정 날짜의 라벨 반환"""
        return self.default_day_labels.get(day, f'제{day}일')
    
    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 변환"""
        return {
            'default_start_times': self.default_start_times,
            'default_duration': self.default_duration,
            'default_break_time': self.default_break_time,
            'default_periods': self.default_periods,
            'default_day_labels': self.default_day_labels
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExamInfoConfig':
        """딕셔너리에서 설정 객체 생성"""
        return cls(**data)


@dataclass
class ExamSchedulingConfig:
    """시험 시간표 배정 설정"""
    
    # 기본 제약 조건
    max_exams_per_day: Optional[int] = None  # 학생별 하루 최대 시험 개수 (None은 제한 없음)
    max_hard_exams_per_day: Optional[int] = None  # 학생별 하루 최대 어려운 시험 개수 (None은 제한 없음)
    
    # 시간 제한 (교시별)
    period_limits: Optional[Dict[str, int]] = None  # 교시별 최대 시간 제한
    
    # 시험 일정 설정
    exam_days: int = 5  # 시험 일수
    periods_per_day: int = 4  # 하루 교시 수
    
    def __post_init__(self):
        if self.period_limits is None:
            self.period_limits = {
                '1교시': 50,
                '2교시': 50, 
                '3교시': 50,
                '4교시': 50
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 변환"""
        return {
            'max_exams_per_day': self.max_exams_per_day,
            'max_hard_exams_per_day': self.max_hard_exams_per_day,
            'period_limits': self.period_limits,
            'exam_days': self.exam_days,
            'periods_per_day': self.periods_per_day
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExamSchedulingConfig':
        """딕셔너리에서 설정 객체 생성"""
        return cls(**data)


# 기본 설정 인스턴스들
DEFAULT_EXAM_INFO_CONFIG = ExamInfoConfig()
DEFAULT_SCHEDULING_CONFIG = ExamSchedulingConfig()

# 전체 기본 설정
DEFAULT_CONFIG = {
    'exam_info': DEFAULT_EXAM_INFO_CONFIG.to_dict(),
    'scheduling': DEFAULT_SCHEDULING_CONFIG.to_dict()
}

@dataclass
class LoggingConfig:
    """로깅 설정"""
    
    # 로그 레벨 설정
    log_level: str = 'INFO'  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    
    # 파일 로깅 설정
    enable_file_logging: bool = False
    log_file_path: str = 'timetabling.log'
    
    # 로그 포맷
    log_format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 환경변수에서 설정 읽기
    def __post_init__(self):
        # 환경변수에서 로그 레벨 읽기
        env_log_level = os.getenv('TIMETABLING_LOG_LEVEL', '').upper()
        if env_log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            self.log_level = env_log_level
        
        # 환경변수에서 파일 로깅 설정 읽기
        env_file_logging = os.getenv('TIMETABLING_LOG_FILE', '').lower()
        if env_file_logging in ['true', '1', 'yes']:
            self.enable_file_logging = True
        
        # 환경변수에서 로그 파일 경로 읽기
        env_log_file = os.getenv('TIMETABLING_LOG_FILE_PATH', '')
        if env_log_file:
            self.log_file_path = env_log_file
    
    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 변환"""
        return {
            'log_level': self.log_level,
            'enable_file_logging': self.enable_file_logging,
            'log_file_path': self.log_file_path,
            'log_format': self.log_format
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LoggingConfig':
        """딕셔너리에서 설정 객체 생성"""
        return cls(**data)


@dataclass
class SystemConfig:
    """시스템 전반 설정"""
    
    # 애플리케이션 설정
    app_name: str = "시험 시간표 배정 시스템"
    app_version: str = "1.0.0"
    
    # 파일 업로드 설정
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: List[str] = None
    
    # 데이터베이스/파일 설정
    data_retention_days: int = 365  # 데이터 보관 기간 (일)
    backup_enabled: bool = True
    backup_interval_hours: int = 24
    
    def __post_init__(self):
        if self.allowed_extensions is None:
            self.allowed_extensions = ['xlsx', 'xls', 'json']
    
    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 변환"""
        return {
            'app_name': self.app_name,
            'app_version': self.app_version,
            'max_file_size': self.max_file_size,
            'allowed_extensions': self.allowed_extensions,
            'data_retention_days': self.data_retention_days,
            'backup_enabled': self.backup_enabled,
            'backup_interval_hours': self.backup_interval_hours
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemConfig':
        """딕셔너리에서 설정 객체 생성"""
        return cls(**data)

# 로깅 설정 인스턴스
DEFAULT_LOGGING_CONFIG = LoggingConfig()

# 시스템 설정 인스턴스
DEFAULT_SYSTEM_CONFIG = SystemConfig()

# 업데이트된 전체 기본 설정
DEFAULT_CONFIG = {
    'exam_info': DEFAULT_EXAM_INFO_CONFIG.to_dict(),
    'scheduling': DEFAULT_SCHEDULING_CONFIG.to_dict(),
    'system': DEFAULT_SYSTEM_CONFIG.to_dict(),
    'logging': DEFAULT_LOGGING_CONFIG.to_dict()
} 