"""
시험 시간표 배정 스케줄러
OR-Tools를 사용하여 시험 시간표를 최적화합니다.
"""
from ortools.sat.python import cp_model
from typing import Dict, List, Any, Tuple, Optional
import pandas as pd
import re
import time
import random
import networkx as nx
from config import ExamSchedulingConfig
from logger_config import get_logger


class ExamScheduler:
    """시험 시간표 배정 스케줄러"""
    
    def __init__(self, config: ExamSchedulingConfig):
        self.config = config
        self.model = None
        self.solver = None
        self.exam_slot_vars = {}
        self.logger = get_logger('scheduler')
        
    def create_slots(self, exam_info: Dict[str, Any]) -> List[str]:
        """시험 슬롯을 생성합니다.
        exam_info의 편집된 날짜/교시 정보를 기반으로 생성합니다.
        """
        exam_dates: Dict[str, str] = exam_info.get('시험날짜', {}) or {}
        date_periods_raw = exam_info.get('date_periods', {}) or {}
        
        # date_periods의 키가 문자열인 경우 정수로 변환
        date_periods: Dict[int, Dict[int, Dict[str, Any]]] = {}
        for day_key, day_data in date_periods_raw.items():
            day_num = int(day_key) if isinstance(day_key, str) else day_key
            period_dict = {}
            for period_key, period_data in day_data.items():
                period_num = int(period_key) if isinstance(period_key, str) else period_key
                period_dict[period_num] = period_data
            date_periods[day_num] = period_dict
        
        self.logger.debug(f"create_slots - exam_dates: {exam_dates}")
        self.logger.debug(f"create_slots - date_periods keys: {list(date_periods.keys())}")

        # 1) 사용할 일자 라벨 결정: 날짜가 비어있지 않은 것 우선
        used_day_labels: List[str] = []
        for day_label, date_str in exam_dates.items():
            # pandas의 nan 값과 빈 문자열 모두 처리
            if str(date_str).strip() != '' and str(date_str).lower() != 'nan':
                used_day_labels.append(day_label)
            else:
                # 날짜가 비어있으면 해당 날짜의 _deleted 상태 확인
                day_match = re.search(r'제(\d+)일', day_label)
                if day_match:
                    day_num = int(day_match.group(1))
                    if day_num in date_periods:
                        day_periods = date_periods[day_num]
                        # 해당 날짜의 모든 교시가 _deleted인지 확인
                        all_deleted = all(
                            isinstance(pdata, dict) and pdata.get('_deleted')
                            for pdata in day_periods.values()
                        )
                        # _deleted가 아닌 경우에만 추가
                        if not all_deleted:
                            used_day_labels.append(day_label)
        
        self.logger.debug(f"create_slots - after step 1: {used_day_labels}")

        # 2) 만약 비어있지 않은 날짜가 없다면 date_periods의 키를 사용
        if not used_day_labels and date_periods:
            # _deleted가 true인 날짜는 제외
            available_days = []
            for day_num in sorted(date_periods.keys()):
                day_periods = date_periods[day_num]
                # 해당 날짜의 모든 교시가 _deleted인지 확인
                all_deleted = all(
                    isinstance(pdata, dict) and pdata.get('_deleted')
                    for pdata in day_periods.values()
                )
                if not all_deleted:
                    available_days.append(day_num)
            
            used_day_labels = [f'제{day_num}일' for day_num in available_days]
        
        self.logger.debug(f"create_slots - after step 2: {used_day_labels}")

        # 3) 여전히 날짜가 없으면 exam_info의 시험날짜 확인
        if not used_day_labels:
            # 시험날짜에서 사용 가능한 날짜 추출
            exam_dates = exam_info.get('시험날짜', {})
            if exam_dates:
                # 시험날짜의 키들을 정렬해서 사용 (제1일, 제2일, ...)
                sorted_dates = sorted(exam_dates.keys(), key=lambda x: int(re.search(r'(\d+)', x).group(1)) if re.search(r'(\d+)', x) else 0)
                used_day_labels = sorted_dates[:2]  # 최대 2일까지만 기본값으로 사용
            else:
                # 시험날짜 정보가 없음
                raise ValueError("시험날짜 정보가 없습니다. custom_exam_info.json 파일의 '시험날짜' 항목을 확인해주세요.")
        
        self.logger.debug(f"create_slots - after step 3: {used_day_labels}")
        
        # 4) date_periods에 없는 날짜와 모든 교시가 _deleted인 날짜는 제외
        final_day_labels = []
        for day_label in used_day_labels:
            day_match = re.search(r'제(\d+)일', day_label)
            if day_match:
                day_num = int(day_match.group(1))
                # date_periods에 없는 날짜는 완전히 삭제된 것으로 간주
                if day_num in date_periods:
                    # 해당 날짜의 모든 교시가 _deleted인지 확인
                    day_periods = date_periods[day_num]
                    all_deleted = all(
                        isinstance(pdata, dict) and pdata.get('_deleted')
                        for pdata in day_periods.values()
                    )
                    # 모든 교시가 _deleted가 아닌 경우에만 추가
                    if not all_deleted:
                        final_day_labels.append(day_label)
            else:
                final_day_labels.append(day_label)
        
        used_day_labels = final_day_labels
        
        self.logger.debug(f"create_slots - after step 4: {used_day_labels}")

        slots: List[str] = []
        for day_label in used_day_labels:
            day_match = re.search(r'제(\d+)일', day_label)
            if not day_match:
                continue
            day_num = int(day_match.group(1))
            periods_for_day: Dict[int, Dict[str, Any]] = date_periods.get(day_num, {})

            # 사용자 편집된 교시 목록 사용 (_deleted가 아닌 교시만 사용)
            period_numbers: List[int] = sorted([
                period_num for period_num, period_data in periods_for_day.items()
                if not (isinstance(period_data, dict) and period_data.get('_deleted'))
            ])

            # 교시 정보가 전혀 없으면 exam_info에서 기본 교시 추출
            if not period_numbers:
                # exam_info의 다른 날짜에서 사용되는 교시들을 찾아서 사용
                default_periods = set()
                for other_day_num, other_periods in date_periods.items():
                    if other_day_num != day_num:
                        active_periods = [
                            p for p, pdata in other_periods.items()
                            if not (isinstance(pdata, dict) and pdata.get('_deleted'))
                        ]
                        default_periods.update(active_periods)
                
                if default_periods:
                    period_numbers = sorted(default_periods)
                else:
                    # 교시 정보가 전혀 없음
                    raise ValueError(f"'{day_label}'의 교시 정보가 없습니다. custom_exam_info.json 파일의 'date_periods' 항목을 확인해주세요.")

            for period_num in period_numbers:
                # 4교시 제외하고 슬롯 생성
                slots.append(f'{day_label}{period_num}교시')

        return slots
    
    def create_slot_mappings(self, slots: List[str], exam_info: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, int]]:
        """슬롯 관련 매핑을 생성합니다."""
        # slot -> day 매핑 (안전하게 정규식으로 파싱)
        slot_to_day: Dict[str, str] = {}
        for slot in slots:
            day_match = re.match(r'(제\d+일)', slot)
            slot_to_day[slot] = day_match.group(1) if day_match else slot[:3]
        
        # slot별 허용 최대 시간(분) - 날짜별 교시 시간 사용
        slot_to_period_limit = {}
        date_periods_raw = exam_info.get('date_periods', {})
        
        # date_periods의 키가 문자열인 경우 정수로 변환 (create_slots와 동일한 로직)
        date_periods: Dict[int, Dict[int, Dict[str, Any]]] = {}
        for day_key, day_data in date_periods_raw.items():
            day_num = int(day_key) if isinstance(day_key, str) else day_key
            period_dict = {}
            for period_key, period_data in day_data.items():
                period_num = int(period_key) if isinstance(period_key, str) else period_key
                period_dict[period_num] = period_data
            date_periods[day_num] = period_dict
        
        for slot in slots:
            # slot 형식: '제1일1교시'
            day_part = slot[:3]  # '제1일'
            period_part = slot[3:]  # '1교시'
            
            # 날짜 번호 추출 - 더 안전한 방법 사용
            day_match = re.search(r'제(\d+)일', day_part)
            period_match = re.search(r'(\d+)교시', period_part)
            
            if day_match and period_match:
                day_num = int(day_match.group(1))
                period_num = int(period_match.group(1))
                
                # 날짜별 교시 시간에서 해당 시간 찾기
                if day_num in date_periods and period_num in date_periods[day_num]:
                    period_data = date_periods[day_num][period_num]
                    
                    # _deleted 상태이거나 기본 데이터 구조가 없는 경우 기본값 계산
                    if isinstance(period_data, dict) and period_data.get('_deleted'):
                        slot_to_period_limit[slot] = self._get_default_period_duration(date_periods, period_num)
                    else:
                        duration = period_data.get('duration') if isinstance(period_data, dict) else None
                        try:
                            if duration is not None:
                                slot_to_period_limit[slot] = int(duration)
                            else:
                                slot_to_period_limit[slot] = self._get_default_period_duration(date_periods, period_num)
                        except (ValueError, TypeError):
                            slot_to_period_limit[slot] = self._get_default_period_duration(date_periods, period_num)
                else:
                    # 기본값 사용
                    slot_to_period_limit[slot] = self._get_default_period_duration(date_periods, period_num)
            else:
                # 파싱 실패시 기본값 사용
                slot_to_period_limit[slot] = self._get_default_period_duration(date_periods, period_num)
        
        return slot_to_day, slot_to_period_limit
    
    def _get_default_period_duration(self, date_periods: Dict[int, Dict[int, Any]], target_period: int) -> int:
        """다른 날짜의 같은 교시에서 평균 시간을 계산하여 기본값을 반환합니다."""
        durations = []
        
        # 모든 날짜의 같은 교시에서 duration 수집
        for day_num, periods in date_periods.items():
            if target_period in periods:
                period_data = periods[target_period]
                if isinstance(period_data, dict) and not period_data.get('_deleted'):
                    duration = period_data.get('duration')
                    if duration is not None:
                        try:
                            durations.append(int(duration))
                        except (ValueError, TypeError):
                            continue
        
        if durations:
            # 평균값 사용 (반올림)
            return round(sum(durations) / len(durations))
        else:
            # 시간 정보가 전혀 없음
            raise ValueError(f"{target_period}교시의 시간 정보가 없습니다. custom_exam_info.json 파일의 'date_periods'에서 '{target_period}교시'의 'duration' 값을 확인해주세요.")
    
    def build_model(self, 
                   subject_info_dict: Dict[str, Any],
                   student_conflict_dict: Dict[str, List[str]],
                   listening_conflict_dict: Dict[str, List[str]],
                   teacher_conflict_dict: Dict[str, List[str]],
                   teacher_unavailable_dates: Dict[str, List[str]],
                   student_subjects: Dict[str, List[str]],
                   slots: List[str],
                   slot_to_day: Dict[str, str],
                   slot_to_period_limit: Dict[str, int],
                   hard_subjects: Dict[str, bool] = None,
                   subject_constraints: Dict[str, Dict[str, Any]] = None,
                   teacher_slot_constraints: Dict[str, Dict[str, Any]] = None,
                   subject_conflicts: Dict[str, Dict[str, Any]] = None,
                   fixed_assignments: Dict[str, List[str]] = None) -> cp_model.CpModel:
        
        # 실제 사용할 슬롯들을 저장
        self.actual_slots = slots
        self.actual_slot_to_day = slot_to_day
        """
        OR-Tools 모델을 구축합니다.
        """
        self.model = cp_model.CpModel()
        
        # 충돌 데이터를 인스턴스 변수로 저장 (진단에 사용)
        self.student_conflict_dict = student_conflict_dict
        self.listening_conflict_dict = listening_conflict_dict
        self.teacher_conflict_dict = teacher_conflict_dict
        self.teacher_unavailable_dates = teacher_unavailable_dates
        self.student_subjects = student_subjects
        
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
        
        # 제약조건: 각 과목 1회 배정 (여러 슬롯에 배정 가능하도록 수정)
        for subject, var_dict in self.exam_slot_vars.items():
            # 각 과목은 최소 1개 슬롯에 배정되어야 함
            self.model.Add(sum(var_dict.values()) >= 1)
            # 각 과목은 최대 1개 슬롯에만 배정 (중복 배정 방지)
            self.model.Add(sum(var_dict.values()) <= 1)
        
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
        
        # 제약조건: 과목별 제약조건 (특정 슬롯 금지)
        if subject_constraints:
            self._add_subject_constraints(subject_constraints)
        
        # 제약조건: 교사 슬롯별 제약조건 (특정 교사의 특정 슬롯 금지)
        if teacher_slot_constraints:
            self._add_teacher_slot_constraints(teacher_slot_constraints, subject_info_dict)
        
        # 제약조건: 과목 충돌 제약조건 (같은 시간 금지/필수)
        if subject_conflicts:
            self._add_subject_conflict_constraints(subject_conflicts)
        
        # 제약조건: 고정 배치 (수동 배치된 과목들)
        if fixed_assignments:
            self._add_fixed_assignment_constraints(fixed_assignments)
        
        # 제약조건: 학생별 하루 시험 수/어려운 시험 수 제한
        self._add_student_constraints(
            student_subjects, 
            subject_info_dict, 
            slots, 
            slot_to_day,
            hard_subjects
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
    
    def _add_subject_constraints(self, subject_constraints: Dict[str, Dict[str, Any]]):
        """과목별 제약조건을 추가합니다."""
        self.logger.debug(f"Adding subject constraints: {len(subject_constraints)} subjects")
        
        for subject, slot_constraints in subject_constraints.items():
            if subject not in self.exam_slot_vars:
                self.logger.debug(f"Subject {subject} not found in exam_slot_vars, skipping")
                continue
                
            for slot_constraint in slot_constraints.keys():
                # 슬롯 ID 표준화 (제3일_1교시 → 제3일1교시)
                standardized_slot = slot_constraint.replace('_', '')
                
                # 해당 슬롯이 존재하고 과목에 변수가 있는 경우 제약조건 추가
                if standardized_slot in self.exam_slot_vars[subject]:
                    self.logger.debug(f"Adding constraint: {subject} cannot be placed in {standardized_slot}")
                    self.model.Add(self.exam_slot_vars[subject][standardized_slot] == 0)
                else:
                    self.logger.debug(f"Slot {standardized_slot} not available for {subject}")
    
    def _add_teacher_slot_constraints(self, 
                                     teacher_slot_constraints: Dict[str, Dict[str, Any]], 
                                     subject_info_dict: Dict[str, Dict[str, Any]]):
        """교사 슬롯별 제약조건을 추가합니다."""
        self.logger.debug(f"Adding teacher slot constraints: {len(teacher_slot_constraints)} teachers")
        
        for teacher, slot_constraints in teacher_slot_constraints.items():
            self.logger.debug(f"Processing teacher {teacher} with {len(slot_constraints)} slot constraints")
            
            # 해당 교사가 담당하는 모든 과목 찾기
            teacher_subjects = []
            for subject, info in subject_info_dict.items():
                if '담당교사' in info and teacher in info['담당교사']:
                    teacher_subjects.append(subject)
            
            self.logger.debug(f"Teacher {teacher} teaches subjects: {teacher_subjects}")
            
            # 각 제약조건 적용
            for slot_constraint in slot_constraints.keys():
                # 슬롯 ID 표준화 (제3일_1교시 → 제3일1교시)
                standardized_slot = slot_constraint.replace('_', '')
                
                # 해당 교사가 담당하는 모든 과목에 대해 해당 슬롯 금지
                for subject in teacher_subjects:
                    if subject in self.exam_slot_vars and standardized_slot in self.exam_slot_vars[subject]:
                        self.logger.debug(f"Adding constraint: {subject} (teacher: {teacher}) cannot be placed in {standardized_slot}")
                        self.model.Add(self.exam_slot_vars[subject][standardized_slot] == 0)
                    else:
                        self.logger.debug(f"Slot {standardized_slot} not available for {subject} (teacher: {teacher})")
    
    def _add_subject_conflict_constraints(self, subject_conflicts: Dict[str, Dict[str, Any]]):
        """과목 충돌 제약조건을 추가합니다."""
        self.logger.debug(f"Adding subject conflict constraints: {len(subject_conflicts)} conflicts")
        
        for conflict_key, conflict_info in subject_conflicts.items():
            subject1 = conflict_info.get('subject1')
            subject2 = conflict_info.get('subject2')
            conflict_type = conflict_info.get('type')
            
            if not all([subject1, subject2, conflict_type]):
                self.logger.debug(f"Incomplete conflict info for {conflict_key}, skipping")
                continue
            
            # 두 과목이 모두 존재하는지 확인
            if subject1 not in self.exam_slot_vars or subject2 not in self.exam_slot_vars:
                self.logger.debug(f"One of subjects {subject1}, {subject2} not found in exam_slot_vars, skipping")
                continue
                
            self.logger.debug(f"Processing conflict: {subject1} vs {subject2}, type: {conflict_type}")
            
            if conflict_type == 'avoid_same_time':
                # 같은 시간에 배치하면 안되는 과목들
                self._add_avoid_same_time_constraint(subject1, subject2)
            elif conflict_type == 'same_time':
                # 같은 시간에 배치되어야 하는 과목들 (필수 동반)
                self._add_same_time_constraint(subject1, subject2)
            else:
                self.logger.debug(f"Unknown conflict type: {conflict_type}")
    
    def _add_avoid_same_time_constraint(self, subject1: str, subject2: str):
        """두 과목이 같은 슬롯에 배치되지 않도록 제약조건을 추가합니다."""
        self.logger.debug(f"Adding avoid_same_time constraint: {subject1} != {subject2}")
        
        # 모든 슬롯에 대해 두 과목이 동시에 배치되지 않도록 제약
        for slot in self._get_all_slots():
            if slot in self.exam_slot_vars[subject1] and slot in self.exam_slot_vars[subject2]:
                self.model.Add(
                    self.exam_slot_vars[subject1][slot] + 
                    self.exam_slot_vars[subject2][slot] <= 1
                )
    
    def _add_same_time_constraint(self, subject1: str, subject2: str):
        """두 과목이 같은 슬롯에 배치되도록 제약조건을 추가합니다."""
        self.logger.debug(f"Adding same_time constraint: {subject1} == {subject2}")
        
        # 두 과목이 모두 배치된 경우, 같은 슬롯에 배치되어야 함
        for slot in self._get_all_slots():
            if slot in self.exam_slot_vars[subject1] and slot in self.exam_slot_vars[subject2]:
                # subject1이 이 슬롯에 배치되면 subject2도 이 슬롯에 배치되어야 함
                self.model.Add(
                    self.exam_slot_vars[subject1][slot] == self.exam_slot_vars[subject2][slot]
                )
    
    def _add_student_constraints(self,
                                student_subjects: Dict[str, List[str]],
                                subject_info_dict: Dict[str, Dict[str, Any]],
                                slots: List[str],
                                slot_to_day: Dict[str, str],
                                hard_subjects: Dict[str, bool] = None):
        """학생별 제약조건을 추가합니다."""
        self.logger.debug(f"_add_student_constraints called with hard_subjects: {hard_subjects}")
        self.logger.debug(f"config.max_hard_exams_per_day: {self.config.max_hard_exams_per_day}")
        
        days = list(set(slot_to_day.values()))
        
        for student in student_subjects:
            for day in days:
                # 하루 최대 시험 수 제한 (None이면 제한 없음)
                if self.config.max_exams_per_day is not None:
                    exams_today = [
                        self.exam_slot_vars[subject][slot]
                        for subject in student_subjects[student]
                        for slot in slots
                        if slot_to_day[slot] == day and slot in self.exam_slot_vars[subject]
                    ]
                    self.model.Add(sum(exams_today) <= self.config.max_exams_per_day)
                
                # 하루 최대 어려운 시험 수 제한 (None이면 제한 없음)
                if self.config.max_hard_exams_per_day is not None:
                    hard_exams_today = [
                        self.exam_slot_vars[subject][slot]
                        for subject in student_subjects[student]
                        for slot in slots
                        if (
                            slot_to_day[slot] == day
                            and hard_subjects and hard_subjects.get(subject, False)
                            and slot in self.exam_slot_vars[subject]
                        )
                    ]
                    
                    # 디버그 출력 추가
                    if hard_exams_today:
                        self.logger.debug(f"Student {student}, Day {day}: {len(hard_exams_today)} hard exam variables")
                        self.logger.debug(f"Hard subjects for this student: {[s for s in student_subjects[student] if hard_subjects and hard_subjects.get(s, False)]}")
                    
                    self.model.Add(sum(hard_exams_today) <= self.config.max_hard_exams_per_day)
    
    def _get_all_slots(self) -> List[str]:
        """모든 슬롯을 반환합니다."""
        if hasattr(self, 'actual_slots'):
            return self.actual_slots
        # fallback: exam_slot_vars에서 슬롯 추출
        all_slots = set()
        for var_dict in self.exam_slot_vars.values():
            all_slots.update(var_dict.keys())
        return list(all_slots)
    
    def set_objective(self, student_subjects: Dict[str, List[str]], slots: List[str], slot_to_day: Dict[str, str], hard_subjects: Dict[str, bool] = None):
        """목적함수를 설정합니다."""
        self.logger.debug(f"set_objective called with hard_subjects: {hard_subjects}")
        
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
                    if (
                        slot_to_day[slot] == day 
                        and subject in self.exam_slot_vars  # 과목이 존재하는지 먼저 확인
                        and slot in self.exam_slot_vars[subject]
                    )
                ]
                hard_exams_today = [
                    self.exam_slot_vars[subject][slot]
                    for subject in student_subjects[student]
                    for slot in slots
                    if (
                        slot_to_day[slot] == day
                        and hard_subjects and hard_subjects.get(subject, False)
                        and subject in self.exam_slot_vars  # 과목이 존재하는지 먼저 확인
                        and slot in self.exam_slot_vars[subject]
                    )
                ]
                
                # 디버그 출력 추가
                if hard_exams_today:
                    self.logger.debug(f"Objective - Student {student}, Day {day}: {len(hard_exams_today)} hard exam variables")
                
                exams_per_day.append(sum(exams_today))
                hard_exams_per_day.append(sum(hard_exams_today))
            
            # max_exams_per_day가 None이 아닌 경우에만 목적함수에 포함
            if self.config.max_exams_per_day is not None:
                max_exam = self.model.NewIntVar(0, self.config.max_exams_per_day, f'max_exam_{student}')
                self.model.AddMaxEquality(max_exam, exams_per_day)
                
                # m값 학생 수 변수
                is_m = self.model.NewBoolVar(f'is_m_{student}')
                self.model.Add(max_exam == self.config.max_exams_per_day).OnlyEnforceIf(is_m)
                self.model.Add(max_exam != self.config.max_exams_per_day).OnlyEnforceIf(is_m.Not())
                students_with_m.append(is_m)
            
            # max_hard_exams_per_day가 None이 아닌 경우에만 목적함수에 포함
            if self.config.max_hard_exams_per_day is not None:
                max_hard_exam = self.model.NewIntVar(0, self.config.max_hard_exams_per_day, f'max_hard_exam_{student}')
                self.model.AddMaxEquality(max_hard_exam, hard_exams_per_day)
                
                # n값 학생 수 변수
                is_n = self.model.NewBoolVar(f'is_n_{student}')
                self.model.Add(max_hard_exam == self.config.max_hard_exams_per_day).OnlyEnforceIf(is_n)
                self.model.Add(max_hard_exam != self.config.max_hard_exams_per_day).OnlyEnforceIf(is_n.Not())
                students_with_n.append(is_n)
        
        # 목적함수 설정 (최소화할 변수가 있는 경우에만)
        objective_terms = []
        if students_with_m:
            objective_terms.append(sum(students_with_m))
        if students_with_n:
            objective_terms.append(sum(students_with_n))
        
        if objective_terms:
            self.model.Minimize(sum(objective_terms))
        else:
            # 목적함수가 없는 경우 임의의 변수를 최소화 (실제로는 영향 없음)
            dummy_var = self.model.NewIntVar(0, 0, 'dummy_objective')
            self.model.Minimize(dummy_var)
    
    def solve(self, time_limit: int = 120, status_callback=None) -> Tuple[str, Dict[str, Any]]:
        """
        모델을 풀이합니다.
        
        Args:
            time_limit: 최대 풀이 시간(초)
            status_callback: 상태 업데이트 콜백 함수 (step, progress)
            
        Returns:
            Tuple[str, Dict[str, Any]]: (상태, 결과)
        """
        if self.model is None:
            raise ValueError("모델이 구축되지 않았습니다. build_model()을 먼저 호출하세요.")
        
        # 제약조건 검증 추가
        validation_result = self._validate_constraints()
        if not validation_result['valid']:
            return "INFEASIBLE", {
                'error': '제약조건 검증 실패',
                'details': validation_result['issues'],
                'total_slots': validation_result['total_slots'],
                'total_subjects': validation_result['total_subjects']
            }
        
        # 솔버가 이미 초기화되지 않은 경우에만 초기화
        if not self.solver:
            self.solver = cp_model.CpSolver()
            self.solver.parameters.max_time_in_seconds = time_limit
            
            self.logger.debug(f"Solver time limit set to {time_limit} seconds")
            self.logger.debug(f"Solver parameters: max_time_in_seconds = {self.solver.parameters.max_time_in_seconds}")
        else:
            self.logger.debug("Using pre-initialized solver")
            self.logger.debug(f"Pre-initialized solver time limit: {self.solver.parameters.max_time_in_seconds}")
        
        start_time = time.time()
        self.logger.debug(f"Starting solver at {start_time}")
        
        # 타이머 기반 남은 시간 표시를 위한 간단한 모니터링
        def update_remaining_time():
            """남은 시간을 업데이트하는 간단한 함수"""
            if status_callback:
                elapsed = time.time() - start_time
                remaining = max(0, time_limit - elapsed)
                if remaining > 0:
                    status_callback(f"최적화 알고리즘을 실행하고 있습니다... (약 {int(remaining)}초 남음)", 75)
        
        # 솔버 실행 시작 알림
        if status_callback:
            status_callback(f"최적화 알고리즘을 실행하고 있습니다... (약 {time_limit}초 남음)", 75)
        
        # 솔버 실행 중 주기적으로 남은 시간 업데이트 (간단한 방식)
        import threading
        import time as time_module
        
        # 타이머 스레드 생성 (1초마다 업데이트)
        timer_thread = threading.Thread(target=lambda: self._simple_timer_update(start_time, time_limit, status_callback))
        timer_thread.daemon = True  # 메인 스레드 종료 시 함께 종료
        timer_thread.start()
        
        status = self.solver.Solve(self.model)
        
        # 타이머 스레드 종료 신호
        self._stop_timer = True
        
        end_time = time.time()
        actual_duration = end_time - start_time
        self.logger.debug(f"Solver finished at {end_time}")
        self.logger.debug(f"Actual solver duration: {actual_duration:.2f} seconds")
        self.logger.debug(f"Solver status: {status}")
        
        # 솔버 완료 후 상태 업데이트
        if status_callback:
            if status == cp_model.OPTIMAL:
                status_callback("최적해를 찾았습니다! 솔루션을 검증하고 있습니다...", 80)
            elif status == cp_model.FEASIBLE:
                status_callback("실행 가능한 해를 찾았습니다! 솔루션을 검증하고 있습니다...", 80)
            elif status == cp_model.INFEASIBLE:
                status_callback("제약조건을 만족하는 해가 없습니다. 진단 중...", 80)
            elif status == cp_model.MODEL_INVALID:
                status_callback("모델이 유효하지 않습니다. 진단 중...", 80)
            else:
                status_callback("솔버가 완료되었습니다. 결과를 분석하고 있습니다...", 80)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            result = self._extract_solution(self.actual_slots, status)
            return "SUCCESS", result
        else:
            # NO_SOLUTION 상태일 때 더 구체적인 진단 정보 제공
            diagnosis = self._diagnose_no_solution()
            return "NO_SOLUTION", {
                'error': '시험 시간표를 생성할 수 없습니다',
                'diagnosis': diagnosis
            }
    
    def _simple_timer_update(self, start_time: float, time_limit: int, status_callback):
        """간단한 타이머 업데이트 함수"""
        self._stop_timer = False
        while not self._stop_timer:
            try:
                elapsed = time.time() - start_time
                remaining = max(0, time_limit - elapsed)
                
                if remaining <= 0 or self._stop_timer:
                    break
                    
                if status_callback:
                    status_callback(f"최적화 알고리즘을 실행하고 있습니다... (약 {int(remaining)}초 남음)", 75)
                
                time.sleep(1)  # 1초마다 업데이트
            except:
                break
    
    def _validate_constraints(self) -> Dict[str, Any]:
        """제약조건의 기본적인 검증을 수행합니다."""
        issues = []
        
        # 1. 슬롯 수와 과목 수 검증 - 실제 사용 가능한 슬롯 수 계산
        # _get_all_slots() 대신 실제 exam_slot_vars에서 사용되는 슬롯을 계산
        all_used_slots = set()
        for subject, var_dict in self.exam_slot_vars.items():
            all_used_slots.update(var_dict.keys())
        
        total_slots = len(all_used_slots)
        total_subjects = len(self.exam_slot_vars)
        
        # 슬롯 수가 과목 수보다 적어도 해결 가능 (각 슬롯에 여러 과목 배정 가능)
        # if total_slots < total_subjects:
        #     issues.append(f"슬롯 수({total_slots})가 과목 수({total_subjects})보다 적습니다.")
        
        # 2. 각 과목의 유효한 슬롯 수 검증
        for subject, var_dict in self.exam_slot_vars.items():
            if len(var_dict) == 0:
                issues.append(f"과목 '{subject}'에 배정 가능한 슬롯이 없습니다.")
        
        # 3. 충돌 데이터 검증
        if hasattr(self, 'student_conflict_dict'):
            for subject, conflicts in self.student_conflict_dict.items():
                if subject in self.exam_slot_vars:
                    for conflict in conflicts:
                        if conflict in self.exam_slot_vars:
                            # 충돌하는 두 과목이 모두 같은 슬롯에 배정 가능한지 확인
                            common_slots = set(self.exam_slot_vars[subject].keys()) & set(self.exam_slot_vars[conflict].keys())
                            if len(common_slots) == 0:
                                issues.append(f"충돌하는 과목 '{subject}'과 '{conflict}'이 공통 슬롯이 없습니다.")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'total_slots': total_slots,
            'total_subjects': total_subjects
        }
    
    def _diagnose_no_solution(self) -> Dict[str, Any]:
        """NO_SOLUTION 상태의 원인을 진단합니다."""
        diagnosis = {
            'possible_causes': [],
            'recommendations': [],
            'constraint_info': {}
        }
        
        # 1. 슬롯과 과목 수 분석 - 실제 사용 가능한 슬롯 수 계산
        all_used_slots = set()
        for subject, var_dict in self.exam_slot_vars.items():
            all_used_slots.update(var_dict.keys())
        
        total_slots = len(all_used_slots)
        total_subjects = len(self.exam_slot_vars)
        
        # 슬롯 수가 과목 수보다 적어도 해결 가능 (각 슬롯에 여러 과목 배정 가능)
        # if total_slots < total_subjects:
        #     diagnosis['possible_causes'].append('슬롯 수가 부족합니다')
        #     diagnosis['recommendations'].append('시험 일수나 교시 수를 늘려보세요')
        
        # 2. 각 과목의 유효한 슬롯 수 분석
        subjects_with_few_slots = []
        for subject, var_dict in self.exam_slot_vars.items():
            if len(var_dict) <= 1:
                subjects_with_few_slots.append(subject)
        
        if subjects_with_few_slots:
            diagnosis['possible_causes'].append('일부 과목의 배정 가능한 슬롯이 너무 적습니다')
            diagnosis['recommendations'].append('해당 과목의 시간 제한이나 교사 제약을 완화해보세요')
            diagnosis['constraint_info']['subjects_with_few_slots'] = subjects_with_few_slots
        
        # 3. 충돌 데이터 분석
        if hasattr(self, 'student_conflict_dict'):
            high_conflict_subjects = []
            for subject, conflicts in self.student_conflict_dict.items():
                if len(conflicts) > total_slots // 2:  # 슬롯 수의 절반 이상과 충돌
                    high_conflict_subjects.append(subject)
            
            if high_conflict_subjects:
                diagnosis['possible_causes'].append('충돌이 너무 많은 과목이 있습니다')
                diagnosis['recommendations'].append('충돌 데이터를 검토하고 불필요한 충돌을 제거해보세요')
                diagnosis['constraint_info']['high_conflict_subjects'] = high_conflict_subjects
        
        # 4. 기본 권장사항
        if not diagnosis['recommendations']:
            diagnosis['recommendations'].extend([
                '풀이 시간을 늘려보세요',
                '시험 일수나 교시 수를 늘려보세요',
                '과목 간 충돌을 줄여보세요',
                '교사 불가능 시간을 줄여보세요'
            ])
        
        diagnosis['constraint_info']['total_slots'] = total_slots
        diagnosis['constraint_info']['total_subjects'] = total_subjects
        
        return diagnosis
    
    def _extract_solution(self, slots: List[str] = None, solver_status=None) -> Dict[str, Any]:
        """해답을 추출합니다."""
        if self.solver is None:
            return {}
        
        # 슬롯별 배정된 과목들
        slot_assignments = {}
        # 실제 사용된 슬롯만 확인
        slots_to_check = slots if slots is not None else self._get_all_slots()
        for slot in slots_to_check:
            assigned_subjects = [
                subject for subject, var_dict in self.exam_slot_vars.items()
                if slot in var_dict and self.solver.Value(var_dict[slot])
            ]
            if assigned_subjects:
                slot_assignments[slot] = assigned_subjects
        
        return {
            'slot_assignments': slot_assignments,
            'solver_status': self.solver.StatusName(solver_status) if solver_status is not None else "UNKNOWN"
        }
    
    def _add_fixed_assignment_constraints(self, fixed_assignments: Dict[str, List[str]]):
        """고정 배치 제약조건을 추가합니다.
        
        Args:
            fixed_assignments: {slot_id: [subject_list]} 형태의 고정 배치 정보
        """
        self.logger.debug(f"Adding fixed assignment constraints: {fixed_assignments}")
        
        for slot_id, assigned_subjects in fixed_assignments.items():
            for subject in assigned_subjects:
                # 과목이 모델에 존재하고 해당 슬롯이 유효한 경우에만 고정
                if subject in self.exam_slot_vars and slot_id in self.exam_slot_vars[subject]:
                    # 해당 과목을 해당 슬롯에 고정 배치
                    self.model.Add(self.exam_slot_vars[subject][slot_id] == 1)
                    self.logger.debug(f"Fixed assignment - {subject} -> {slot_id}")
                    
                    # 다른 모든 슬롯에는 배치하지 않도록 설정
                    for other_slot in self.exam_slot_vars[subject]:
                        if other_slot != slot_id:
                            self.model.Add(self.exam_slot_vars[subject][other_slot] == 0)
                            
                else:
                    self.logger.warning(f"Cannot fix assignment - {subject} to {slot_id} (subject or slot not found in model)")
        
        self.logger.debug(f"Fixed assignment constraints added successfully")
    
    def find_maximum_cliques(self, 
                            subject_info_dict: Dict[str, Any],
                            student_conflict_dict: Dict[str, List[str]],
                            listening_conflict_dict: Dict[str, List[str]],
                            teacher_conflict_dict: Dict[str, List[str]],
                            fixed_assignments: Dict[str, List[str]] = None) -> Dict[str, Any]:
        """
        충돌 데이터를 바탕으로 최대 클리크를 찾습니다.
        
        Args:
            subject_info_dict: 과목 정보 딕셔너리
            student_conflict_dict: 학생 충돌 딕셔너리
            listening_conflict_dict: 듣기평가 충돌 딕셔너리
            teacher_conflict_dict: 교사 충돌 딕셔너리
            fixed_assignments: 이미 배치된 과목들 (제외 대상)
            
        Returns:
            Dict containing:
            - max_clique: 최대 클리크 과목 리스트
            - all_cliques: 모든 클리크 리스트
            - conflict_graph: 충돌 그래프 정보
            - min_clique_size: 최소 클리크 크기
        """
        self.logger.debug("Starting maximum clique search...")
        
        # 1. 이미 배치된 과목들 제외
        fixed_subjects = set()
        if fixed_assignments:
            for slot_subjects in fixed_assignments.values():
                fixed_subjects.update(slot_subjects)
        
        # 2. 배치 가능한 과목들만 대상으로 함
        available_subjects = [subject for subject in subject_info_dict.keys() 
                            if subject not in fixed_subjects]
        
        if not available_subjects:
            self.logger.warning("No available subjects for clique search")
            return {
                'max_clique': [],
                'all_cliques': [],
                'conflict_graph': {},
                'min_clique_size': 0
            }
        
        self.logger.debug(f"Available subjects for clique search: {len(available_subjects)}")
        
        # 3. 충돌 그래프 생성
        G = nx.Graph()
        G.add_nodes_from(available_subjects)
        
        # 4. 충돌 관계를 엣지로 추가
        conflict_count = 0
        for subject in available_subjects:
            # 학생 충돌
            for conflict in student_conflict_dict.get(subject, []):
                if conflict in available_subjects:
                    G.add_edge(subject, conflict)
                    conflict_count += 1
            
            # 듣기평가 충돌
            for conflict in listening_conflict_dict.get(subject, []):
                if conflict in available_subjects:
                    G.add_edge(subject, conflict)
                    conflict_count += 1
            
            # 교사 충돌
            for conflict in teacher_conflict_dict.get(subject, []):
                if conflict in available_subjects:
                    G.add_edge(subject, conflict)
                    conflict_count += 1
        
        self.logger.debug(f"Conflict graph created with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        
        # 5. 모든 최대 클리크 찾기
        try:
            all_max_cliques = list(nx.find_cliques(G))
        except Exception as e:
            self.logger.error(f"Error finding cliques: {e}")
            return {
                'max_clique': [],
                'all_cliques': [],
                'conflict_graph': {'nodes': G.number_of_nodes(), 'edges': G.number_of_edges()},
                'min_clique_size': 0
            }
        
        if not all_max_cliques:
            self.logger.warning("No cliques found")
            return {
                'max_clique': [],
                'all_cliques': [],
                'conflict_graph': {'nodes': G.number_of_nodes(), 'edges': G.number_of_edges()},
                'min_clique_size': 0
            }
        
        # 6. 최대 크기 클리크들 찾기
        max_size = max(len(clique) for clique in all_max_cliques)
        max_cliques = [clique for clique in all_max_cliques if len(clique) == max_size]
        
        # 7. 최소 클리크 크기 계산: max(전체 과목수의 10%, 3개)
        total_subjects = len(subject_info_dict)
        min_clique_size = max(int(total_subjects * 0.1), 3)
        
        # 8. 최소 크기 이상의 클리크만 필터링
        valid_cliques = [clique for clique in all_max_cliques if len(clique) >= min_clique_size]
        
        self.logger.debug(f"Found {len(all_max_cliques)} total cliques")
        self.logger.debug(f"Found {len(max_cliques)} maximum cliques of size {max_size}")
        self.logger.debug(f"Found {len(valid_cliques)} cliques >= min size {min_clique_size}")
        
        # 9. 랜덤하게 최대 클리크 선택
        selected_max_clique = random.choice(max_cliques) if max_cliques else []
        
        return {
            'max_clique': selected_max_clique,
            'all_cliques': all_max_cliques,
            'max_cliques': max_cliques,
            'valid_cliques': valid_cliques,
            'conflict_graph': {
                'nodes': G.number_of_nodes(),
                'edges': G.number_of_edges(),
                'max_size': max_size,
                'min_size': min_clique_size
            },
            'min_clique_size': min_clique_size
        }
    
    def place_clique_subjects(self,
                            clique_subjects: List[str],
                            subject_info_dict: Dict[str, Any],
                            slots: List[str],
                            slot_to_period_limit: Dict[str, int],
                            teacher_unavailable_dates: Dict[str, List[str]] = None,
                            subject_constraints: Dict[str, Dict[str, Any]] = None,
                            teacher_slot_constraints: Dict[str, Dict[str, Any]] = None,
                            current_assignments: Dict[str, List[str]] = None,
                            student_conflict_dict: Dict[str, List[str]] = None,
                            listening_conflict_dict: Dict[str, List[str]] = None,
                            teacher_conflict_dict: Dict[str, List[str]] = None,
                            student_subjects: Dict[str, List[str]] = None,
                            slot_to_day: Dict[str, str] = None,
                            hard_subjects: Dict[str, bool] = None) -> Dict[str, Any]:
        """
        클리크 과목들을 슬롯에 배치합니다.
        
        Args:
            clique_subjects: 배치할 클리크 과목들
            subject_info_dict: 과목 정보
            slots: 사용 가능한 슬롯들
            slot_to_period_limit: 슬롯별 시간 제한
            teacher_unavailable_dates: 교사 불가능 날짜
            subject_constraints: 과목별 제약조건
            teacher_slot_constraints: 교사 슬롯별 제약조건
            current_assignments: 현재 배치 상태
            
        Returns:
            Dict containing:
            - placed_subjects: 배치된 과목들 {subject: slot}
            - unplaced_subjects: 배치되지 않은 과목들
            - placement_details: 배치 상세 정보
        """
        self.logger.debug(f"Starting clique placement for {len(clique_subjects)} subjects")
        
        if not current_assignments:
            current_assignments = {}
        
        placed_subjects = {}
        unplaced_subjects = []
        placement_details = []
        
        # 이미 배치된 슬롯들 찾기 (다른 과목이 있는 슬롯)
        occupied_slots = {slot for slot, subjects in current_assignments.items() if subjects}
        empty_slots = [slot for slot in slots if slot not in occupied_slots]
        
        # 슬롯 우선순위: 이미 다른 과목이 있는 슬롯을 먼저 고려
        slot_priority = list(occupied_slots) + empty_slots
        
        for subject in clique_subjects:
            if subject not in subject_info_dict:
                self.logger.warning(f"Subject {subject} not found in subject_info_dict")
                unplaced_subjects.append(subject)
                continue
            
            # 해당 과목이 배치 가능한 슬롯들 찾기
            valid_slots = self._find_valid_slots_for_subject(
                subject, subject_info_dict, slot_priority, slot_to_period_limit,
                teacher_unavailable_dates, subject_constraints, teacher_slot_constraints,
                current_assignments, student_conflict_dict, listening_conflict_dict, teacher_conflict_dict,
                student_subjects, slot_to_day, hard_subjects
            )
            
            if valid_slots:
                # 랜덤하게 슬롯 선택
                selected_slot = random.choice(valid_slots)
                
                # 배치 실행
                if selected_slot not in current_assignments:
                    current_assignments[selected_slot] = []
                current_assignments[selected_slot].append(subject)
                placed_subjects[subject] = selected_slot
                
                # 배치 상세 정보 기록
                placement_details.append({
                    'subject': subject,
                    'slot': selected_slot,
                    'valid_slots_count': len(valid_slots),
                    'placement_strategy': 'occupied_slot' if selected_slot in occupied_slots else 'empty_slot'
                })
                
                self.logger.debug(f"Placed {subject} in {selected_slot}")
            else:
                unplaced_subjects.append(subject)
                placement_details.append({
                    'subject': subject,
                    'slot': None,
                    'valid_slots_count': 0,
                    'placement_strategy': 'failed'
                })
                self.logger.warning(f"Could not place {subject} - no valid slots")
        
        self.logger.debug(f"Clique placement completed: {len(placed_subjects)} placed, {len(unplaced_subjects)} unplaced")
        
        return {
            'placed_subjects': placed_subjects,
            'unplaced_subjects': unplaced_subjects,
            'placement_details': placement_details,
            'updated_assignments': current_assignments
        }
    
    def _find_valid_slots_for_subject(self,
                                    subject: str,
                                    subject_info_dict: Dict[str, Any],
                                    slot_priority: List[str],
                                    slot_to_period_limit: Dict[str, int],
                                    teacher_unavailable_dates: Dict[str, List[str]] = None,
                                    subject_constraints: Dict[str, Dict[str, Any]] = None,
                                    teacher_slot_constraints: Dict[str, Dict[str, Any]] = None,
                                    current_assignments: Dict[str, List[str]] = None,
                                    student_conflict_dict: Dict[str, List[str]] = None,
                                    listening_conflict_dict: Dict[str, List[str]] = None,
                                    teacher_conflict_dict: Dict[str, List[str]] = None,
                                    student_subjects: Dict[str, List[str]] = None,
                                    slot_to_day: Dict[str, str] = None,
                                    hard_subjects: Dict[str, bool] = None) -> List[str]:
        """
        특정 과목이 배치 가능한 슬롯들을 찾습니다.
        """
        valid_slots = []
        subject_info = subject_info_dict[subject]
        duration = subject_info.get('시간')
        
        for slot in slot_priority:
            # 1. 시간 제한 확인
            if duration is not None and duration > slot_to_period_limit.get(slot, 0):
                continue
            
            # 2. 교사 불가능 날짜 확인
            if teacher_unavailable_dates:
                teachers = subject_info.get('담당교사', [])
                for teacher in teachers:
                    if teacher in teacher_unavailable_dates and slot in teacher_unavailable_dates[teacher]:
                        break
                else:
                    continue  # 모든 교사가 가능한 경우에만 계속
            
            # 3. 과목별 제약조건 확인
            if subject_constraints and subject in subject_constraints:
                slot_constraints = subject_constraints[subject]
                standardized_slot = slot.replace('_', '')
                if standardized_slot in slot_constraints:
                    continue  # 제약조건에 의해 배치 불가
            
            # 4. 교사 슬롯별 제약조건 확인
            if teacher_slot_constraints:
                teachers = subject_info.get('담당교사', [])
                for teacher in teachers:
                    if teacher in teacher_slot_constraints:
                        slot_constraints = teacher_slot_constraints[teacher]
                        standardized_slot = slot.replace('_', '')
                        if standardized_slot in slot_constraints:
                            break  # 해당 교사가 이 슬롯에 배치 불가
                else:
                    continue  # 모든 교사가 가능한 경우에만 계속
            
            # 5. 충돌 확인 (기존 배치된 과목들과)
            if current_assignments and slot in current_assignments:
                existing_subjects = current_assignments[slot]
                if not self._check_conflicts_with_existing_subjects(subject, existing_subjects, 
                                                                   student_conflict_dict, listening_conflict_dict, teacher_conflict_dict):
                    continue
            
            # 6. 학생 부담 제약조건 확인
            if student_subjects and slot_to_day:
                if not self._check_student_burden_constraints(subject, slot, current_assignments, 
                                                            student_subjects, slot_to_day, hard_subjects, self.config):
                    continue
            
            # 모든 조건을 통과한 경우
            valid_slots.append(slot)
        
        return valid_slots
    
    def _check_conflicts_with_existing_subjects(self, 
                                              new_subject: str, 
                                              existing_subjects: List[str],
                                              student_conflict_dict: Dict[str, List[str]] = None,
                                              listening_conflict_dict: Dict[str, List[str]] = None,
                                              teacher_conflict_dict: Dict[str, List[str]] = None) -> bool:
        """
        새 과목이 기존 과목들과 충돌하지 않는지 확인합니다.
        충돌이 있으면 False, 없으면 True를 반환합니다.
        """
        for existing_subject in existing_subjects:
            # 학생 충돌 확인
            if student_conflict_dict:
                if (new_subject in student_conflict_dict and existing_subject in student_conflict_dict[new_subject]) or \
                   (existing_subject in student_conflict_dict and new_subject in student_conflict_dict[existing_subject]):
                    return False
            
            # 듣기평가 충돌 확인
            if listening_conflict_dict:
                if (new_subject in listening_conflict_dict and existing_subject in listening_conflict_dict[new_subject]) or \
                   (existing_subject in listening_conflict_dict and new_subject in listening_conflict_dict[existing_subject]):
                    return False
            
            # 교사 충돌 확인
            if teacher_conflict_dict:
                if (new_subject in teacher_conflict_dict and existing_subject in teacher_conflict_dict[new_subject]) or \
                   (existing_subject in teacher_conflict_dict and new_subject in teacher_conflict_dict[existing_subject]):
                    return False
        
        return True
    
    def _check_student_burden_constraints(self,
                                        new_subject: str,
                                        slot: str,
                                        current_assignments: Dict[str, List[str]],
                                        student_subjects: Dict[str, List[str]],
                                        slot_to_day: Dict[str, str],
                                        hard_subjects: Dict[str, bool] = None,
                                        config = None) -> bool:
        """
        새 과목을 해당 슬롯에 배치했을 때 학생 부담 제약조건을 위배하지 않는지 확인합니다.
        기존 _add_student_constraints 로직을 재사용합니다.
        """
        # 해당 슬롯의 날짜 확인
        day = slot_to_day.get(slot)
        if not day:
            return True  # 날짜 정보가 없으면 통과
        
        # 해당 날짜의 모든 슬롯들 찾기
        day_slots = [s for s in slot_to_day.keys() if slot_to_day[s] == day]
        
        # 해당 날짜에 이미 배치된 과목들 수집
        existing_subjects_today = []
        for day_slot in day_slots:
            if day_slot in current_assignments:
                existing_subjects_today.extend(current_assignments[day_slot])
        
        # 새 과목을 추가했을 때의 상황 시뮬레이션
        subjects_today_with_new = existing_subjects_today + [new_subject]
        
        # 각 학생별로 확인 (기존 _add_student_constraints와 동일한 로직)
        for student in student_subjects:
            # 해당 학생이 수강하는 과목들 중 해당 날짜에 배치될 과목들
            exams_today = [
                subject for subject in student_subjects[student]
                if subject in subjects_today_with_new
            ]
            
            # 사용할 config 객체 결정
            use_config = config if config is not None else self.config
            
            # 하루 최대 시험 수 제한 확인 (기존 로직과 동일)
            if hasattr(use_config, 'max_exams_per_day') and use_config.max_exams_per_day is not None:
                if len(exams_today) > use_config.max_exams_per_day:
                    self.logger.debug(f"Student {student} would have {len(exams_today)} exams on {day} (limit: {use_config.max_exams_per_day})")
                    return False
            
            # 하루 최대 어려운 시험 수 제한 확인 (기존 로직과 동일)
            if hasattr(use_config, 'max_hard_exams_per_day') and use_config.max_hard_exams_per_day is not None:
                hard_exams_today = [
                    subject for subject in exams_today
                    if hard_subjects and hard_subjects.get(subject, False)
                ]
                if len(hard_exams_today) > use_config.max_hard_exams_per_day:
                    self.logger.debug(f"Student {student} would have {len(hard_exams_today)} hard exams on {day} (limit: {use_config.max_hard_exams_per_day})")
                    return False

        return True
    
    def set_initial_solution_from_clique(self, clique_placements: Dict[str, str]):
        """
        클리크 배치 결과를 OR-Tools의 초기 해로 설정합니다.
        
        Args:
            clique_placements: {subject: slot} 형태의 클리크 배치 결과
        """
        self.logger.debug(f"Setting initial solution from clique placements: {clique_placements}")
        
        try:
            # 클리크로 배치된 과목들을 힌트로 설정
            for subject, slot in clique_placements.items():
                if subject in self.exam_slot_vars and slot in self.exam_slot_vars[subject]:
                    var = self.exam_slot_vars[subject][slot]
                    self.model.AddHint(var, 1)
                    self.logger.debug(f"Add hint: {subject} -> {slot} = 1")
            
            # 나머지 모든 변수들을 0으로 힌트 설정
            hint_count = 0
            for subject, var_dict in self.exam_slot_vars.items():
                for slot, var in var_dict.items():
                    if not (subject in clique_placements and clique_placements[subject] == slot):
                        self.model.AddHint(var, 0)
                        hint_count += 1
            
            self.logger.debug(f"Added {len(clique_placements)} clique hints and {hint_count} zero hints")
            
        except Exception as e:
            self.logger.error(f"Error setting initial solution: {e}")
    
    def create_schedule_with_clique_hint(self,
                                       subject_info_dict: Dict[str, Any],
                                       student_conflict_dict: Dict[str, List[str]],
                                       listening_conflict_dict: Dict[str, List[str]],
                                       teacher_conflict_dict: Dict[str, List[str]],
                                       teacher_unavailable_dates: Dict[str, List[str]],
                                       student_subjects: Dict[str, List[str]],
                                       slots: List[str],
                                       slot_to_day: Dict[str, str],
                                       slot_to_period_limit: Dict[str, int],
                                       hard_subjects: Dict[str, bool] = None,
                                       subject_constraints: Dict[str, Dict[str, Any]] = None,
                                       teacher_slot_constraints: Dict[str, Dict[str, Any]] = None,
                                       subject_conflicts: Dict[str, Dict[str, Any]] = None,
                                       fixed_assignments: Dict[str, List[str]] = None,
                                       time_limit: int = 10,
                                       status_callback=None) -> Tuple[str, Dict[str, Any]]:
        """
        클리크를 초기 해로 사용하여 자동배치를 실행합니다.
        """
        self.logger.info("Starting schedule creation with clique hint...")
        
        try:
            # 1. 최대 클리크 찾기
            if status_callback:
                status_callback("최대 클리크를 분석하고 있습니다...", 10)
            
            clique_result = self.find_maximum_cliques(
                subject_info_dict,
                student_conflict_dict,
                listening_conflict_dict,
                teacher_conflict_dict,
                fixed_assignments
            )
            
            clique_placements = {}
            if clique_result['max_clique']:
                self.logger.info(f"Found maximum clique with {len(clique_result['max_clique'])} subjects")
                
                # 2. 클리크 배치 (고정하지 않음)
                if status_callback:
                    status_callback("클리크 과목들을 배치하고 있습니다...", 20)
                
                placement_result = self.place_clique_subjects(
                    clique_result['max_clique'],
                    subject_info_dict,
                    slots,
                    slot_to_period_limit,
                    teacher_unavailable_dates,
                    subject_constraints,
                    teacher_slot_constraints,
                    fixed_assignments or {},
                    student_conflict_dict,
                    listening_conflict_dict,
                    teacher_conflict_dict,
                    student_subjects,
                    slot_to_day,
                    hard_subjects
                )
                
                clique_placements = placement_result['placed_subjects']
                self.logger.info(f"Placed {len(clique_placements)} clique subjects as hints")
            else:
                self.logger.info("No maximum clique found, proceeding without hints")
            
            # 3. 모델 구축
            if status_callback:
                status_callback("최적화 모델을 구축하고 있습니다...", 30)
            
            self.build_model(
                subject_info_dict,
                student_conflict_dict,
                listening_conflict_dict,
                teacher_conflict_dict,
                teacher_unavailable_dates,
                student_subjects,
                slots,
                slot_to_day,
                slot_to_period_limit,
                hard_subjects,
                subject_constraints,
                teacher_slot_constraints,
                subject_conflicts,
                fixed_assignments
            )
            
            # 4. 목적함수 설정
            if status_callback:
                status_callback("목적함수를 설정하고 있습니다...", 40)
            
            self.set_objective(student_subjects, slots, slot_to_day, hard_subjects)
            
            # 5. 클리크 배치를 초기 해로 설정 (모델에 힌트 추가)
            if clique_placements:
                if status_callback:
                    status_callback("클리크 힌트를 설정하고 있습니다...", 50)
                self.set_initial_solution_from_clique(clique_placements)
            
            # 6. 솔버 초기화
            self.solver = cp_model.CpSolver()
            self.solver.parameters.max_time_in_seconds = time_limit
            self.logger.debug(f"Solver initialized for clique hint schedule")
            
            # 7. 솔버 실행 (클리크 배치가 변경될 수 있음)
            if status_callback:
                status_callback("최적화를 실행하고 있습니다...", 60)
            
            self.logger.debug("About to call solve() method")
            try:
                status, result = self.solve(time_limit, status_callback)
                self.logger.debug(f"Solve completed with status: {status}")
            except Exception as e:
                self.logger.error(f"Error in solve method: {e}")
                raise
            
            # 7. 결과에 클리크 정보 추가
            if status == "SUCCESS" and result:
                result['clique_info'] = {
                    'max_clique_size': len(clique_result['max_clique']) if clique_result['max_clique'] else 0,
                    'max_clique_subjects': clique_result['max_clique'],
                    'placed_as_hints': len(clique_placements),
                    'clique_placements': clique_placements
                }
            
            return status, result
            
        except Exception as e:
            self.logger.error(f"Error in create_schedule_with_clique_hint: {e}")
            return "ERROR", {"error": str(e)}