"""
시험 시간표 배정 웹 애플리케이션
Flask를 사용한 웹 인터페이스
"""
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
from flask_cors import CORS
import os
import json
import tempfile
import shutil
from pathlib import Path
from werkzeug.utils import secure_filename
import traceback

from config import ExamSchedulingConfig
from exam_scheduler_app import ExamSchedulerApp

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # 실제 운영시에는 환경변수로 관리
CORS(app)

# 업로드 설정
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 업로드 폴더 생성
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """파일 확장자 검증"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_files():
    """파일 업로드 페이지"""
    if request.method == 'POST':
        # 파일 업로드 처리
        files = request.files.getlist('files')
        uploaded_files = []
        
        print(f"Received {len(files)} files")  # 디버깅
        
        for file in files:
            if file and file.filename:  # 파일이 존재하고 파일명이 있는 경우
                print(f"Processing file: {file.filename}")  # 디버깅
                
                if allowed_file(file.filename):
                    # 원본 파일명 유지 (secure_filename 사용하지 않음)
                    filename = file.filename
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    uploaded_files.append(filename)
                    print(f"Saved file: {filename} to {filepath}")  # 디버깅
                else:
                    print(f"Invalid file format: {file.filename}")  # 디버깅
                    flash(f'허용되지 않는 파일 형식: {file.filename}', 'error')
            else:
                print("Empty file or no filename")  # 디버깅
        
        print(f"Uploaded files: {uploaded_files}")  # 디버깅
        
        if uploaded_files:
            flash(f'{len(uploaded_files)}개 파일이 업로드되었습니다.', 'success')
            return jsonify({
                'success': True,
                'message': f'{len(uploaded_files)}개 파일이 업로드되었습니다.',
                'files': uploaded_files
            })
        else:
            return jsonify({
                'success': False,
                'error': '업로드된 파일이 없습니다.'
            }), 400
    
    return render_template('upload.html')

@app.route('/configure')
def configure():
    """설정 조정 페이지"""
    return render_template('configure.html')

@app.route('/api/schedule', methods=['POST'])
def create_schedule():
    """시험 시간표 생성 API"""
    try:
        # 설정 데이터 받기
        config_data = request.json.get('config', {})
        
        # 설정 객체 생성
        config = ExamSchedulingConfig(
            max_exams_per_day=config_data.get('max_exams_per_day', 3),
            max_hard_exams_per_day=config_data.get('max_hard_exams_per_day', 2),
            hard_exam_threshold=config_data.get('hard_exam_threshold', 60),
            exam_days=config_data.get('exam_days', 5),
            periods_per_day=config_data.get('periods_per_day', 3),
            period_limits=config_data.get('period_limits', {
                '1교시': 80,
                '2교시': 50,
                '3교시': 100
            })
        )
        
        # 애플리케이션 초기화
        app_instance = ExamSchedulerApp(config=config, data_dir=UPLOAD_FOLDER)
        
        # 데이터 로드
        if not app_instance.load_all_data():
            return jsonify({
                'success': False,
                'error': '데이터 로드에 실패했습니다. 파일을 확인해주세요.'
            }), 400
        
        # 시험 시간표 생성
        status, result = app_instance.create_schedule(time_limit=120)
        
        if status == "SUCCESS":
            # 결과 저장
            app_instance.save_results(result, 'results')
            
            # 요약 정보 생성
            summary = app_instance.get_summary(result)
            
            return jsonify({
                'success': True,
                'result': result,
                'summary': summary,
                'config': config.to_dict()
            })
        else:
            return jsonify({
                'success': False,
                'error': f'시험 시간표 생성 실패: {status}',
                'details': result.get('error', '')
            }), 400
            
    except Exception as e:
        print(f"Error in create_schedule: {str(e)}")  # 디버깅
        print(f"Traceback: {traceback.format_exc()}")  # 디버깅
        return jsonify({
            'success': False,
            'error': f'오류가 발생했습니다: {str(e)}',
            'traceback': traceback.format_exc()
        }), 500

@app.route('/results')
def results():
    """결과 표시 페이지"""
    return render_template('results.html')

@app.route('/api/results')
def get_results():
    """결과 데이터 API"""
    try:
        result_file = Path('results/schedule_result.json')
        summary_file = Path('results/schedule_summary.json')
        
        if result_file.exists() and summary_file.exists():
            with open(result_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
            with open(summary_file, 'r', encoding='utf-8') as f:
                summary = json.load(f)
            
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
            return redirect(url_for('results'))
    except Exception as e:
        flash(f'다운로드 중 오류: {str(e)}', 'error')
        return redirect(url_for('results'))

@app.route('/api/upload-status')
def upload_status():
    """업로드된 파일 상태 확인"""
    try:
        files = os.listdir(UPLOAD_FOLDER)
        print(f"Files in upload folder: {files}")  # 디버깅
        
        required_files = [
            'bunbanbaejeongpyo.xlsx',
            '시험 범위.xlsx', 
            '시험 정보.xlsx',
            '시험 불가 교사.xlsx'
        ]
        
        status = {}
        for file in required_files:
            status[file] = file in files
        
        print(f"File status: {status}")  # 디버깅
        
        return jsonify({
            'success': True,
            'files': status,
            'all_uploaded': all(status.values())
        })
    except Exception as e:
        print(f"Error in upload_status: {str(e)}")  # 디버깅
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 