#!/usr/bin/env python3
"""
Test script to check data loading functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_loader import DataLoader

def test_data_loading():
    """Test all data loading methods"""
    try:
        print("=== Testing DataLoader ===")
        data_loader = DataLoader("uploads")
        
        print("\n1. Testing load_exam_info_with_custom...")
        exam_info = data_loader.load_exam_info_with_custom()
        print(f"✓ Exam info loaded successfully")
        print(f"  - 학년도: {exam_info.get('학년도', 'N/A')}")
        print(f"  - 학기: {exam_info.get('학기', 'N/A')}")
        print(f"  - 고사종류: {exam_info.get('고사종류', 'N/A')}")
        print(f"  - Date periods: {len(exam_info.get('date_periods', {}))} days")
        
        print("\n2. Testing load_custom_subject_info...")
        subject_info = data_loader.load_custom_subject_info()
        print(f"✓ Subject info loaded successfully")
        print(f"  - Total subjects: {len(subject_info)}")
        print(f"  - Sample subjects: {list(subject_info.keys())[:5]}")
        
        print("\n3. Testing load_teacher_unavailable_with_custom...")
        teacher_unavailable = data_loader.load_teacher_unavailable_with_custom()
        print(f"✓ Teacher constraints loaded successfully")
        print(f"  - Total teachers: {len(teacher_unavailable)}")
        print(f"  - Sample teachers: {list(teacher_unavailable.keys())[:3]}")
        
        print("\n4. Testing load_enrollment_data...")
        student_conflicts, double_enroll, student_names, enroll_bool = data_loader.load_enrollment_data()
        print(f"✓ Enrollment data loaded successfully")
        print(f"  - Total students: {len(student_names)}")
        print(f"  - Total subjects: {len(student_conflicts)}")
        
        print("\n5. Testing load_custom_conflicts...")
        student_conflicts, listening_conflicts, teacher_conflicts = data_loader.load_custom_conflicts()
        print(f"✓ Custom conflicts loaded successfully")
        print(f"  - Student conflicts: {len(student_conflicts)}")
        print(f"  - Listening conflicts: {len(listening_conflicts)}")
        print(f"  - Teacher conflicts: {len(teacher_conflicts)}")
        
        print("\n=== All tests passed! ===")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_data_loading()
    if success:
        print("\n✅ Data loading is working correctly!")
    else:
        print("\n❌ Data loading has issues!")
