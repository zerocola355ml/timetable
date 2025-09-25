# 🎓 지능형 시험 시간표 자동 배치 시스템
- 필수 설정 파일은 익명화되어 샘플로 sample_data 폴더에 있으니 활용하실 수 있습니다.

> **Google OR-Tools를 활용한 제약 조건 프로그래밍 기반 시험 시간표 최적화 웹 애플리케이션**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com)
[![OR-Tools](https://img.shields.io/badge/OR--Tools-CP--SAT-orange.svg)](https://developers.google.com/optimization)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📋 프로젝트 소개

복잡한 제약 조건을 가진 교육기관의 시험 시간표를 **자동으로 생성**하고 **수동으로 조정**할 수 있는 웹 기반 시스템입니다. 

**제약 조건 프로그래밍(CP-SAT)**을 활용하여 다수의 제약 조건을 동시에 만족하는 최적의 시간표를 생성하며, 직관적인 **드래그 앤 드롭 인터페이스**를 통해 사용자가 실시간으로 조정할 수 있습니다.

### 🎯 해결하는 문제
- **복잡한 제약 조건**: 교사 스케줄, 학생 충돌, 과목 특성 등 다차원 제약
- **수동 작업의 비효율성**: 기존 엑셀 기반 수동 배치의 시간 소모
- **검증의 어려움**: 충돌 검사 및 최적화 평가의 복잡성
- **사용자 친화성**: 기술적 배경이 없는 교육 관계자도 쉽게 사용

## ✨ 핵심 기능

### 🤖 자동 최적화
- **Google OR-Tools CP-SAT 솔버** 활용한 제약 조건 프로그래밍
- **다중 제약 조건 동시 처리**: 교사, 학생, 과목별 충돌 방지
- **학생 부담 최적화**: 일일 시험 수 제한 및 어려운 과목 분산 배치
- **실시간 진행률 모니터링**: 최적화 과정 시각화

### 🎮 인터랙티브 수동 조정
- **드래그 앤 드롭 인터페이스**: 직관적인 과목 배치
- **실시간 검증 시스템**: 배치 가능성 즉시 확인
- **스마트 추천 엔진**: 최적 배치 위치 자동 추천
- **자동 저장**: 수동 배치 데이터 영속성 보장

### 📊 종합 데이터 관리
- **다양한 데이터 소스 지원**: Excel, JSON 파일 통합 처리
- **동적 설정 시스템**: JSON 기반 유연한 제약 조건 관리
- **실시간 분석 대시보드**: 학생 부담 및 충돌 통계 제공

## 🛠️ 기술 스택

### Backend Architecture
- **Python 3.8+**: 핵심 개발 언어
- **Flask**: 경량 웹 프레임워크
- **Google OR-Tools (CP-SAT)**: 제약 조건 프로그래밍 솔버
- **Pandas**: 고성능 데이터 처리 및 분석
- **OpenPyXL**: Excel 파일 읽기/쓰기

### Frontend Technology
- **HTML5/CSS3**: 시맨틱 마크업 및 반응형 디자인
- **JavaScript (ES6+)**: 모던 자바스크립트 및 비동기 처리
- **Bootstrap 5**: 반응형 UI 컴포넌트
- **Font Awesome**: 아이콘 시스템

### Development & Deployment
- **Git**: 버전 관리
- **JSON**: 설정 데이터 관리
- **RESTful API**: 모듈화된 백엔드 아키텍처

## 🔧 터미널 디버깅 메시지 제어

시스템의 디버깅 메시지를 환경변수로 쉽게 제어할 수 있습니다.

### 📋 로그 레벨 설정

```bash
# 환경변수로 로그 레벨 설정
export TIMETABLING_LOG_LEVEL=DEBUG    # 모든 디버그 메시지 출력
export TIMETABLING_LOG_LEVEL=INFO     # 정보 메시지만 출력 (기본값)
export TIMETABLING_LOG_LEVEL=WARNING  # 경고 이상만 출력
export TIMETABLING_LOG_LEVEL=ERROR    # 오류 이상만 출력
export TIMETABLING_LOG_LEVEL=CRITICAL # 치명적 오류만 출력
```

### 🛠️ 로깅 제어 도구 사용

#### Python 스크립트 사용
```bash
# 현재 로그 레벨 확인
python log_control.py --show

# 디버그 모드 활성화
python log_control.py --enable-debug

# 정보 모드로 설정
python log_control.py --level INFO

# 디버그 모드로 애플리케이션 실행
python log_control.py --run "python exam_scheduler_app.py" --level DEBUG
```

#### Windows 배치 파일 사용
```cmd
# 디버그 모드 활성화
log_control.bat debug

# 정보 모드로 설정
log_control.bat info

# 디버그 모드로 애플리케이션 실행
log_control.bat run-debug

# 웹 애플리케이션을 디버그 모드로 실행
log_control.bat run-web-debug
```

### 📁 파일 로깅 설정

```bash
# 파일 로깅 활성화
export TIMETABLING_LOG_FILE=true
export TIMETABLING_LOG_FILE_PATH=logs/timetabling.log

# 또는 Python 스크립트로 설정
python log_control.py --file-logging true --log-file logs/timetabling.log
```

### 🎯 사용 시나리오

#### 개발 환경
```bash
# 상세한 디버그 정보가 필요한 경우
export TIMETABLING_LOG_LEVEL=DEBUG
python exam_scheduler_app.py
```

#### 운영 환경
```bash
# 중요한 메시지만 출력하는 경우
export TIMETABLING_LOG_LEVEL=WARNING
python web_app.py
```

#### 문제 해결
```bash
# 오류 메시지만 확인하는 경우
export TIMETABLING_LOG_LEVEL=ERROR
python exam_scheduler_app.py
```

## 🚀 빠른 시작

### 1️⃣ 저장소 클론
```bash
git clone https://github.com/zerocola355ml/timetabling-system.git
cd timetabling-system
```

### 2️⃣ 가상환경 설정
```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3️⃣ 의존성 설치
```bash
pip install -r requirements.txt
```

### 4️⃣ 애플리케이션 실행
```bash
python web_app.py
```

### 5️⃣ 웹 브라우저에서 접속
```
http://localhost:5000
```

## 📁 프로젝트 구조

```
timetabling-system/
├── 🐍 web_app.py                 # Flask 웹 애플리케이션 (메인 진입점)
├── 🐍 exam_scheduler_app.py      # 스케줄링 애플리케이션 통합 관리
├── 🐍 scheduler.py               # OR-Tools CP-SAT 솔버 구현
├── 🐍 data_loader.py            # 데이터 로딩 및 전처리
├── 🐍 config.py                 # 설정 관리 및 기본값
├── 🐍 logger_config.py          # 로깅 시스템 설정
├── 🐍 log_control.py            # 로깅 제어 스크립트
├── 🐍 log_control.bat           # Windows 로깅 제어 배치 파일
├── 📁 templates/                # Jinja2 HTML 템플릿
│   ├── index.html               # 메인 대시보드
│   ├── schedule_manager.html    # 시간표 관리 인터페이스
│   ├── data_review.html         # 데이터 검토 페이지
│   └── ...                     # 기타 페이지들
├── 📁 static/                   # 정적 파일 (CSS, JS, 이미지)
├── 📁 sample_data/              # 익명화된 샘플 데이터
│   ├── 과목 정보.xlsx           # 과목별 상세 정보
│   └── 학생배정정보.xlsx        # 학생 수강 정보
├── 📁 uploads/                  # 사용자 업로드 파일 (gitignore)
├── 📁 results/                  # 생성된 시간표 결과
└── 📄 requirements.txt          # Python 패키지 의존성
```

## 📊 샘플 데이터 활용

프로젝트에는 **익명화된 샘플 데이터**가 포함되어 있어 즉시 시스템을 체험할 수 있습니다:

### 📋 포함된 샘플 데이터
- **`과목 정보.xlsx`**: 과목별 시험 시간, 듣기평가 여부, 담당 교사 등
- **`학생배정정보.xlsx`**: 학생별 수강 과목 정보 및 충돌 데이터

### 🎯 샘플 데이터 사용법
1. 웹 애플리케이션 실행 후 `/data-review` 페이지 접속
2. `sample_data` 폴더의 파일들을 `uploads` 폴더로 복사
3. 각 데이터 설정 페이지에서 파일 업로드
4. `/schedule-manager`에서 자동 시간표 생성 체험

## ⚙️ 핵심 알고리즘

### 🔧 제약 조건 처리
```python
# 주요 제약 조건들
constraints = {
    'teacher_conflicts': '교사별 동시 배치 방지',
    'student_conflicts': '학생별 과목 충돌 방지', 
    'listening_exams': '듣기평가 동시 배치 방지',
    'daily_limits': '일일 최대 시험 수 제한',
    'hard_subjects': '어려운 과목 분산 배치',
    'fixed_assignments': '수동 배치 보존'
}
```

### 🎯 최적화 목표
- **학생 부담 최소화**: 일일 시험 수 균등 분배
- **교사 스케줄 최적화**: 교사별 불가능 시간 반영
- **제약 조건 만족도**: 모든 하드 제약 조건 100% 만족
- **사용자 만족도**: 수동 조정 가능한 유연성 제공

## 📈 성능 및 확장성

### ⚡ 성능 지표
- **처리 속도**: 일반적인 학교 규모(1,000명 이하)에서 **1-2분 내** 생성
- **메모리 효율성**: 대용량 데이터 처리 시 메모리 사용량 최적화
- **동시성**: 멀티스레딩을 통한 비동기 처리

### 🔄 확장성
- **모듈화된 구조**: 새로운 제약 조건 쉽게 추가
- **플러그인 아키텍처**: 기능 확장 시 기존 코드 영향 최소화
- **설정 기반**: JSON 파일을 통한 유연한 설정 관리

## 🎨 사용자 경험 (UX)

### 💡 직관적 인터페이스
- **드래그 앤 드롭**: 복잡한 기술 없이 직관적 조작
- **실시간 피드백**: 배치 가능성 즉시 확인
- **시각적 표현**: 색상 코딩을 통한 상태 구분
- **반응형 디자인**: 모든 디바이스에서 최적화

### 🔍 스마트 검증 시스템
- **충돌 감지**: 실시간 충돌 검사 및 경고
- **최적화 추천**: AI 기반 배치 위치 제안
- **데이터 검증**: 업로드 파일 자동 검증

## 🧪 테스트 및 품질 보증

### ✅ 검증된 기능들
- **제약 조건 만족도**: 모든 하드 제약 조건 100% 만족 검증
- **데이터 무결성**: 파일 업로드 및 처리 과정 검증
- **사용자 인터페이스**: 크로스 브라우저 호환성 테스트
- **성능 테스트**: 대용량 데이터 처리 성능 검증

## 🤝 기여 가이드

### 📝 개발 환경 설정
```bash
# 개발 의존성 설치
pip install -r requirements-dev.txt

# 코드 스타일 검사
flake8 .

# 테스트 실행
python -m pytest tests/
```

### 🔄 기여 프로세스
1. **Fork** the Project
2. **Feature Branch** 생성 (`git checkout -b feature/AmazingFeature`)
3. **Commit** 변경사항 (`git commit -m 'Add some AmazingFeature'`)
4. **Push** to Branch (`git push origin feature/AmazingFeature`)
5. **Pull Request** 생성

## 📄 라이선스

이 프로젝트는 **MIT 라이선스** 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 📞 연락처

**개발자**: [zerocola355ml](https://github.com/zerocola355ml)  
**이메일**: sin51611630@gmail.com  
**프로젝트 링크**: [https://github.com/zerocola355ml/timetabling-system](https://github.com/zerocola355ml/timetabling-system)

## 🙏 감사의 말

- **Google OR-Tools 팀**: 강력한 최적화 솔버 제공
- **Flask 개발팀**: 경량 웹 프레임워크
- **Bootstrap 팀**: 반응형 UI 컴포넌트
- **모든 오픈소스 기여자들**: 지식 공유와 협업

---

<div align="center">

**💡 이 프로젝트는 제약 조건 프로그래밍과 웹 개발의 융합을 통해 실제 업무 문제를 해결하는 것을 목표로 합니다.**

</div>