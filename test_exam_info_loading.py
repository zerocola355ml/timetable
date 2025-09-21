#!/usr/bin/env python3
"""
Test script to check exam info data loading
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_loader import DataLoader

def test_exam_info_loading():
    """Test loading exam info data"""
    try:
        data_loader = DataLoader("uploads")
        
        print("=== Testing load_exam_info_with_custom ===")
        exam_info = data_loader.load_exam_info_with_custom()
        
        print("=== Exam Info Data ===")
        print(f"학년도: {exam_info.get('학년도', 'N/A')}")
        print(f"학기: {exam_info.get('학기', 'N/A')}")
        print(f"고사종류: {exam_info.get('고사종류', 'N/A')}")
        print()
        
        print("=== 시험날짜 ===")
        for day_label, date_string in exam_info.get('시험날짜', {}).items():
            print(f"{day_label}: {date_string}")
        print()
        
        print("=== Date Periods ===")
        for day, periods in exam_info.get('date_periods', {}).items():
            print(f"Day {day}:")
            for period, data in periods.items():
                print(f"  Period {period}: {data}")
        print()
        
        print("=== Testing load_custom_subject_info ===")
        subject_info = data_loader.load_custom_subject_info()
        print(f"Loaded {len(subject_info)} subjects")
        for subject, info in list(subject_info.items())[:5]:  # 처음 5개만 출력
            print(f"  {subject}: {info}")
        print()
        
        print("=== Testing load_teacher_unavailable_with_custom ===")
        teacher_unavailable = data_loader.load_teacher_unavailable_with_custom()
        print(f"Loaded {len(teacher_unavailable)} teachers")
        for teacher, slots in list(teacher_unavailable.items())[:3]:  # 처음 3개만 출력
            print(f"  {teacher}: {slots}")
        print()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_exam_info_loading() 