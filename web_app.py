"""
시험 시간표 배정 웹 애플리케이션
Flask를 사용한 웹 인터페이스
"""
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for, session, make_response
from flask_cors import CORS
import os
import json
import tempfile
import shutil
from pathlib import Path
from werkzeug.utils import secure_filename
import traceback
import threading
import pandas as pd
from datetime import datetime, timedelta
import random
from collections import defaultdict
import numpy as np
from config import ExamSchedulingConfig, DEFAULT_EXAM_INFO_CONFIG, DEFAULT_SYSTEM_CONFIG
from exam_scheduler_app import ExamSchedulerApp
from data_loader import DataLoader
from logger_config import get_logger, setup_logging

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # 실제 운영시에는 환경변수로 관리
CORS(app)

# 로깅 시스템 초기화
setup_logging()
logger = get_logger('web_app')

# 전역 로거를 모든 함수에서 사용할 수 있도록 설정
def get_logger():
    return logger

# 모든 함수에서 self.logger 대신 logger 사용하도록 설정
import builtins
builtins.logger = logger

# 업로드 설정
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = set(DEFAULT_SYSTEM_CONFIG.allowed_extensions)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = DEFAULT_SYSTEM_CONFIG.max_file_size

# 업로드 폴더 생성
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# 스케줄링 진행상황 전역 변수
schedule_status = {
    "step": "대기중",
    "progress": 0,
    "is_running": False,
    "result": None,
    "error": None
}
schedule_lock = threading.Lock()

# 충돌 데이터 저장/로드 함수들
def get_custom_conflicts_file(conflict_type):
    """커스텀 충돌 데이터 파일 경로 반환"""
    if conflict_type == 'same_grade':
        return os.path.join(UPLOAD_FOLDER, 'same_grade_conflicts.json')
    elif conflict_type == 'individual':
        return os.path.join(UPLOAD_FOLDER, 'individual_conflicts.json')
    elif conflict_type == 'student_removed':
        return os.path.join(UPLOAD_FOLDER, 'student_removed_conflicts.json')
    elif conflict_type == 'same_grade_removed':
        return os.path.join(UPLOAD_FOLDER, 'same_grade_removed_conflicts.json')
    else:
        # 기존 호환성을 위해
        return os.path.join(UPLOAD_FOLDER, f'custom_{conflict_type}_conflicts.json')

def load_custom_conflicts(conflict_type):
    """커스텀 충돌 데이터 로드"""
    file_path = get_custom_conflicts_file(conflict_type)
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:  # Only try to parse if file has content
                    return json.loads(content)
                else:
                    return []
        except Exception as e:
            self.logger.debug(f"Error loading custom conflicts: {e}")
    return []

def save_custom_conflicts(conflict_type, conflicts):
    """커스텀 충돌 데이터 저장"""
    file_path = get_custom_conflicts_file(conflict_type)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(conflicts, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        self.logger.debug(f"Error saving custom conflicts: {e}")
        return False

def load_teacher_conflicts():
    """교사 충돌 파일을 로드합니다."""
    conflicts_file = os.path.join(app.config['UPLOAD_FOLDER'], 'teacher_conflicts.json')
    if os.path.exists(conflicts_file):
        try:
            with open(conflicts_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.debug(f"Error loading teacher conflicts: {e}")
    
    # 기본 빈 리스트 반환
    return []

def save_teacher_conflicts(conflicts):
    """교사 충돌 파일을 저장합니다."""
    try:
        conflicts_file = os.path.join(app.config['UPLOAD_FOLDER'], 'teacher_conflicts.json')
        with open(conflicts_file, 'w', encoding='utf-8') as f:
            json.dump(conflicts, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        self.logger.debug(f"Error saving teacher conflicts: {e}")
        return False

def allowed_file(filename):
    """파일 확장자 검증"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def standardize_time_slot_key(time_slot):
    """시간대 키를 표준 형식으로 변환합니다.
    
    Args:
        time_slot (str): 원본 시간대 문자열 (예: "제1일 1교시(08:30-09:20)")
        
    Returns:
        str: 표준화된 시간대 키 (예: "제1일_1교시")
    """
    import re
    
    # "제X일 X교시" 패턴 매칭
    match = re.match(r'제(\d+)일\s+(\d+)교시', time_slot)
    if match:
        day = match.group(1)
        period = match.group(2)
        return f"제{day}일_{period}교시"
    
    # 이미 표준 형식인 경우 그대로 반환
    if re.match(r'제\d+일_\d+교시', time_slot):
        return time_slot
    
    # 기타 형식은 그대로 반환 (호환성 유지)
    return time_slot

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')

@app.route('/uploads/<filename>')
def serve_upload(filename):
    """uploads 폴더의 파일 서빙"""
    try:
        return send_file(os.path.join(UPLOAD_FOLDER, filename))
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404




@app.route('/schedule-manager')
def schedule_manager():
    """통합 시험 시간표 관리 페이지"""
    return render_template('schedule_manager.html')

@app.route('/api/data/<filename>')
def get_data_file(filename):
    """데이터 파일 API"""
    import json
    import os
    
    try:
        if filename == 'exam_info.json':
            # uploads/custom_exam_info.json을 우선 확인
            custom_path = 'uploads/custom_exam_info.json'
            default_path = 'exam_info.json'
            
            if os.path.exists(custom_path):
                with open(custom_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # custom_exam_info.json 형식을 schedule_manager.html이 기대하는 형식으로 변환
                if 'date_periods' in data and '시험타임' not in data:
                    data['시험타임'] = {}
                    for day_num, periods in data.get('date_periods', {}).items():
                        day_name = f"제{day_num}일"
                        for period_num, period_data in periods.items():
                            key = f"{day_name}{period_num}교시"
                            data['시험타임'][key] = {
                                '시작': f"{period_data['start_time']}:00",
                                '종료': f"{period_data['end_time']}:00",
                                '진행시간': int(period_data['duration'])
                            }
                
                return jsonify(data)
            elif os.path.exists(default_path):
                with open(default_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return jsonify(data)
            else:
                return jsonify({'error': 'exam_info.json not found'}), 404
        elif filename == 'subject_info.json':
            try:
                # data_loader를 사용해서 custom_exam_scope.json에서 과목 정보 로드
                from data_loader import DataLoader
                data_loader = DataLoader(app.config['UPLOAD_FOLDER'])
                data = data_loader.load_subject_info()
                return jsonify(data)
            except Exception as e:
                return jsonify({'error': f'Error loading subject info: {str(e)}'}), 500
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Error reading file: {str(e)}'}), 500

@app.route('/api/schedule-status')
def get_schedule_status():
    """스케줄링 진행상황 조회 API"""
    with schedule_lock:
        return jsonify(schedule_status.copy())

@app.route('/api/debug-config', methods=['GET'])
def get_debug_config():
    """디버깅 설정을 반환하는 API"""
    from logger_config import is_debug_enabled
    
    debug_enabled = is_debug_enabled()
    
    config = {
        'enabled': debug_enabled,
        'level': 'debug' if debug_enabled else 'info',
        'showTimestamp': True,
        'showModule': True
    }
    
    logger.debug(f"디버깅 설정 반환: {config}")
    return jsonify(config)

@app.route('/api/debug-config', methods=['POST'])
def set_debug_config():
    """디버깅 설정을 변경하는 API (개발용)"""
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)
        level = data.get('level', 'info')
        
        # 환경변수 업데이트
        os.environ['TIMETABLING_LOG_LEVEL'] = level.upper()
        
        # 로깅 시스템 재초기화
        from logger_config import setup_logging
        setup_logging()
        
        logger.info(f"디버깅 설정 변경: enabled={enabled}, level={level}")
        
        return jsonify({
            'success': True,
            'message': '디버깅 설정이 변경되었습니다',
            'config': {
                'enabled': enabled,
                'level': level
            }
        })
        
    except Exception as e:
        logger.error(f"디버깅 설정 변경 오류: {e}")
        return jsonify({
            'success': False,
            'message': f'설정 변경 실패: {str(e)}'
        }), 500

@app.route('/api/schedule', methods=['POST'])
def create_schedule():
    """시험 시간표 생성 API"""
    logger.debug("=" * 50)
    logger.debug("🔥 SCHEDULE API CALLED! 🔥")
    logger.debug("=" * 50)
    
    global schedule_status
    
    try:
        # 상태 초기화
        with schedule_lock:
            schedule_status.update({
                "step": "요청을 처리하고 있습니다...",
                "progress": 5,
                "is_running": True,
                "result": None,
                "error": None
            })
        
        # 설정 데이터 받기
        payload = request.json or {}
        config_data = payload.get('config', {})
        user_time_limit = payload.get('time_limit', 120)
        
        
        # 설정 객체 생성 (일수/교시시간 제한은 /exam-info 데이터 사용)
        with schedule_lock:
            schedule_status["step"] = "설정을 구성하고 있습니다..."
            schedule_status["progress"] = 10
        
        # 학생 부담 조정 설정 파일에서 설정 로드
        student_burden_config_file = os.path.join(UPLOAD_FOLDER, 'student_burden_config.json')
        if os.path.exists(student_burden_config_file):
            try:
                with open(student_burden_config_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:  # Only try to parse if file has content
                        student_burden_config = json.loads(content)
                    else:
                        student_burden_config = {
                            'max_exams_per_day': None,
                            'max_hard_exams_per_day': None
                        }
            except (json.JSONDecodeError, FileNotFoundError):
                student_burden_config = {
                    'max_exams_per_day': None,
                    'max_hard_exams_per_day': None
                }
        else:
            # 기본값 사용 (제한 없음)
            student_burden_config = {
                'max_exams_per_day': None,
                'max_hard_exams_per_day': None
            }
            
        config = ExamSchedulingConfig(
            max_exams_per_day=student_burden_config.get('max_exams_per_day'),
            max_hard_exams_per_day=student_burden_config.get('max_hard_exams_per_day'),
            exam_days=6,  # 실제 슬롯 생성은 exam_info 기반으로 하므로 이 값은 더 이상 의미 없음
            periods_per_day=4,  # 기본값 (슬롯 생성은 exam_info의 date_periods 기준)
            period_limits={}
        )
        
        # 애플리케이션 초기화
        app_instance = ExamSchedulerApp(config=config, data_dir=UPLOAD_FOLDER)
        
        # 고정 배치 설정 (기본값: True, 프론트엔드에서 전달된 값 사용)
        keep_manual = config_data.get('keep_manual_assignments', True)
        app_instance.set_use_fixed_assignments(keep_manual)
        
        # 데이터 로드
        with schedule_lock:
            schedule_status["step"] = "데이터를 로드하고 있습니다..."
            schedule_status["progress"] = 20
            
        if not app_instance.load_all_data():
            with schedule_lock:
                schedule_status["step"] = "데이터 로드 실패"
                schedule_status["is_running"] = False
                schedule_status["error"] = "데이터 로드에 실패했습니다."
            return jsonify({
                'success': False,
                'error': '데이터 로드에 실패했습니다. 파일을 확인해주세요.'
            }), 400
        
        # 시험 시간표 생성
        def update_status(step, progress):
            with schedule_lock:
                schedule_status["step"] = step
                schedule_status["progress"] = progress
        
        status, result = app_instance.create_schedule(time_limit=int(user_time_limit), status_callback=update_status)
        
        if status == "SUCCESS":
            # 결과 저장
            with schedule_lock:
                schedule_status["step"] = "결과를 저장하고 있습니다..."
                schedule_status["progress"] = 90
                
            app_instance.save_results(result, "results")
            
            # 완료 상태
            with schedule_lock:
                schedule_status["step"] = "완료"
                schedule_status["progress"] = 100
                schedule_status["is_running"] = False
                schedule_status["result"] = "success"
            
            return jsonify({
                'success': True,
                'message': '시험 시간표가 성공적으로 생성되었습니다!',
                'slot_assignments': result.get('slot_assignments', {})
            })
        else:
            # 실패 상태 업데이트
            with schedule_lock:
                schedule_status["step"] = "생성 실패"
                schedule_status["is_running"] = False
                schedule_status["error"] = status
                schedule_status["progress"] = 100
                
            # 더 구체적인 에러 메시지 제공
            error_message = f'시험 시간표 생성 실패: {status}'
            if status == "NO_SOLUTION":
                # 진단 정보가 있으면 사용
                if isinstance(result, dict) and 'diagnosis' in result:
                    diagnosis = result['diagnosis']
                    error_message = '시험 시간표를 생성할 수 없습니다.\n\n'
                    
                    if diagnosis.get('possible_causes'):
                        error_message += '🔍 가능한 원인:\n'
                        for cause in diagnosis['possible_causes']:
                            error_message += f'• {cause}\n'
                        error_message += '\n'
                    
                    if diagnosis.get('recommendations'):
                        error_message += '💡 해결 방법:\n'
                        for rec in diagnosis['recommendations']:
                            error_message += f'• {rec}\n'
                        error_message += '\n'
                    
                    if diagnosis.get('constraint_info'):
                        info = diagnosis['constraint_info']
                        error_message += f'📊 제약조건 정보:\n'
                        error_message += f'• 총 슬롯 수: {info.get("total_slots", "N/A")}\n'
                        error_message += f'• 총 과목 수: {info.get("total_subjects", "N/A")}\n'
                        
                        if info.get('subjects_with_few_slots'):
                            error_message += f'• 배정 가능 슬롯이 적은 과목: {", ".join(info["subjects_with_few_slots"])}\n'
                        
                        if info.get('high_conflict_subjects'):
                            error_message += f'• 충돌이 많은 과목: {", ".join(info["high_conflict_subjects"])}\n'
                else:
                    error_message = '시험 시간표를 생성할 수 없습니다. 가능한 원인:\n' + \
                                  '• 시험 일수나 교시 수가 너무 많습니다.\n' + \
                                  '• 과목 간 충돌이 너무 많습니다.\n' + \
                                  '• 교사 불가능 시간이 너무 많습니다.\n' + \
                                  '• 풀이 시간을 늘려보세요.'
            elif status == "INFEASIBLE":
                if isinstance(result, dict) and 'details' in result:
                    details = result['details']
                    error_message = '시험 시간표 생성이 불가능합니다.\n\n'
                    error_message += '🔍 제약조건 문제:\n'
                    for issue in details:
                        error_message += f'• {issue}\n'
                    error_message += '\n💡 해결 방법:\n'
                    error_message += '• 시험 일수나 교시 수를 늘려보세요\n'
                    error_message += '• 과목 간 충돌을 줄여보세요\n'
                    error_message += '• 교사 불가능 시간을 줄여보세요'
                else:
                    error_message = '시험 시간표 생성이 불가능합니다. 제약조건이 너무 엄격합니다.'
                
                # INFEASIBLE 상태에 대한 진단 정보도 제공
                diagnosis = {
                    'possible_causes': ['제약조건이 너무 엄격합니다'],
                    'recommendations': [
                        '시험 일수나 교시 수를 늘려보세요',
                        '과목 간 충돌을 줄여보세요',
                        '교사 불가능 시간을 줄여보세요'
                    ],
                    'constraint_info': {
                        'total_slots': result.get('total_slots', 'N/A') if isinstance(result, dict) else 'N/A',
                        'total_subjects': result.get('total_subjects', 'N/A') if isinstance(result, dict) else 'N/A'
                    }
                }
                
                # validation_result에서 추가 정보 가져오기
                if isinstance(result, dict) and 'details' in result:
                    # details가 validation_result['issues']인 경우, 추가 정보도 포함
                    if hasattr(result, 'get') and result.get('total_slots') is not None:
                        diagnosis['constraint_info']['total_slots'] = result.get('total_slots')
                    if hasattr(result, 'get') and result.get('total_subjects') is not None:
                        diagnosis['constraint_info']['total_subjects'] = result.get('total_subjects')
            elif status == "ERROR":
                error_message = f'시험 시간표 생성 중 오류가 발생했습니다: {result.get("error", "알 수 없는 오류")}'
            
            # INFEASIBLE 상태일 때는 diagnosis 변수가 정의되어 있음
            if status == "INFEASIBLE" and 'diagnosis' in locals():
                return jsonify({
                    'success': False,
                    'error': error_message,
                    'details': result.get('details', []) if isinstance(result, dict) else [],
                    'diagnosis': diagnosis
                }), 400
            else:
                return jsonify({
                    'success': False,
                    'error': error_message,
                    'details': result.get('details', []) if isinstance(result, dict) else [],
                    'diagnosis': result.get('diagnosis', {}) if isinstance(result, dict) else {}
                }), 400
            
    except Exception as e:
        # 예외 발생시 상태 업데이트
        with schedule_lock:
            schedule_status["step"] = "오류 발생"
            schedule_status["is_running"] = False
            schedule_status["error"] = str(e)
            schedule_status["progress"] = 100
            
        self.logger.debug(f"Error in create_schedule: {str(e)}")  # 디버깅
        self.logger.debug(f"Traceback: {traceback.format_exc()}")  # 디버깅
        return jsonify({
            'success': False,
            'error': f'오류가 발생했습니다: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500


@app.route('/api/results')
def get_results():
    """결과 데이터 API"""
    try:
        result_file = Path('results/schedule_result.json')
        summary_file = Path('results/schedule_summary.json')
        
        if result_file.exists() and summary_file.exists():
            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:  # Only try to parse if file has content
                        result = json.loads(content)
                    else:
                        return jsonify({
                            'success': False,
                            'error': '결과 파일이 비어있습니다.'
                        }), 404
                with open(summary_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:  # Only try to parse if file has content
                        summary = json.loads(content)
                    else:
                        return jsonify({
                            'success': False,
                            'error': '요약 파일이 비어있습니다.'
                        }), 404
            except (json.JSONDecodeError, FileNotFoundError) as e:
                return jsonify({
                    'success': False,
                    'error': f'결과 파일 파싱 오류: {str(e)}'
                }), 500
            
            return jsonify({
                'success': True,
                'result': result,
                'summary': summary
            })
        else:
            return jsonify({
                'success': False,
                'error': '결과 파일을 찾을 수 없습니다.'
            }), 404
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'결과 로드 중 오류: {str(e)}'
        }), 500

@app.route('/download/<filename>')
def download_file(filename):
    """결과 파일 다운로드"""
    try:
        file_path = Path('results') / filename
        if file_path.exists():
            return send_file(file_path, as_attachment=True)
        else:
            flash('파일을 찾을 수 없습니다.', 'error')
            return redirect(url_for('schedule_manager'))
    except Exception as e:
        flash(f'다운로드 중 오류: {str(e)}', 'error')
        return redirect(url_for('schedule_manager'))

@app.route('/api/upload-status')
def upload_status():
    """업로드된 파일 상태 확인"""
    try:
        files = os.listdir(UPLOAD_FOLDER)
        self.logger.debug(f"Files in upload folder: {files}")  # 디버깅
        
        required_files = [
            '학생배정정보.xlsx',
            '과목 정보.xlsx', 
            '시험 정보.xlsx',
            '시험 불가 교사.xlsx'
        ]
        
        status = {}
        for file in required_files:
            status[file] = file in files
        
        self.logger.debug(f"File status: {status}")  # 디버깅
        
        return jsonify({
            'success': True,
            'files': status,
            'all_uploaded': all(status.values())
        })
    except Exception as e:
        self.logger.debug(f"Error in upload_status: {str(e)}")  # 디버깅
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/data-review')
def data_review():
    """데이터 검토 및 편집 페이지"""
    return render_template('data_review.html')




@app.route('/conflict-selection')
def conflict_selection():
    """충돌 데이터 유형 선택 페이지"""
    return render_template('conflict_selection.html')

@app.route('/conflict-data')
def conflict_data():
    """과목 충돌 정보 편집 페이지 (개별 학생) - 기존 링크 호환성을 위해 유지"""
    try:
        # 필요한 파일들이 있는지 확인
        exam_info_path = os.path.join(app.config['UPLOAD_FOLDER'], '과목 정보.xlsx')
        exam_scope_path = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_scope.json')
        
        if not os.path.exists(exam_info_path) or not os.path.exists(exam_scope_path):
            # 파일이 없으면 과목 정보 파일을 먼저 업로드하라는 메시지와 함께 페이지 렌더링
            return render_template('conflict_data.html', show_upload_message=True)
        
        return render_template('conflict_data.html', show_upload_message=False)
    except Exception as e:
        self.logger.debug(f"Error in conflict_data route: {e}")
        # 에러가 발생해도 페이지는 렌더링
        return render_template('conflict_data.html', show_upload_message=True)

@app.route('/conflict-data-same-grade')
def conflict_data_same_grade():
    """같은 학년 학생 충돌 정보 편집 페이지"""
    try:
        # individual_conflicts.json 파일 삭제 (파일이 없을 때 에러 방지)
        individual_conflicts_path = os.path.join(app.config['UPLOAD_FOLDER'], 'individual_conflicts.json')
        if os.path.exists(individual_conflicts_path):
            try:
                os.remove(individual_conflicts_path)
                self.logger.debug(f"individual_conflicts.json 파일이 삭제되었습니다.")
            except Exception as e:
                self.logger.debug(f"individual_conflicts.json 파일 삭제 중 오류: {e}")
        
        # 학생배정정보.xlsx 파일 삭제 (파일이 없을 때 에러 방지)
        enrollment_file_path = os.path.join(app.config['UPLOAD_FOLDER'], '학생배정정보.xlsx')
        if os.path.exists(enrollment_file_path):
            try:
                os.remove(enrollment_file_path)
                self.logger.debug(f"학생배정정보.xlsx 파일이 삭제되었습니다.")
            except Exception as e:
                self.logger.debug(f"학생배정정보.xlsx 파일 삭제 중 오류: {e}")
        
        # 과목 정보 파일 존재 여부 확인
        subject_info_path = os.path.join(app.config['UPLOAD_FOLDER'], '과목 정보.xlsx')
        exam_scope_path = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_scope.json')
        
        show_upload_message = not (os.path.exists(subject_info_path) and os.path.exists(exam_scope_path))
        
        return render_template('conflict_data_same_grade.html', show_upload_message=show_upload_message)
    except Exception as e:
        self.logger.debug(f"Error in conflict_data_same_grade route: {e}")
        # 에러가 발생해도 페이지는 렌더링 (업로드 메시지 표시)
        return render_template('conflict_data_same_grade.html', show_upload_message=True)

@app.route('/api/conflict-data')
def get_conflict_data():
    """과목 충돌 정보 로드 (개별 학생)"""
    try:
        # 파일 존재 여부 확인
        file_path = Path(app.config['UPLOAD_FOLDER']) / "학생배정정보.xlsx"
        if not file_path.exists():
            return jsonify({
                'success': False,
                'error': 'no_file',
                'message': '분반배정표 파일이 업로드되지 않았습니다.'
            })
        
        data_loader = DataLoader(app.config['UPLOAD_FOLDER'])
        student_conflict_dict, double_enroll_dict, student_names, enroll_bool = data_loader.load_enrollment_data()
        
        # 제거된 충돌 목록 로드
        removed_conflicts = load_custom_conflicts('student_removed')
        removed_pairs = set()
        for removed in removed_conflicts:
            # 양방향으로 제거된 쌍 저장
            removed_pairs.add((removed['subject1'], removed['subject2']))
            removed_pairs.add((removed['subject2'], removed['subject1']))
        
        # 충돌 정보를 프론트엔드에서 사용하기 쉬운 형태로 변환
        conflicts = []
        for subject1, conflict_subjects in student_conflict_dict.items():
            for subject2 in conflict_subjects:
                # 중복 방지를 위해 정렬된 키 사용
                if subject1 < subject2:
                    # 제거된 충돌인지 확인
                    if (subject1, subject2) not in removed_pairs:
                        shared_students = double_enroll_dict[subject1].get(subject2, [])
                        conflicts.append({
                            'subject1': subject1,
                            'subject2': subject2,
                            'shared_students': shared_students,
                            'student_count': len(shared_students),
                            'type': '개별 학생',
                            'description': f'{subject1}과 {subject2}는 {len(shared_students)}명의 공통 수강 학생이 있어 같은 시간에 배정할 수 없습니다.'
                        })
        
        # 커스텀 충돌 추가 (제거되지 않은 것들만)
        custom_conflicts = load_custom_conflicts('individual')
        for custom_conflict in custom_conflicts:
            subject1 = custom_conflict['subject1']
            subject2 = custom_conflict['subject2']
            if (subject1, subject2) not in removed_pairs and (subject2, subject1) not in removed_pairs:
                conflicts.append(custom_conflict)
        
        return jsonify({
            'success': True,
            'conflicts': conflicts,
            'subjects': list(enroll_bool.columns),
            'total_conflicts': len(conflicts)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/conflict-data-same-grade')
def get_same_grade_conflict_data():
    """같은 학년 학생 충돌 정보 로드"""
    try:
        # 같은 학년 충돌 데이터 로드
        conflicts = load_custom_conflicts('same_grade')
        
        return jsonify({
            'success': True,
            'conflicts': conflicts,
            'total_conflicts': len(conflicts)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# @app.route('/api/update-same-grade-conflicts', methods=['POST'])
# def update_same_grade_conflicts():
#     """같은 학년 학생 충돌 정보 업데이트"""
#     try:
#         data = request.get_json()
#         conflicts_to_remove = data.get('conflicts_to_remove', [])
        
#         # 제거된 충돌 목록 로드
#         removed_conflicts = load_custom_conflicts('same_grade_removed')
        
#         # 제거할 충돌들 처리
#         removed_count = 0
#         for conflict_to_remove in conflicts_to_remove:
#             subject1 = conflict_to_remove['subject1']
#             subject2 = conflict_to_remove['subject2']
            
#             # 이미 제거된 충돌인지 확인
#             already_removed = any(
#                 (conflict['subject1'] == subject1 and conflict['subject2'] == subject2) or
#                 (conflict['subject1'] == subject2 and conflict['subject2'] == subject1)
#                 for conflict in removed_conflicts
#             )
            
#             if not already_removed:
#                 removed_conflicts.append({
#                     'subject1': subject1,
#                     'subject2': subject2,
#                     'removed_at': str(datetime.now())
#                 })
#                 removed_count += 1
        
#         # 수정된 제거된 충돌 목록 저장
#         if save_custom_conflicts('same_grade_removed', removed_conflicts):
#             return jsonify({
#                 'success': True,
#                 'message': f'{removed_count}개의 충돌이 제거되었습니다.'
#             })
#         else:
#             return jsonify({
#                 'success': False,
#                 'error': '충돌 저장에 실패했습니다.'
#             }), 500
            
#     except Exception as e:
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# @app.route('/api/update-conflicts', methods=['POST'])
# def update_conflicts():
#     """개별 학생 충돌 정보 업데이트"""
#     try:
#         data = request.get_json()
#         conflicts_to_remove = data.get('conflicts_to_remove', [])
        
#         # 제거된 충돌 목록 로드 (기존 제거된 충돌들)
#         removed_conflicts = load_custom_conflicts('student_removed')
        
#         # 제거할 충돌들 처리
#         removed_count = 0
#         for conflict_to_remove in conflicts_to_remove:
#             subject1 = conflict_to_remove['subject1']
#             subject2 = conflict_to_remove['subject2']
            
#             # 이미 제거된 충돌인지 확인
#             already_removed = any(
#                 (conflict['subject1'] == subject1 and conflict['subject2'] == subject2) or
#                 (conflict['subject1'] == subject2 and conflict['subject2'] == subject1)
#                 for conflict in removed_conflicts
#             )
            
#             if not already_removed:
#                 removed_conflicts.append({
#                     'subject1': subject1,
#                     'subject2': subject2,
#                     'removed_at': str(datetime.now())
#                 })
#                 removed_count += 1
        
#         # 수정된 제거된 충돌 목록 저장
#         if save_custom_conflicts('student_removed', removed_conflicts):
#             return jsonify({
#                 'success': True,
#                 'message': f'{removed_count}개의 충돌이 제거되었습니다.'
#             })
#         else:
#             return jsonify({
#                 'success': False,
#                 'error': '충돌 저장에 실패했습니다.'
#             }), 500
            
#     except Exception as e:
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

@app.route('/api/update-listening-conflicts', methods=['POST'])
def update_listening_conflicts():
    """듣기평가 충돌 정보 업데이트"""
    try:
        data = request.get_json()
        conflicts_to_remove = data.get('conflicts_to_remove', [])
        
        # 커스텀 충돌 로드
        custom_conflicts = load_custom_conflicts('listening')
        
        # 제거할 충돌들 처리
        removed_count = 0
        for conflict_to_remove in conflicts_to_remove:
            subject1 = conflict_to_remove['subject1']
            subject2 = conflict_to_remove['subject2']
            
            # 커스텀 충돌에서 제거
            custom_conflicts = [conflict for conflict in custom_conflicts 
                              if not ((conflict['subject1'] == subject1 and conflict['subject2'] == subject2) or
                                     (conflict['subject1'] == subject2 and conflict['subject2'] == subject1))]
            removed_count += 1
        
        # 수정된 커스텀 충돌 저장
        if save_custom_conflicts('listening', custom_conflicts):
            return jsonify({
                'success': True,
                'message': f'{removed_count}개의 듣기평가 충돌이 제거되었습니다.'
            })
        else:
            return jsonify({
                'success': False,
                'error': '충돌 저장에 실패했습니다.'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/update-teacher-conflicts', methods=['POST'])
def update_teacher_conflicts():
    """교사 충돌 정보 업데이트"""
    try:
        data = request.json
        conflicts_to_remove = data.get('conflicts_to_remove', [])
        
        # 기존 교사 충돌 데이터 로드
        existing_conflicts = load_teacher_conflicts()
        
        # 제거할 충돌들 처리
        removed_count = 0
        for conflict_to_remove in conflicts_to_remove:
            subject1 = conflict_to_remove['subject1']
            subject2 = conflict_to_remove['subject2']
            
            # 기존 충돌 목록에서 제거
            existing_conflicts = [
                c for c in existing_conflicts
                if not ((c['subject1'] == subject1 and c['subject2'] == subject2) or
                       (c['subject1'] == subject2 and c['subject2'] == subject1))
            ]
            removed_count += 1
        
        # 수정된 충돌 목록 저장
        if save_teacher_conflicts(existing_conflicts):
            return jsonify({
                'success': True,
                'message': f'{removed_count}개의 교사 충돌이 제거되었습니다.'
            })
        else:
            return jsonify({
                'success': False,
                'error': '충돌 저장에 실패했습니다.'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/listening-conflicts')
def get_listening_conflicts():
    """듣기평가 충돌 정보 로드"""
    try:
        # 과목 정보 파일 확인
        exam_scope_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_scope.json')
        if not os.path.exists(exam_scope_file):
            return jsonify({
                'success': False,
                'error': 'no_exam_scope',
                'message': '과목 정보 파일이 없습니다. 먼저 과목 정보를 설정해주세요.'
            }), 404
        
        data_loader = DataLoader(app.config['UPLOAD_FOLDER'])
        # 과목 정보 로드
        subject_info = data_loader.load_subject_info()
        
        # 듣기평가 과목들 추출
        listening_subjects = [subject for subject, info in subject_info.items() if info['듣기평가'] == 1]
        
        # 초기에는 빈 충돌 목록으로 시작 (자동생성 버튼으로만 생성)
        conflicts = []
        
        # 커스텀 충돌만 로드 (기존에 저장된 듣기 충돌이 있다면)
        custom_conflicts = load_custom_conflicts('listening')
        conflicts.extend(custom_conflicts)
        
        return jsonify({
            'success': True,
            'conflicts': conflicts,
            'subjects': list(subject_info.keys()),  # 모든 과목 반환
            'listening_subjects': listening_subjects,  # 듣기 과목만 별도로
            'total_listening_subjects': len(listening_subjects)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/teacher-conflicts')
def get_teacher_conflicts():
    """교사 충돌 정보 로드 (기본 정보만)"""
    try:
        # 과목 정보 파일 확인
        exam_scope_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_scope.json')
        if not os.path.exists(exam_scope_file):
            return jsonify({
                'success': False,
                'error': 'no_exam_scope',
                'message': '과목 정보 파일이 없습니다. 먼저 과목 정보를 설정해주세요.'
            }), 404
        
        data_loader = DataLoader(app.config['UPLOAD_FOLDER'])
        # 과목 정보 로드
        subject_info = data_loader.load_subject_info()
        
        # 교사 충돌 파일에서 데이터 로드
        conflicts = load_teacher_conflicts()
        
        subjects = list(subject_info.keys())
        
        return jsonify({
            'success': True,
            'conflicts': conflicts,
            'subjects': subjects
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/teachers-list')
def get_teachers_list():
    """교사 목록 조회 API (교사 충돌 추가용)"""
    try:
        # 과목 정보 파일 확인
        exam_scope_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_scope.json')
        if not os.path.exists(exam_scope_file):
            return jsonify({
                'success': False,
                'error': 'no_exam_scope',
                'message': '과목 정보 파일이 없습니다. 먼저 과목 정보를 설정해주세요.'
            }), 404
        
        # 과목 정보 로드
        with open(exam_scope_file, 'r', encoding='utf-8') as f:
            subjects = json.load(f)
        
        # 교사 리스트 추출 (담당교사 필드에서 중복 제거 후 오름차순 정렬)
        teachers = set()
        for subject_data in subjects.values():
            if '담당교사' in subject_data and isinstance(subject_data['담당교사'], list):
                teachers.update(subject_data['담당교사'])
        
        teachers = sorted(list(teachers))
        
        return jsonify({
            'success': True,
            'teachers': teachers
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'교사 목록 로드 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/listening-conflicts')
def listening_conflicts():
    """듣기평가 충돌 편집 페이지"""
    return render_template('listening_conflicts.html')

@app.route('/teacher-conflicts')
def teacher_conflicts():
    """교사 충돌 편집 페이지"""
    return render_template('teacher_conflicts.html')

@app.route('/api/add-student-conflict', methods=['POST'])
def add_student_conflict():
    """학생 충돌 추가"""
    try:
        data = request.get_json()
        subject1 = data.get('subject1')
        subject2 = data.get('subject2')
        shared_students = data.get('shared_students', [])
        
        if not subject1 or not subject2:
            return jsonify({'success': False, 'error': '과목명이 필요합니다.'}), 400
        
        # 새로운 충돌 생성
        new_conflict = {
            'subject1': subject1,
            'subject2': subject2,
            'shared_students': shared_students,
            'student_count': len(shared_students),
            'type': '학생',
            'description': f'{subject1}과 {subject2}는 {len(shared_students)}명의 공통 수강 학생이 있어 같은 시간에 배정할 수 없습니다.'
        }
        
        # 기존 커스텀 충돌 로드
        custom_conflicts = load_custom_conflicts('individual')
        
        # 중복 확인
        for conflict in custom_conflicts:
            if (conflict['subject1'] == subject1 and conflict['subject2'] == subject2) or \
               (conflict['subject1'] == subject2 and conflict['subject2'] == subject1):
                return jsonify({'success': False, 'error': '이미 존재하는 충돌입니다.'}), 400
        
        # 새 충돌 추가
        custom_conflicts.append(new_conflict)
        
        # 저장
        if save_custom_conflicts('individual', custom_conflicts):
            return jsonify({
                'success': True,
                'message': f'{subject1}과 {subject2} 간의 학생 충돌이 추가되었습니다.',
                'conflict': new_conflict
            })
        else:
            return jsonify({'success': False, 'error': '충돌 저장에 실패했습니다.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/add-listening-conflict', methods=['POST'])
def add_listening_conflict():
    """듣기평가 충돌 추가"""
    try:
        data = request.get_json()
        subject1 = data.get('subject1')
        subject2 = data.get('subject2')
        
        if not subject1 or not subject2:
            return jsonify({'success': False, 'error': '과목명이 필요합니다.'}), 400
        
        # 새로운 충돌 생성
        new_conflict = {
            'subject1': subject1,
            'subject2': subject2,
            'type': '듣기평가',
            'description': f'{subject1}과 {subject2}는 모두 듣기평가가 있어 같은 시간에 배정할 수 없습니다.'
        }
        
        # 기존 커스텀 충돌 로드
        custom_conflicts = load_custom_conflicts('listening')
        
        # 중복 확인
        for conflict in custom_conflicts:
            if (conflict['subject1'] == subject1 and conflict['subject2'] == subject2) or \
               (conflict['subject1'] == subject2 and conflict['subject2'] == subject1):
                return jsonify({'success': False, 'error': '이미 존재하는 충돌입니다.'}), 400
        
        # 새 충돌 추가
        custom_conflicts.append(new_conflict)
        
        # 저장
        if save_custom_conflicts('listening', custom_conflicts):
            return jsonify({
                'success': True,
                'message': f'{subject1}과 {subject2} 간의 듣기평가 충돌이 추가되었습니다.',
                'conflict': new_conflict
            })
        else:
            return jsonify({'success': False, 'error': '충돌 저장에 실패했습니다.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate-teacher-conflicts', methods=['POST'])
def generate_teacher_conflicts():
    """과목 정보를 바탕으로 교사 충돌 정보를 자동 생성합니다."""
    try:
        # 과목 정보 파일 확인
        exam_scope_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_scope.json')
        if not os.path.exists(exam_scope_file):
            return jsonify({
                'success': False,
                'error': '과목 정보 파일을 먼저 업로드해주세요.',
                'redirect': '/exam-scope'
            }), 400
        
        data_loader = DataLoader(app.config['UPLOAD_FOLDER'])
        # 과목 정보 로드
        subject_info = data_loader.load_subject_info()
        
        # 교사 충돌 정보 생성
        conflicts = []
        subjects = list(subject_info.keys())
        
        for i, subject1 in enumerate(subjects):
            teachers1 = set(subject_info[subject1]['담당교사'])
            for subject2 in subjects[i+1:]:
                teachers2 = set(subject_info[subject2]['담당교사'])
                common_teachers = teachers1 & teachers2
                
                if common_teachers:
                    conflicts.append({
                        'subject1': subject1,
                        'subject2': subject2,
                        'type': '교사',
                        'common_teachers': list(common_teachers),
                        'description': f'{subject1}과 {subject2}는 {", ".join(common_teachers)} 교사가 담당하여 같은 시간에 배정할 수 없습니다.'
                    })
        
        # 교사 충돌 파일에 저장 (기존 데이터를 완전히 덮어씀)
        save_teacher_conflicts(conflicts)
        
        return jsonify({
            'success': True,
            'conflicts': conflicts,
            'subjects': subjects,
            'message': f'{len(conflicts)}개의 교사 충돌이 생성되었습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'교사 충돌 생성 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/add-teacher-conflict', methods=['POST'])
def add_teacher_conflict():
    """교사 충돌 추가"""
    try:
        data = request.get_json()
        subject1 = data.get('subject1')
        subject2 = data.get('subject2')
        common_teachers = data.get('common_teachers', [])
        
        if not subject1 or not subject2:
            return jsonify({'success': False, 'error': '과목명이 필요합니다.'}), 400
        
        # 새로운 충돌 생성
        new_conflict = {
            'subject1': subject1,
            'subject2': subject2,
            'type': '교사',
            'common_teachers': common_teachers,
            'description': f'{subject1}과 {subject2}는 {", ".join(common_teachers)} 교사가 담당하여 같은 시간에 배정할 수 없습니다.'
        }
        
        # 기존 교사 충돌 데이터 로드
        existing_conflicts = load_teacher_conflicts()
        
        # 중복 확인
        for conflict in existing_conflicts:
            if (conflict['subject1'] == subject1 and conflict['subject2'] == subject2) or \
               (conflict['subject1'] == subject2 and conflict['subject2'] == subject1):
                return jsonify({'success': False, 'error': '이미 존재하는 충돌입니다.'}), 400
        
        # 새 충돌을 리스트에 추가
        existing_conflicts.append(new_conflict)
        
        # 저장
        if save_teacher_conflicts(existing_conflicts):
            return jsonify({
                'success': True,
                'message': f'{subject1}과 {subject2} 간의 교사 충돌이 추가되었습니다.',
                'conflict': new_conflict
            })
        else:
            return jsonify({'success': False, 'error': '충돌 저장에 실패했습니다.'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reset-all-data', methods=['POST'])
def reset_all_data():
    """uploads 폴더 내 모든 파일을 삭제하여 완전 초기화"""
    try:
        import shutil
        import os
        
        uploads_folder = app.config['UPLOAD_FOLDER']
        
        # uploads 폴더가 존재하는지 확인
        if not os.path.exists(uploads_folder):
            return jsonify({
                'success': True,
                'message': 'uploads 폴더가 존재하지 않습니다. 이미 초기화된 상태입니다.',
                'deleted_files': 0
            })
        
        # uploads 폴더 내 모든 파일과 폴더 삭제
        deleted_count = 0
        deleted_files = []
        
        try:
            for filename in os.listdir(uploads_folder):
                file_path = os.path.join(uploads_folder, filename)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                    deleted_count += 1
                    deleted_files.append(filename)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    deleted_count += 1
                    deleted_files.append(filename + '/')
        except Exception as e:
            self.logger.debug(f"Error deleting files: {e}")
        
        return jsonify({
            'success': True,
            'message': f'uploads 폴더가 완전히 초기화되었습니다. ({deleted_count}개 항목 삭제됨)',
            'deleted_files': deleted_count,
            'deleted_items': deleted_files
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'초기화 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/reset-student-conflicts', methods=['POST'])
def reset_student_conflicts():
    """학생 충돌 편집을 원본 상태로 초기화"""
    try:
        # 학생 충돌 관련 파일들 삭제
        student_files = [
            'custom_student_conflicts.json',
            'custom_student_removed_conflicts.json'
        ]
        
        deleted_count = 0
        for filename in student_files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_count += 1
        
        return jsonify({
            'success': True,
            'message': f'학생 충돌이 원본 상태로 초기화되었습니다. ({deleted_count}개 파일 삭제됨)',
            'deleted_files': deleted_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'학생 충돌 초기화 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/complete-reset-student-conflicts', methods=['POST'])
def complete_reset_student_conflicts():
    """학생 충돌 데이터를 완전히 초기화하고 업로드된 파일도 제거"""
    try:
        # 학생 충돌 관련 파일들 삭제
        student_files = [
            'custom_student_conflicts.json',
            'custom_student_removed_conflicts.json',
            'individual_conflicts.json'
        ]
        
        # 분반배정표 파일도 삭제
        enrollment_files = [
            '학생배정정보.xlsx'
        ]
        
        deleted_count = 0
        for filename in student_files + enrollment_files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_count += 1
        
        return jsonify({
            'success': True,
            'message': f'학생 충돌 데이터와 업로드된 파일이 완전히 제거되었습니다. ({deleted_count}개 파일 삭제됨)',
            'deleted_files': deleted_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'완전 초기화 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/generate-listening-conflicts', methods=['POST'])
def generate_listening_conflicts():
    """과목 정보를 바탕으로 듣기평가 충돌 정보를 자동 생성합니다."""
    try:
        # 과목 정보 파일 확인
        exam_scope_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_scope.json')
        if not os.path.exists(exam_scope_file):
            return jsonify({
                'success': False,
                'error': '과목 정보 파일을 먼저 업로드해주세요.',
                'redirect': '/exam-scope'
            }), 400
        
        data_loader = DataLoader(app.config['UPLOAD_FOLDER'])
        # 과목 정보 로드
        subject_info = data_loader.load_subject_info()
        
        # 듣기평가 과목들 추출
        listening_subjects = [subject for subject, info in subject_info.items() if info['듣기평가'] == 1]
        
        # 듣기평가 충돌 정보 생성
        conflicts = []
        for i, subject1 in enumerate(listening_subjects):
            for subject2 in listening_subjects[i+1:]:
                conflicts.append({
                    'subject1': subject1,
                    'subject2': subject2,
                    'type': '듣기평가',
                    'description': f'{subject1}과 {subject2}는 모두 듣기평가가 있어 같은 시간에 배정할 수 없습니다.'
                })
        
        # 듣기평가 충돌 파일에 저장 (기존 데이터를 완전히 덮어씀)
        save_custom_conflicts('listening', conflicts)
        
        return jsonify({
            'success': True,
            'conflicts': conflicts,
            'subjects': list(subject_info.keys()),
            'listening_subjects': listening_subjects,
            'total_listening_subjects': len(listening_subjects),
            'message': f'{len(conflicts)}개의 듣기평가 충돌이 생성되었습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'듣기평가 충돌 생성 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/reset-listening-conflicts', methods=['POST'])
def reset_listening_conflicts():
    """듣기 충돌 편집을 원본 상태로 초기화"""
    try:
        # 듣기 충돌 관련 파일들 삭제
        listening_files = [
            'custom_listening_conflicts.json'
        ]
        
        deleted_count = 0
        for filename in listening_files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_count += 1
        
        return jsonify({
            'success': True,
            'message': f'듣기 충돌이 원본 상태로 초기화되었습니다. ({deleted_count}개 파일 삭제됨)',
            'deleted_files': deleted_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'듣기 충돌 초기화 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/reset-teacher-conflicts', methods=['POST'])
def reset_teacher_conflicts():
    """교사 충돌 편집을 원본 상태로 초기화"""
    try:
        # 교사 충돌 파일 삭제
        teacher_conflicts_file = os.path.join(app.config['UPLOAD_FOLDER'], 'teacher_conflicts.json')
        
        deleted_count = 0
        if os.path.exists(teacher_conflicts_file):
            os.remove(teacher_conflicts_file)
            deleted_count = 1
        
        return jsonify({
            'success': True,
            'message': f'교사 충돌이 원본 상태로 초기화되었습니다. ({deleted_count}개 파일 삭제됨)',
            'deleted_files': deleted_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'교사 충돌 초기화 중 오류가 발생했습니다: {str(e)}'
        }), 500


@app.route('/exam-scope')
def exam_scope():
    """과목 정보 편집 페이지"""
    return render_template('exam_scope.html')

@app.route('/api/exam-scope-data')
def get_exam_scope_data():
    """과목 정보 데이터를 반환합니다"""
    try:
        data_loader = DataLoader(app.config['UPLOAD_FOLDER'])
        
        # 과목 정보 데이터 로드
        try:
            subject_info = data_loader.load_subject_info()
        except FileNotFoundError:
            # 파일이 없을 때는 안내 메시지 반환
            return jsonify({
                'success': False,
                'error': 'no_file',
                'message': '과목 정보 파일이 업로드되지 않았습니다. 파일을 업로드해주세요.'
            }), 404
        
        return jsonify({
            'success': True,
            'data': subject_info
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'과목 정보 데이터 로드 중 오류가 발생했습니다: {str(e)}'
        }), 500





@app.route('/api/reset-exam-scope', methods=['POST'])
def reset_exam_scope():
    """과목 정보를 초기화"""
    try:
        # 같은 학년 충돌 데이터 초기화
        conflict_files = [
            'same_grade_conflicts.json',
            'same_grade_removed_conflicts.json'
        ]
        
        deleted_count = 0
        for filename in conflict_files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_count += 1
        
        return jsonify({
            'success': True,
            'message': f'충돌 데이터가 초기화되었습니다. ({deleted_count}개 파일 삭제됨)',
            'deleted_files': deleted_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'초기화 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/complete-reset-exam-scope', methods=['POST'])
def complete_reset_exam_scope():
    """과목 정보를 완전히 초기화"""
    try:
        # 삭제할 파일들 목록
        files_to_delete = [
            'custom_exam_scope.json',    # 업로드된 엑셀의 JSON 표현
            '과목 정보.xlsx',            # 원본 업로드 파일
            'same_grade_conflicts.json', # 같은 학년 충돌 데이터
            'same_grade_removed_conflicts.json'  # 같은 학년 제거된 충돌 데이터
        ]
        
        deleted_count = 0
        deleted_files = []
        
        for filename in files_to_delete:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_count += 1
                deleted_files.append(filename)
        
        return jsonify({
            'success': True,
            'message': f'완전 초기화가 완료되었습니다. ({deleted_count}개 파일 삭제됨)',
            'deleted_files': deleted_files,
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'완전 초기화 중 오류가 발생했습니다: {str(e)}'
        }), 500

# 헬퍼 함수들
def load_custom_data(filename, default_value):
    """커스텀 데이터 파일을 로드합니다"""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:  # Only try to parse if file has content
                    return json.loads(content)
                else:
                    return default_value
        except Exception as e:
            self.logger.debug(f"Error loading {filename}: {e}")
    return default_value

def save_custom_data(filename, data):
    """커스텀 데이터를 파일에 저장합니다"""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        self.logger.debug(f"Error saving {filename}: {e}")

# 시험 정보 편집 관련 라우트들
def get_merged_exam_info():
    """시험 정보 데이터를 순수 딕셔너리로 반환하는 헬퍼 함수"""
    # 커스텀 시험 정보 데이터 로드
    custom_exam_info = load_custom_data('custom_exam_info.json', {})
    
    # 기본 시험 정보 구조 (원본 파일 없이도 작동)
    default_exam_info = {
        '학년도': '2024',
        '학기': '1',
        '고사종류': '중간고사',
        '시험날짜': {},
        'date_periods': {}
    }
    
    # 커스텀 데이터가 있으면 기본 정보와 병합
    if custom_exam_info:
        # 기본 정보 업데이트 (년도, 학기, 고사종류 등)
        for key in ['학년도', '학기', '고사종류']:
            if key in custom_exam_info:
                default_exam_info[key] = custom_exam_info[key]
        
        # 시험날짜 정보 병합 - 커스텀 데이터에 있는 것만
        if '시험날짜' in custom_exam_info:
            default_exam_info['시험날짜'] = custom_exam_info['시험날짜']
        
        # date_periods가 있으면 커스텀 데이터로 완전히 교체
        if 'date_periods' in custom_exam_info:
            default_exam_info['date_periods'] = custom_exam_info['date_periods']
        
        # 기타 필드들 업데이트
        for key, value in custom_exam_info.items():
            if key not in ['시험날짜', 'date_periods']:
                default_exam_info[key] = value
    
    # 커스텀 데이터가 완전히 없거나 date_periods가 없는 경우에만 기본 구조 제공
    if not custom_exam_info or 'date_periods' not in custom_exam_info:
        # 오늘 날짜를 YYYY-MM-DD 형식으로 가져오기
        today_date = datetime.now().strftime('%Y-%m-%d')
        
        # 기본 시험날짜 설정
        if not default_exam_info['시험날짜']:
            default_exam_info['시험날짜'] = {'제1일': today_date}
        
        # 기본 date_periods 구조 설정 (1일 1~4교시)
        if not default_exam_info['date_periods']:
            default_exam_info['date_periods'] = {}
            
            # 설정에서 기본값 가져오기
            config = DEFAULT_EXAM_INFO_CONFIG
            
            for period in range(1, config.default_periods + 1):
                start_time = config.get_start_time(period)
                duration = config.default_duration
                end_time = calculateEndTime(start_time, duration)
                
                default_exam_info['date_periods'][1] = default_exam_info['date_periods'].get(1, {})
                default_exam_info['date_periods'][1][period] = {
                    'start_time': start_time,
                    'duration': duration,
                    'end_time': end_time
                }
    
    return default_exam_info

@app.route('/exam-info')
def exam_info():
    """시험 정보 편집 페이지"""
    # 방문 시 기본 custom_exam_info.json 파일 자동 생성
    try:
        custom_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_info.json')
        if not os.path.exists(custom_file_path):
            # 기본 구조 생성
            default_data = {
                '학년도': '2024',
                '학기': '1',
                '고사종류': '중간고사',
                '시험날짜': {},
                'date_periods': {}
            }
            
            # 오늘 날짜를 YYYY-MM-DD 형식으로 가져오기
            today_date = datetime.now().strftime('%Y-%m-%d')
            default_data['시험날짜'] = {'제1일': today_date}
            
            # 기본 date_periods 구조 설정 (1일 1~4교시)
            config = DEFAULT_EXAM_INFO_CONFIG
            default_data['date_periods'] = {}
            
            for period in range(1, config.default_periods + 1):
                start_time = config.get_start_time(period)
                duration = config.default_duration
                end_time = calculateEndTime(start_time, duration)
                
                default_data['date_periods'][1] = default_data['date_periods'].get(1, {})
                default_data['date_periods'][1][period] = {
                    'start_time': start_time,
                    'duration': duration,
                    'end_time': end_time
                }
            
            # 파일 저장
            with open(custom_file_path, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, ensure_ascii=False, indent=2)
            
            pass
    except Exception as e:
        pass
    
    return render_template('exam_info.html')

@app.route('/api/exam-info-data')
def get_exam_info_data():
    """시험 정보 데이터를 반환합니다"""
    try:
        merged_exam_info = get_merged_exam_info()
        
        return jsonify({
            'success': True,
            'data': merged_exam_info
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'시험 정보 데이터 로드 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/update-exam-info', methods=['POST'])
def update_exam_info():
    """시험 정보를 업데이트합니다"""
    try:
        data = request.get_json()
        field = data.get('field')
        value = data.get('value')
        
        
        if not field:
            return jsonify({
                'success': False,
                'error': '필드명이 필요합니다.'
            }), 400
        
        # 커스텀 시험 정보 데이터 로드
        custom_data = load_custom_data('custom_exam_info.json', {})
        
        # 중첩된 필드 처리 (예: periods.1.start_time)
        if '.' in field:
            parts = field.split('.')
            current = custom_data
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # null 값이면 해당 필드를 완전히 삭제
            if value is None:
                if parts[-1] in current:
                    del current[parts[-1]]
            else:
                current[parts[-1]] = value
        else:
            # null 값이면 해당 필드를 완전히 삭제
            if value is None:
                if field in custom_data:
                    del custom_data[field]
            else:
                custom_data[field] = value
        
        # 커스텀 데이터 저장
        save_custom_data('custom_exam_info.json', custom_data)
        
        return jsonify({
            'success': True,
            'message': '시험 정보가 업데이트되었습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'시험 정보 업데이트 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/reset-exam-info', methods=['POST'])
def reset_exam_info():
    """시험 정보 편집을 원본 상태로 초기화"""
    try:
        # 시험 정보 관련 파일들 삭제
        exam_info_files = [
            'custom_exam_info.json'
        ]
        
        deleted_count = 0
        for filename in exam_info_files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_count += 1
        
        # 초기화 후 기본값 생성
        # 오늘 날짜를 YYYY-MM-DD 형식으로 가져오기
        today_date = datetime.now().strftime('%Y-%m-%d')
        
        # 설정에서 기본값 가져오기
        config = DEFAULT_EXAM_INFO_CONFIG
        
        default_exam_info = {
            '학년도': '2024',
            '학기': '1',
            '고사종류': '중간고사',
            '시험날짜': {
                config.get_day_label(1): today_date  # 오늘 날짜로 시작
            },
            'date_periods': {}
        }
        
        # 기본 교시 설정
        for period in range(1, config.default_periods + 1):
            start_time = config.get_start_time(period)
            duration = config.default_duration
            end_time = calculateEndTime(start_time, duration)
            
            default_exam_info['date_periods'][1] = default_exam_info['date_periods'].get(1, {})
            default_exam_info['date_periods'][1][period] = {
                'start_time': start_time,
                'duration': duration,
                'end_time': end_time
            }
        
        # 기본값을 custom_exam_info.json에 저장
        save_custom_data('custom_exam_info.json', default_exam_info)
        
        return jsonify({
            'success': True,
            'message': f'시험 정보가 기본값으로 초기화되었습니다. (제1일: {today_date}, 1~4교시 설정됨)',
            'deleted_files': deleted_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'시험 정보 초기화 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/exam-info-config')
def get_exam_info_config():
    """시험 정보 기본 설정을 반환합니다"""
    try:
        # 커스텀 설정 파일 경로
        config_file = os.path.join(app.config['UPLOAD_FOLDER'], 'exam_info_config.json')
        
        # 커스텀 설정이 있으면 사용, 없으면 기본값 사용
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                custom_config = json.load(f)
                config_data = custom_config
        else:
            config_data = DEFAULT_EXAM_INFO_CONFIG.to_dict()
        
        return jsonify({
            'success': True,
            'data': config_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'설정 데이터 로드 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/update-exam-info-config', methods=['POST'])
def update_exam_info_config():
    """시험 정보 기본 설정을 업데이트합니다"""
    try:
        data = request.get_json()
        
        # 설정 파일 경로
        config_file = os.path.join(app.config['UPLOAD_FOLDER'], 'exam_info_config.json')
        
        # 기존 설정 로드
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                current_config = json.load(f)
        else:
            current_config = DEFAULT_EXAM_INFO_CONFIG.to_dict()
        
        # 설정 업데이트 (빈 객체인 경우 기본값 사용)
        if not data:
            current_config = DEFAULT_SYSTEM_CONFIG.to_dict()
        else:
            for key, value in data.items():
                if key in current_config:
                    current_config[key] = value
        
        # 설정 저장
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(current_config, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': '설정이 업데이트되었습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'설정 업데이트 중 오류가 발생했습니다: {str(e)}'
        }), 500

# === 학생 부담 조정 관련 라우트 ===

@app.route('/student-burden-config')
def student_burden_config():
    """학생 부담 조정 설정 페이지"""
    return render_template('student_burden_config.html')

@app.route('/api/student-burden-config')
def get_student_burden_config():
    """학생 부담 조정 설정 데이터 조회 API"""
    try:
        # 기본 설정 파일에서 현재 설정 로드
        config_file = os.path.join(UPLOAD_FOLDER, 'student_burden_config.json')
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:  # Only try to parse if file has content
                        config_data = json.loads(content)
                    else:
                        config_data = {
                            'max_exams_per_day': None,
                            'max_hard_exams_per_day': None
                        }
            except (json.JSONDecodeError, FileNotFoundError):
                config_data = {
                    'max_exams_per_day': None,
                    'max_hard_exams_per_day': None
                }
        else:
            # 기본값 사용 (제한 없음)
            config_data = {
                'max_exams_per_day': None,
                'max_hard_exams_per_day': None
            }
        
        # 과목별 어려운 과목 설정 로드
        hard_subjects_file = os.path.join(UPLOAD_FOLDER, 'hard_subjects_config.json')
        hard_subjects_data = {}
        if os.path.exists(hard_subjects_file):
            try:
                with open(hard_subjects_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:  # Only try to parse if file has content
                        hard_subjects_data = json.loads(content)
                    else:
                        hard_subjects_data = {}
            except (json.JSONDecodeError, FileNotFoundError):
                hard_subjects_data = {}
        
        # exam-scope 데이터에서 과목 정보 가져오기
        # custom_exam_scope.json 파일이 있는지 확인
        exam_scope_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_scope.json')
        if not os.path.exists(exam_scope_file):
            return jsonify({
                'success': False,
                'error': 'no_exam_scope',
                'message': '과목 정보 파일이 없습니다. 먼저 과목 정보를 설정해주세요.'
            }), 404
        
        data_loader = DataLoader(app.config['UPLOAD_FOLDER'])
        merged_subject_info = data_loader.load_subject_info()
        
        # 과목별 어려운 과목 여부 설정
        for subject in merged_subject_info:
            if subject not in hard_subjects_data:
                hard_subjects_data[subject] = False
        
        return jsonify({
            'success': True,
            'config': config_data,
            'hard_subjects': hard_subjects_data,
            'subjects': merged_subject_info
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/update-student-burden-config', methods=['POST'])
def update_student_burden_config():
    """학생 부담 조정 설정 업데이트 API"""
    try:
        data = request.json
        if not data:
            return jsonify({
                'success': False,
                'error': '데이터가 제공되지 않았습니다.'
            }), 400
        
        # 설정 데이터 검증
        max_exams_per_day = data.get('max_exams_per_day')
        max_hard_exams_per_day = data.get('max_hard_exams_per_day')
        hard_subjects = data.get('hard_subjects', {})
        
        # 값이 제공된 경우에만 유효성 검사 (null은 제한 없음을 의미)
        if max_exams_per_day is not None:
            if not isinstance(max_exams_per_day, int) or max_exams_per_day <= 0:
                return jsonify({
                    'success': False,
                    'error': '하루 최대 시험 개수는 양의 정수여야 합니다.'
                }), 400
        
        if max_hard_exams_per_day is not None:
            if not isinstance(max_hard_exams_per_day, int) or max_hard_exams_per_day <= 0:
                return jsonify({
                    'success': False,
                    'error': '하루 최대 어려운 시험 개수는 양의 정수여야 합니다.'
                }), 400
        
        # 두 값이 모두 설정된 경우에만 관계 검증
        if max_exams_per_day is not None and max_hard_exams_per_day is not None:
            if max_hard_exams_per_day > max_exams_per_day:
                return jsonify({
                    'success': False,
                    'error': '하루 최대 어려운 시험 개수는 하루 최대 시험 개수보다 클 수 없습니다.'
                }), 400
        
        # 기본 설정 저장
        config_data = {
            'max_exams_per_day': max_exams_per_day,
            'max_hard_exams_per_day': max_hard_exams_per_day
        }
        
        config_file = os.path.join(UPLOAD_FOLDER, 'student_burden_config.json')
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        # 과목별 어려운 과목 설정 저장
        hard_subjects_file = os.path.join(UPLOAD_FOLDER, 'hard_subjects_config.json')
        with open(hard_subjects_file, 'w', encoding='utf-8') as f:
            json.dump(hard_subjects, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': '학생 부담 조정 설정이 성공적으로 저장되었습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/update-hard-subject', methods=['POST'])
def update_hard_subject():
    """과목별 어려운 과목 설정 업데이트 API"""
    try:
        data = request.json
        subject = data.get('subject')
        is_hard = data.get('is_hard')
        
        if subject is None or is_hard is None:
            return jsonify({
                'success': False,
                'error': '필수 파라미터가 누락되었습니다.'
            }), 400
        
        # 과목별 어려운 과목 설정 로드
        hard_subjects_file = os.path.join(UPLOAD_FOLDER, 'hard_subjects_config.json')
        hard_subjects_data = {}
        if os.path.exists(hard_subjects_file):
            try:
                with open(hard_subjects_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:  # Only try to parse if file has content
                        hard_subjects_data = json.loads(content)
                    else:
                        hard_subjects_data = {}
            except (json.JSONDecodeError, FileNotFoundError):
                hard_subjects_data = {}
        
        # 설정 업데이트
        hard_subjects_data[subject] = is_hard
        
        # 저장
        with open(hard_subjects_file, 'w', encoding='utf-8') as f:
            json.dump(hard_subjects_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': f'과목 "{subject}"의 어려운 과목 설정이 업데이트되었습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# === 교사 제약 편집 관련 라우트 ===

@app.route('/teacher-constraints')
def teacher_constraints():
    """교사 제약 편집 페이지"""
    return render_template('teacher_constraints.html')

@app.route('/api/teacher-constraints-data')
def get_teacher_constraints_data():
    """교사 제약 데이터 조회 API"""
    try:
        # 과목 정보 파일 확인
        exam_scope_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_scope.json')
        if not os.path.exists(exam_scope_file):
            return jsonify({
                'success': False,
                'error': 'no_exam_scope',
                'message': '과목 정보 파일이 없습니다. 먼저 과목 정보를 설정해주세요.'
            }), 404
        
        # 시험 정보 파일 확인
        exam_info_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_info.json')
        if not os.path.exists(exam_info_file):
            return jsonify({
                'success': False,
                'error': 'no_exam_info',
                'message': '시험 정보 파일이 없습니다. 먼저 시험 정보를 설정해주세요.'
            }), 404
        
        # 과목 정보 로드
        with open(exam_scope_file, 'r', encoding='utf-8') as f:
            subjects = json.load(f)
        
        # 교사 리스트 추출 (담당교사 필드에서 중복 제거 후 오름차순 정렬)
        teachers = set()
        for subject_data in subjects.values():
            if '담당교사' in subject_data and isinstance(subject_data['담당교사'], list):
                teachers.update(subject_data['담당교사'])
        
        teachers = sorted(list(teachers))
        
        # 시험 정보 로드
        with open(exam_info_file, 'r', encoding='utf-8') as f:
            exam_info = json.load(f)
        
        # 교사 제약 조건 파일 확인
        constraints_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_teacher_constraints.json')
        constraints = {}
        if os.path.exists(constraints_file):
            with open(constraints_file, 'r', encoding='utf-8') as f:
                constraints = json.load(f)
        
        # 시험 시간 슬롯 생성 (표준 형식: "제X일_X교시")
        time_slots = []
        if 'date_periods' in exam_info:
            for day, periods in exam_info['date_periods'].items():
                for period, time_info in periods.items():
                    # 표준 형식으로 생성: "제X일_X교시"
                    day_number = day.replace('일차', '')
                    time_slots.append(f"제{day_number}일_{period}교시")
        
        return jsonify({
            'success': True,
            'subjects': teachers,  # 교사 리스트 반환
            'time_slots': time_slots,
            'constraints': constraints
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'교사 제약 데이터 로드 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/update-teacher-constraints', methods=['POST'])
def update_teacher_constraints():
    """교사 제약 데이터 업데이트 API"""
    try:
        data = request.json
        constraints = data.get('constraints', [])
        
        # 커스텀 교사 제약 데이터 저장
        save_custom_teacher_constraints(constraints)
        
        return jsonify({
            'success': True,
            'message': '교사 제약이 성공적으로 저장되었습니다.',
            'saved_count': len(constraints)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'교사 제약 저장 실패: {str(e)}'
        }), 500

@app.route('/api/add-teacher-constraint', methods=['POST'])
def add_teacher_constraint():
    """교사 제약 조건을 추가합니다"""
    try:
        data = request.get_json()
        teacher = data.get('teacher')
        time_slot = data.get('time_slot')

        if not teacher or not time_slot:
            return jsonify({
                'success': False,
                'error': '교사와 시간 슬롯을 모두 입력해주세요.'
            }), 400
        
        # 교사 제약 조건 파일 경로
        constraints_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_teacher_constraints.json')
        
        # 기존 조건 로드
        constraints = {}
        if os.path.exists(constraints_file):
            with open(constraints_file, 'r', encoding='utf-8') as f:
                constraints = json.load(f)
        
        # 시간대 키를 표준 형식으로 변환 (예: "제1일 1교시(08:30-09:20)" -> "제1일_1교시")
        standardized_time_slot = standardize_time_slot_key(time_slot)
        
        # 조건 추가
        if teacher not in constraints:
            constraints[teacher] = {}
        
        constraints[teacher][standardized_time_slot] = {
            'created_at': datetime.now().isoformat()
        }
        
        # 파일에 저장
        with open(constraints_file, 'w', encoding='utf-8') as f:
            json.dump(constraints, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': f'{teacher} 교사의 제약 조건이 추가되었습니다.',
            'constraint': {
                'teacher': teacher,
                'time_slot': standardized_time_slot
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'교사 제약 조건 추가 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/delete-teacher-constraint', methods=['POST'])
def delete_teacher_constraint():
    """교사 제약 조건을 삭제합니다"""
    try:
        data = request.get_json()
        teacher = data.get('teacher')
        time_slot = data.get('time_slot')

        if not teacher or not time_slot:
            return jsonify({
                'success': False,
                'error': '교사와 시간 슬롯을 모두 입력해주세요.'
            }), 400
        
        # 교사 제약 조건 파일 경로
        constraints_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_teacher_constraints.json')
        
        if not os.path.exists(constraints_file):
            return jsonify({
                'success': False,
                'error': '교사 제약 조건 파일이 없습니다.'
            }), 404
        
        # 기존 조건 로드
        with open(constraints_file, 'r', encoding='utf-8') as f:
            constraints = json.load(f)
        
        # 시간대 키를 표준 형식으로 변환
        standardized_time_slot = standardize_time_slot_key(time_slot)
        
        # 조건 삭제
        if teacher in constraints and standardized_time_slot in constraints[teacher]:
            del constraints[teacher][standardized_time_slot]
            
            # 교사에 제약 조건이 없으면 교사도 삭제
            if not constraints[teacher]:
                del constraints[teacher]
            
            # 파일에 저장
            with open(constraints_file, 'w', encoding='utf-8') as f:
                json.dump(constraints, f, ensure_ascii=False, indent=2)
            
            return jsonify({
                'success': True,
                'message': f'{teacher} 교사의 제약 조건이 삭제되었습니다.'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'{teacher} 교사의 {standardized_time_slot} 시간대 제약 조건을 찾을 수 없습니다.'
            }), 404
        
        # 저장
        save_custom_teacher_constraints(updated_constraints)
        
        return jsonify({
            'success': True,
            'message': f'{teacher_name} 교사의 제약이 삭제되었습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'교사 제약 삭제 실패: {str(e)}'
        }), 500

@app.route('/api/reset-teacher-constraints', methods=['POST'])
def reset_teacher_constraints():
    """교사 제약 편집을 원본 상태로 초기화"""
    try:
        # 교사 제약 관련 파일들 삭제
        constraint_files = [
            'custom_teacher_constraints.json'
        ]
        
        deleted_count = 0
        for filename in constraint_files:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_count += 1
        
        return jsonify({
            'success': True,
            'message': f'교사 제약이 원본 상태로 초기화되었습니다. ({deleted_count}개 파일 삭제됨)',
            'deleted_files': deleted_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'교사 제약 초기화 중 오류가 발생했습니다: {str(e)}'
        }), 500

# 교사 제약 관련 헬퍼 함수들

def load_custom_teacher_constraints():
    """커스텀 교사 제약 데이터 로드"""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_teacher_constraints.json')
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:  # Only try to parse if file has content
                    return json.loads(content)
                else:
                    return []
        except Exception as e:
            self.logger.debug(f"Error loading custom teacher constraints: {e}")
    return []

def save_custom_teacher_constraints(constraints):
    """커스텀 교사 제약 데이터 저장"""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_teacher_constraints.json')
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(constraints, f, ensure_ascii=False, indent=2)
    except Exception as e:
        self.logger.debug(f"Error saving custom teacher constraints: {e}")
        raise

def merge_teacher_constraints(original_constraints, custom_constraints):
    """원본 교사 제약과 커스텀 교사 제약 병합"""
    merged = {}
    
    # 원본 데이터 추가
    for teacher, slots in original_constraints.items():
        merged[teacher] = {
            'teacher_name': teacher,
            'constraint_slots': slots,
            'is_original': True,
            'is_custom': False
        }
    
    # 커스텀 데이터 추가/덮어쓰기
    for constraint in custom_constraints:
        teacher = constraint.get('teacher_name')
        if teacher:
            merged[teacher] = {
                'teacher_name': teacher,
                'constraint_slots': constraint.get('constraint_slots', []),
                'is_original': teacher in original_constraints,
                'is_custom': True
            }
    
    return list(merged.values())

# 같은 학년 과목 충돌 생성 관련 API
@app.route('/api/generate-same-grade-conflicts', methods=['POST'])
def generate_same_grade_conflicts():
    """과목 정보를 바탕으로 같은 학년 과목 간의 충돌 정보를 생성합니다."""
    try:
        # custom_exam_scope.json 파일이 존재하는지 확인
        custom_exam_scope_path = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_scope.json')
        
        if not os.path.exists(custom_exam_scope_path):
            return jsonify({
                'success': False,
                'error': '과목 정보 파일을 먼저 업로드해주세요.',
                'redirect': '/exam-scope'
            }), 400
        
        # custom_exam_scope.json 파일 로드
        with open(custom_exam_scope_path, 'r', encoding='utf-8') as f:
            exam_scope_data = json.load(f)
        
        # 같은 학년 과목 간의 충돌 정보 생성
        conflicts = []
        
        # 모든 과목 쌍에 대해 검사
        subject_names = list(exam_scope_data.keys())
        
        for i, subj1 in enumerate(subject_names):
            for j, subj2 in enumerate(subject_names[i+1:], i+1):
                # 두 과목의 학년 정보 가져오기
                grade1 = exam_scope_data[subj1].get('학년', '')
                grade2 = exam_scope_data[subj2].get('학년', '')
                
                # 학년이 겹치는지 확인
                if grade1 and grade2:
                    # 학년이 쉼표로 구분된 경우 처리 (예: "2,3")
                    grades1 = [g.strip() for g in grade1.split(',')]
                    grades2 = [g.strip() for g in grade2.split(',')]
                    
                    # 공통 학년이 있는지 확인
                    common_grades = set(grades1) & set(grades2)
                    
                    if common_grades:
                        conflict_info = {
                            'subject1': subj1,
                            'subject2': subj2,
                            'common_grades': list(common_grades),
                            'type': '같은 학년',
                            'description': f'{subj1}과 {subj2}는 {", ".join(common_grades)}학년에서 공통으로 수강되어 같은 시간에 배정할 수 없습니다.',
                            'is_original': True,
                            'is_custom': False
                        }
                        conflicts.append(conflict_info)
        
        # 충돌 정보를 파일로 저장
        save_custom_conflicts('same_grade', conflicts)
        
        # 과목별 학년 정보 생성
        subject_grade_stats = {}
        for subject_name, subject_data in exam_scope_data.items():
            grade_info = subject_data.get('학년', '')
            if grade_info:
                # 학년이 쉼표로 구분된 경우 처리 (예: "2,3")
                grades = [g.strip() + '학년' for g in grade_info.split(',') if g.strip()]
                subject_grade_stats[subject_name] = grades
            else:
                subject_grade_stats[subject_name] = []
        
        # subject_stats.json 파일로 저장
        stats_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'subject_stats.json')
        try:
            with open(stats_file_path, 'w', encoding='utf-8') as f:
                json.dump(subject_grade_stats, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"subject_stats.json 파일이 생성되었습니다.")
        except Exception as e:
            self.logger.debug(f"subject_stats.json 파일 생성 중 오류: {e}")
        
        return jsonify({
            'success': True,
            'message': f'같은 학년 과목 충돌 정보가 성공적으로 생성되었습니다. {len(conflicts)}개의 충돌이 생성되었습니다.',
            'conflicts_count': len(conflicts)
        })
        
    except Exception as e:
        self.logger.debug(f"Error generating same grade conflicts: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'충돌 정보 생성 중 오류가 발생했습니다: {str(e)}'
        }), 500


@app.route('/api/upload-enrollment-file', methods=['POST'])
def upload_enrollment_file():
    """분반배정표 파일 업로드 및 학생 충돌 정보 업데이트"""
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': '파일이 선택되지 않았습니다.'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': '파일이 선택되지 않았습니다.'
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': '지원되지 않는 파일 형식입니다. .xlsx 또는 .xls 파일을 업로드해주세요.'
            }), 400
        
        # 파일 저장
        filename = '학생배정정보.xlsx'
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # 데이터 로더를 사용하여 파일 처리
        data_loader = DataLoader(app.config['UPLOAD_FOLDER'])
        enrollment_data = data_loader.load_enrollment_data(file_path)
        
        if enrollment_data is None or len(enrollment_data) != 4:
            return jsonify({
                'success': False,
                'error': '파일에서 유효한 데이터를 읽을 수 없습니다.'
            }), 400
        
        # 튜플에서 enroll_bool (DataFrame) 추출
        student_conflict_dict, double_enroll_dict, student_names, enroll_bool = enrollment_data
        
        if enroll_bool is None or enroll_bool.empty:
            return jsonify({
                'success': False,
                'error': '파일에서 유효한 데이터를 읽을 수 없습니다.'
            }), 400
        
        # 과목 검증: custom_exam_scope.json의 과목들과 업로드된 파일의 과목들 비교
        try:
            custom_exam_scope_path = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_scope.json')
            if os.path.exists(custom_exam_scope_path):
                with open(custom_exam_scope_path, 'r', encoding='utf-8') as f:
                    custom_exam_scope = json.load(f)
                
                # custom_exam_scope.json의 과목명들
                scope_subjects = set(custom_exam_scope.keys())
                
                # 업로드된 파일의 과목명들 (enroll_bool의 컬럼명)
                uploaded_subjects = set(enroll_bool.columns)
                
                # custom_exam_scope.json에 있지만 업로드된 파일에 없는 과목들
                missing_subjects = scope_subjects - uploaded_subjects
                
                # 경고 메시지 생성 (extra_subjects는 경고하지 않음)
                warning_messages = []
                
                if missing_subjects:
                    missing_list = ', '.join(sorted(missing_subjects))
                    warning_messages.append(f"다음 과목들이 업로드된 파일에 없습니다: {missing_list}")
                
                # 경고가 있으면 사용자에게 알림
                if warning_messages:
                    warning_text = "\\n".join(warning_messages)
                    warning_text += "\\n\\n과목 이름이 잘못되었거나 누락되었을 수 있습니다. 과목 정보 설정을 확인후 다시 업로드해주세요."
                    
                    return jsonify({
                        'success': False,
                        'error': '과목 검증 실패',
                        'warning': warning_text,
                        'missing_subjects': list(missing_subjects)
                    }), 400
        except Exception as e:
            # 검증 실패해도 계속 진행
            pass
        
        # 학생 충돌 정보 생성
        conflicts = data_loader.generate_student_conflicts(enroll_bool)
        
        # same_grade_conflicts.json 파일 삭제 (파일이 없을 때 에러 방지)
        same_grade_conflicts_path = os.path.join(app.config['UPLOAD_FOLDER'], 'same_grade_conflicts.json')
        if os.path.exists(same_grade_conflicts_path):
            try:
                os.remove(same_grade_conflicts_path)
            except Exception as e:
                pass
        
        # 기존 커스텀 충돌 데이터와 병합
        custom_conflicts = load_custom_conflicts('individual')
        
        # 새로운 충돌 데이터로 교체
        save_custom_conflicts('individual', conflicts)
        
        # 추가 JSON 파일 생성 예시
        # 예시 1: 과목별 학생 수 통계 JSON (시험 과목만 대상)
        subject_stats = {}
        
        # custom_exam_scope.json에서 시험 과목 목록 로드
        try:
            custom_exam_scope_path = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_scope.json')
            if os.path.exists(custom_exam_scope_path):
                with open(custom_exam_scope_path, 'r', encoding='utf-8') as f:
                    exam_scope_data = json.load(f)
                exam_subjects = set(exam_scope_data.keys())
            else:
                # custom_exam_scope.json이 없으면 모든 과목 대상
                exam_subjects = set(enroll_bool.columns)
        except Exception as e:
            # 오류 시 모든 과목 대상
            exam_subjects = set(enroll_bool.columns)
        
        # 시험 과목 중에서 실제 수강 데이터가 있는 과목만 처리
        for subject in enroll_bool.columns:
            if subject in exam_subjects:
                enrolled_students = enroll_bool[enroll_bool[subject]].index.tolist()
                subject_stats[subject] = {
                    'student_count': len(enrolled_students),
                    'students': enrolled_students
                }
        
        # subject_stats.json 파일로 저장
        stats_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'subject_stats.json')
        try:
            with open(stats_file_path, 'w', encoding='utf-8') as f:
                json.dump(subject_stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass
        
        return jsonify({
            'success': True,
            'message': f'분반배정표 파일이 성공적으로 업로드되었습니다. {len(conflicts)}개의 학생 충돌이 생성되었습니다.',
            'conflicts_count': len(conflicts)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'파일 업로드 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/upload-exam-scope-file', methods=['POST'])
def upload_exam_scope_file():
    """과목 정보 파일 업로드 처리"""
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': '파일이 선택되지 않았습니다.'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': '파일이 선택되지 않았습니다.'
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': '지원되지 않는 파일 형식입니다. .xlsx 또는 .xls 파일을 업로드해주세요.'
            }), 400
        
        # 파일 저장
        filename = '과목 정보.xlsx'
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # 데이터 로더를 사용하여 파일 처리
        data_loader = DataLoader(app.config['UPLOAD_FOLDER'])
        exam_scope_data = data_loader.load_subject_info(filename)
        
        if not exam_scope_data:
            return jsonify({
                'success': False,
                'error': '파일에서 유효한 데이터를 읽을 수 없습니다.'
            }), 400
        
        # 과목 정보 데이터를 커스텀 데이터로 저장
        custom_exam_scope_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_scope.json')
        
        # 딕셔너리를 그대로 저장 (이미 올바른 형식)
        exam_scope_dict = exam_scope_data
        
        # 커스텀 과목 정보 데이터 저장
        with open(custom_exam_scope_file, 'w', encoding='utf-8') as f:
            json.dump(exam_scope_dict, f, ensure_ascii=False, indent=2)
        
        # 같은 학년 충돌 데이터 초기화 (새 과목 정보로 인해 기존 충돌 데이터가 무효화됨)
        same_grade_conflicts_file = os.path.join(app.config['UPLOAD_FOLDER'], 'same_grade_conflicts.json')
        same_grade_removed_file = os.path.join(app.config['UPLOAD_FOLDER'], 'same_grade_removed_conflicts.json')
        
        # 기존 충돌 데이터 파일들 삭제
        for file_path in [same_grade_conflicts_file, same_grade_removed_file]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    self.logger.debug(f"충돌 데이터 파일이 초기화되었습니다: {os.path.basename(file_path)}")
                except Exception as e:
                    self.logger.debug(f"충돌 데이터 파일 초기화 중 오류: {e}")
        
        return jsonify({
            'success': True,
            'message': f'과목 정보 파일이 성공적으로 업로드되었습니다. {len(exam_scope_dict)}개의 과목 정보가 로드되었습니다. 기존 충돌 데이터가 초기화되었습니다.',
            'subjects_count': len(exam_scope_dict)
        })
        
    except Exception as e:
        self.logger.debug(f"Error uploading exam scope file: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'파일 업로드 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/download-exam-scope-template')
def download_exam_scope_template():
    """과목 정보 양식 파일 다운로드"""
    try:
        # 간단한 양식 파일 생성 (pandas 사용)
        import pandas as pd
        
        # 샘플 데이터로 양식 생성 (새로운 구조에 맞춤)
        sample_data = {
            '과목명': ['수학', '영어', '국어', '과학', '사회'],
            '시간(분)': [100, 60, 80, 50, 50],
            '듣기평가': [0, 1, 0, 0, 0],
            '자율감독': ['', 1, '', 1, ''],
            '학년': ['1', '2', '3', '1,2', '1,2,3'],
            '담당교사': ['김수학,이수학,박수학', '이영어', '박국어', '정과학', '한사회, 두사회']
        }
        
        df = pd.DataFrame(sample_data)
        
        # 임시 파일 생성
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        df.to_excel(temp_file.name, index=False, engine='openpyxl')
        temp_file.close()
        
        # 파일 전송
        return send_file(
            temp_file.name,
            as_attachment=True,
            download_name='과목_정보.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        self.logger.debug(f"Error creating exam scope template: {e}")
        return jsonify({
            'success': False,
            'error': f'양식 파일 생성 중 오류가 발생했습니다: {str(e)}'
        }), 500

def calculateEndTime(start_time, duration_minutes):
    """시작 시간과 지속 시간으로부터 종료 시간을 계산합니다."""
    if not start_time or not duration_minutes:
        return '00:00'
    
    try:
        # 시작 시간을 시간과 분으로 분리
        hours, minutes = map(int, start_time.split(':'))
        
        # 총 분 계산
        total_minutes = hours * 60 + minutes + int(duration_minutes)
        
        # 시간과 분으로 변환
        end_hours = total_minutes // 60
        end_minutes = total_minutes % 60
        
        # 24시간을 넘어가는 경우 처리
        end_hours = end_hours % 24
        
        return f"{end_hours:02d}:{end_minutes:02d}"
    except:
        return '00:00'


@app.route('/subject-constraints')
def subject_constraints():
    """과목 조건 설정 페이지"""
    return render_template('subject_constraints.html')

@app.route('/subject-conflicts')
def subject_conflicts():
    """과목 충돌 설정 페이지"""
    return render_template('subject_conflicts.html')


@app.route('/api/subject-constraints-data')
def get_subject_constraints_data():
    """과목 조건 데이터를 반환합니다"""
    try:
        # 과목 정보 파일 확인
        exam_scope_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_scope.json')
        if not os.path.exists(exam_scope_file):
            return jsonify({
                'success': False,
                'error': 'no_exam_scope',
                'message': '과목 정보 파일이 없습니다. 먼저 과목 정보를 설정해주세요.'
            }), 404
        
        # 시험 정보 파일 확인
        exam_info_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_info.json')
        if not os.path.exists(exam_info_file):
            return jsonify({
                'success': False,
                'error': 'no_exam_info',
                'message': '시험 정보 파일이 없습니다. 먼저 시험 정보를 설정해주세요.'
            }), 404
        
        # 과목 정보 로드
        with open(exam_scope_file, 'r', encoding='utf-8') as f:
            subjects = json.load(f)
        
        # 시험 정보 로드
        with open(exam_info_file, 'r', encoding='utf-8') as f:
            exam_info = json.load(f)
        
        # 과목 조건 파일 확인
        constraints_file = os.path.join(app.config['UPLOAD_FOLDER'], 'subject_constraints.json')
        constraints = {}
        if os.path.exists(constraints_file):
            with open(constraints_file, 'r', encoding='utf-8') as f:
                constraints = json.load(f)
        
        # 시험 시간 슬롯 생성 (표준 형식: "제X일_X교시")
        time_slots = []
        if 'date_periods' in exam_info:
            for day, periods in exam_info['date_periods'].items():
                for period, time_info in periods.items():
                    # 표준 형식으로 생성: "제X일_X교시"
                    day_number = day.replace('일차', '')
                    time_slots.append(f"제{day_number}일_{period}교시")
        
        return jsonify({
            'success': True,
            'subjects': list(subjects.keys()),
            'time_slots': time_slots,
            'constraints': constraints
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'과목 조건 데이터 로드 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/add-subject-constraint', methods=['POST'])
def add_subject_constraint():
    """과목 조건을 추가합니다"""
    try:
        data = request.get_json()
        subject = data.get('subject')
        time_slot = data.get('time_slot')

        
        if not subject or not time_slot:
            return jsonify({
                'success': False,
                'error': '과목과 시간 슬롯을 모두 입력해주세요.'
            }), 400
        
        # 과목 조건 파일 경로
        constraints_file = os.path.join(app.config['UPLOAD_FOLDER'], 'subject_constraints.json')
        
        # 기존 조건 로드
        constraints = {}
        if os.path.exists(constraints_file):
            with open(constraints_file, 'r', encoding='utf-8') as f:
                constraints = json.load(f)
        
        # 시간대 키를 표준 형식으로 변환 (예: "제1일 1교시(08:30-09:20)" -> "제1일_1교시")
        standardized_time_slot = standardize_time_slot_key(time_slot)
        
        # 조건 추가
        if subject not in constraints:
            constraints[subject] = {}
        
        constraints[subject][standardized_time_slot] = {
            'created_at': datetime.now().isoformat()
        }
        
        # 파일 저장
        with open(constraints_file, 'w', encoding='utf-8') as f:
            json.dump(constraints, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': '과목 조건이 추가되었습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'과목 조건 추가 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/delete-subject-constraint', methods=['POST'])
def delete_subject_constraint():
    """과목 조건을 삭제합니다"""
    try:
        data = request.get_json()
        subject = data.get('subject')
        time_slot = data.get('time_slot')
        
        if not subject or not time_slot:
            return jsonify({
                'success': False,
                'error': '과목과 시간 슬롯을 모두 입력해주세요.'
            }), 400
        
        # 과목 조건 파일 경로
        constraints_file = os.path.join(app.config['UPLOAD_FOLDER'], 'subject_constraints.json')
        
        if not os.path.exists(constraints_file):
            return jsonify({
                'success': False,
                'error': '과목 조건 파일이 존재하지 않습니다.'
            }), 404
        
        # 기존 조건 로드
        with open(constraints_file, 'r', encoding='utf-8') as f:
            constraints = json.load(f)
        
        # 시간대 키를 표준 형식으로 변환
        standardized_time_slot = standardize_time_slot_key(time_slot)
        
        # 조건 삭제
        if subject in constraints and standardized_time_slot in constraints[subject]:
            del constraints[subject][standardized_time_slot]
            
            # 과목에 조건이 없으면 과목도 삭제
            if not constraints[subject]:
                del constraints[subject]
        
        # 파일 저장
        with open(constraints_file, 'w', encoding='utf-8') as f:
            json.dump(constraints, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': '과목 조건이 삭제되었습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'과목 조건 삭제 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/reset-subject-constraints', methods=['POST'])
def reset_subject_constraints():
    """과목 조건을 원본으로 초기화합니다"""
    try:
        # 과목 조건 파일 경로
        constraints_file = os.path.join(app.config['UPLOAD_FOLDER'], 'subject_constraints.json')
        
        # 파일이 존재하면 삭제
        if os.path.exists(constraints_file):
            os.remove(constraints_file)
        
        return jsonify({
            'success': True,
            'message': '과목 조건이 원본으로 초기화되었습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'과목 조건 초기화 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/subject-conflicts-data')
def get_subject_conflicts_data():
    """과목 충돌 데이터를 반환합니다"""
    try:
        # 과목 정보 파일 확인
        exam_scope_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_scope.json')
        if not os.path.exists(exam_scope_file):
            return jsonify({
                'success': False,
                'error': 'no_exam_scope',
                'message': '과목 정보 파일이 없습니다. 먼저 과목 정보를 설정해주세요.'
            }), 404
        
        # 시험 정보 파일 확인
        exam_info_file = os.path.join(app.config['UPLOAD_FOLDER'], 'custom_exam_info.json')
        if not os.path.exists(exam_info_file):
            return jsonify({
                'success': False,
                'error': 'no_exam_info',
                'message': '시험 정보 파일이 없습니다. 먼저 시험 정보를 설정해주세요.'
            }), 404
        
        # 과목 정보 로드
        with open(exam_scope_file, 'r', encoding='utf-8') as f:
            subjects = json.load(f)
        
        # 과목 충돌 파일 확인
        conflicts_file = os.path.join(app.config['UPLOAD_FOLDER'], 'subject_conflicts.json')
        conflicts = {}
        if os.path.exists(conflicts_file):
            with open(conflicts_file, 'r', encoding='utf-8') as f:
                conflicts = json.load(f)
        
        return jsonify({
            'success': True,
            'subjects': list(subjects.keys()),
            'conflicts': conflicts
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'과목 충돌 데이터 로드 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/add-subject-conflict', methods=['POST'])
def add_subject_conflict():
    """과목 충돌을 추가합니다"""
    try:
        data = request.get_json()
        subject1 = data.get('subject1')
        subject2 = data.get('subject2')
        conflict_type = data.get('type')
        priority = data.get('priority')
        reason = data.get('reason')
        
        if not subject1 or not subject2 or not conflict_type or not priority:
            return jsonify({
                'success': False,
                'error': '모든 필수 항목을 입력해주세요.'
            }), 400
        
        if subject1 == subject2:
            return jsonify({
                'success': False,
                'error': '서로 다른 과목을 선택해주세요.'
            }), 400
        
        # 과목 충돌 파일 경로
        conflicts_file = os.path.join(app.config['UPLOAD_FOLDER'], 'subject_conflicts.json')
        
        # 기존 충돌 로드
        conflicts = {}
        if os.path.exists(conflicts_file):
            with open(conflicts_file, 'r', encoding='utf-8') as f:
                conflicts = json.load(f)
        
        # 충돌 키 생성 (정렬하여 일관성 유지)
        conflict_key = '_'.join(sorted([subject1, subject2]))
        
        # 충돌 추가
        conflicts[conflict_key] = {
            'subject1': subject1,
            'subject2': subject2,
            'type': conflict_type,
            'priority': priority,
            'reason': reason,
            'created_at': datetime.now().isoformat()
        }
        
        # 파일 저장
        with open(conflicts_file, 'w', encoding='utf-8') as f:
            json.dump(conflicts, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': '과목 충돌이 추가되었습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'과목 충돌 추가 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/delete-subject-conflict', methods=['POST'])
def delete_subject_conflict():
    """과목 충돌을 삭제합니다"""
    try:
        data = request.get_json()
        conflict_key = data.get('key')
        
        if not conflict_key:
            return jsonify({
                'success': False,
                'error': '충돌 키를 입력해주세요.'
            }), 400
        
        # 과목 충돌 파일 경로
        conflicts_file = os.path.join(app.config['UPLOAD_FOLDER'], 'subject_conflicts.json')
        
        if not os.path.exists(conflicts_file):
            return jsonify({
                'success': False,
                'error': '과목 충돌 파일이 존재하지 않습니다.'
            }), 404
        
        # 기존 충돌 로드
        with open(conflicts_file, 'r', encoding='utf-8') as f:
            conflicts = json.load(f)
        
        # 충돌 삭제
        if conflict_key in conflicts:
            del conflicts[conflict_key]
            
            # 파일 저장
            with open(conflicts_file, 'w', encoding='utf-8') as f:
                json.dump(conflicts, f, ensure_ascii=False, indent=2)
            
            return jsonify({
                'success': True,
                'message': '과목 충돌이 삭제되었습니다.'
            })
        else:
            return jsonify({
                'success': False,
                'error': '해당 충돌 설정을 찾을 수 없습니다.'
            }), 404
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'과목 충돌 삭제 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/save-subject-conflicts', methods=['POST'])
def save_subject_conflicts():
    """과목 충돌 설정을 저장합니다"""
    try:
        data = request.get_json()
        conflicts = data.get('conflicts', {})
        
        # 과목 충돌 파일 경로
        conflicts_file = os.path.join(app.config['UPLOAD_FOLDER'], 'subject_conflicts.json')
        
        # 파일 저장
        with open(conflicts_file, 'w', encoding='utf-8') as f:
            json.dump(conflicts, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': '과목 충돌 설정이 저장되었습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'과목 충돌 설정 저장 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/download-teacher-conflicts')
def download_teacher_conflicts():
    """교사 충돌 데이터 다운로드"""
    try:
        conflicts_file = os.path.join(app.config['UPLOAD_FOLDER'], 'teacher_conflicts.json')
        
        if not os.path.exists(conflicts_file):
            return jsonify({
                'success': False,
                'error': '교사 충돌 파일이 존재하지 않습니다.'
            }), 404
        
        # 파일 내용 읽기
        with open(conflicts_file, 'r', encoding='utf-8') as f:
            conflicts_data = json.load(f)
        
        # JSON 문자열로 변환하여 응답
        response = make_response(json.dumps(conflicts_data, ensure_ascii=False, indent=2))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = 'attachment; filename=teacher_conflicts.json'
        
        return response
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'교사 충돌 다운로드 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/get-teacher-conflicts-data')
def get_teacher_conflicts_data():
    """교사 충돌 데이터를 JSON 형태로 반환"""
    try:
        conflicts = load_teacher_conflicts()
        
        return jsonify({
            'success': True,
            'data': conflicts
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'교사 충돌 데이터 로드 중 오류가 발생했습니다: {str(e)}'
        }), 500

@app.route('/api/get-all-data-json')
def get_all_data_json():
    """모든 데이터를 JSON 형태로 반환"""
    try:
        data_loader = DataLoader(app.config['UPLOAD_FOLDER'])
        
        # 교사 충돌 데이터
        teacher_conflicts = load_teacher_conflicts()
        
        # 과목 정보 데이터
        try:
            subject_info = data_loader.load_subject_info()
        except FileNotFoundError:
            subject_info = {}
        
        # 과목 충돌 데이터
        subject_conflicts = load_custom_data('subject_conflicts.json', {})
        
        # 과목 제약 데이터
        subject_constraints = load_custom_data('subject_constraints.json', {})
        
        # 교사 제약 데이터
        teacher_constraints = load_custom_data('teacher_constraints.json', {})
        
        # 학생 충돌 데이터
        student_conflicts = load_custom_data('individual_conflicts.json', [])
        
        # 듣기 충돌 데이터
        listening_conflicts = load_custom_data('custom_listening_conflicts.json', [])
        
        # 학생 부담 설정
        student_burden_config = load_custom_data('student_burden_config.json', {})
        
        # 하드 과목 설정
        hard_subjects_config = load_custom_data('hard_subjects_config.json', {})
        
        all_data = {
            'teacher_conflicts': teacher_conflicts,
            'subject_info': subject_info,
            'subject_conflicts': subject_conflicts,
            'subject_constraints': subject_constraints,
            'teacher_constraints': teacher_constraints,
            'student_conflicts': student_conflicts,
            'listening_conflicts': listening_conflicts,
            'student_burden_config': student_burden_config,
            'hard_subjects_config': hard_subjects_config
        }
        
        return jsonify({
            'success': True,
            'data': all_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'전체 데이터 로드 중 오류가 발생했습니다: {str(e)}'
        }), 500


@app.route('/api/manual-schedule', methods=['GET'])
def get_manual_schedule():
    """수동 배치 시간표 데이터 조회 API"""
    try:
        manual_schedule_file = os.path.join(UPLOAD_FOLDER, 'manual_schedule.json')
        if os.path.exists(manual_schedule_file):
            with open(manual_schedule_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    schedule_data = json.loads(content)
                    return jsonify({
                        'success': True,
                        'data': schedule_data
                    })
        
        # 파일이 없거나 빈 경우 빈 스케줄 반환
        return jsonify({
            'success': True,
            'data': {
                'slot_assignments': {},
                'metadata': {
                    'last_modified': None,
                    'created_by': 'manual',
                    'version': '1.0'
                }
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/manual-schedule', methods=['POST'])
def save_manual_schedule():
    """수동 배치 시간표 데이터 저장 API"""
    try:
        data = request.get_json()
        if not data or 'slot_assignments' not in data:
            return jsonify({
                'success': False,
                'error': 'Invalid data format. slot_assignments required.'
            }), 400
        
        # 메타데이터 추가
        created_by = data.get('created_by', 'manual')
        schedule_data = {
            'slot_assignments': data['slot_assignments'],
            'metadata': {
                'last_modified': datetime.now().isoformat(),
                'created_by': created_by,
                'version': '1.0'
            }
        }
        
        manual_schedule_file = os.path.join(UPLOAD_FOLDER, 'manual_schedule.json')
        with open(manual_schedule_file, 'w', encoding='utf-8') as f:
            json.dump(schedule_data, f, ensure_ascii=False, indent=2)
        
        message = '자동 생성 시간표가 저장되었습니다.' if created_by == 'automatic' else '수동 배치 시간표가 저장되었습니다.'
        return jsonify({
            'success': True,
            'message': message
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/manual-schedule', methods=['DELETE'])
def clear_manual_schedule():
    """수동 배치 시간표 데이터 삭제 API"""
    try:
        manual_schedule_file = os.path.join(UPLOAD_FOLDER, 'manual_schedule.json')
        if os.path.exists(manual_schedule_file):
            os.remove(manual_schedule_file)
        
        return jsonify({
            'success': True,
            'message': '수동 배치 시간표가 삭제되었습니다.'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 