"""
시험 시간표 배정 시스템 설정 관리
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class ExamSchedulingConfig:
    """시험 시간표 배정 설정"""
    
    # 기본 제약 조건
    max_exams_per_day: int = 3  # 학생별 하루 최대 시험 개수
    max_hard_exams_per_day: int = 2  # 학생별 하루 최대 어려운 시험 개수
    hard_exam_threshold: int = 60  # 어려운 시험 기준 시간(분)
    
    # 시간 제한 (교시별)
    period_limits: Optional[Dict[str, int]] = None  # 교시별 최대 시간 제한
    
    # 시험 일정 설정
    exam_days: int = 5  # 시험 일수
    periods_per_day: int = 3  # 하루 교시 수
    
    def __post_init__(self):
        if self.period_limits is None:
            self.period_limits = {
                '1교시': 80,
                '2교시': 50, 
                '3교시': 100
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 변환"""
        return {
            'max_exams_per_day': self.max_exams_per_day,
            'max_hard_exams_per_day': self.max_hard_exams_per_day,
            'hard_exam_threshold': self.hard_exam_threshold,
            'period_limits': self.period_limits,
            'exam_days': self.exam_days,
            'periods_per_day': self.periods_per_day
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExamSchedulingConfig':
        """딕셔너리에서 설정 객체 생성"""
        return cls(**data)


# 기본 설정 인스턴스
DEFAULT_CONFIG = ExamSchedulingConfig() 