#!/usr/bin/env python3
"""
요약 생성 기능 테스트 스크립트
"""

import json
from exam_scheduler_app import ExamSchedulerApp
from config import ExamSchedulingConfig

def test_summary_generation():
    """요약 생성 기능을 테스트합니다."""
    
    # 설정 로드
    config = ExamSchedulingConfig()
    
    # 앱 초기화
    app = ExamSchedulerApp(config, data_dir=".")
    
    # 데이터 로드
    print("데이터 로딩 중...")
    if not app.load_all_data():
        print("데이터 로드 실패")
        return
    
    print("데이터 로드 완료")
    
    # 스케줄 생성
    print("스케줄 생성 중...")
    status, result = app.create_schedule(time_limit=120)
    
    print(f"스케줄 생성 결과: {status}")
    print(f"결과 구조: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
    
    if status == "SUCCESS":
        # 결과 저장
        app.save_results(result)
        
        # 저장된 결과 확인
        try:
            with open("results/schedule_summary.json", "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:  # Only try to parse if file has content
                    summary = json.loads(content)
                else:
                    print("요약 파일이 비어있습니다.")
                    return
            
            print("\n=== 요약 결과 ===")
            print(f"상태: {summary.get('status')}")
            print(f"총 슬롯 수: {summary.get('total_slots_used')}")
            print(f"총 과목 수: {summary.get('total_subjects')}")
            print(f"학생 수: {summary.get('total_students')}")
            print(f"일별 분포: {summary.get('daily_distribution')}")
            print(f"교시별 분포: {summary.get('period_distribution')}")
            print(f"어려운 시험 수: {summary.get('hard_exams_count')}")
            print(f"하루 3과목 이상 시험: {summary.get('students_with_3_exams_per_day')}명")
            print(f"하루 어려운 시험 2과목 이상: {summary.get('students_with_2_hard_exams_per_day')}명")
            
            # 디버깅: 학생별 시험 배정 확인
            print("\n=== 학생별 시험 배정 디버깅 ===")
            slot_assignments = result.get('slot_assignments', {})
            if app.enrollment_data:
                student_conflict_dict, _, student_names, enroll_bool = app.enrollment_data
                
                # 첫 3명 학생에 대해 디버깅
                for i, student in enumerate(student_names[:3] if student_names else []):
                    print(f"\n학생 {student}:")
                    
                    # 학생이 수강하는 시험 대상 과목
                    student_exam_subjects = []
                    if enroll_bool is not None:
                        for subject in enroll_bool.columns:
                            if enroll_bool.loc[student, subject] is True and subject in (app.subject_info or {}):
                                student_exam_subjects.append(subject)
                    
                    print(f"  수강 과목: {student_exam_subjects}")
                    
                    # 학생별로 실제 시험 배정 정보 생성
                    student_exam_slots = {}
                    for slot, subjects in slot_assignments.items():
                        day = slot.split('교시')[0]
                        if day not in student_exam_slots:
                            student_exam_slots[day] = []
                        
                        for subject in subjects:
                            if subject in student_exam_subjects:
                                student_exam_slots[day].append(subject)
                    
                    print(f"  일별 시험: {student_exam_slots}")
                    
                    # 일별 시험 수
                    daily_exam_counts = {day: len(subjects) for day, subjects in student_exam_slots.items()}
                    print(f"  일별 시험 수: {daily_exam_counts}")
                    
                    # 최대 시험 수
                    max_exam = max(daily_exam_counts.values()) if daily_exam_counts else 0
                    print(f"  최대 시험 수: {max_exam}")

            print("\n=== enroll_bool.index/student_names 비교 ===")
            print('enroll_bool.index 샘플:', list(enroll_bool.index)[:10])
            print('student_names 샘플:', student_names[:10])
            
            print('\nenroll_bool 샘플:')
            for student in list(enroll_bool.index)[:5]:
                print(student, [enroll_bool.loc[student, subject] for subject in enroll_bool.columns[:5]])
            
            print('\nenroll_bool.columns 샘플:', list(enroll_bool.columns)[:10])
            print('subject_info.keys 샘플:', list(app.subject_info.keys())[:10])
            
            common_subjects = set(enroll_bool.columns) & set(app.subject_info.keys())
            print('enroll_bool과 subject_info의 교집합:', common_subjects)
            print('교집합 개수:', len(common_subjects))
            
            print('교집합 과목별 True 값 학생 수:')
            for subject in list(common_subjects)[:10]:
                true_count = enroll_bool[subject].sum()
                print(f'{subject}: {true_count}')
            
            print('\n=== 학생별 수강 과목 추출 디버깅 ===')
            for i, student in enumerate(student_names[:3]):  # 앞 3명만 테스트
                s = str(student).strip()
                print(f'\n학생 {i+1}: {student} (변환: {s})')
                
                # enroll_bool 인덱스에 실제로 존재하는지 확인
                if s in enroll_bool.index:
                    print(f'  ✓ enroll_bool.index에 존재')
                    
                    # 시험 대상 과목 중 True인 것들 찾기
                    valid_subjects = [subject for subject in enroll_bool.columns if subject in (app.subject_info or {})]
                    student_exam_subjects = []
                    
                    print(f'  시험 대상 과목 수: {len(valid_subjects)}')
                    true_count = 0
                    for subject in valid_subjects:
                        try:
                            value = enroll_bool.loc[s, subject]
                            if value:
                                student_exam_subjects.append(subject)
                                true_count += 1
                        except Exception as e:
                            print(f'    {subject}: 오류 - {e}')
                    
                    print(f'  True인 과목 수: {true_count}')
                    print(f'  최종 수강 과목: {student_exam_subjects[:5]}...')  # 앞 5개만 출력
                else:
                    print(f'  ✗ enroll_bool.index에 존재하지 않음')
                    print(f'  enroll_bool.index 샘플: {list(enroll_bool.index)[:5]}')
            
            print('\n=== 4일차 생명과학II + 물리학II 수강 학생 확인 ===')
            if enroll_bool is not None:
                # 생명과학II와 물리학II를 모두 수강하는 학생들
                both_students = enroll_bool.index[(enroll_bool['생명과학II']) & (enroll_bool['물리학II'])].tolist()
                print(f'생명과학II + 물리학II 모두 수강하는 학생 수: {len(both_students)}')
                print(f'앞 5명: {both_students[:5]}')
                
                # 이 학생들이 실제로 4일차에 시험을 치는지 확인
                for student in both_students[:3]:  # 앞 3명만 확인
                    s = str(student).strip()
                    student_exam_subjects = []
                    if enroll_bool is not None:
                        for subject in ['생명과학II', '물리학II']:
                            if bool(enroll_bool.loc[s, subject]):
                                student_exam_subjects.append(subject)
                    
                    print(f'\n학생 {student}:')
                    print(f'  수강 과목: {student_exam_subjects}')
                    
                    # 4일차 시험 확인
                    day4_exams = []
                    for slot, subjects in slot_assignments.items():
                        if slot.startswith('제4일'):
                            for subject in subjects:
                                if subject in student_exam_subjects:
                                    day4_exams.append(f'{slot}: {subject}')
                    
                    print(f'  4일차 시험: {day4_exams}')
                    
                    # 어려운 시험 여부 확인
                    hard_exams = []
                    for exam in day4_exams:
                        subject = exam.split(': ')[1]
                        if app.subject_info and app.subject_info.get(subject, {}).get('시간', 0) >= app.config.hard_exam_threshold:
                            hard_exams.append(exam)
                    
                    print(f'  4일차 어려운 시험: {hard_exams}')
                    print(f'  4일차 어려운 시험 수: {len(hard_exams)}')
                    
                    # 추가 디버깅: slot_assignments에서 4일차 과목들 확인
                    print(f'  \\n=== 4일차 slot_assignments 디버깅 ===')
                    for slot, subjects in slot_assignments.items():
                        if slot.startswith('제4일'):
                            print(f'    {slot}: {subjects}')
                            for subject in subjects:
                                if subject in ['생명과학II', '물리학II']:
                                    print(f'      ✓ {subject} 발견!')
                    
                    # 학생의 수강 과목과 slot_assignments의 과목 매칭 확인
                    print(f'  \\n=== 과목 매칭 디버깅 ===')
                    print(f'    학생 수강 과목: {student_exam_subjects}')
                    print(f'    slot_assignments의 생명과학II: {any("생명과학II" in subjects for subjects in slot_assignments.values())}')
                    print(f'    slot_assignments의 물리학II: {any("물리학II" in subjects for subjects in slot_assignments.values())}')
                    
                    # 정확한 매칭 확인
                    for slot, subjects in slot_assignments.items():
                        if slot.startswith('제4일'):
                            for subject in subjects:
                                if subject in student_exam_subjects:
                                    print(f'    ✓ 매칭 성공: {slot} - {subject}')
                                else:
                                    print(f'    ✗ 매칭 실패: {slot} - {subject} (학생이 수강하지 않음)')
                    
                    # 2일차 시험 확인 (실제 배정된 날)
                    print(f'  \\n=== 2일차 시험 확인 ===')
                    day2_exams = []
                    for slot, subjects in slot_assignments.items():
                        if slot.startswith('제2일'):
                            for subject in subjects:
                                if subject in student_exam_subjects:
                                    day2_exams.append(f'{slot}: {subject}')
                    
                    print(f'  2일차 시험: {day2_exams}')
                    
                    # 2일차 어려운 시험 여부 확인
                    day2_hard_exams = []
                    for exam in day2_exams:
                        subject = exam.split(': ')[1]
                        if app.subject_info and app.subject_info.get(subject, {}).get('시간', 0) >= app.config.hard_exam_threshold:
                            day2_hard_exams.append(exam)
                    
                    print(f'  2일차 어려운 시험: {day2_hard_exams}')
                    print(f'  2일차 어려운 시험 수: {len(day2_hard_exams)}')
                    
                    # 물리학II가 어느 날에 배정되어 있는지 확인
                    print(f'  \\n=== 물리학II 배정 확인 ===')
                    for slot, subjects in slot_assignments.items():
                        if '물리학II' in subjects:
                            print(f'    물리학II 배정: {slot} - {subjects}')
                    
                    # 해당 날짜의 시험 확인
                    physics_day = None
                    for slot, subjects in slot_assignments.items():
                        if '물리학II' in subjects:
                            physics_day = slot[:slot.find('교시')]
                            break
                    
                    if physics_day:
                        print(f'  \\n=== {physics_day} 시험 확인 ===')
                        day_exams = []
                        for slot, subjects in slot_assignments.items():
                            if slot.startswith(physics_day):
                                for subject in subjects:
                                    if subject in student_exam_subjects:
                                        day_exams.append(f'{slot}: {subject}')
                        
                        print(f'  {physics_day} 시험: {day_exams}')
                        
                        # 어려운 시험 여부 확인
                        day_hard_exams = []
                        for exam in day_exams:
                            subject = exam.split(': ')[1]
                            if app.subject_info and app.subject_info.get(subject, {}).get('시간', 0) >= app.config.hard_exam_threshold:
                                day_hard_exams.append(exam)
                        
                        print(f'  {physics_day} 어려운 시험: {day_hard_exams}')
                        print(f'  {physics_day} 어려운 시험 수: {len(day_hard_exams)}')
            
        except Exception as e:
            print(f"요약 파일 읽기 오류: {e}")
    else:
        print(f"스케줄 생성 실패: {result}")

if __name__ == "__main__":
    test_summary_generation() 