# 지능형 시험 시간표 자동 배치 시스템

Intelligent Exam Timetable Scheduling System

## 📋 프로젝트 개요

복잡한 제약 조건을 가진 시험 시간표를 자동으로 생성하고 수동으로 조정할 수 있는 웹 기반 시스템입니다. 제약 조건 프로그래밍(CP-SAT)을 활용하여 최적의 시간표를 생성하며, 직관적인 드래그 앤 드롭 인터페이스를 제공합니다.

## ✨ 주요 기능

### 🤖 자동 시간표 생성
- **제약 조건 프로그래밍**: Google OR-Tools CP-SAT 솔버 활용
- **다중 제약 조건 처리**: 교사, 학생, 과목별 충돌 방지
- **학생 부담 최적화**: 일일 시험 수 제한 및 어려운 과목 분산
- **실시간 진행률 표시**: 생성 과정 모니터링

### 🎯 수동 배치 시스템
- **드래그 앤 드롭**: 직관적인 과목 배치
- **실시간 검증**: 배치 가능성 즉시 확인
- **스마트 추천**: 최적 배치 위치 추천
- **자동 저장**: 수동 배치 데이터 영속성

### 📊 데이터 관리
- **다양한 데이터 소스**: Excel, JSON 파일 지원
- **동적 설정**: JSON 기반 유연한 제약 조건 관리
- **실시간 분석**: 학생 부담 및 충돌 분석

## 🛠️ 기술 스택

### Backend
- **Python 3.x**: 핵심 개발 언어
- **Flask**: 웹 프레임워크
- **Google OR-Tools (CP-SAT)**: 제약 조건 프로그래밍 솔버
- **Pandas**: 데이터 처리 및 분석
- **OpenPyXL**: Excel 파일 처리

### Frontend
- **HTML5/CSS3**: 반응형 웹 인터페이스
- **JavaScript (ES6+)**: 동적 UI 및 사용자 상호작용
- **Bootstrap 5**: UI 프레임워크
- **Font Awesome**: 아이콘 라이브러리

## 🚀 설치 및 실행

### 1. 저장소 클론
```bash
git clone https://github.com/your-username/timetabling-system.git
cd timetabling-system
```

### 2. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 애플리케이션 실행
```bash
python web_app.py
```

### 5. 웹 브라우저에서 접속
```
http://localhost:5000
```

## 📁 프로젝트 구조

```
timetabling-system/
├── web_app.py                 # Flask 웹 애플리케이션
├── exam_scheduler_app.py      # 메인 스케줄링 로직
├── scheduler.py               # CP-SAT 솔버 구현
├── data_loader.py            # 데이터 로딩 및 처리
├── templates/                # HTML 템플릿
│   ├── base.html
│   ├── configure.html
│   └── schedule_manager.html
├── static/                   # 정적 파일 (CSS, JS, 이미지)
├── uploads/                  # 업로드된 데이터 파일 (gitignore)
└── requirements.txt          # Python 의존성
```

## ⚙️ 설정 파일

시스템은 다음 JSON 설정 파일들을 통해 동작합니다:

- `custom_exam_info.json`: 시험 일정 및 교시 정보
- `hard_subjects_config.json`: 어려운 과목 정의
- `student_burden_config.json`: 학생 부담 제한 설정
- `subject_constraints.json`: 과목별 제약 조건
- `subject_conflicts.json`: 과목 충돌 관계
- `custom_teacher_constraints.json`: 교사 제약 조건
- `individual_conflicts.json`: 개별 학생 충돌
- `same_grade_conflicts.json`: 학년별 충돌

## 🎯 사용 방법

### 1. 데이터 설정
1. `/configure` 페이지에서 시험 정보 및 제약 조건 설정
2. Excel 파일 업로드 (학생 배정 정보)
3. JSON 설정 파일들을 통한 세부 제약 조건 설정

### 2. 시간표 생성
1. `/schedule-manager` 페이지에서 자동 생성 또는 수동 배치
2. 드래그 앤 드롭으로 과목 배치
3. 실시간 검증 및 추천 시스템 활용

### 3. 결과 확인
- 생성된 시간표 검증
- 학생 부담 분석
- 충돌 및 경고 확인

## 🔧 주요 알고리즘

### 제약 조건 처리
- **시간 충돌**: 교사, 학생, 과목별 동시 배치 방지
- **학생 부담**: 일일 최대 시험 수 제한
- **과목 특성**: 듣기평가, 어려운 과목 등 특수 처리
- **고정 배치**: 수동 배치된 과목 보존

### 최적화 목표
- 학생 부담 최소화
- 교사 스케줄 최적화
- 제약 조건 만족도 최대화

## 📈 성능 및 확장성

- **처리 속도**: 일반적인 학교 규모(1000명 이하)에서 1-2분 내 생성
- **확장성**: 모듈화된 구조로 새로운 제약 조건 쉽게 추가
- **사용자 경험**: 실시간 피드백 및 직관적 인터페이스

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

## 📞 연락처

프로젝트 링크: [https://github.com/your-username/timetabling-system](https://github.com/your-username/timetabling-system)

## 🙏 감사의 말

- Google OR-Tools 팀
- Flask 개발팀
- Bootstrap 팀
- 모든 오픈소스 기여자들