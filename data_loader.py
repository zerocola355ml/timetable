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
        
    def load_enrollment_data(self, file_path: Union[str, Path] = "학생배정정보.xlsx") -> Tuple[Dict, Dict, List, pd.DataFrame]:
        """
        새로운 양식의 학생배정정보에서 수강 데이터를 로드합니다.
        
        Args:
            file_path (Union[str, Path]): 로드할 학생배정정보 파일 경로.
        
        Returns:
            Tuple[Dict, Dict, List, pd.DataFrame]: 학생 충돌 딕셔너리, 과목쌍 공동 수강 학생 딕셔너리, 학생 이름 리스트, 수강 여부 DataFrame
        """
        try:
            # Construct the full path to the enrollment file.
            # If a file_path is provided, use it directly. Otherwise, use the default.
            if file_path == "학생배정정보.xlsx": # Default case
                current_file_path = self.data_dir / file_path
            else:
                # Otherwise, use the provided file_path directly.
                current_file_path = file_path
            
            sheet = 0  # 첫 번째 시트
            
            # 전체 데이터 읽기
            df = pd.read_excel(current_file_path, sheet_name=sheet, header=None)
            
            # 과목명: 1행 F열부터 (인덱스 5부터)
            df_header = df.iloc[0, 5:].tolist()
            subject_cols = [col for col in df_header if pd.notna(col)]  # 빈값 제거
            
            # 학생 데이터: 2행부터 (인덱스 1부터)
            df_students = df.iloc[1:, :]
            
            # 빈 행 제거 (모든 열이 NaN인 행)
            df_students = df_students.dropna(how='all')
            
            # 학생 정보 추출
            student_data = []
            for idx, row in df_students.iterrows():
                # A열: 순번, B열: 학년, C열: 반, D열: 번호, E열: 이름
                order = row.iloc[0]  # A열 (순번)
                grade = row.iloc[1]  # B열 (학년)
                class_num = row.iloc[2]  # C열 (반)
                number = row.iloc[3]  # D열 (번호)
                name = row.iloc[4]  # E열 (이름)
                
                # 유효한 데이터인지 확인
                if pd.notna(grade) and pd.notna(class_num) and pd.notna(number) and pd.notna(name):
                    student_data.append({
                        'order': order,
                        'grade': int(grade),
                        'class': int(class_num),
                        'number': int(number),
                        'name': str(name)
                    })
            
            # 학년, 반, 번호의 최대값을 확인하여 자릿수 결정
            max_grade = max([s['grade'] for s in student_data])
            max_class = max([s['class'] for s in student_data])
            max_number = max([s['number'] for s in student_data])
            
            # 자릿수 계산
            grade_digits = len(str(max_grade))
            class_digits = len(str(max_class))
            number_digits = len(str(max_number))
            
            # 학번 생성 및 학생 정보 정리
            student_names = []
            student_info = {}
            
            for student in student_data:
                # 학번 생성 (학년 + 반 + 번호, 각각 0으로 패딩)
                grade_str = str(student['grade']).zfill(grade_digits)
                class_str = str(student['class']).zfill(class_digits)
                number_str = str(student['number']).zfill(number_digits)
                student_id = f"{grade_str}{class_str}{number_str}"
                
                # 학생 이름 (학번 + 이름)
                student_name = f"{student_id}{student['name']}"
                student_names.append(student_name)
                
                # 학생 정보 저장
                student_info[student_name] = {
                    'student_id': student_id,
                    'grade': student['grade'],
                    'class': student['class'],
                    'number': student['number'],
                    'name': student['name']
                }
            
            # 수강 데이터: F열부터 (인덱스 5부터)
            enroll_matrix = df_students.iloc[:, 5:5+len(subject_cols)]
            enroll_matrix.columns = subject_cols
            enroll_matrix.index = student_names
            
            # 빈값이거나 0이면 미수강, 다른 값이 있으면 수강
            # 수강 여부는 빈값이 아니고 0이 아닌 경우
            enroll_bool = ~(enroll_matrix.isna() | (enroll_matrix == 0))
            
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
        
        except Exception as e:
            print(f"Error loading enrollment data: {e}")
            import traceback
            traceback.print_exc()
            return None, None, None, None
    
    def load_subject_info(self, file_path: Union[str, Path] = "과목 정보.xlsx") -> Dict[str, Dict[str, Any]]:
        """
        과목 정보 파일에서 과목 정보를 로드합니다.
        
        Returns:
            Dict[str, Dict[str, Any]]: 과목별 정보 딕셔너리
        """
        try:
            file_path = self.data_dir / str(file_path)
            print(f"DEBUG: Loading subject info from {file_path}")
            
            if not file_path.exists():
                print(f"ERROR: File {file_path} does not exist")
                raise FileNotFoundError(f"과목 정보 파일을 찾을 수 없습니다: {file_path}")
            
            sheet = 0  # 첫 시트
            
            # 데이터 읽기 (A열 2행부터)
            print("DEBUG: Reading Excel file...")
            df = pd.read_excel(file_path, sheet_name=sheet, header=None)
            print(f"DEBUG: Excel file loaded, shape: {df.shape}")
            
            # 과목명 추출 (A열 2행부터)
            subject_names = df.iloc[1:, 0].dropna().astype(str).tolist()
            print(f"DEBUG: Found {len(subject_names)} subjects: {subject_names[:5]}...")
            
            # 과목 정보 딕셔너리
            subject_info_dict = {}
            
            for idx, subject in enumerate(subject_names):
                row_idx = idx + 1  # 0-based index, 실제 엑셀 2행부터 시작
                
                # B열: 시간(분)
                time_val = df.iloc[row_idx, 1]
                if pd.isna(time_val):
                    time_processed = None
                elif isinstance(time_val, str):
                    try:
                        time_processed = int(time_val)
                    except ValueError:
                        time_processed = time_val  # 변환 불가시 원본 저장
                else:
                    time_processed = int(time_val)
                
                # C열: 듣기평가 (1이면 True, 비어있거나 0이면 False)
                listen_val = df.iloc[row_idx, 2]
                if pd.isna(listen_val) or str(listen_val).strip() in ['', '0']:
                    listen_processed = False
                else:
                    listen_processed = True
                
                # D열: 자율감독 (1이면 True, 비어있거나 0이면 False)
                self_val = df.iloc[row_idx, 3]
                if pd.isna(self_val) or str(self_val).strip() in ['', '0']:
                    self_processed = False
                else:
                    self_processed = True
                
                # E열: 학년 (콤마로 구분, 공백 무시)
                grade_val = df.iloc[row_idx, 4]
                if pd.isna(grade_val):
                    grade_processed = ""
                elif isinstance(grade_val, str):
                    # 콤마로 구분된 경우 공백 제거 후 다시 합치기
                    if ',' in grade_val:
                        grades = [g.strip() for g in grade_val.split(',') if g.strip()]
                        grade_processed = ','.join(grades)
                    else:
                        # 단일 값인 경우 그대로 사용
                        grade_processed = grade_val.strip()
                else:
                    # 숫자 등 다른 타입인 경우 문자열로 변환
                    grade_processed = str(grade_val)
                
                # F열: 담당교사 (콤마로 구분, 공백 무시)
                teacher_val = df.iloc[row_idx, 5]
                teacher_list = []
                if not pd.isna(teacher_val):
                    teachers = [t.strip() for t in str(teacher_val).split(',') if t.strip()]
                    teacher_list.extend(teachers)
                
                # 딕셔너리 저장
                subject_info_dict[subject] = {
                    '시간': time_processed,
                    '듣기평가': listen_processed,
                    '자율감독': self_processed,
                    '학년': grade_processed,
                    '담당교사': teacher_list
                }
            
            print(f"DEBUG: Successfully processed {len(subject_info_dict)} subjects")
            return subject_info_dict
            
        except Exception as e:
            print(f"ERROR in load_subject_info: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

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
        
        # 원본과 커스텀 데이터 병합 (_deleted 표시된 항목은 제외)
        merged_subject_info = {}
        for subject, info in original_subject_info.items():
            # 커스텀에서 삭제 표시된 과목은 제외
            if subject in custom_subject_info and custom_subject_info[subject].get('_deleted'):
                continue
            merged_subject_info[subject] = info.copy()
            if subject in custom_subject_info and not custom_subject_info[subject].get('_deleted'):
                # 커스텀 데이터로 덮어쓰기
                merged_subject_info[subject].update(custom_subject_info[subject])
        
        # 커스텀에서만 있는 과목들 추가 (삭제 표시 제외)
        for subject, info in custom_subject_info.items():
            if subject not in original_subject_info and not info.get('_deleted'):
                merged_subject_info[subject] = info
        
        return merged_subject_info
    

        
        
    def load_exam_info_with_custom(self) -> Dict[str, Any]:
        """커스텀 시험 정보를 로드합니다."""
        custom_exam_info = self._load_json_file('custom_exam_info.json', {})
        
        if custom_exam_info:
            return custom_exam_info
        
        # custom_exam_info.json이 없으면 기본 구조 반환
        print("Warning: custom_exam_info.json not found. Using default structure.")
        return {
            '학년도': '2024',
            '학기': '1학기',
            '고사종류': '중간고사',
            '시험날짜': {},
            '시험타임': {},
            'date_periods': {}
        }
    

    
    def load_teacher_unavailable_with_custom(self, file_path: Union[str, Path] = "시험 불가 교사.xlsx") -> Dict[str, List[str]]:
        """
        커스텀 교사 제약 데이터를 로드합니다.
        
        Returns:
            Dict[str, List[str]]: 교사별 불가능한 시험 슬롯 딕셔너리
        """
        # 커스텀 데이터 로드
        custom_file = self.data_dir / 'custom_teacher_constraints.json'
        custom_data = {}
        
        if custom_file.exists():
            try:
                with open(custom_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:  # Only try to parse if file has content
                        custom_constraints = json.loads(content)
                    else:
                        custom_constraints = []
                    
                # 커스텀 데이터를 딕셔너리 형태로 변환
                for constraint in custom_constraints:
                    teacher_name = constraint.get('teacher_name')
                    constraint_slots = constraint.get('constraint_slots', [])
                    if teacher_name:
                        custom_data[teacher_name] = constraint_slots
                        
            except Exception as e:
                print(f"교사 제약 커스텀 데이터 로드 오류: {e}")
        
        return custom_data
    
    def generate_conflict_dicts(self, subject_info_dict: Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """
        과목 정보에서 충돌 딕셔너리들을 생성합니다.
        
        Returns:
            Tuple[Dict[str, List[str]], Dict[str, List[str]]]: 
            - listening_conflict_dict: 듣기평가 충돌 딕셔너리
            - teacher_conflict_dict: 담당교사 충돌 딕셔너리
        """
        try:
            print(f"DEBUG: generate_conflict_dicts 시작 - 과목 수: {len(subject_info_dict)}")
            
            # 1. 듣기평가가 있는 과목 리스트 추출
            listening_subjects = [subject for subject, info in subject_info_dict.items() if info.get('듣기평가')]
            print(f"DEBUG: 듣기평가 과목 수: {len(listening_subjects)}")
            
            # 2. 듣기평가 충돌 딕셔너리 생성
            listening_conflict_dict = {subject: [] for subject in listening_subjects}
            for subj1, subj2 in itertools.combinations(listening_subjects, 2):
                listening_conflict_dict[subj1].append(subj2)
                listening_conflict_dict[subj2].append(subj1)
            
            # 3. 담당교사 충돌 딕셔너리 생성
            teacher_conflict_dict = {subject: [] for subject in subject_info_dict}
            subjects = list(subject_info_dict.keys())
            print(f"DEBUG: 교사 충돌 검사 시작 - 총 과목 수: {len(subjects)}")
            
            for i, subj1 in enumerate(subjects):
                try:
                    print(f"DEBUG: 과목 '{subj1}' 처리 중... ({i+1}/{len(subjects)})")
                    
                    # 담당교사 정보가 있는지 확인
                    if '담당교사' not in subject_info_dict[subj1]:
                        print(f"Warning: 과목 '{subj1}'에 담당교사 정보가 없습니다.")
                        continue
                    
                    # 담당교사 정보 확인
                    teachers1_raw = subject_info_dict[subj1]['담당교사']
                    print(f"DEBUG: 과목 '{subj1}' 담당교사 정보: {teachers1_raw} (타입: {type(teachers1_raw)})")
                    
                    if not teachers1_raw:
                        print(f"Warning: 과목 '{subj1}'의 담당교사가 비어있습니다.")
                        continue
                        
                    teachers1 = set(teachers1_raw)
                    print(f"DEBUG: 과목 '{subj1}' 담당교사 집합: {teachers1}")
                    
                    for subj2 in subjects[i+1:]:
                        try:
                            # 담당교사 정보가 있는지 확인
                            if '담당교사' not in subject_info_dict[subj2]:
                                continue
                                
                            teachers2_raw = subject_info_dict[subj2]['담당교사']
                            if not teachers2_raw:
                                continue
                                
                            teachers2 = set(teachers2_raw)
                            
                            # 교사가 겹치면 충돌 추가
                            if teachers1 and teachers2 and (teachers1 & teachers2):
                                print(f"DEBUG: 교사 충돌 발견! '{subj1}' <-> '{subj2}' (공통 교사: {teachers1 & teachers2})")
                                teacher_conflict_dict[subj1].append(subj2)
                                teacher_conflict_dict[subj2].append(subj1)
                                
                        except Exception as e:
                            print(f"Warning: 과목 '{subj2}' 처리 중 오류: {e}")
                            continue
                            
                except Exception as e:
                    print(f"Warning: 과목 '{subj1}' 처리 중 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"DEBUG: generate_conflict_dicts 완료")
            return listening_conflict_dict, teacher_conflict_dict
            
        except Exception as e:
            print(f"Error in generate_conflict_dicts: {e}")
            import traceback
            traceback.print_exc()
            # 에러 발생 시 빈 딕셔너리 반환
            return {}, {}
    
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
        original_student_conflicts, _, _, _ = self.load_enrollment_data()
        original_listening_conflicts, original_teacher_conflicts = self.generate_conflict_dicts(
            self.load_subject_info()
        )
        
        # 2. 커스텀 충돌 파일들 로드
        custom_student_conflicts = self._load_json_file('custom_student_conflicts.json', [])
        custom_student_removed = self._load_json_file('custom_student_removed_conflicts.json', [])
        custom_listening_conflicts = self._load_json_file('custom_listening_conflicts.json', [])
        
        # 3. 교사 충돌 파일 로드
        custom_teacher_conflicts = self._load_json_file('teacher_conflicts.json', [])
        custom_teacher_removed = []  # 단일 리스트 구조에서는 제거된 충돌을 별도로 저장하지 않음
        
        # 4. 새로운 충돌 유형들 로드
        same_grade_conflicts = self._load_json_file('same_grade_conflicts.json', [])
        individual_conflicts = self._load_json_file('individual_conflicts.json', [])
        same_grade_removed = self._load_json_file('same_grade_removed_conflicts.json', [])
        
        # 5. 학생 충돌 처리 (기존 + 새로운 유형들)
        student_conflicts = self._merge_student_conflicts(
            original_student_conflicts, custom_student_conflicts, custom_student_removed
        )
        
        # 6. 새로운 충돌 유형들 병합
        student_conflicts = self._merge_new_conflict_types(
            student_conflicts, same_grade_conflicts, individual_conflicts, same_grade_removed
        )
        
        # 7. 듣기 충돌 처리
        listening_conflicts = self._merge_listening_conflicts(
            original_listening_conflicts, custom_listening_conflicts
        )
        
        # 8. 교사 충돌 처리
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
                    content = f.read().strip()
                    if content:  # Only try to parse if file has content
                        return json.loads(content)
                    else:
                        return default_value
            except Exception as e:
                print(f"Error loading {filename}: {e}")
        return default_value
    
    def _merge_student_conflicts(self, original: Dict[str, List[str]], 
                                custom_added: List[Dict], 
                                custom_removed: List[Dict]) -> Dict[str, List[str]]:
        """학생 충돌을 병합합니다."""
        try:
            print(f"DEBUG: _merge_student_conflicts 시작 - 원본 과목 수: {len(original)}")
            
            # 원본 충돌 복사
            merged = {subject: conflicts.copy() for subject, conflicts in original.items()}
            
            # 제거된 충돌 처리
            removed_pairs = set()
            for removed in custom_removed:
                try:
                    subject1, subject2 = removed['subject1'], removed['subject2']
                    removed_pairs.add((subject1, subject2))
                    removed_pairs.add((subject2, subject1))
                except Exception as e:
                    print(f"Warning: 제거된 충돌 처리 중 오류: {e}, 데이터: {removed}")
                    continue
            
            # 원본에서 제거된 충돌 삭제
            for subject, conflicts in merged.items():
                try:
                    merged[subject] = [c for c in conflicts if (subject, c) not in removed_pairs]
                except Exception as e:
                    print(f"Warning: 과목 '{subject}' 충돌 제거 중 오류: {e}")
                    continue
            
            # 추가된 커스텀 충돌 처리
            for custom_conflict in custom_added:
                try:
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
                except Exception as e:
                    print(f"Warning: 커스텀 충돌 추가 중 오류: {e}, 데이터: {custom_conflict}")
                    continue
            
            print(f"DEBUG: _merge_student_conflicts 완료")
            return merged
            
        except Exception as e:
            print(f"Error in _merge_student_conflicts: {e}")
            import traceback
            traceback.print_exc()
            # 에러 발생 시 원본 반환
            return original
    
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
    
    def generate_student_conflicts(self, enroll_bool: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        수강 데이터에서 학생 충돌 정보를 생성합니다.
        
        Args:
            enroll_bool: 수강 여부 불린 매트릭스 (학생명이 인덱스, 과목명이 컬럼)
            
        Returns:
            List[Dict[str, Any]]: 충돌 정보 리스트
        """
        conflicts = []
        
        # 과목명 추출 (컬럼에서)
        subject_cols = enroll_bool.columns.tolist()
        
        # 모든 과목 쌍에 대해 검사
        for i, subj1 in enumerate(subject_cols):
            for j, subj2 in enumerate(subject_cols[i+1:], i+1):
                # 두 과목을 모두 수강하는 학생 찾기
                both_enrolled = enroll_bool[
                    (enroll_bool[subj1]) & (enroll_bool[subj2])
                ]
                
                if not both_enrolled.empty:
                    # 공통 수강 학생 목록 (인덱스에서)
                    common_students = both_enrolled.index.tolist()
                    
                    conflict_info = {
                        'subject1': subj1,
                        'subject2': subj2,
                        'shared_students': common_students,
                        'student_count': len(common_students),
                        'type': '학생',
                        'description': f'{subj1}과 {subj2}는 {len(common_students)}명의 공통 수강 학생이 있어 같은 시간에 배정할 수 없습니다.',
                        'is_original': True,
                        'is_custom': False
                    }
                    
                    conflicts.append(conflict_info)
        
        return conflicts 

    def _merge_new_conflict_types(self, base_conflicts: Dict[str, List[str]], 
                                 same_grade: List[Dict], 
                                 individual: List[Dict], 
                                 same_grade_removed: List[Dict]) -> Dict[str, List[str]]:
        """새로운 충돌 유형들을 기존 충돌에 병합합니다."""
        try:
            print(f"DEBUG: _merge_new_conflict_types 시작")
            
            # 기존 충돌 복사
            merged = {subject: conflicts.copy() for subject, conflicts in base_conflicts.items()}
            
            # 제거된 같은 학년 충돌 처리
            removed_pairs = set()
            for removed in same_grade_removed:
                try:
                    subject1, subject2 = removed['subject1'], removed['subject2']
                    removed_pairs.add((subject1, subject2))
                    removed_pairs.add((subject2, subject1))
                except Exception as e:
                    print(f"Warning: 제거된 같은 학년 충돌 처리 중 오류: {e}, 데이터: {removed}")
                    continue
            
            # 같은 학년 충돌 추가
            for conflict in same_grade:
                try:
                    subject1, subject2 = conflict['subject1'], conflict['subject2']
                    if (subject1, subject2) not in removed_pairs and (subject2, subject1) not in removed_pairs:
                        if subject2 not in merged.get(subject1, []):
                            if subject1 not in merged:
                                merged[subject1] = []
                            merged[subject1].append(subject2)
                        if subject1 not in merged.get(subject2, []):
                            if subject2 not in merged:
                                merged[subject2] = []
                            merged[subject2].append(subject1)
                except Exception as e:
                    print(f"Warning: 같은 학년 충돌 추가 중 오류: {e}, 데이터: {conflict}")
                    continue
            
            # 개별 학생 충돌 추가
            for conflict in individual:
                try:
                    subject1, subject2 = conflict['subject1'], conflict['subject2']
                    if (subject1, subject2) not in removed_pairs and (subject2, subject1) not in removed_pairs:
                        if subject2 not in merged.get(subject1, []):
                            if subject1 not in merged:
                                merged[subject1] = []
                            merged[subject1].append(subject2)
                        if subject1 not in merged.get(subject2, []):
                            if subject2 not in merged:
                                merged[subject2] = []
                            merged[subject2].append(subject1)
                except Exception as e:
                    print(f"Warning: 개별 학생 충돌 추가 중 오류: {e}, 데이터: {conflict}")
                    continue
            
            print(f"DEBUG: _merge_new_conflict_types 완료")
            return merged
            
        except Exception as e:
            print(f"Error in _merge_new_conflict_types: {e}")
            return base_conflicts 