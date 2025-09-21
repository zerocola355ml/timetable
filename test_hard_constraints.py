#!/usr/bin/env python3
"""
하드 과목 제약조건 테스트 스크립트
"""

import json
import os
from config import ExamSchedulingConfig
from exam_scheduler_app import ExamSchedulerApp

def test_hard_constraints():
    """하드 과목 제약조건을 테스트합니다."""
    
    # 설정 생성 (max_hard_exams_per_day = 1)
    config = ExamSchedulingConfig(
        max_exams_per_day=3,
        max_hard_exams_per_day=1,
        hard_exam_threshold=60
    )
    
    print(f"Config: max_hard_exams_per_day = {config.max_hard_exams_per_day}")
    
    # 애플리케이션 초기화
    app = ExamSchedulerApp(config=config, data_dir="uploads")
    
    # 데이터 로드
    print("Loading data...")
    if not app.load_all_data():
        print("Failed to load data")
        return
    
    print("Data loaded successfully")
    
    # 하드 과목 설정 로드
    hard_subjects = app._load_hard_subjects_config()
    print(f"Hard subjects loaded: {hard_subjects}")
    
    # 몇 개 과목이 하드로 설정되어 있는지 확인
    hard_count = sum(1 for is_hard in hard_subjects.values() if is_hard)
    print(f"Total hard subjects: {hard_count}")
    
    # 시험 슬롯 생성
    print("Creating exam slots...")
    slots = app.scheduler.create_slots(app.exam_info)
    print(f"Created {len(slots)} slots: {slots}")
    
    if not slots:
        print("No slots created!")
        return
    
    # 슬롯 매핑 생성
    slot_to_day, slot_to_period_limit = app.scheduler.create_slot_mappings(slots, app.exam_info)
    print(f"Slot to day mapping: {slot_to_day}")
    
    # 모델 구축 (디버그 출력 포함)
    print("Building model...")
    app.scheduler.build_model(
        subject_info_dict=app.subject_info_dict,
        student_conflict_dict=app.student_conflict_dict,
        listening_conflict_dict=app.listening_conflict_dict,
        teacher_conflict_dict=app.teacher_conflict_dict,
        teacher_unavailable_dates=app.teacher_unavailable_dates,
        student_subjects=app.student_subjects,
        slots=slots,
        slot_to_day=slot_to_day,
        slot_to_period_limit=slot_to_period_limit,
        hard_subjects=hard_subjects
    )
    
    # 목적함수 설정
    print("Setting objective...")
    app.scheduler.set_objective(app.student_subjects, slots, slot_to_day, hard_subjects)
    
    print("Model built successfully!")
    print("You can now check the debug output above to see if hard subject constraints are properly set.")

if __name__ == "__main__":
    test_hard_constraints()
