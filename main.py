# ------------------ Day13(25.06.23) ------------------
from ortools.sat.python import cp_model
import pandas as pd
import itertools
import json

# ---------------------------
# 1. 데이터 로드 (이전 코드 그대로)
# ---------------------------

### 분반배정표 읽기

# 1. 데이터 읽기 (C14부터 유효 데이터)
file = 'bunbanbaejeongpyo.xlsx'
sheet = '분반배정표'

# 과목명: 1행 C열부터
df_header = pd.read_excel(file, sheet_name=sheet, header=None, nrows=1)
subject_cols = df_header.iloc[0, 2:].tolist()  # C열부터 끝까지

# 학생명: A열 14행부터
df_students = pd.read_excel(file, sheet_name=sheet, header=None)
student_rows = df_students.iloc[13:, :]  # 0-based index, 14행부터
student_names = student_rows.iloc[:, 0].tolist()  # A열

# 수강 데이터: 14행부터, C열부터
enroll_matrix = student_rows.iloc[:, 2:]
enroll_matrix.columns = subject_cols
enroll_matrix.index = student_names

# 빈값 미수강, 아니면 수강
enroll_bool = ~enroll_matrix.isna()

# 1번 딕셔너리: 과목별로 겹칠 수 없는 과목 리스트
student_conflict_dict = {subj: [] for subj in subject_cols}

# 2번 딕셔너리: {A: {B: [학생1, 학생2, ...]}}
double_enroll_dict = {subj: {} for subj in subject_cols}

# 모든 과목 쌍에 대해 검사
for subj1, subj2 in itertools.combinations(subject_cols, 2):
    # 두 과목을 모두 듣는 학생 리스트
    both_students = enroll_bool.index[(enroll_bool[subj1]) & (enroll_bool[subj2])].tolist()
    if both_students:
        # 1번: conflict_dict에 양방향 추가
        student_conflict_dict[subj1].append(subj2)
        student_conflict_dict[subj2].append(subj1)
        # 2번: double_enroll_dict에 양방향 추가
        double_enroll_dict[subj1][subj2] = both_students
        double_enroll_dict[subj2][subj1] = both_students

# 결과 예시 출력
# print("1. 과목별 겹칠 수 없는 과목 리스트 예시:")
# for k, v in list(conflict_dict.items())[:5]:
#     print(f"{k}: {v[:5]}... (총 {len(v)}개)")
#
# print("\n2. 두 과목을 동시에 듣는 학생 딕셔너리 예시:")
# for k, v in list(double_enroll_dict.items())[:2]:
#     for k2, v2 in list(v.items())[:2]:
#         print(f"{k} & {k2}: {v2[:5]}... (총 {len(v2)}명)")

# 필요시 저장
with open('학생_충돌_딕셔너리.json', 'w', encoding='utf-8') as f:
    json.dump(student_conflict_dict, f, ensure_ascii=False, indent=2)
with open('과목쌍_공동수강학생_딕셔너리.json', 'w', encoding='utf-8') as f:
    json.dump(double_enroll_dict, f, ensure_ascii=False, indent=2)


### 시험 범위 읽기
# 파일 및 시트명
file = '시험 범위.xlsx'
sheet = 0  # 첫 시트라면 0, 아니면 이름 입력

# 데이터 읽기 (C열 3행부터)
df = pd.read_excel(file, sheet_name=sheet, header=None)

# 과목명 추출 (C열 3행부터)
subject_names = df.iloc[2:, 2].dropna().astype(str).tolist()

# 과목 정보 딕셔너리
subject_info_dict = {}

for idx, subject in enumerate(subject_names):
    row_idx = idx + 2  # 0-based index, 실제 엑셀 3행부터 시작

    # F열: 시간
    time_val = df.iloc[row_idx, 5]
    if pd.isna(time_val):
        time_processed = None
    elif isinstance(time_val, str):
        try:
            time_processed = int(time_val)
        except ValueError:
            time_processed = time_val  # 변환 불가시 원본 저장
    else:
        time_processed = int(time_val)

    # G열: 듣기
    listen_val = df.iloc[row_idx, 6]
    if str(listen_val).strip().upper() in ['X', '0', '']:
        listen_processed = 0
    elif str(listen_val).strip().upper() in ['O', '1']:
        listen_processed = 1
    else:
        listen_processed = 0

    # H열: 자율
    self_val = df.iloc[row_idx, 7]
    if str(self_val).strip().upper() in ['X', '0', '']:
        self_processed = 0
    elif str(self_val).strip().upper() in ['O', '1']:
        self_processed = 1
    else:
        self_processed = 0

    # N열: 학년
    grade_val = df.iloc[row_idx, 13]

    # J~M열: 담당교사
    teacher_cells = df.iloc[row_idx, 9:13]
    teacher_list = []
    for cell in teacher_cells:
        if pd.isna(cell):
            continue
        # 콤마로 분리
        teachers = [t.strip() for t in str(cell).split(',') if t.strip()]
        teacher_list.extend(teachers)

    # 딕셔너리 저장
    subject_info_dict[subject] = {
        '시간': time_processed,
        '듣기': listen_processed,
        '자율': self_processed,
        '학년': grade_val,
        '담당교사': teacher_list
    }

# 결과 예시 출력
# for subj, info in list(subject_info_dict.items())[:5]:
#     print(f"{subj}: {info}")

# 필요시 저장
with open('subject_info.json', 'w', encoding='utf-8') as f:
    json.dump(subject_info_dict, f, ensure_ascii=False, indent=2)


# 1. 듣기평가가 있는 과목 리스트 추출
listening_subjects = [subject for subject, info in subject_info_dict.items() if info['듣기'] == 1]

# 2. 듣기평가 충돌 딕셔너리 생성
listening_conflict_dict = {subject: [] for subject in listening_subjects}
for subj1, subj2 in itertools.combinations(listening_subjects, 2):
    listening_conflict_dict[subj1].append(subj2)
    listening_conflict_dict[subj2].append(subj1)

# 3. 담당교사 충돌 딕셔너리 생성
teacher_conflict_dict = {subject: [] for subject in subject_info_dict}
subjects = list(subject_info_dict.keys())
for i, subj1 in enumerate(subjects):
    teachers1 = set(subject_info_dict[subj1]['담당교사'])
    for subj2 in subjects[i+1:]:
        teachers2 = set(subject_info_dict[subj2]['담당교사'])
        if teachers1 & teachers2:  # 교사가 겹치면
            teacher_conflict_dict[subj1].append(subj2)
            teacher_conflict_dict[subj2].append(subj1)

# 4. 예시 출력
# print("\n듣기평가 충돌 listening_conflict_dict 예시:")
# for subj, conflicts in list(listening_conflict_dict.items())[:5]:
#     print(f"{subj}: {conflicts}")
#
# print("\n담당교사 충돌 teacher_conflict_dict 예시:")
# for subj, conflicts in list(teacher_conflict_dict.items())[:5]:
#     print(f"{subj}: {conflicts}")

# 5. 필요시 저장
with open('listening_conflict_dict.json', 'w', encoding='utf-8') as f:
    json.dump(listening_conflict_dict, f, ensure_ascii=False, indent=2)
with open('teacher_conflict_dict.json', 'w', encoding='utf-8') as f:
    json.dump(teacher_conflict_dict, f, ensure_ascii=False, indent=2)

### 시험 정보.xlsx 읽기
file = '시험 정보.xlsx'
sheet = 0  # 첫 시트라면 0, 아니면 시트명 입력

# 1. 파일 전체 읽기 (헤더 없이)
df = pd.read_excel(file, sheet_name=sheet, header=None)

# 2. 1~3행: 년, 학기, 고사 종류
exam_year = str(df.iloc[0, 1]).strip()    # 1행 B열
exam_semester = str(df.iloc[1, 1]).strip()  # 2행 B열
exam_type = str(df.iloc[2, 1]).strip()    # 3행 B열

# 3. 4~9행: 제1일~제6일 시험 날짜
exam_dates = {}
for i in range(6):  # 0~5
    day_label = str(df.iloc[3 + i, 0]).strip()   # 4~9행 A열: '제1일', '제2일', ...
    date_val = str(df.iloc[3 + i, 1]).strip()   # 4~9행 B열: '6월 14일' 등
    exam_dates[day_label] = date_val

# 4. 10~33행: 각 시험 타임(제n일 m교시)의 시작/종료/진행시간
exam_times = {}
for i in range(24):  # 0~23
    row = 9 + i  # 10~33행
    time_label = str(df.iloc[row, 0]).strip()  # A열: '제1일1교시' 등
    start_time = str(df.iloc[row, 1]).strip()  # B열: 시작시간
    end_time = str(df.iloc[row, 2]).strip()    # C열: 종료시간
    duration = int(df.iloc[row, 3]) if not pd.isna(df.iloc[row, 3]) else None  # D열: 진행시간(분)
    exam_times[time_label] = {
        '시작': start_time,
        '종료': end_time,
        '진행시간': duration
    }

# 5. 결과 예시 출력
# print(f"학년도: {exam_year}")
# print(f"학기: {exam_semester}")
# print(f"고사 종류: {exam_type}")
# print(f"시험 날짜: {exam_dates}")
# print("시험 타임 예시:")
# for k, v in list(exam_times.items())[:3]:
#     print(f"{k}: {v}")

# 6. 딕셔너리로 묶어서 저장(필요시)
exam_info = {
    '학년도': exam_year,
    '학기': exam_semester,
    '고사종류': exam_type,
    '시험날짜': exam_dates,
    '시험타임': exam_times
}

import json
with open('exam_info.json', 'w', encoding='utf-8') as f:
    json.dump(exam_info, f, ensure_ascii=False, indent=2)

### 시험 불가 교사 읽기
# 파일 읽기
file = '시험 불가 교사.xlsx'
sheet = 0  # 첫 시트라면 0, 아니면 시트명 입력

df = pd.read_excel(file, sheet_name=sheet, header=None)

# A2부터 아래로 교사명
teacher_names = df.iloc[1:, 0].dropna().astype(str).tolist()

# B~Y열: 24개 슬롯 (제1일1교시~제6일4교시)
slot_codes = [
    f'{day}{period}교시'
    for day in range(1, 7)       # 1~6일
    for period in range(1, 5)    # 1~4교시
]
# ['11교시', '12교시', ..., '64교시']

# 제n일m교시 → '제n일m교시'
slot_labels = [f'제{code[0]}일{code[1]}교시' for code in slot_codes]

# # 실제로는 ['제1일1교시', '제1일2교시', ...] 형태
# slot_labels = []
# for day in range(1, 7):
#     for period in range(1, 5):
#         slot_labels.append(f'제{day}일{period}교시')

teacher_unavailable_dates = {}

for i, teacher in enumerate(teacher_names):
    # B~Y열 (1~24)
    unavailable_slots = []
    for j, slot_label in enumerate(slot_labels):
        val = df.iloc[i+1, j+1]  # i+1: 데이터는 2행부터, j+1: B열부터
        if not pd.isna(val) and int(val) == 1:
            unavailable_slots.append(slot_label)
    teacher_unavailable_dates[teacher] = unavailable_slots

# 저장
with open('teacher_unavailable_dates.json', 'w', encoding='utf-8') as f:
    json.dump(teacher_unavailable_dates, f, ensure_ascii=False, indent=2)

# ---------------------------
# 2. 변수 선언
# ---------------------------
# subjects, subject_info_dict, student_conflict_dict, listening_conflict_dict, teacher_conflict_dict
# exam_times, exam_dates, student_names, enroll_bool

# ---------------------------
# 2. 시험 슬롯/타임 정의
# ---------------------------
# 5일 × 3교시 = 15개 슬롯
days = list(exam_dates.keys())[:5]  # ['제1일', ..., '제5일']
periods = ['1교시', '2교시', '3교시']
slots = [f'{day}{period}' for day in days for period in periods]
max_num_of_exam_for_student = 3 # 학생별 하루 최대 시험 개수
max_num_of_hard_exam_for_student = 2 # 학생별 하루 최대 60분 이상 시험 개수
hard_exam_period = 60 # 어려운 시험 기준은 60분

# 각 slot별 허용 최대 시간(분)
slot_to_period_limit = {}
for slot in slots:
    period = slot[-3:]  # '1교시', '2교시', '3교시'
    if period == '1교시':
        slot_to_period_limit[slot] = 80
    elif period == '2교시':
        slot_to_period_limit[slot] = 50
    elif period == '3교시':
        slot_to_period_limit[slot] = 100

# slot -> day 매핑
slot_to_day = {slot: slot[:3] for slot in slots}

# ---------------------------
# 3. OR-Tools 모델 생성
# ---------------------------
model = cp_model.CpModel()

# 변수 생성 (시간 제한 미리 필터링)
exam_slot_vars = {}
for subject in subject_info_dict.keys():
    duration = subject_info_dict[subject]['시간']
    valid_slots = [
        slot for slot in slots
        if duration is None or duration <= slot_to_period_limit[slot]
    ]
    exam_slot_vars[subject] = {
        slot: model.NewBoolVar(f'{subject}_{slot}')
        for slot in valid_slots
    }

# 제약조건: 각 과목 1회 배정
for subject, var_dict in exam_slot_vars.items():
    model.Add(sum(var_dict.values()) == 1)

# 제약조건: 충돌 방지 (수정 버전)
for slot in slots:
    # 현재 슬롯에 변수가 존재하는 과목들만 필터링
    subjects_in_slot = [
        subj for subj, var_dict in exam_slot_vars.items()
        if slot in var_dict
    ]

    for i in range(len(subjects_in_slot)):
        subj1 = subjects_in_slot[i]
        # 학생 충돌
        for conflict in student_conflict_dict.get(subj1, []):
            if conflict in exam_slot_vars and slot in exam_slot_vars[conflict]:
                if subj1 < conflict:
                    model.Add(
                        exam_slot_vars[subj1][slot] +
                        exam_slot_vars[conflict][slot] <= 1
                    )
        # 듣기 충돌
        for conflict in listening_conflict_dict.get(subj1, []):
            if conflict in exam_slot_vars and slot in exam_slot_vars[conflict]:
                if subj1 < conflict:
                    model.Add(
                        exam_slot_vars[subj1][slot] +
                        exam_slot_vars[conflict][slot] <= 1
                    )
        # 교사 충돌
        for conflict in teacher_conflict_dict.get(subj1, []):
            if conflict in exam_slot_vars and slot in exam_slot_vars[conflict]:
                if subj1 < conflict:
                    model.Add(
                        exam_slot_vars[subj1][slot] +
                        exam_slot_vars[conflict][slot] <= 1
                    )

# (3) slot별 시간 제한 (1교시: 80분, 2교시: 50분, 3교시: 100분)
for subject in subject_info_dict.keys():
    duration = subject_info_dict[subject]['시간']
    for slot in slots:
        if slot not in exam_slot_vars[subject]:
            continue  # 변수 자체가 없으면 건너뜀
        if duration is not None and duration > slot_to_period_limit[slot]:
            model.Add(exam_slot_vars[subject][slot] == 0)

# (4) 교사별 불가능 날짜 반영
for subject in subject_info_dict.keys():
    teachers = subject_info_dict[subject]['담당교사']
    for teacher in teachers:
        if teacher not in teacher_unavailable_dates:
            continue
        for slot in teacher_unavailable_dates[teacher]:
            if slot in exam_slot_vars[subject]:
                model.Add(exam_slot_vars[subject][slot] == 0)

# (5) 학생별 하루 시험 수/60분 이상 시험수 제한
student_subjects = {
    student: [subject for subject in subject_info_dict.keys() if enroll_bool.loc[student, subject]]
    for student in student_names if student in enroll_bool.index
}

# 하루에 최대 3과목, 60분 이상 과목은 최대 2개
for student in student_subjects:
    for day in days:
        exams_today = [
            exam_slot_vars[subject][slot]
            for subject in student_subjects[student]
            for slot in slots
            if slot_to_day[slot] == day and slot in exam_slot_vars[subject]
        ]
        model.Add(sum(exams_today) <= max_num_of_exam_for_student)

        long_exams_today = [
            exam_slot_vars[subject][slot]
            for subject in student_subjects[student]
            for slot in slots
            if (
                slot_to_day[slot] == day
                and subject_info_dict[subject]['시간'] is not None
                and subject_info_dict[subject]['시간'] >= hard_exam_period
                and slot in exam_slot_vars[subject]
            )
        ]
        model.Add(sum(long_exams_today) <= max_num_of_hard_exam_for_student)


# ---------------------------
# 5. 목적함수 (max_num_of_exam_for_student, max_num_of_hard_exam_for_student 최소화)
# ---------------------------


students_with_m = []
students_with_n = []

for student in student_subjects:
    # 각 학생의 day별 시험 수, 60분 이상 시험 수
    exams_per_day = []
    long_exams_per_day = []
    for day in days:
        exams_today = [
            exam_slot_vars[subject][slot]
            for subject in student_subjects[student]
            for slot in slots
            if slot_to_day[slot] == day and slot in exam_slot_vars[subject]
        ]
        long_exams_today = [
            exam_slot_vars[subject][slot]
            for subject in student_subjects[student]
            for slot in slots
            if (
                slot_to_day[slot] == day
                and subject_info_dict[subject]['시간'] is not None
                and subject_info_dict[subject]['시간'] >= hard_exam_period
                and slot in exam_slot_vars[subject]
            )
        ]
        exams_per_day.append(sum(exams_today))
        long_exams_per_day.append(sum(long_exams_today))
    max_exam = model.NewIntVar(0, max_num_of_exam_for_student, f'max_exam_{student}')
    max_long_exam = model.NewIntVar(0, max_num_of_hard_exam_for_student, f'max_long_exam_{student}')
    model.AddMaxEquality(max_exam, exams_per_day)
    model.AddMaxEquality(max_long_exam, long_exams_per_day)
    # m, n값 학생 수 변수
    is_m = model.NewBoolVar(f'is_m_{student}')
    is_n = model.NewBoolVar(f'is_n_{student}')
    model.Add(max_exam == max_num_of_exam_for_student).OnlyEnforceIf(is_m)
    model.Add(max_exam != max_num_of_exam_for_student).OnlyEnforceIf(is_m.Not())
    model.Add(max_long_exam == max_num_of_hard_exam_for_student).OnlyEnforceIf(is_n)
    model.Add(max_long_exam != max_num_of_hard_exam_for_student).OnlyEnforceIf(is_n.Not())
    students_with_m.append(is_m)
    students_with_n.append(is_n)


model.Minimize(sum(students_with_m) + sum(students_with_n))

# ---------------------------
# 6. 풀이 및 결과 출력
# ---------------------------
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 120  # 시간 제한
status = solver.Solve(model)

if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
    print("시험 시간표 배정 결과:")
    for slot in slots:
        assigned_subjects = [
            subject for subject in subject_info_dict.keys()
            if slot in exam_slot_vars[subject] and solver.Value(exam_slot_vars[subject][slot])
        ]
        if assigned_subjects:
            print(f"{slot}: {', '.join(assigned_subjects)}")

    # print("\n학생별 하루 최대 시험 수/60분 이상 시험 수:")
    # 학생별 day별 시험수, 60분 이상 시험수 저장
    student_max_per_day = {}
    student_max_long_per_day = {}
    student_exam_subjects_per_day = {}
    student_long_exam_subjects_per_day = {}

    for student in student_subjects:
        exams_per_day = []
        long_exams_per_day = []
        exam_subjects_per_day = []
        long_exam_subjects_per_day = []
        for day in days:
            # 오늘 배정된 과목
            subjects_today = [
                subject for subject in student_subjects[student]
                for slot in slots
                if slot_to_day[slot] == day and slot in exam_slot_vars[subject]
                and solver.Value(exam_slot_vars[subject][slot])
            ]
            exams_today = len(subjects_today)
            # 오늘 배정된 60분 이상 과목
            long_subjects_today = [
                subject for subject in student_subjects[student]
                for slot in slots
                if (
                    slot_to_day[slot] == day
                    and subject_info_dict[subject]['시간'] is not None
                    and subject_info_dict[subject]['시간'] >= hard_exam_period
                    and slot in exam_slot_vars[subject]
                    and solver.Value(exam_slot_vars[subject][slot])
                )
            ]
            long_exams_today = len(long_subjects_today)
            exams_per_day.append(exams_today)
            long_exams_per_day.append(long_exams_today)
            exam_subjects_per_day.append(subjects_today)
            long_exam_subjects_per_day.append(long_subjects_today)
        student_max_per_day[student] = max(exams_per_day)
        student_max_long_per_day[student] = max(long_exams_per_day)
        student_exam_subjects_per_day[student] = exam_subjects_per_day
        student_long_exam_subjects_per_day[student] = long_exam_subjects_per_day
        # print(f"{student}: {exams_per_day} (60분↑: {long_exams_per_day})")

    # 하루에 3, 2과목 치는 학생 명단
    for num in [3, 2]:
        students_with_num = [
            student for student in student_max_per_day
            if student_max_per_day[student] == num
        ]
        print(f"\n하루에 {num}과목 치는 학생 수: {len(students_with_num)}명")
        for student in students_with_num:
            # 어떤 날에 3/2/1과목 쳤는지, 그 과목들 출력
            for i, subjects_today in enumerate(student_exam_subjects_per_day[student]):
                if len(subjects_today) == num:
                    day_str = days[i]
                    print(f"{student} ({day_str}): {', '.join(subjects_today)}")

    # 하루에 60분 이상 과목 3, 2과목 치는 학생 명단
    for num in [3, 2]:
        students_with_long_num = [
            student for student in student_max_long_per_day
            if student_max_long_per_day[student] == num
        ]
        print(f"\n하루에 60분 이상 과목 {num}과목 치는 학생 수: {len(students_with_long_num)}명")
        for student in students_with_long_num:
            for i, long_subjects_today in enumerate(student_long_exam_subjects_per_day[student]):
                if len(long_subjects_today) == num:
                    day_str = days[i]
                    print(f"{student} ({day_str}): {', '.join(long_subjects_today)}")
else:
    print("해를 찾지 못했습니다. 상태:", solver.StatusName(status))
