"""
시험 시간표 배정 메인 애플리케이션
모든 모듈을 통합하여 시험 시간표를 생성합니다.
"""
from typing import Dict, List, Any, Tuple, Optional
import pandas as pd
import os
import json
from pathlib import Path

from config import ExamSchedulingConfig, DEFAULT_CONFIG
from data_loader import DataLoader
from scheduler import ExamScheduler


class ExamSchedulerApp:
    """시험 시간표 배정 메인 애플리케이션"""
    
    def __init__(self, config: Optional[ExamSchedulingConfig] = None, data_dir: str = "."):
        self.config = config or DEFAULT_CONFIG
        self.data_dir = data_dir  # data_dir을 인스턴스 변수로 저장
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
        self.subject_constraints = {}  # 추가: 과목별 제약조건
        self.teacher_slot_constraints = {}  # 추가: 교사 슬롯별 제약조건
        self.subject_conflicts = {}  # 추가: 과목 충돌 제약조건
        self.enroll_bool = None
        self.student_names = []
        
    def load_all_data(self) -> bool:
        """
        모든 데이터를 로드합니다.
        
        Returns:
            bool: 성공 여부
        """
        try:
            # 1. 기본 수강 데이터 로드 (학생 명단, 수강 정보)
            try:
                (_, double_enroll_dict, 
                 self.student_names, self.enroll_bool) = self.data_loader.load_enrollment_data()
            except Exception as e:
                print(f"DEBUG: Failed to load enrollment data, continuing without it: {e}")
                self.student_names = []
                self.enroll_bool = None
            
            # 2. 과목 정보 로드 (커스텀 편집 반영)
            self.subject_info_dict = self.data_loader.load_custom_subject_info()
            
            # 3. 시험 정보 로드 (최신 커스텀 병합 반영)
            self.exam_info = self.data_loader.load_exam_info_with_custom()
            print(f"DEBUG: Loaded exam_info date_periods keys: {list(self.exam_info.get('date_periods', {}).keys())}")
            for day, periods in self.exam_info.get('date_periods', {}).items():
                active_periods = [p for p, pdata in periods.items() if not (isinstance(pdata, dict) and pdata.get('_deleted'))]
                deleted_periods = [p for p, pdata in periods.items() if isinstance(pdata, dict) and pdata.get('_deleted')]
                print(f"DEBUG: Day {day}: active={active_periods}, deleted={deleted_periods}")
            
            # 4. 교사 불가능 날짜 로드 (커스텀 편집 반영)
            self.teacher_unavailable_dates = self.data_loader.load_teacher_unavailable_with_custom()
            
            # 5. 학생 충돌 데이터 로드 (우선순위: individual -> same_grade -> enrollment_based)
            self.student_conflict_dict = self._load_student_conflicts_with_priority()
            
            # 6. 기타 커스텀 충돌 데이터 로드 (듣기평가, 교사 충돌)
            _, self.listening_conflict_dict, self.teacher_conflict_dict = (
                self.data_loader.load_custom_conflicts()
            )
            
            # 7. 과목별 제약조건 로드
            self.subject_constraints = self._load_subject_constraints()
            
            # 8. 교사 슬롯별 제약조건 로드
            self.teacher_slot_constraints = self._load_teacher_slot_constraints()
            
            # 9. 과목 충돌 제약조건 로드
            self.subject_conflicts = self._load_subject_conflicts()
            
            # 10. 학생별 과목 매핑 생성
            if self.enroll_bool is not None and len(self.student_names) > 0:
                self.student_subjects = {
                    student: [subject for subject in self.subject_info_dict.keys() 
                             if self.enroll_bool.loc[student, subject]]
                    for student in self.student_names if student in self.enroll_bool.index
                }
            else:
                print("DEBUG: No enrollment data available, creating empty student subjects")
                self.student_subjects = {}
            
            return True
            
        except Exception as e:
            print(f"데이터 로드 중 오류 발생: {e}")
            return False
    
    def _load_subject_constraints(self) -> Dict[str, Dict[str, Any]]:
        """과목별 제약조건을 로드합니다."""
        try:
            constraints_file = os.path.join(self.data_dir, 'subject_constraints.json')
            if os.path.exists(constraints_file):
                with open(constraints_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
            return {}
        except Exception as e:
            print(f"과목별 제약조건 로드 중 오류 발생: {e}")
            return {}
    
    def _load_teacher_slot_constraints(self) -> Dict[str, Dict[str, Any]]:
        """교사 슬롯별 제약조건을 로드합니다."""
        try:
            constraints_file = os.path.join(self.data_dir, 'custom_teacher_constraints.json')
            if os.path.exists(constraints_file):
                with open(constraints_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
            return {}
        except Exception as e:
            print(f"교사 슬롯별 제약조건 로드 중 오류 발생: {e}")
            return {}
    
    def _load_subject_conflicts(self) -> Dict[str, Dict[str, Any]]:
        """과목 충돌 제약조건을 로드합니다."""
        try:
            conflicts_file = os.path.join(self.data_dir, 'subject_conflicts.json')
            if os.path.exists(conflicts_file):
                with open(conflicts_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
            return {}
        except Exception as e:
            print(f"과목 충돌 제약조건 로드 중 오류 발생: {e}")
            return {}
    
    def _load_student_conflicts_with_priority(self) -> Dict[str, List[str]]:
        """
        우선순위에 따라 학생 충돌 데이터를 로드합니다.
        1순위: individual_conflicts.json
        2순위: same_grade_conflicts.json  
        3순위: enrollment 기반 student_conflict_dict (기존 방식)
        """
        print("DEBUG: Loading student conflicts with priority logic...")
        
        # 1순위: individual_conflicts.json
        individual_conflicts = self._load_json_file('individual_conflicts.json')
        if individual_conflicts:
            print(f"DEBUG: Using individual_conflicts.json ({len(individual_conflicts)} conflicts)")
            return self._convert_individual_to_conflict_dict(individual_conflicts)
        
        # 2순위: same_grade_conflicts.json
        same_grade_conflicts = self._load_json_file('same_grade_conflicts.json')
        if same_grade_conflicts:
            print(f"DEBUG: Using same_grade_conflicts.json ({len(same_grade_conflicts)} conflicts)")
            return self._convert_same_grade_to_conflict_dict(same_grade_conflicts)
        
        # 3순위: enrollment 기반 (기존 방식)
        try:
            enrollment_conflicts, _, _, _ = self.data_loader.load_enrollment_data()
            if enrollment_conflicts:
                print(f"DEBUG: Using enrollment-based conflicts ({len(enrollment_conflicts)} subjects)")
                return enrollment_conflicts
            else:
                print("DEBUG: Enrollment conflicts is None or empty")
                return {}
        except Exception as e:
            print(f"DEBUG: Failed to load enrollment data: {e}")
            return {}
    
    def _load_json_file(self, filename: str) -> list:
        """JSON 파일을 로드하고 유효성을 검사합니다."""
        try:
            file_path = os.path.join(self.data_dir, filename)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        if isinstance(data, list) and len(data) > 0:
                            return data
            return []
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return []
    
    def _convert_individual_to_conflict_dict(self, individual_conflicts: list) -> Dict[str, List[str]]:
        """individual_conflicts.json 형식을 student_conflict_dict 형식으로 변환합니다."""
        conflict_dict = {}
        
        for conflict in individual_conflicts:
            subject1 = conflict.get('subject1')
            subject2 = conflict.get('subject2')
            
            if subject1 and subject2:
                # 양방향 충돌 관계 설정
                if subject1 not in conflict_dict:
                    conflict_dict[subject1] = []
                if subject2 not in conflict_dict:
                    conflict_dict[subject2] = []
                
                if subject2 not in conflict_dict[subject1]:
                    conflict_dict[subject1].append(subject2)
                if subject1 not in conflict_dict[subject2]:
                    conflict_dict[subject2].append(subject1)
        
        print(f"DEBUG: Converted individual_conflicts to conflict_dict with {len(conflict_dict)} subjects")
        return conflict_dict
    
    def _convert_same_grade_to_conflict_dict(self, same_grade_conflicts: list) -> Dict[str, List[str]]:
        """same_grade_conflicts.json 형식을 student_conflict_dict 형식으로 변환합니다."""
        conflict_dict = {}
        
        for conflict in same_grade_conflicts:
            subject1 = conflict.get('subject1')
            subject2 = conflict.get('subject2')
            
            if subject1 and subject2:
                # 양방향 충돌 관계 설정
                if subject1 not in conflict_dict:
                    conflict_dict[subject1] = []
                if subject2 not in conflict_dict:
                    conflict_dict[subject2] = []
                
                if subject2 not in conflict_dict[subject1]:
                    conflict_dict[subject1].append(subject2)
                if subject1 not in conflict_dict[subject2]:
                    conflict_dict[subject2].append(subject1)
        
        print(f"DEBUG: Converted same_grade_conflicts to conflict_dict with {len(conflict_dict)} subjects")
        return conflict_dict
    
    def create_schedule(self, time_limit: int = 120, status_callback=None) -> Tuple[str, Dict[str, Any]]:
        """
        시험 시간표를 생성합니다.
        
        Args:
            time_limit: 최대 풀이 시간(초)
            status_callback: 상태 업데이트 콜백 함수
            
        Returns:
            Tuple[str, Dict[str, Any]]: (상태, 결과)
        """
        try:
            print(f"DEBUG: Starting schedule creation with time_limit={time_limit}")
            print(f"DEBUG: exam_info keys: {list(self.exam_info.keys())}")
            
            # 1. 시험 슬롯 생성: /exam-info 편집 결과를 그대로 사용
            if status_callback:
                status_callback("시험 슬롯을 생성하고 있습니다...", 50)
                
            print("DEBUG: Creating exam slots...")
            try:
                slots = self.scheduler.create_slots(self.exam_info)
                print(f"DEBUG: Created {len(slots)} slots: {slots}")
                
                if not slots:
                    print("ERROR: No slots created!")
                    return "ERROR", {"error": "시험 슬롯이 생성되지 않았습니다. 시험 정보를 확인해주세요."}
            except ValueError as e:
                print(f"ERROR: Slot creation failed: {e}")
                return "ERROR", {"error": str(e)}
            
            print("DEBUG: Creating slot mappings...")
            try:
                slot_to_day, slot_to_period_limit = self.scheduler.create_slot_mappings(slots, self.exam_info)
            except ValueError as e:
                print(f"ERROR: Slot mapping failed: {e}")
                return "ERROR", {"error": str(e)}
            print(f"DEBUG: slot_to_day: {slot_to_day}")
            print(f"DEBUG: slot_to_period_limit: {slot_to_period_limit}")
            
            # 2. 모델 구축
            if status_callback:
                status_callback("최적화 모델을 구축하고 있습니다...", 60)
                
            print("DEBUG: Building optimization model...")
            # 어려운 과목 설정 로드
            hard_subjects = self._load_hard_subjects_config()
            print(f"DEBUG: Loaded hard_subjects: {hard_subjects}")
            print(f"DEBUG: Config max_hard_exams_per_day: {self.config.max_hard_exams_per_day}")
            
            self.scheduler.build_model(
                subject_info_dict=self.subject_info_dict,
                student_conflict_dict=self.student_conflict_dict,
                listening_conflict_dict=self.listening_conflict_dict,
                teacher_conflict_dict=self.teacher_conflict_dict,
                teacher_unavailable_dates=self.teacher_unavailable_dates,
                student_subjects=self.student_subjects,
                slots=slots,
                slot_to_day=slot_to_day,
                slot_to_period_limit=slot_to_period_limit,
                hard_subjects=hard_subjects,
                subject_constraints=self.subject_constraints,  # 추가
                teacher_slot_constraints=self.teacher_slot_constraints,  # 추가
                subject_conflicts=self.subject_conflicts,  # 추가
                fixed_assignments=self._load_fixed_assignments() if getattr(self, 'use_fixed_assignments', True) else {}  # 추가: 고정 배치
            )
            print("DEBUG: Model built successfully")
            
            # 3. 목적함수 설정
            if status_callback:
                status_callback("제약조건을 설정하고 있습니다...", 70)
                
            print("DEBUG: Setting objective function...")
            self.scheduler.set_objective(self.student_subjects, slots, slot_to_day, hard_subjects)
            print("DEBUG: Objective set successfully")
            
            # 4. 모델 풀이 (실제 시간제한 적용 단계)
            if status_callback:
                print("DEBUG: 상태 업데이트 - 최적화 알고리즘 시작")
                status_callback("최적화 알고리즘을 실행하고 있습니다... (시간제한 적용)", 75)
                
            print(f"DEBUG: Starting optimization solver with time_limit={time_limit} seconds...")
            status, result = self.scheduler.solve(time_limit, status_callback)
            print(f"DEBUG: Solve completed with status={status}")
            
            # 솔버 완료 즉시 상태 업데이트
            if status_callback:
                print("DEBUG: 상태 업데이트 - 최적화 완료")
                if status == "SUCCESS":
                    status_callback("최적화 완료, 솔루션을 검증하고 있습니다...", 85)
                else:
                    status_callback("최적화 실패, 문제를 진단하고 있습니다...", 85)
            
            if status == "SUCCESS":
                # 5. 결과 분석
                if status_callback:
                    status_callback("결과를 분석하고 있습니다...", 90)
                print("DEBUG: Analyzing results...")
                analysis_results = self._analyze_results(slots, slot_to_day)
                result.update(analysis_results)
                result['slots'] = slots
                result['slot_to_day'] = slot_to_day
                print("DEBUG: Results analyzed successfully")
            else:
                # 실패 시에도 상태 업데이트
                if status_callback:
                    status_callback("문제 진단을 완료했습니다.", 90)
            
            return status, result
            
        except Exception as e:
            print(f"스케줄 생성 중 오류 발생: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return "ERROR", {"error": str(e)}
    
    def _load_hard_subjects_config(self) -> Dict[str, bool]:
        """어려운 과목 설정을 로드합니다."""
        try:
            hard_subjects_file = os.path.join(self.data_dir, 'hard_subjects_config.json')
            if os.path.exists(hard_subjects_file):
                with open(hard_subjects_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:  # Only try to parse if file has content
                        return json.loads(content)
                    else:
                        return {}
            else:
                # 기본값: 모든 과목을 어렵지 않음으로 설정
                return {}
        except Exception as e:
            print(f"Warning: Failed to load hard subjects config: {e}")
            return {}
    
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
                    if (
                        slot_to_day[slot] == day 
                        and subject in self.scheduler.exam_slot_vars  # 과목이 존재하는지 먼저 확인
                        and slot in self.scheduler.exam_slot_vars[subject]
                        and self.scheduler.solver.Value(self.scheduler.exam_slot_vars[subject][slot])
                    )
                ]
                exams_today = len(subjects_today)
                
                # 오늘 배정된 어려운 과목
                hard_subjects = self._load_hard_subjects_config()
                hard_subjects_today = [
                    subject for subject in self.student_subjects[student]
                    for slot in slots
                    if (
                        slot_to_day[slot] == day
                        and hard_subjects.get(subject, False)
                        and subject in self.scheduler.exam_slot_vars  # 과목이 존재하는지 먼저 확인
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
        slots = result.get('slots', [])
        slot_to_day = result.get('slot_to_day', {})
        
        summary = {
            'total_students': len(self.student_subjects),
            'total_subjects': len(self.subject_info_dict),
            'total_slots': len(slots),
            'exam_distribution': {},
            'hard_exam_distribution': {}
        }
        
        # 하루 시험 수 분포
        if self.config.max_exams_per_day is not None:
            for num in range(1, self.config.max_exams_per_day + 1):
                students_with_num = [
                    student for student in analysis['max_exams_per_day']
                    if analysis['max_exams_per_day'][student] == num
                ]
                summary['exam_distribution'][num] = {
                    'count': len(students_with_num),
                    'students': students_with_num
                }
        else:
            # max_exams_per_day가 None인 경우, 실제 분석 데이터를 기반으로 분포 계산
            if 'max_exams_per_day' in analysis:
                max_value = max(analysis['max_exams_per_day'].values()) if analysis['max_exams_per_day'] else 0
                for num in range(1, max_value + 1):
                    students_with_num = [
                        student for student in analysis['max_exams_per_day']
                        if analysis['max_exams_per_day'][student] == num
                    ]
                    summary['exam_distribution'][num] = {
                        'count': len(students_with_num),
                        'students': students_with_num
                    }
        
        # 하루 어려운 시험 수 분포
        if self.config.max_hard_exams_per_day is not None:
            for num in range(1, self.config.max_hard_exams_per_day + 1):
                students_with_num = [
                    student for student in analysis['max_hard_exams_per_day']
                    if analysis['max_hard_exams_per_day'][student] == num
                ]
                summary['hard_exam_distribution'][num] = {
                    'count': len(students_with_num),
                    'students': students_with_num
                }
        else:
            # max_hard_exams_per_day가 None인 경우, 실제 분석 데이터를 기반으로 분포 계산
            if 'max_hard_exams_per_day' in analysis:
                max_value = max(analysis['max_hard_exams_per_day'].values()) if analysis['max_hard_exams_per_day'] else 0
                for num in range(1, max_value + 1):
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
    
    def _load_fixed_assignments(self) -> Dict[str, List[str]]:
        """고정 배치 정보를 manual_schedule.json에서 로드합니다.
        
        Returns:
            {slot_id: [subject_list]} 형태의 고정 배치 정보
        """
        try:
            manual_schedule_file = os.path.join(self.data_dir, 'manual_schedule.json')
            if not os.path.exists(manual_schedule_file):
                print("DEBUG: No manual_schedule.json found, no fixed assignments")
                return {}
            
            with open(manual_schedule_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    print("DEBUG: Empty manual_schedule.json, no fixed assignments")
                    return {}
                
                data = json.loads(content)
                fixed_assignments = data.get('slot_assignments', {})
                
                print(f"DEBUG: Loaded fixed assignments from manual_schedule.json: {fixed_assignments}")
                return fixed_assignments
                
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"DEBUG: Failed to load manual_schedule.json: {e}")
            return {}
        except Exception as e:
            print(f"DEBUG: Unexpected error loading fixed assignments: {e}")
            return {}
    
    def set_use_fixed_assignments(self, use_fixed: bool):
        """고정 배치 사용 여부를 설정합니다."""
        self.use_fixed_assignments = use_fixed
        print(f"DEBUG: Fixed assignments usage set to: {use_fixed}")


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