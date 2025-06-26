"""
시험 시간표 배정 메인 애플리케이션
모든 모듈을 통합하여 시험 시간표를 생성합니다.
"""
from typing import Dict, List, Any, Tuple, Optional
import pandas as pd
from pathlib import Path

from config import ExamSchedulingConfig, DEFAULT_CONFIG
from data_loader import DataLoader
from scheduler import ExamScheduler


class ExamSchedulerApp:
    """시험 시간표 배정 메인 애플리케이션"""
    
    def __init__(self, config: Optional[ExamSchedulingConfig] = None, data_dir: str = "."):
        self.config = config or DEFAULT_CONFIG
        self.data_loader = DataLoader(data_dir)
        self.scheduler = ExamScheduler(self.config)
        
        # 데이터 저장소
        self.subject_info_dict = {}
        self.student_conflict_dict = {}
        self.listening_conflict_dict = {}
        self.teacher_conflict_dict = {}
        self.teacher_unavailable_dates = {}
        self.student_subjects = {}
        self.exam_info = {}
        self.enroll_bool = None
        self.student_names = []
        
    def load_all_data(self) -> bool:
        """
        모든 데이터를 로드합니다.
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 1. 수강 데이터 로드
            (self.student_conflict_dict, _, 
             self.student_names, self.enroll_bool) = self.data_loader.load_enrollment_data()
            
            # 2. 과목 정보 로드
            self.subject_info_dict = self.data_loader.load_subject_info()
            
            # 3. 시험 정보 로드
            self.exam_info = self.data_loader.load_exam_info()
            
            # 4. 교사 불가능 날짜 로드
            self.teacher_unavailable_dates = self.data_loader.load_teacher_unavailable()
            
            # 5. 충돌 딕셔너리 생성
            self.listening_conflict_dict, self.teacher_conflict_dict = (
                self.data_loader.generate_conflict_dicts(self.subject_info_dict)
            )
            
            # 6. 학생별 과목 매핑 생성
            self.student_subjects = {
                student: [subject for subject in self.subject_info_dict.keys() 
                         if self.enroll_bool.loc[student, subject]]
                for student in self.student_names if student in self.enroll_bool.index
            }
            
            return True
            
        except Exception as e:
            print(f"데이터 로드 중 오류 발생: {e}")
            return False
    
    def create_schedule(self, time_limit: int = 120) -> Tuple[str, Dict[str, Any]]:
        """
        시험 시간표를 생성합니다.
        
        Args:
            time_limit: 최대 풀이 시간(초)
            
        Returns:
            Tuple[str, Dict[str, Any]]: (상태, 결과)
        """
        try:
            # 1. 시험 슬롯 생성
            slots = self.scheduler.create_slots(self.exam_info['시험날짜'])
            slot_to_day, slot_to_period_limit = self.scheduler.create_slot_mappings(slots)
            
            # 2. 모델 구축
            self.scheduler.build_model(
                subject_info_dict=self.subject_info_dict,
                student_conflict_dict=self.student_conflict_dict,
                listening_conflict_dict=self.listening_conflict_dict,
                teacher_conflict_dict=self.teacher_conflict_dict,
                teacher_unavailable_dates=self.teacher_unavailable_dates,
                student_subjects=self.student_subjects,
                slots=slots,
                slot_to_day=slot_to_day,
                slot_to_period_limit=slot_to_period_limit
            )
            
            # 3. 목적함수 설정
            self.scheduler.set_objective(self.student_subjects, slots, slot_to_day)
            
            # 4. 모델 풀이
            status, result = self.scheduler.solve(time_limit)
            
            if status == "SUCCESS":
                # 5. 결과 분석
                result.update(self._analyze_results(slots, slot_to_day))
            
            return status, result
            
        except Exception as e:
            print(f"스케줄 생성 중 오류 발생: {e}")
            return "ERROR", {"error": str(e)}
    
    def _analyze_results(self, slots: List[str], slot_to_day: Dict[str, str]) -> Dict[str, Any]:
        """결과를 분석합니다."""
        if not hasattr(self.scheduler, 'solver') or self.scheduler.solver is None:
            return {}
        
        # 학생별 day별 시험수, 어려운 시험수 저장
        student_max_per_day = {}
        student_max_hard_per_day = {}
        student_exam_subjects_per_day = {}
        student_hard_exam_subjects_per_day = {}
        
        days = list(set(slot_to_day.values()))
        
        for student in self.student_subjects:
            exams_per_day = []
            hard_exams_per_day = []
            exam_subjects_per_day = []
            hard_exam_subjects_per_day = []
            
            for day in days:
                # 오늘 배정된 과목
                subjects_today = [
                    subject for subject in self.student_subjects[student]
                    for slot in slots
                    if slot_to_day[slot] == day and slot in self.scheduler.exam_slot_vars[subject]
                    and self.scheduler.solver.Value(self.scheduler.exam_slot_vars[subject][slot])
                ]
                exams_today = len(subjects_today)
                
                # 오늘 배정된 어려운 과목
                hard_subjects_today = [
                    subject for subject in self.student_subjects[student]
                    for slot in slots
                    if (
                        slot_to_day[slot] == day
                        and self.subject_info_dict[subject]['시간'] is not None
                        and self.subject_info_dict[subject]['시간'] >= self.config.hard_exam_threshold
                        and slot in self.scheduler.exam_slot_vars[subject]
                        and self.scheduler.solver.Value(self.scheduler.exam_slot_vars[subject][slot])
                    )
                ]
                hard_exams_today = len(hard_subjects_today)
                
                exams_per_day.append(exams_today)
                hard_exams_per_day.append(hard_exams_today)
                exam_subjects_per_day.append(subjects_today)
                hard_exam_subjects_per_day.append(hard_subjects_today)
            
            student_max_per_day[student] = max(exams_per_day)
            student_max_hard_per_day[student] = max(hard_exams_per_day)
            student_exam_subjects_per_day[student] = exam_subjects_per_day
            student_hard_exam_subjects_per_day[student] = hard_exam_subjects_per_day
        
        return {
            'student_analysis': {
                'max_exams_per_day': student_max_per_day,
                'max_hard_exams_per_day': student_max_hard_per_day,
                'exam_subjects_per_day': student_exam_subjects_per_day,
                'hard_exam_subjects_per_day': student_hard_exam_subjects_per_day
            },
            'days': days,
            'slots': slots
        }
    
    def get_summary(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """결과 요약을 생성합니다."""
        if 'student_analysis' not in result:
            return {}
        
        analysis = result['student_analysis']
        days = result.get('days', [])
        
        summary = {
            'total_students': len(self.student_subjects),
            'total_subjects': len(self.subject_info_dict),
            'total_slots': len(result.get('slots', [])),
            'exam_distribution': {},
            'hard_exam_distribution': {}
        }
        
        # 하루 시험 수 분포
        for num in range(1, self.config.max_exams_per_day + 1):
            students_with_num = [
                student for student in analysis['max_exams_per_day']
                if analysis['max_exams_per_day'][student] == num
            ]
            summary['exam_distribution'][num] = {
                'count': len(students_with_num),
                'students': students_with_num
            }
        
        # 하루 어려운 시험 수 분포
        for num in range(1, self.config.max_hard_exams_per_day + 1):
            students_with_num = [
                student for student in analysis['max_hard_exams_per_day']
                if analysis['max_hard_exams_per_day'][student] == num
            ]
            summary['hard_exam_distribution'][num] = {
                'count': len(students_with_num),
                'students': students_with_num
            }
        
        return summary
    
    def save_results(self, result: Dict[str, Any], output_dir: str = "."):
        """결과를 파일로 저장합니다."""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # JSON 파일로 저장
        import json
        with open(output_path / "schedule_result.json", 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        # 요약 정보 저장
        summary = self.get_summary(result)
        with open(output_path / "schedule_summary.json", 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    
    def print_results(self, result: Dict[str, Any]):
        """결과를 콘솔에 출력합니다."""
        if 'slot_assignments' not in result:
            print("결과가 없습니다.")
            return
        
        print("=== 시험 시간표 배정 결과 ===")
        for slot, subjects in result['slot_assignments'].items():
            print(f"{slot}: {', '.join(subjects)}")
        
        # 요약 정보 출력
        summary = self.get_summary(result)
        print(f"\n=== 요약 정보 ===")
        print(f"총 학생 수: {summary['total_students']}명")
        print(f"총 과목 수: {summary['total_subjects']}개")
        print(f"총 슬롯 수: {summary['total_slots']}개")
        
        print(f"\n=== 하루 시험 수 분포 ===")
        for num, info in summary['exam_distribution'].items():
            print(f"{num}과목: {info['count']}명")
        
        print(f"\n=== 하루 어려운 시험 수 분포 ===")
        for num, info in summary['hard_exam_distribution'].items():
            print(f"{num}과목: {info['count']}명")


def main():
    """메인 함수"""
    # 1. 애플리케이션 초기화
    app = ExamSchedulerApp()
    
    # 2. 데이터 로드
    print("데이터를 로드하는 중...")
    if not app.load_all_data():
        print("데이터 로드에 실패했습니다.")
        return
    
    print("데이터 로드 완료!")
    
    # 3. 시험 시간표 생성
    print("시험 시간표를 생성하는 중...")
    status, result = app.create_schedule(time_limit=120)
    
    if status == "SUCCESS":
        print("시험 시간표 생성 완료!")
        app.print_results(result)
        app.save_results(result)
    else:
        print(f"시험 시간표 생성 실패: {status}")
        if 'error' in result:
            print(f"오류: {result['error']}")


if __name__ == "__main__":
    main() 