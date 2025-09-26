#!/usr/bin/env python3
"""
클리크 분석 성능 테스트
"""
import time
import json
import os
from scheduler import ExamScheduler
from config import ExamSchedulingConfig
from data_loader import DataLoader

def test_clique_performance():
    print("=== 클리크 분석 성능 테스트 ===")
    
    # 데이터 로드
    data_loader = DataLoader('uploads')
    config = ExamSchedulingConfig()
    scheduler = ExamScheduler(config)

    # 과목 정보 로드
    subject_info = data_loader.load_subject_info()
    student_conflicts = data_loader.load_student_conflicts()
    listening_conflicts = data_loader.load_listening_conflicts()
    teacher_conflicts = data_loader.load_teacher_conflicts()

    print(f'과목 수: {len(subject_info)}')
    print(f'학생 충돌 수: {len(student_conflicts)}')
    print(f'듣기평가 충돌 수: {len(listening_conflicts)}')
    print(f'교사 충돌 수: {len(teacher_conflicts)}')
    print()

    # 클리크 분석 시간 측정 (5회 평균)
    total_time = 0
    times = []
    
    for i in range(5):
        start_time = time.time()
        result = scheduler.find_maximum_cliques(
            subject_info,
            student_conflicts,
            listening_conflicts,
            teacher_conflicts
        )
        end_time = time.time()
        
        elapsed = end_time - start_time
        times.append(elapsed)
        total_time += elapsed
        
        print(f'테스트 {i+1}: {elapsed:.3f}초')
    
    avg_time = total_time / 5
    min_time = min(times)
    max_time = max(times)
    
    print(f'\n=== 결과 ===')
    print(f'평균 시간: {avg_time:.3f}초')
    print(f'최소 시간: {min_time:.3f}초')
    print(f'최대 시간: {max_time:.3f}초')
    print(f'최대 클리크 크기: {len(result["max_clique"])}')
    print(f'전체 클리크 수: {len(result["all_cliques"])}')
    print(f'유효한 클리크 수: {len(result["valid_cliques"])}')
    
    # 충돌 그래프 정보
    graph_info = result["conflict_graph"]
    print(f'그래프 노드 수: {graph_info["nodes"]}')
    print(f'그래프 엣지 수: {graph_info["edges"]}')
    print(f'최대 클리크 크기: {graph_info["max_size"]}')
    print(f'최소 클리크 크기: {graph_info["min_size"]}')
    
    return avg_time, result

if __name__ == "__main__":
    test_clique_performance()
