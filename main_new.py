"""
시험 시간표 배정 시스템 - 새로운 모듈화 버전
"""
from exam_scheduler_app import ExamSchedulerApp
from config import ExamSchedulingConfig


def main():
    """메인 함수"""
    # 1. 설정 생성 (사용자가 조정 가능)
    config = ExamSchedulingConfig(
        max_exams_per_day=3,           # 학생별 하루 최대 시험 개수
        max_hard_exams_per_day=2,      # 학생별 하루 최대 어려운 시험 개수
        hard_exam_threshold=60,        # 어려운 시험 기준 시간(분) - 사용자가 조정 가능!
        exam_days=5,                   # 시험 일수
        periods_per_day=3,             # 하루 교시 수
        period_limits={                # 교시별 최대 시간 제한
            '1교시': 80,
            '2교시': 50,
            '3교시': 100
        }
    )
    
    # 2. 애플리케이션 초기화
    app = ExamSchedulerApp(config=config)
    
    # 3. 데이터 로드
    print("데이터를 로드하는 중...")
    if not app.load_all_data():
        print("데이터 로드에 실패했습니다.")
        return
    
    print("데이터 로드 완료!")
    print(f"총 학생 수: {len(app.student_names)}명")
    print(f"총 과목 수: {len(app.subject_info_dict)}개")
    
    # 4. 시험 시간표 생성
    print("시험 시간표를 생성하는 중...")
    status, result = app.create_schedule(time_limit=120)
    
    if status == "SUCCESS":
        print("시험 시간표 생성 완료!")
        app.print_results(result)
        app.save_results(result)
        
        # 5. 상세 분석 결과 출력
        print("\n=== 상세 분석 ===")
        summary = app.get_summary(result)
        
        # 하루에 3과목 치는 학생들
        if 3 in summary['exam_distribution']:
            students_3 = summary['exam_distribution'][3]['students']
            print(f"\n하루에 3과목 치는 학생 수: {len(students_3)}명")
            for student in students_3[:5]:  # 처음 5명만 출력
                print(f"  - {student}")
            if len(students_3) > 5:
                print(f"  ... 외 {len(students_3) - 5}명")
        
        # 하루에 어려운 시험 2과목 치는 학생들
        if 2 in summary['hard_exam_distribution']:
            students_hard_2 = summary['hard_exam_distribution'][2]['students']
            print(f"\n하루에 어려운 시험 2과목 치는 학생 수: {len(students_hard_2)}명")
            for student in students_hard_2[:5]:  # 처음 5명만 출력
                print(f"  - {student}")
            if len(students_hard_2) > 5:
                print(f"  ... 외 {len(students_hard_2) - 5}명")
        
    else:
        print(f"시험 시간표 생성 실패: {status}")
        if 'error' in result:
            print(f"오류: {result['error']}")


if __name__ == "__main__":
    main() 