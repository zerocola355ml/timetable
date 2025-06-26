# 시험 시간표 배정 시스템

시험 시간표를 자동으로 최적화하여 배정하는 시스템입니다. OR-Tools를 사용하여 제약조건을 만족하는 최적의 시험 시간표를 생성합니다.

## 🚀 주요 기능

- **자동 시험 시간표 생성**: 제약조건을 만족하는 최적의 시험 시간표 자동 생성
- **유연한 설정**: 어려운 과목 기준, 하루 최대 시험 수 등을 사용자가 조정 가능
- **다양한 제약조건 지원**:
  - 학생별 과목 충돌 방지
  - 듣기평가 충돌 방지
  - 교사별 불가능 시간 반영
  - 학생별 하루 최대 시험 수 제한
  - 학생별 하루 최대 어려운 시험 수 제한

## 📁 프로젝트 구조

```
timetabling/
├── config.py                 # 설정 관리 모듈
├── data_loader.py           # 데이터 로딩 모듈
├── scheduler.py             # OR-Tools 스케줄러 모듈
├── exam_scheduler_app.py    # 메인 애플리케이션
├── main_new.py              # 새로운 메인 실행 파일
├── main.py                  # 기존 실행 파일
├── requirements.txt         # 의존성 패키지
└── README.md               # 프로젝트 설명서
```

## 🛠️ 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 실행

```bash
python main_new.py
```

## ⚙️ 설정 조정

`main_new.py` 파일에서 다음 설정들을 조정할 수 있습니다:

```python
config = ExamSchedulingConfig(
    max_exams_per_day=3,           # 학생별 하루 최대 시험 개수
    max_hard_exams_per_day=2,      # 학생별 하루 최대 어려운 시험 개수
    hard_exam_threshold=60,        # 어려운 시험 기준 시간(분) - 이 값을 조정하면 됩니다!
    exam_days=5,                   # 시험 일수
    periods_per_day=3,             # 하루 교시 수
    period_limits={                # 교시별 최대 시간 제한
        '1교시': 80,
        '2교시': 50,
        '3교시': 100
    }
)
```

### 주요 설정 항목

- **`hard_exam_threshold`**: 어려운 과목의 기준 시간(분). 이 시간 이상의 과목을 어려운 과목으로 분류
- **`max_exams_per_day`**: 학생이 하루에 치를 수 있는 최대 시험 개수
- **`max_hard_exams_per_day`**: 학생이 하루에 치를 수 있는 최대 어려운 시험 개수
- **`period_limits`**: 각 교시별로 배정 가능한 최대 시험 시간

## 📊 입력 파일 형식

시스템은 다음 엑셀 파일들을 입력으로 사용합니다:

1. **`bunbanbaejeongpyo.xlsx`**: 분반배정표 (학생별 수강 과목)
2. **`시험 범위.xlsx`**: 과목별 정보 (시간, 듣기평가 여부, 담당교사 등)
3. **`시험 정보.xlsx`**: 시험 일정 정보
4. **`시험 불가 교사.xlsx`**: 교사별 불가능한 시험 시간

## 📈 결과 출력

시스템은 다음 결과를 생성합니다:

- **콘솔 출력**: 시험 시간표 배정 결과 및 요약 정보
- **`schedule_result.json`**: 상세한 배정 결과
- **`schedule_summary.json`**: 요약 통계 정보

## 🔧 모듈별 설명

### `config.py`
- `ExamSchedulingConfig` 클래스로 모든 설정을 관리
- 하드코딩된 값들을 설정 가능하게 변경

### `data_loader.py`
- `DataLoader` 클래스로 엑셀 파일에서 데이터 로딩
- 각 파일 형식에 맞는 파싱 로직 포함

### `scheduler.py`
- `ExamScheduler` 클래스로 OR-Tools 모델 생성 및 풀이
- 제약조건 설정 및 최적화 로직 포함

### `exam_scheduler_app.py`
- `ExamSchedulerApp` 클래스로 모든 모듈을 통합
- 데이터 로딩부터 결과 분석까지 전체 워크플로우 관리

## 🎯 개선 사항

### 1단계 완료 ✅
- [x] 코드 모듈화
- [x] 설정 유연성 개선
- [x] 하드코딩된 값들을 설정 가능하게 변경

### 2단계 예정 🔄
- [ ] 웹 인터페이스 구축 (Flask/FastAPI)
- [ ] 파일 업로드 기능
- [ ] 설정 조정 UI
- [ ] 결과 시각화

### 3단계 예정 📋
- [ ] 에러 처리 및 검증
- [ ] 사용자 친화적 에러 메시지
- [ ] 성능 최적화

## 💡 사용 예시

### 어려운 과목 기준을 90분으로 변경하고 싶은 경우:

```python
config = ExamSchedulingConfig(
    hard_exam_threshold=90,  # 60분에서 90분으로 변경
    # ... 다른 설정들
)
```

### 하루 최대 시험 수를 4개로 늘리고 싶은 경우:

```python
config = ExamSchedulingConfig(
    max_exams_per_day=4,     # 3개에서 4개로 변경
    # ... 다른 설정들
)
```

## 🤝 기여하기

1. 이슈를 생성하여 개선 사항을 제안
2. Fork하여 개발
3. Pull Request 생성

## 📝 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 