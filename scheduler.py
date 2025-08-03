"""
시험 시간표 배정 스케줄러
OR-Tools를 사용하여 시험 시간표를 최적화합니다.
"""
from ortools.sat.python import cp_model
from typing import Dict, List, Any, Tuple, Optional
import pandas as pd
from config import ExamSchedulingConfig


class ExamScheduler:
    """시험 시간표 배정 스케줄러"""
    
    def __init__(self, config: ExamSchedulingConfig):
        self.config = config
        self.model = None
        self.solver = None
        self.exam_slot_vars = {}
        
    def create_slots(self, exam_dates: Dict[str, str]) -> List[str]:
        """시험 슬롯을 생성합니다."""
        days = list(exam_dates.keys())[:self.config.exam_days]
        periods = [f'{i}교시' for i in range(1, self.config.periods_per_day + 1)]
        return [f'{day}{period}' for day in days for period in periods]
    
    def create_slot_mappings(self, slots: List[str], exam_info: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, int]]:
        """슬롯 관련 매핑을 생성합니다."""
        # slot -> day 매핑
        slot_to_day = {slot: slot[:3] for slot in slots}
        
        # slot별 허용 최대 시간(분) - 날짜별 교시 시간 사용
        slot_to_period_limit = {}
        date_periods = exam_info.get('date_periods', {})
        
        for slot in slots:
            # slot 형식: '제1일1교시'
            day_part = slot[:3]  # '제1일'
            period_part = slot[3:]  # '1교시'
            
            # 날짜 번호 추출
            day_num = int(day_part[1])  # '제1일' -> 1
            period_num = int(period_part[0])  # '1교시' -> 1
            
            # 날짜별 교시 시간에서 해당 시간 찾기
            if day_num in date_periods and period_num in date_periods[day_num]:
                period_data = date_periods[day_num][period_num]
                slot_to_period_limit[slot] = period_data.get('duration', 60)
            else:
                # 기본값 사용
                slot_to_period_limit[slot] = self.config.period_limits.get(period_part, 100)
        
        return slot_to_day, slot_to_period_limit
    
    def build_model(self, 
                   subject_info_dict: Dict[str, Dict[str, Any]],
                   student_conflict_dict: Dict[str, List[str]],
                   listening_conflict_dict: Dict[str, List[str]],
                   teacher_conflict_dict: Dict[str, List[str]],
                   teacher_unavailable_dates: Dict[str, List[str]],
                   student_subjects: Dict[str, List[str]],
                   slots: List[str],
                   slot_to_day: Dict[str, str],
                   slot_to_period_limit: Dict[str, int]) -> cp_model.CpModel:
        """
        OR-Tools 모델을 구축합니다.
        """
        self.model = cp_model.CpModel()
        
        # 변수 생성 (시간 제한 미리 필터링)
        self.exam_slot_vars = {}
        for subject in subject_info_dict.keys():
            duration = subject_info_dict[subject]['시간']
            valid_slots = [
                slot for slot in slots
                if duration is None or duration <= slot_to_period_limit[slot]
            ]
            self.exam_slot_vars[subject] = {
                slot: self.model.NewBoolVar(f'{subject}_{slot}')
                for slot in valid_slots
            }
        
        # 제약조건: 각 과목 1회 배정
        for subject, var_dict in self.exam_slot_vars.items():
            self.model.Add(sum(var_dict.values()) == 1)
        
        # 제약조건: 충돌 방지
        self._add_conflict_constraints(
            student_conflict_dict, 
            listening_conflict_dict, 
            teacher_conflict_dict
        )
        
        # 제약조건: 시간 제한
        self._add_time_constraints(subject_info_dict, slot_to_period_limit)
        
        # 제약조건: 교사별 불가능 날짜
        self._add_teacher_constraints(subject_info_dict, teacher_unavailable_dates)
        
        # 제약조건: 학생별 하루 시험 수/어려운 시험 수 제한
        self._add_student_constraints(
            student_subjects, 
            subject_info_dict, 
            slots, 
            slot_to_day
        )
        
        return self.model
    
    def _add_conflict_constraints(self, 
                                 student_conflict_dict: Dict[str, List[str]],
                                 listening_conflict_dict: Dict[str, List[str]],
                                 teacher_conflict_dict: Dict[str, List[str]]):
        """충돌 방지 제약조건을 추가합니다."""
        for slot in self._get_all_slots():
            subjects_in_slot = [
                subj for subj, var_dict in self.exam_slot_vars.items()
                if slot in var_dict
            ]
            
            for i in range(len(subjects_in_slot)):
                subj1 = subjects_in_slot[i]
                
                # 학생 충돌
                for conflict in student_conflict_dict.get(subj1, []):
                    if conflict in self.exam_slot_vars and slot in self.exam_slot_vars[conflict]:
                        if subj1 < conflict:
                            self.model.Add(
                                self.exam_slot_vars[subj1][slot] +
                                self.exam_slot_vars[conflict][slot] <= 1
                            )
                
                # 듣기 충돌
                for conflict in listening_conflict_dict.get(subj1, []):
                    if conflict in self.exam_slot_vars and slot in self.exam_slot_vars[conflict]:
                        if subj1 < conflict:
                            self.model.Add(
                                self.exam_slot_vars[subj1][slot] +
                                self.exam_slot_vars[conflict][slot] <= 1
                            )
                
                # 교사 충돌
                for conflict in teacher_conflict_dict.get(subj1, []):
                    if conflict in self.exam_slot_vars and slot in self.exam_slot_vars[conflict]:
                        if subj1 < conflict:
                            self.model.Add(
                                self.exam_slot_vars[subj1][slot] +
                                self.exam_slot_vars[conflict][slot] <= 1
                            )
    
    def _add_time_constraints(self, 
                             subject_info_dict: Dict[str, Dict[str, Any]],
                             slot_to_period_limit: Dict[str, int]):
        """시간 제한 제약조건을 추가합니다."""
        for subject in subject_info_dict.keys():
            duration = subject_info_dict[subject]['시간']
            for slot in self._get_all_slots():
                if slot not in self.exam_slot_vars[subject]:
                    continue
                if duration is not None and duration > slot_to_period_limit[slot]:
                    self.model.Add(self.exam_slot_vars[subject][slot] == 0)
    
    def _add_teacher_constraints(self,
                                subject_info_dict: Dict[str, Dict[str, Any]],
                                teacher_unavailable_dates: Dict[str, List[str]]):
        """교사별 불가능 날짜 제약조건을 추가합니다."""
        for subject in subject_info_dict.keys():
            teachers = subject_info_dict[subject]['담당교사']
            for teacher in teachers:
                if teacher not in teacher_unavailable_dates:
                    continue
                for slot in teacher_unavailable_dates[teacher]:
                    if slot in self.exam_slot_vars[subject]:
                        self.model.Add(self.exam_slot_vars[subject][slot] == 0)
    
    def _add_student_constraints(self,
                                student_subjects: Dict[str, List[str]],
                                subject_info_dict: Dict[str, Dict[str, Any]],
                                slots: List[str],
                                slot_to_day: Dict[str, str]):
        """학생별 제약조건을 추가합니다."""
        days = list(set(slot_to_day.values()))
        
        for student in student_subjects:
            for day in days:
                # 하루 최대 시험 수 제한
                exams_today = [
                    self.exam_slot_vars[subject][slot]
                    for subject in student_subjects[student]
                    for slot in slots
                    if slot_to_day[slot] == day and slot in self.exam_slot_vars[subject]
                ]
                self.model.Add(sum(exams_today) <= self.config.max_exams_per_day)
                
                # 하루 최대 어려운 시험 수 제한
                hard_exams_today = [
                    self.exam_slot_vars[subject][slot]
                    for subject in student_subjects[student]
                    for slot in slots
                    if (
                        slot_to_day[slot] == day
                        and subject_info_dict[subject]['시간'] is not None
                        and subject_info_dict[subject]['시간'] >= self.config.hard_exam_threshold
                        and slot in self.exam_slot_vars[subject]
                    )
                ]
                self.model.Add(sum(hard_exams_today) <= self.config.max_hard_exams_per_day)
    
    def _get_all_slots(self) -> List[str]:
        """모든 슬롯을 반환합니다."""
        all_slots = set()
        for var_dict in self.exam_slot_vars.values():
            all_slots.update(var_dict.keys())
        return list(all_slots)
    
    def set_objective(self, student_subjects: Dict[str, List[str]], slots: List[str], slot_to_day: Dict[str, str]):
        """목적함수를 설정합니다."""
        days = list(set(slot_to_day.values()))
        students_with_m = []
        students_with_n = []
        
        for student in student_subjects:
            # 각 학생의 day별 시험 수, 어려운 시험 수
            exams_per_day = []
            hard_exams_per_day = []
            for day in days:
                exams_today = [
                    self.exam_slot_vars[subject][slot]
                    for subject in student_subjects[student]
                    for slot in slots
                    if slot_to_day[slot] == day and slot in self.exam_slot_vars[subject]
                ]
                hard_exams_today = [
                    self.exam_slot_vars[subject][slot]
                    for subject in student_subjects[student]
                    for slot in slots
                    if (
                        slot_to_day[slot] == day
                        and slot in self.exam_slot_vars[subject]
                    )
                ]
                exams_per_day.append(sum(exams_today))
                hard_exams_per_day.append(sum(hard_exams_today))
            
            max_exam = self.model.NewIntVar(0, self.config.max_exams_per_day, f'max_exam_{student}')
            max_hard_exam = self.model.NewIntVar(0, self.config.max_hard_exams_per_day, f'max_hard_exam_{student}')
            self.model.AddMaxEquality(max_exam, exams_per_day)
            self.model.AddMaxEquality(max_hard_exam, hard_exams_per_day)
            
            # m, n값 학생 수 변수
            is_m = self.model.NewBoolVar(f'is_m_{student}')
            is_n = self.model.NewBoolVar(f'is_n_{student}')
            self.model.Add(max_exam == self.config.max_exams_per_day).OnlyEnforceIf(is_m)
            self.model.Add(max_exam != self.config.max_exams_per_day).OnlyEnforceIf(is_m.Not())
            self.model.Add(max_hard_exam == self.config.max_hard_exams_per_day).OnlyEnforceIf(is_n)
            self.model.Add(max_hard_exam != self.config.max_hard_exams_per_day).OnlyEnforceIf(is_n.Not())
            
            students_with_m.append(is_m)
            students_with_n.append(is_n)
        
        self.model.Minimize(sum(students_with_m) + sum(students_with_n))
    
    def solve(self, time_limit: int = 120) -> Tuple[str, Dict[str, Any]]:
        """
        모델을 풀이합니다.
        
        Returns:
            Tuple[str, Dict[str, Any]]: (상태, 결과)
        """
        if self.model is None:
            raise ValueError("모델이 구축되지 않았습니다. build_model()을 먼저 호출하세요.")
        
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = time_limit
        status = self.solver.Solve(self.model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            result = self._extract_solution()
            return "SUCCESS", result
        else:
            return "NO_SOLUTION", {}
    
    def _extract_solution(self) -> Dict[str, Any]:
        """해답을 추출합니다."""
        if self.solver is None:
            return {}
        
        # 슬롯별 배정된 과목들
        slot_assignments = {}
        for slot in self._get_all_slots():
            assigned_subjects = [
                subject for subject, var_dict in self.exam_slot_vars.items()
                if slot in var_dict and self.solver.Value(var_dict[slot])
            ]
            if assigned_subjects:
                slot_assignments[slot] = assigned_subjects
        
        return {
            'slot_assignments': slot_assignments,
            'solver_status': self.solver.StatusName(self.solver.Solve(self.model))
        } 