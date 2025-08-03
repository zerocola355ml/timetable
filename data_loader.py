"""
데이터 로딩 모듈
엑셀 파일에서 시험 시간표 배정에 필요한 데이터를 로드합니다.
"""
import pandas as pd
import itertools
import json
from typing import Dict, List, Any, Tuple, Union
from pathlib import Path


class DataLoader:
    """데이터 로딩 클래스"""
    
    def __init__(self, data_dir: str = "."):
        self.data_dir = Path(data_dir)
        
    def load_enrollment_data(self, file_path: Union[str, Path] = "bunbanbaejeongpyo.xlsx") -> Tuple[Dict, Dict, List[str], pd.DataFrame]:
        """
        분반배정표에서 수강 데이터를 로드합니다.
        
        Returns:
            Tuple[Dict, Dict, List[str], pd.DataFrame]: 
            - student_conflict_dict: 과목별로 겹칠 수 없는 과목 리스트
            - double_enroll_dict: 과목쌍별 공동수강학생 딕셔너리
            - student_names: 학생명 리스트
            - enroll_bool: 수강 여부 불린 매트릭스
        """
        file_path = self.data_dir / str(file_path)
        sheet = '분반배정표'
        
        # 과목명: 1행 C열부터
        df_header = pd.read_excel(file_path, sheet_name=sheet, header=None, nrows=1)
        subject_cols = df_header.iloc[0, 2:].tolist()  # C열부터 끝까지
        
        # 학생명: A열 14행부터
        df_students = pd.read_excel(file_path, sheet_name=sheet, header=None)
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
        
        return student_conflict_dict, double_enroll_dict, student_names, enroll_bool
    
    def load_subject_info(self, file_path: Union[str, Path] = "시험 범위.xlsx") -> Dict[str, Dict[str, Any]]:
        """
        시험 범위 파일에서 과목 정보를 로드합니다.
        
        Returns:
            Dict[str, Dict[str, Any]]: 과목별 정보 딕셔너리
        """
        file_path = self.data_dir / str(file_path)
        sheet = 0  # 첫 시트
        
        # 데이터 읽기 (C열 3행부터)
        df = pd.read_excel(file_path, sheet_name=sheet, header=None)
        
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
                '듣기평가': listen_processed,
                '자율감독': self_processed,
                '학년': grade_val,
                '담당교사': teacher_list
            }
        
        return subject_info_dict

    def load_custom_subject_info(self) -> Dict[str, Dict[str, Any]]:
        """
        커스텀 과목 정보를 로드하고 원본과 병합합니다.
        
        Returns:
            Dict[str, Dict[str, Any]]: 병합된 과목별 정보 딕셔너리
        """
        # 원본 과목 정보 로드
        original_subject_info = self.load_subject_info()
        
        # 커스텀 과목 정보 로드
        custom_subject_info = self._load_json_file('custom_subject_info.json', {})
        
        # 원본과 커스텀 데이터 병합
        merged_subject_info = {}
        for subject, info in original_subject_info.items():
            merged_subject_info[subject] = info.copy()
            if subject in custom_subject_info:
                # 커스텀 데이터로 덮어쓰기
                merged_subject_info[subject].update(custom_subject_info[subject])
        
        # 커스텀에서만 있는 과목들 추가
        for subject, info in custom_subject_info.items():
            if subject not in original_subject_info:
                merged_subject_info[subject] = info
        
        return merged_subject_info
    
    def load_exam_info(self, file_path: Union[str, Path] = "시험 정보.xlsx") -> Dict[str, Any]:
        """
        시험 정보 파일을 로드합니다.
        
        Returns:
            Dict[str, Any]: 시험 정보 딕셔너리
        """
        file_path = self.data_dir / str(file_path)
        sheet = 0  # 첫 시트
        
        # 파일 전체 읽기 (헤더 없이)
        df = pd.read_excel(file_path, sheet_name=sheet, header=None)
        
        # 1~3행: 년, 학기, 고사 종류
        exam_year = str(df.iloc[0, 1]).strip()    # 1행 B열
        exam_semester = str(df.iloc[1, 1]).strip()  # 2행 B열
        exam_type = str(df.iloc[2, 1]).strip()    # 3행 B열
        
        # 4~9행: 제1일~제6일 시험 날짜
        exam_dates = {}
        for i in range(6):  # 0~5
            day_label = str(df.iloc[3 + i, 0]).strip()   # 4~9행 A열: '제1일', '제2일', ...
            date_val = str(df.iloc[3 + i, 1]).strip()   # 4~9행 B열: '6월 14일' 등
            exam_dates[day_label] = date_val
        
        # 10~33행: 각 시험 타임(제n일 m교시)의 시작/종료/진행시간
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
        
        # 날짜별 교시 시간 구조로 변환
        date_periods = {}
        for day in range(1, 7):  # 1~6일
            date_periods[day] = {}
            for period in range(1, 5):  # 1~4교시
                time_label = f'제{day}일{period}교시'
                if time_label in exam_times:
                    time_data = exam_times[time_label]
                    date_periods[day][period] = {
                        'start_time': time_data['시작'],
                        'end_time': time_data['종료'],
                        'duration': time_data['진행시간']
                    }
        
        return {
            '학년도': exam_year,
            '학기': exam_semester,
            '고사종류': exam_type,
            '시험날짜': exam_dates,
            '시험타임': exam_times,  # 기존 구조 유지 (하위 호환성)
            'date_periods': date_periods  # 새로운 날짜별 구조
        }
    
    def load_teacher_unavailable(self, file_path: Union[str, Path] = "시험 불가 교사.xlsx") -> Dict[str, List[str]]:
        """
        시험 불가 교사 파일을 로드합니다.
        
        Returns:
            Dict[str, List[str]]: 교사별 불가능한 시험 슬롯 딕셔너리
        """
        file_path = self.data_dir / str(file_path)
        sheet = 0  # 첫 시트
        
        df = pd.read_excel(file_path, sheet_name=sheet, header=None)
        
        # A2부터 아래로 교사명
        teacher_names = df.iloc[1:, 0].dropna().astype(str).tolist()
        
        # B~Y열: 24개 슬롯 (제1일1교시~제6일4교시)
        slot_codes = [
            f'{day}{period}교시'
            for day in range(1, 7)       # 1~6일
            for period in range(1, 5)    # 1~4교시
        ]
        
        # 제n일m교시 → '제n일m교시'
        slot_labels = [f'제{code[0]}일{code[1]}교시' for code in slot_codes]
        
        teacher_unavailable_dates = {}
        
        for i, teacher in enumerate(teacher_names):
            # B~Y열 (1~24)
            unavailable_slots = []
            for j, slot_label in enumerate(slot_labels):
                val = df.iloc[i+1, j+1]  # i+1: 데이터는 2행부터, j+1: B열부터
                if not pd.isna(val) and int(val) == 1:
                    unavailable_slots.append(slot_label)
            teacher_unavailable_dates[teacher] = unavailable_slots
        
        return teacher_unavailable_dates
    
    def generate_conflict_dicts(self, subject_info_dict: Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """
        과목 정보에서 충돌 딕셔너리들을 생성합니다.
        
        Returns:
            Tuple[Dict[str, List[str]], Dict[str, List[str]]]: 
            - listening_conflict_dict: 듣기평가 충돌 딕셔너리
            - teacher_conflict_dict: 담당교사 충돌 딕셔너리
        """
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
        
        return listening_conflict_dict, teacher_conflict_dict
    
    def save_data_to_json(self, data: Dict[str, Any], filename: str):
        """데이터를 JSON 파일로 저장합니다."""
        file_path = self.data_dir / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2) 
    
    def load_custom_conflicts(self) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], Dict[str, List[str]]]:
        """
        커스텀 충돌 데이터를 로드합니다 (웹 편집 반영).
        
        Returns:
            Tuple[Dict, Dict, Dict]: (student_conflicts, listening_conflicts, teacher_conflicts)
        """
        # 1. 원본 충돌 데이터 로드
        original_student_conflicts, _ = self.load_enrollment_data()
        original_listening_conflicts, original_teacher_conflicts = self.generate_conflict_dicts(
            self.load_subject_info()
        )
        
        # 2. 커스텀 충돌 파일들 로드
        custom_student_conflicts = self._load_json_file('custom_student_conflicts.json', [])
        custom_student_removed = self._load_json_file('custom_student_removed_conflicts.json', [])
        custom_listening_conflicts = self._load_json_file('custom_listening_conflicts.json', [])
        custom_teacher_conflicts = self._load_json_file('custom_teacher_conflicts.json', [])
        custom_teacher_removed = self._load_json_file('custom_teacher_removed_conflicts.json', [])
        
        # 3. 학생 충돌 처리
        student_conflicts = self._merge_student_conflicts(
            original_student_conflicts, custom_student_conflicts, custom_student_removed
        )
        
        # 4. 듣기 충돌 처리
        listening_conflicts = self._merge_listening_conflicts(
            original_listening_conflicts, custom_listening_conflicts
        )
        
        # 5. 교사 충돌 처리
        teacher_conflicts = self._merge_teacher_conflicts(
            original_teacher_conflicts, custom_teacher_conflicts, custom_teacher_removed
        )
        
        return student_conflicts, listening_conflicts, teacher_conflicts
    
    def _load_json_file(self, filename: str, default_value: Any) -> Any:
        """JSON 파일을 로드합니다."""
        file_path = self.data_dir / filename
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading {filename}: {e}")
        return default_value
    
    def _merge_student_conflicts(self, original: Dict[str, List[str]], 
                                custom_added: List[Dict], 
                                custom_removed: List[Dict]) -> Dict[str, List[str]]:
        """학생 충돌을 병합합니다."""
        # 원본 충돌 복사
        merged = {subject: conflicts.copy() for subject, conflicts in original.items()}
        
        # 제거된 충돌 처리
        removed_pairs = set()
        for removed in custom_removed:
            subject1, subject2 = removed['subject1'], removed['subject2']
            removed_pairs.add((subject1, subject2))
            removed_pairs.add((subject2, subject1))
        
        # 원본에서 제거된 충돌 삭제
        for subject, conflicts in merged.items():
            merged[subject] = [c for c in conflicts if (subject, c) not in removed_pairs]
        
        # 추가된 커스텀 충돌 처리
        for custom_conflict in custom_added:
            subject1, subject2 = custom_conflict['subject1'], custom_conflict['subject2']
            if (subject1, subject2) not in removed_pairs and (subject2, subject1) not in removed_pairs:
                if subject2 not in merged.get(subject1, []):
                    if subject1 not in merged:
                        merged[subject1] = []
                    merged[subject1].append(subject2)
                if subject1 not in merged.get(subject2, []):
                    if subject2 not in merged:
                        merged[subject2] = []
                    merged[subject2].append(subject1)
        
        return merged
    
    def _merge_listening_conflicts(self, original: Dict[str, List[str]], 
                                  custom_added: List[Dict]) -> Dict[str, List[str]]:
        """듣기 충돌을 병합합니다."""
        # 원본 충돌 복사
        merged = {subject: conflicts.copy() for subject, conflicts in original.items()}
        
        # 추가된 커스텀 충돌 처리
        for custom_conflict in custom_added:
            subject1, subject2 = custom_conflict['subject1'], custom_conflict['subject2']
            if subject2 not in merged.get(subject1, []):
                if subject1 not in merged:
                    merged[subject1] = []
                merged[subject1].append(subject2)
            if subject1 not in merged.get(subject2, []):
                if subject2 not in merged:
                    merged[subject2] = []
                merged[subject2].append(subject1)
        
        return merged
    
    def _merge_teacher_conflicts(self, original: Dict[str, List[str]], 
                                custom_added: List[Dict], 
                                custom_removed: List[Dict]) -> Dict[str, List[str]]:
        """교사 충돌을 병합합니다."""
        # 원본 충돌 복사
        merged = {subject: conflicts.copy() for subject, conflicts in original.items()}
        
        # 제거된 충돌 처리
        removed_pairs = set()
        for removed in custom_removed:
            subject1, subject2 = removed['subject1'], removed['subject2']
            removed_pairs.add((subject1, subject2))
            removed_pairs.add((subject2, subject1))
        
        # 원본에서 제거된 충돌 삭제
        for subject, conflicts in merged.items():
            merged[subject] = [c for c in conflicts if (subject, c) not in removed_pairs]
        
        # 추가된 커스텀 충돌 처리
        for custom_conflict in custom_added:
            subject1, subject2 = custom_conflict['subject1'], custom_conflict['subject2']
            if (subject1, subject2) not in removed_pairs and (subject2, subject1) not in removed_pairs:
                if subject2 not in merged.get(subject1, []):
                    if subject1 not in merged:
                        merged[subject1] = []
                    merged[subject1].append(subject2)
                if subject1 not in merged.get(subject2, []):
                    if subject2 not in merged:
                        merged[subject2] = []
                    merged[subject2].append(subject1)
        
        return merged 