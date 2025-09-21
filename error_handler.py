"""
에러 처리 및 검증 모듈
파일 검증, 데이터 검증, 에러 메시지 생성을 담당합니다.
"""
import os
import pandas as pd
import logging
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path
import json

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ValidationError(Exception):
    """검증 에러 클래스"""
    pass

class FileValidationError(ValidationError):
    """파일 검증 에러"""
    pass

class DataValidationError(ValidationError):
    """데이터 검증 에러"""
    pass

class ExamSchedulerValidator:
    """시험 스케줄러 검증 클래스"""
    
    def __init__(self):
        self.required_files = [
            "학생배정정보.xlsx",
            "과목 정보.xlsx", 
            "시험 정보.xlsx",
            "시험 불가 교사.xlsx"
        ]
        
        self.required_sheets = {
            "학생배정정보.xlsx": [0],
            "과목 정보.xlsx": [0],  # 첫 번째 시트
            "시험 정보.xlsx": [0],  # 첫 번째 시트
            "시험 불가 교사.xlsx": [0]  # 첫 번째 시트
        }
    
    def validate_uploaded_files(self, upload_dir: str) -> Tuple[bool, List[str], List[str]]:
        """
        업로드된 파일들을 검증합니다.
        
        Returns:
            Tuple[bool, List[str], List[str]]: (성공여부, 성공한 파일들, 에러 메시지들)
        """
        errors = []
        success_files = []
        
        logger.info(f"Validating files in {upload_dir}")
        
        for required_file in self.required_files:
            file_path = Path(upload_dir) / required_file
            
            if not file_path.exists():
                error_msg = f"필수 파일이 없습니다: {required_file}"
                errors.append(error_msg)
                logger.error(error_msg)
                continue
            
            # 파일 형식 검증
            if not self._validate_file_format(file_path):
                error_msg = f"파일 형식이 올바르지 않습니다: {required_file}"
                errors.append(error_msg)
                logger.error(error_msg)
                continue
            
            # 파일 내용 검증
            try:
                if not self._validate_file_content(file_path, required_file):
                    error_msg = f"파일 내용이 올바르지 않습니다: {required_file}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    continue
            except Exception as e:
                error_msg = f"파일 검증 중 오류 발생: {required_file} - {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
                continue
            
            success_files.append(required_file)
            logger.info(f"File validated successfully: {required_file}")
        
        return len(errors) == 0, success_files, errors
    
    def _validate_file_format(self, file_path: Path) -> bool:
        """파일 형식 검증"""
        try:
            # 파일 크기 확인 (최소 1KB)
            if file_path.stat().st_size < 1024:
                logger.warning(f"File too small: {file_path}")
                return False
            
            # Excel 파일인지 확인
            if not str(file_path).lower().endswith(('.xlsx', '.xls')):
                logger.warning(f"Not an Excel file: {file_path}")
                return False
            
            # 파일이 읽기 가능한지 확인
            pd.read_excel(file_path, nrows=1)
            return True
            
        except Exception as e:
            logger.error(f"File format validation failed for {file_path}: {str(e)}")
            return False
    
    def _validate_file_content(self, file_path: Path, filename: str) -> bool:
        """파일 내용 검증"""
        try:
            if filename == "학생배정정보.xlsx":
                return self._validate_enrollment_file(file_path)
            elif filename == "과목 정보.xlsx":
                return self._validate_subject_info_file(file_path)
            elif filename == "시험 정보.xlsx":
                return self._validate_exam_info_file(file_path)
            elif filename == "시험 불가 교사.xlsx":
                return self._validate_teacher_unavailable_file(file_path)
            else:
                return True
                
        except Exception as e:
            logger.error(f"Content validation failed for {filename}: {str(e)}")
            return False
    
    def _validate_enrollment_file(self, file_path: Path) -> bool:
        """새로운 양식의 학생배정정보 파일 검증"""
        try:
            # 학생배정정보 시트 존재 확인
            excel_file = pd.ExcelFile(file_path)
            # 첫 번째 시트 존재 확인
            if len(excel_file.sheet_names) == 0:
                logger.error("엑셀 파일에 시트가 없습니다.")
                return False
            
            # 최소 데이터 확인 (2행부터 학생 데이터)
            df = pd.read_excel(file_path, sheet_name=0, header=None)
            if len(df) < 2:
                logger.error("학생배정정보에 충분한 데이터가 없습니다.")
                return False
            
            # 과목명 확인 (1행 F열부터, 인덱스 5부터)
            if len(df.columns) < 6:
                logger.error("과목 정보가 없습니다. (최소 6열 필요: A-E열 + 최소 1개 과목)")
                return False
            
            # 1행에 과목명이 있는지 확인
            header_row = df.iloc[0, 5:]  # F열부터
            if header_row.isna().all():
                logger.error("1행에 과목명이 없습니다.")
                return False
            
            # 2행부터 학생 데이터가 있는지 확인
            student_data = df.iloc[1:, :]
            if student_data.isna().all().all():
                logger.error("2행부터 학생 데이터가 없습니다.")
                return False
            
            # 최소한 하나의 학생 데이터 행이 유효한지 확인
            valid_student_rows = 0
            for idx, row in student_data.iterrows():
                # B열(학년), C열(반), D열(번호), E열(이름)이 모두 유효한지 확인
                if (pd.notna(row.iloc[1]) and pd.notna(row.iloc[2]) and 
                    pd.notna(row.iloc[3]) and pd.notna(row.iloc[4])):
                    valid_student_rows += 1
            
            if valid_student_rows == 0:
                logger.error("유효한 학생 데이터가 없습니다.")
                return False
            
            logger.info(f"학생배정정보 파일 검증 성공: {valid_student_rows}명의 학생 데이터 확인")
            return True
            
        except Exception as e:
            logger.error(f"Enrollment file validation error: {str(e)}")
            return False
    
    def _validate_subject_info_file(self, file_path: Path) -> bool:
        """과목 정보 파일 검증"""
        try:
            df = pd.read_excel(file_path, sheet_name=0, header=None)
            
            # 최소 3행 이상 필요 (과목명이 3행부터)
            if len(df) < 3:
                logger.error("과목 정보 파일에 충분한 데이터가 없습니다.")
                return False
            
            # C열에 과목명이 있는지 확인
            if len(df.columns) < 3:
                logger.error("과목 정보가 없습니다.")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Subject info file validation error: {str(e)}")
            return False
    
    def _validate_exam_info_file(self, file_path: Path) -> bool:
        """시험 정보 파일 검증"""
        try:
            df = pd.read_excel(file_path, sheet_name=0, header=None)
            
            # 최소 10행 이상 필요
            if len(df) < 10:
                logger.error("시험 정보 파일에 충분한 데이터가 없습니다.")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Exam info file validation error: {str(e)}")
            return False
    
    def _validate_teacher_unavailable_file(self, file_path: Path) -> bool:
        """시험 불가 교사 파일 검증"""
        try:
            df = pd.read_excel(file_path, sheet_name=0, header=None)
            
            # 최소 1행 이상 필요
            if len(df) < 1:
                logger.error("시험 불가 교사 파일에 데이터가 없습니다.")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Teacher unavailable file validation error: {str(e)}")
            return False
    
    def validate_config(self, config_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """설정 데이터 검증"""
        errors = []
        
        # 필수 필드 확인
        required_fields = ['max_exams_per_day', 'max_hard_exams_per_day', 'hard_exam_threshold']
        for field in required_fields:
            if field not in config_data:
                errors.append(f"필수 설정이 없습니다: {field}")
        
        # 값 범위 검증
        if 'max_exams_per_day' in config_data:
            value = config_data['max_exams_per_day']
            if not isinstance(value, int) or value < 1 or value > 10:
                errors.append("하루 최대 시험 수는 1~10 사이의 정수여야 합니다.")
        
        if 'max_hard_exams_per_day' in config_data:
            value = config_data['max_hard_exams_per_day']
            if not isinstance(value, int) or value < 0 or value > 5:
                errors.append("하루 최대 어려운 시험 수는 0~5 사이의 정수여야 합니다.")
        
        if 'hard_exam_threshold' in config_data:
            value = config_data['hard_exam_threshold']
            if not isinstance(value, (int, float)) or value < 0 or value > 100:
                errors.append("어려운 시험 기준은 0~100 사이의 숫자여야 합니다.")
        
        if 'exam_days' in config_data:
            value = config_data['exam_days']
            if not isinstance(value, int) or value < 1 or value > 10:
                errors.append("시험 일수는 1~10 사이의 정수여야 합니다.")
        
        if 'periods_per_day' in config_data:
            value = config_data['periods_per_day']
            if not isinstance(value, int) or value < 1 or value > 5:
                errors.append("하루 교시 수는 1~5 사이의 정수여야 합니다.")
        
        return len(errors) == 0, errors

class ErrorMessageGenerator:
    """사용자 친화적인 에러 메시지 생성기"""
    
    @staticmethod
    def get_file_upload_error(file_errors: List[str]) -> str:
        """파일 업로드 에러 메시지"""
        if not file_errors:
            return "알 수 없는 오류가 발생했습니다."
        
        if len(file_errors) == 1:
            return file_errors[0]
        
        error_list = "\n".join([f"• {error}" for error in file_errors])
        return f"다음 파일들에 문제가 있습니다:\n{error_list}"
    
    @staticmethod
    def get_scheduling_error(error_type: str, details: str = "") -> str:
        """스케줄링 에러 메시지"""
        error_messages = {
            "INFEASIBLE": "주어진 조건으로는 시험 시간표를 만들 수 없습니다. 설정을 조정해보세요.",
            "TIMEOUT": "시간 초과로 인해 최적해를 찾지 못했습니다. 더 긴 시간을 설정하거나 조건을 완화해보세요.",
            "DATA_ERROR": f"데이터 오류: {details}",
            "CONFIG_ERROR": f"설정 오류: {details}",
            "UNKNOWN": f"알 수 없는 오류가 발생했습니다: {details}"
        }
        
        return error_messages.get(error_type, error_messages["UNKNOWN"])
    
    @staticmethod
    def get_validation_error(validation_errors: List[str]) -> str:
        """검증 에러 메시지"""
        if not validation_errors:
            return "검증 오류가 발생했습니다."
        
        if len(validation_errors) == 1:
            return validation_errors[0]
        
        error_list = "\n".join([f"• {error}" for error in validation_errors])
        return f"다음 검증 오류가 있습니다:\n{error_list}"

def log_error(error: Exception, context: str = ""):
    """에러 로깅"""
    logger.error(f"Error in {context}: {str(error)}")
    logger.error(f"Traceback: {error.__traceback__}")

def create_error_response(error: Exception, context: str = "") -> Dict[str, Any]:
    """에러 응답 생성"""
    log_error(error, context)
    
    if isinstance(error, ValidationError):
        return {
            'success': False,
            'error': str(error),
            'error_type': 'validation'
        }
    else:
        return {
            'success': False,
            'error': f"오류가 발생했습니다: {str(error)}",
            'error_type': 'system'
        } 