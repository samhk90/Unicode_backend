from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from supabase import create_client, Client
from django.contrib.auth import authenticate, login as auth_login
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from django.db import models
from .models import Teacher, Timetable, Student, Slots, Attendance, Classes, Subject, TeacherSubjectAssignment
from django.core.cache import cache
from django.db.models import Prefetch, F, Count, Q

from django.utils import timezone
import os
from datetime import datetime, timedelta
import calendar

url: str = os.environ.get("SUPABASE_URL", "https://gipdgkwmxmmykyaliwhr.supabase.co")
key: str = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdpcGRna3dteG1teWt5YWxpd2hyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MDU1OTg4NTIsImV4cCI6MjAyMTE3NDg1Mn0.GrCKjv0gzqFMRr5l3iTEWSa79LX2HU4P0KjEmWxfkKI")
supabase: Client = create_client(url, key)

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    email = request.data.get('email')
    password = request.data.get('password')
    
    if not email or not password:
        return Response({
            'error': 'Please provide both email and password'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Authenticate with Supabase
        response = supabase.auth.sign_in_with_password({
            'email': email,
            'password': password
        })
        
        # Get the session and user data
        session = response.session
        user = response.user
        
        if user:
            # Fetch teacher data if exists
            try:
                teacher = Teacher.objects.get(Email=email)
                teacher_data = {
                    'teacher_id': str(teacher.Teacherid),
                    'first_name': teacher.FirstName,
                    'last_name': teacher.LastName,
                    'email': teacher.Email,
                    'department_name': teacher.DepartmentID.DepartmentName,
                    'role_name': teacher.RoleID.RoleName
                }
            except Teacher.DoesNotExist:
                teacher_data = None

            return Response({
                'message': 'Login successful',
                'teacher': teacher_data,
                'access_token': session.access_token,
                'refresh_token': session.refresh_token
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
            
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_slots(request):
    try:
        slots=Slots.objects.all()
        slot_data = []
        for slot in slots:
            slot_data.append({
                'slot_id': slot.Slotid,
                'start_time': slot.get_formatted_start_time(),
                'end_time': slot.get_formatted_end_time()
            })
        return Response({
            'message': 'Slots fetched successfully',
            'data': slot_data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_timetable(request):
    try:
        teacher_id = request.GET.get('teacher_id')
        day = request.GET.get('day')
        batch_id = request.GET.get('batch_id')
        
        if not teacher_id:
            return Response({
                'error': 'teacher_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Generate cache key based on request parameters
        cache_key = f'timetable_{teacher_id}_{day or "all"}_{batch_id or "all"}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return Response({
                'message': 'Timetable fetched successfully (cached)',
                'data': cached_data
            }, status=status.HTTP_200_OK)

        # Build efficient query with prefetch_related
        timetable_query = (
            Timetable.objects
            .select_related(
                'ClassID',
                'ClassID__DepartmentID',
                'SlotID',
                'Batch',
                'SubjectAssignmentID__TeacherID',
                'SubjectAssignmentID__TeacherID__DepartmentID',
                'SubjectAssignmentID__SubjectID'
            )
            .filter(SubjectAssignmentID__TeacherID_id=teacher_id)
            .order_by('Day', 'SlotID__start_time')
        )

        # Apply filters
        if day:
            timetable_query = timetable_query.filter(Day=day)
        if batch_id:
            timetable_query = timetable_query.filter(Batch_id=batch_id)

        # Use values() to optimize query
        timetable_data = []
        for entry in timetable_query:
            teacher = entry.SubjectAssignmentID.TeacherID
            subject = entry.SubjectAssignmentID.SubjectID
            
            entry_data = {
                'timetable_id': entry.TimetableID,
                'day': entry.Day,
                'class': {
                    'id': entry.ClassID.ClassID,
                    'name': entry.ClassID.ClassName,
                    'department': {
                        'id': entry.ClassID.DepartmentID.DepartmentID,
                        'name': entry.ClassID.DepartmentID.DepartmentName
                    }
                },
                'batch_name': entry.Batch.BatchName,
                'slot': {
                    'id': entry.SlotID.Slotid,
                    'start_time': entry.SlotID.get_formatted_start_time(),
                    'end_time': entry.SlotID.get_formatted_end_time()
                },
                'subject': {
                    'id': subject.SubjectID,
                    'name': subject.SubjectName,
                    'type': 'Theory' if subject.SubjectType else 'Practical'
                },
                'teacher': {
                    'id': str(teacher.Teacherid),
                    'name': f"{teacher.FirstName} {teacher.LastName}",
                    'department': {
                        'id': teacher.DepartmentID.DepartmentID,
                        'name': teacher.DepartmentID.DepartmentName
                    }
                }
            }
            timetable_data.append(entry_data)

        # Cache the results for 10 minutes
        cache.set(cache_key, timetable_data, timeout=600)
        
        return Response({
            'message': 'Timetable fetched successfully',
            'data': timetable_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['GET'])
def get_student(request):
    try:
        # Get query parameters
        student_id = request.GET.get('student_id')
        class_id = request.GET.get('class_id')
        batch = request.GET.get('batch')
        prn = request.GET.get('prn')
        
        # Start with all students with necessary related fields
        student_query = Student.objects.select_related(
            'CurrentClassID',
            'CurrentClassID__DepartmentID',
            'CurrentClassID__YearID',
            'RoleID'
        )
        
        # Apply filters if provided
        if student_id:
            student_query = student_query.filter(StudentID=student_id)
        if class_id:
            student_query = student_query.filter(CurrentClassID_id=class_id)
        if batch:
            student_query = student_query.filter(batch=batch)
        if prn:
            student_query = student_query.filter(PRN=prn)
            
        # Get the students
        students = student_query.all()
        
        # Format the response
        student_data = []
        for student in students:
            student_data.append({
                'student_id': str(student.StudentID),
                'prn': student.PRN,
                'first_name': student.FirstName,
                'last_name': student.LastName,
                'email': student.Email,
                'mobile': student.MobileNumber,
                'class': student.CurrentClassID.ClassName,
                'department': student.CurrentClassID.DepartmentID.DepartmentName,
                'year': student.CurrentClassID.YearID.YearName,
                'roll_number': student.RollNumber,
                'batch': student.batch,
            })
        return Response({
            'message': 'Student data fetched successfully',
            'count': len(student_data),
            'data': student_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_teacher_lectures(request):
    try:
        teacher_id = request.GET.get('teacher_id')
        day = request.GET.get('day')
        
        if not teacher_id or not day:
            return Response({
                'error': 'Both teacher_id and day are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Cache key for this specific request
        cache_key = f'teacher_lectures_{teacher_id}_{day}'
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return Response({
                'message': 'Lectures fetched successfully (cached)',
                'data': cached_data
            }, status=status.HTTP_200_OK)

        # Build query with necessary joins
        lectures = (
            Timetable.objects
            .select_related(
                'SlotID',
                'ClassID',
                'Batch',
                'SubjectAssignmentID__TeacherID',
                'SubjectAssignmentID__SubjectID'
            )
            .filter(
                SubjectAssignmentID__TeacherID_id=teacher_id,
                Day=day
            )
            .order_by('SlotID__start_time')
        )

        lecture_data = []
        for lecture in lectures:
            teacher = lecture.SubjectAssignmentID.TeacherID
            subject = lecture.SubjectAssignmentID.SubjectID
            
            lecture_data.append({
                'id': str(lecture.TimetableID),
                'subject': subject.SubjectName,
                'teacherName': f"{teacher.FirstName} {teacher.LastName}",
                'department': lecture.ClassID.DepartmentID.DepartmentName,
                'className': lecture.ClassID.ClassName,
                'batch': lecture.Batch.BatchName,
                'timeFrom': lecture.SlotID.get_formatted_start_time(),
                'timeTo': lecture.SlotID.get_formatted_end_time(),
                'subjectType': 'Theory' if subject.SubjectType else 'Practical'
            })

        # Cache the results for 10 minutes
        cache.set(cache_key, lecture_data, timeout=600)
        
        return Response({
            'message': 'Lectures fetched successfully',
            'data': lecture_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_lecture_students(request):
    try:
        timetable_id = request.GET.get('timetable_id')
        date = request.GET.get('date')  # Add date parameter
        
        if not timetable_id or not date:
            return Response({
                'error': 'Both timetable_id and date are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get the timetable entry with subject info
        timetable = (
            Timetable.objects
            .select_related(
                'ClassID', 
                'Batch',
                'SubjectAssignmentID__SubjectID'  # Include subject info
            )
            .get(TimetableID=timetable_id)
        )

        # Check if attendance is already taken for this subject on this date
        subject_id = timetable.SubjectAssignmentID.SubjectID
        attendance_exists = (
            Attendance.objects
            .filter(
                SubjectID=subject_id,
                Date=date
            )
            .exists()
        )

        if attendance_exists:
            return Response({
                'error': 'Attendance for this subject has already been taken today'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get students based on subject type
        student_query = Student.objects.order_by('RollNumber')
        
        if timetable.SubjectAssignmentID.SubjectID.SubjectType:  # Theory
            student_query = student_query.filter(
                CurrentClassID=timetable.ClassID,
        
            )
        else:  # Practical - only filter by batch
            student_query = student_query.filter(
                batch=timetable.Batch.Batchid
            )

        student_data = []
        for student in student_query:
            student_data.append({
                'id': str(student.StudentID),
                'rollNo': student.RollNumber,
                'name': f"{student.FirstName} {student.LastName}",
                'status': 'absent'  # Default status
            })

        return Response({
            'message': 'Students fetched successfully',
            'data': student_data
        }, status=status.HTTP_200_OK)

    except Timetable.DoesNotExist:
        return Response({
            'error': 'Timetable entry not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def submit_attendance(request):
    try:
        timetable_id = request.data.get('timetable_id')
        attendance_data = request.data.get('attendance')
        date = request.data.get('date')
        
        if not all([timetable_id, attendance_data, date]):
            return Response({
                'error': 'timetable_id, attendance data, and date are required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get the timetable entry to validate
        timetable = Timetable.objects.get(TimetableID=timetable_id)

        # Check if attendance already exists for this subject on this date
        subject_id = timetable.SubjectAssignmentID.SubjectID.SubjectID
        attendance_exists = (
            Attendance.objects
            .filter(
                SubjectID=subject_id,
                Date=date
            )
            .exists()
        )

        if attendance_exists:
            return Response({
                'error': 'Attendance for this subject has already been taken today'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create attendance records
        attendance_records = []
        for student_attendance in attendance_data:
            attendance_records.append(
                Attendance(
                    StudentID_id=student_attendance['student_id'],
                    SubjectID=timetable.SubjectAssignmentID.SubjectID,
                    Date=date,
                    Status=True if student_attendance['status'].lower() == 'present' else False,
                )
            )

        # Bulk create all attendance records
        Attendance.objects.bulk_create(attendance_records)

        return Response({
            'message': 'Attendance submitted successfully'
        }, status=status.HTTP_201_CREATED)

    except Timetable.DoesNotExist:
        return Response({
            'error': 'Timetable entry not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_attendance_report(request):
    try:
        class_id = request.GET.get('classId')
        report_type = request.GET.get('report_type')
        subject_id = request.GET.get('subject_id')
        date_param = request.GET.get('date')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if not class_id:
            return Response({
                'error': 'class_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Initialize date range based on report type
        date_range = None
        if report_type == 'daily':
            if not date_param:
                return Response({
                    'error': 'date is required for daily report'
                }, status=status.HTTP_400_BAD_REQUEST)
            date_range = (date_param, date_param)
            
        elif report_type == 'weekly':
            if not date_param:
                return Response({
                    'error': 'date is required for weekly report'
                }, status=status.HTTP_400_BAD_REQUEST)
            date_obj = datetime.strptime(date_param, '%Y-%m-%d')
            start_of_week = date_obj - timedelta(days=date_obj.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            date_range = (start_of_week.strftime('%Y-%m-%d'), end_of_week.strftime('%Y-%m-%d'))
            
        elif report_type == 'monthly':
            if not date_param:
                return Response({
                    'error': 'date is required for monthly report'
                }, status=status.HTTP_400_BAD_REQUEST)
            date_obj = datetime.strptime(date_param, '%Y-%m-%d')
            _, last_day = calendar.monthrange(date_obj.year, date_obj.month)
            start_of_month = date_obj.replace(day=1)
            end_of_month = date_obj.replace(day=last_day)
            date_range = (start_of_month.strftime('%Y-%m-%d'), end_of_month.strftime('%Y-%m-%d'))
            
        elif report_type == 'custom':
            if not start_date or not end_date:
                return Response({
                    'error': 'start_date and end_date are required for custom report'
                }, status=status.HTTP_400_BAD_REQUEST)
            date_range = (start_date, end_date)

        # Base query with all necessary joins
        base_query = (
            Attendance.objects
            .select_related(
                'StudentID',
                'SubjectID',
                'ClassID'
            )
            .filter(ClassID_id=class_id)
        )

        # Apply date range filter
        if date_range:
            base_query = base_query.filter(Date__range=date_range)

        # Apply subject filter if provided
        if subject_id:
            base_query = base_query.filter(SubjectID_id=subject_id)

        # Get all students in the class
        students = Student.objects.filter(CurrentClassID_id=class_id).order_by('RollNumber')
        
        # Get the total number of days in the date range for calculating percentages
        total_days = len(set(base_query.values_list('Date', flat=True)))
        if total_days == 0:
            return Response({
                'error': 'No attendance records found for the specified date range'
            }, status=status.HTTP_404_NOT_FOUND)

        attendance_data = []
        if report_type == 'daily':
            # For daily report, just show present/absent status for that day
            for student in students:
                student_attendance = base_query.filter(StudentID=student).first()
                attendance_data.append({
                    'student_id': str(student.StudentID),
                    'roll_number': student.RollNumber,
                    'name': f"{student.FirstName} {student.LastName}",
                    'status': 'Present' if (student_attendance and student_attendance.Status) else 'Absent'
                })
        else:
            # For weekly/monthly/custom reports, show attendance statistics
            for student in students:
                student_attendance = base_query.filter(StudentID=student)
                present_days = student_attendance.filter(Status=True).count()
                total_classes = student_attendance.count()
                
                # Calculate attendance percentage based on actual days present
                attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0
                
                attendance_data.append({
                    'student_id': str(student.StudentID),
                    'roll_number': student.RollNumber,
                    'name': f"{student.FirstName} {student.LastName}",
                    'total_classes': total_classes,
                    'present_days': present_days,
                    'absent_days': total_days - present_days,
                    'attendance_percentage': round(attendance_percentage, 2)
                })

        # Calculate class-wide statistics
        total_students = len(attendance_data)
        if report_type == 'daily':
            present_students = sum(1 for d in attendance_data if d['status'] == 'Present')
            absent_students = total_students - present_students
            avg_attendance = (present_students / total_students * 100) if total_students > 0 else 0
        else:
            avg_attendance = sum(d['attendance_percentage'] for d in attendance_data) / total_students if total_students > 0 else 0
            threshold = 75  # Students with attendance >= 75% are considered regular
            present_students = sum(1 for d in attendance_data if d['attendance_percentage'] >= threshold)
            absent_students = total_students - present_students

        response_data = {
            'report_type': report_type,
            'class_name': Classes.objects.get(ClassID=class_id).ClassName,
            'date_range': {
                'start': date_range[0] if date_range else None,
                'end': date_range[1] if date_range else None
            },
            'total_days': total_days,
            'statistics': {
                'total_students': total_students,
                'average_attendance': round(avg_attendance, 2),
                'present_students': present_students,
                'absent_students': absent_students
            },
            'attendance_data': attendance_data
        }

        if subject_id:
            response_data['subject'] = Subject.objects.get(SubjectID=subject_id).SubjectName

        return Response({
            'message': 'Attendance report generated successfully',
            'data': response_data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_teacher_subjects(request):
    try:
        teacher_id = request.GET.get('teacher_id')
        
        if not teacher_id:
            return Response({
                'error': 'teacher_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get teacher subject assignments with related data
        assignments = (
            TeacherSubjectAssignment.objects
            .select_related(
                'TeacherID',
                'SubjectID',
                'SubjectID__CurrentClassID',
                'SubjectID__CurrentClassID__DepartmentID',
                'SubjectID__Subjectdep',
                'SubjectID__Subjectyr'
            )
            .filter(TeacherID_id=teacher_id)
        )

        # Format the response
        subject_data = []
        for assignment in assignments:
            subject = assignment.SubjectID
            subject_data.append({
                'assignment_id': assignment.AssignmentID,
                'subject': {
                    'id': subject.SubjectID,
                    'name': subject.SubjectName,
                    'semester': subject.SubjectSemester,
                    'type': 'Theory' if subject.SubjectType else 'Practical',
                    'batch': subject.SubjectBatch,
                    'class': {
                        'id': subject.CurrentClassID.ClassID,
                        'name': subject.CurrentClassID.ClassName,
                        'department': {
                            'id': subject.CurrentClassID.DepartmentID.DepartmentID,
                            'name': subject.CurrentClassID.DepartmentID.DepartmentName
                        }
                    },
                    'department': {
                        'id': subject.Subjectdep.DepartmentID,
                        'name': subject.Subjectdep.DepartmentName
                    },
                    'year': {
                        'id': subject.Subjectyr.YearID,
                        'name': subject.Subjectyr.YearName
                    }
                }
            })

        return Response(subject_data,
         status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_department_classes(request):
    try:
        teacher_id = request.GET.get('teacher_id')
        
        if not teacher_id:
            return Response({
                'error': 'teacher_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Get teacher with department info
        try:
            teacher = Teacher.objects.select_related('DepartmentID').get(Teacherid=teacher_id)
        except Teacher.DoesNotExist:
            return Response({
                'error': 'Teacher not found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Get classes matching teacher's department
        classes = (
            Classes.objects
            .select_related(
                'DepartmentID',
                'YearID'
            )
            .filter(DepartmentID=teacher.DepartmentID)
            .order_by('YearID__YearName', 'ClassName')
        )

        # Format the response
        class_data = []
        for class_obj in classes:
            class_data.append({
                'id': class_obj.ClassID,
                'name': class_obj.ClassName,
                'department': {
                    'id': class_obj.DepartmentID.DepartmentID,
                    'name': class_obj.DepartmentID.DepartmentName
                },
                'year': {
                    'id': class_obj.YearID.YearID,
                    'name': class_obj.YearID.YearName
                }
            })

        return Response({
            'message': 'Department classes fetched successfully',
            'teacher_department': teacher.DepartmentID.DepartmentName,
            'data': class_data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_daily_attendance(request):
    try:
        class_id = request.GET.get('classId')
        subject_id = request.GET.get('subject_id')
        date = request.GET.get('date')
        
        if not all([class_id, date]):
            return Response({'error': 'classId and date are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)

        base_query = (
            Attendance.objects
            .select_related('StudentID', 'SubjectID')
            .filter(ClassID_id=class_id, Date=date)
        )

        if subject_id:
            base_query = base_query.filter(SubjectID_id=subject_id)

        students = Student.objects.filter(CurrentClassID_id=class_id).order_by('RollNumber')
        
        attendance_data = []
        for student in students:
            student_attendance = base_query.filter(StudentID=student).first()
            attendance_data.append({
                'rollNo': student.RollNumber,
                'name': f"{student.FirstName} {student.LastName}",
                'status': 'Present' if (student_attendance and student_attendance.Status) else 'Absent'
            })

        present_count = sum(1 for d in attendance_data if d['status'] == 'Present')
        total_students = len(attendance_data)
        
        return Response({
            'date': date,
            'class': Classes.objects.get(ClassID=class_id).ClassName,
            'subject': Subject.objects.get(SubjectID=subject_id).SubjectName if subject_id else None,
            'stats': {
                'present': present_count,
                'absent': total_students - present_count,
                'total': total_students
            },
            'students': attendance_data
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_weekly_attendance(request):
    try:
        class_id = request.GET.get('classId')
        subject_id = request.GET.get('subject_id')
        date = request.GET.get('date')
        
        if not all([class_id, date]):
            return Response({'error': 'classId and date are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)

        date_obj = datetime.strptime(date, '%Y-%m-%d')
        start_date = date_obj - timedelta(days=date_obj.weekday())
        end_date = start_date + timedelta(days=6)
        
        base_query = (
            Attendance.objects
            .select_related('StudentID', 'SubjectID')
            .filter(
                ClassID_id=class_id,
                Date__range=[start_date.strftime('%Y-%m-%d'), 
                            end_date.strftime('%Y-%m-%d')]
            )
        )

        if subject_id:
            base_query = base_query.filter(SubjectID_id=subject_id)

        # Get actual number of working days in the week
        total_days = len(set(base_query.values_list('Date', flat=True)))
        if total_days == 0:
            return Response({'error': 'No attendance records found for this week'}, 
                          status=status.HTTP_404_NOT_FOUND)

        students = Student.objects.filter(CurrentClassID_id=class_id).order_by('RollNumber')
        weekly_data = []
        
        for student in students:
            student_attendance = base_query.filter(StudentID=student)
            present_days = student_attendance.filter(Status=True).count()
            # Ensure present_days doesn't exceed total_days
            present_days = min(present_days, total_days)
            # Calculate absent days ensuring it's not negative
            absent_days = total_days - present_days
            # Calculate percentage capped at 100%
            attendance_percentage = min((present_days / total_days * 100), 100) if total_days > 0 else 0
            
            weekly_data.append({
                'rollNo': student.RollNumber,
                'name': f"{student.FirstName} {student.LastName}",
                'totalDays': total_days,
                'presentDays': present_days,
                'absentDays': absent_days,
                'percentage': round(attendance_percentage, 2)
            })

        # Calculate class statistics
        total_students = len(weekly_data)
        present_count = sum(d['presentDays'] for d in weekly_data)
        total_possible = total_students * total_days
        class_percentage = min((present_count / total_possible * 100), 100) if total_possible > 0 else 0

        return Response({
            'week': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d'),
                'totalDays': total_days
            },
            'class': Classes.objects.get(ClassID=class_id).ClassName,
            'subject': Subject.objects.get(SubjectID=subject_id).SubjectName if subject_id else None,
            'summary': {
                'totalStudents': total_students,
                'averageAttendance': round(class_percentage, 2)
            },
            'weeklyStats': weekly_data
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_monthly_attendance(request):
    try:
        class_id = request.GET.get('classId')
        subject_id = request.GET.get('subject_id')
        date = request.GET.get('date')
        
        if not all([class_id, date]):
            return Response({'error': 'classId and date are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)

        # Calculate month range
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        _, last_day = calendar.monthrange(date_obj.year, date_obj.month)
        start_date = date_obj.replace(day=1)
        end_date = date_obj.replace(day=last_day)
        
        base_query = (
            Attendance.objects
            .select_related('StudentID', 'SubjectID')
            .filter(
                ClassID_id=class_id,
                Date__range=[start_date.strftime('%Y-%m-%d'), 
                            end_date.strftime('%Y-%m-%d')]
            )
        )

        if subject_id:
            base_query = base_query.filter(SubjectID_id=subject_id)

        # Get total number of working days
        total_days = len(set(base_query.values_list('Date', flat=True)))
        if total_days == 0:
            return Response({'error': 'No attendance records found for this month'}, 
                          status=status.HTTP_404_NOT_FOUND)

        students = Student.objects.filter(CurrentClassID_id=class_id).order_by('RollNumber')
        monthly_data = []
        
        for student in students:
            student_attendance = base_query.filter(StudentID=student)
            present_days = student_attendance.filter(Status=True).count()
            # Ensure present_days doesn't exceed total_days
            present_days = min(present_days, total_days)
            # Calculate absent days ensuring it's not negative
            absent_days = total_days - present_days
            # Calculate percentage capped at 100%
            attendance_percentage = min((present_days / total_days * 100), 100) if total_days > 0 else 0
            
            monthly_data.append({
                'rollNo': student.RollNumber,
                'name': f"{student.FirstName} {student.LastName}",
                'totalDays': total_days,
                'presentDays': present_days,
                'absentDays': absent_days,
                'percentage': round(attendance_percentage, 2)
            })

        # Calculate class statistics
        total_students = len(monthly_data)
        present_count = sum(d['presentDays'] for d in monthly_data)
        total_possible = total_students * total_days
        class_percentage = min((present_count / total_possible * 100), 100) if total_possible > 0 else 0
        below_threshold = sum(1 for d in monthly_data if d['percentage'] < 75)

        return Response({
            'month': {
                'start': start_date.strftime('%Y-%m-%d'),
                'end': end_date.strftime('%Y-%m-%d'),
                'totalDays': total_days
            },
            'class': Classes.objects.get(ClassID=class_id).ClassName,
            'subject': Subject.objects.get(SubjectID=subject_id).SubjectName if subject_id else None,
            'summary': {
                'totalStudents': total_students,
                'averageAttendance': round(class_percentage, 2),
                'belowThreshold': below_threshold
            },
            'monthlyStats': monthly_data
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_custom_attendance(request):
    try:
        class_id = request.GET.get('classId')
        subject_id = request.GET.get('subject_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if not all([class_id, start_date, end_date]):
            return Response({'error': 'classId, start_date and end_date are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)

        base_query = (
            Attendance.objects
            .select_related('StudentID', 'SubjectID')
            .filter(
                ClassID_id=class_id,
                Date__range=[start_date, end_date]
            )
        )

        if subject_id:
            base_query = base_query.filter(SubjectID_id=subject_id)

        # Get actual number of working days in the date range
        total_days = len(set(base_query.values_list('Date', flat=True)))
        if total_days == 0:
            return Response({'error': 'No attendance records found'}, 
                          status=status.HTTP_404_NOT_FOUND)

        students = Student.objects.filter(CurrentClassID_id=class_id).order_by('RollNumber')
        custom_data = []
        
        for student in students:
            student_attendance = base_query.filter(StudentID=student)
            present_days = student_attendance.filter(Status=True).count()
            # Ensure present_days doesn't exceed total_days
            present_days = min(present_days, total_days)
            # Calculate absent days ensuring it's not negative
            absent_days = total_days - present_days
            # Calculate percentage capped at 100%
            attendance_percentage = min((present_days / total_days * 100), 100) if total_days > 0 else 0
            
            custom_data.append({
                'rollNo': student.RollNumber,
                'name': f"{student.FirstName} {student.LastName}",
                'totalDays': total_days,
                'presentDays': present_days,
                'absentDays': absent_days,
                'percentage': round(attendance_percentage, 2)
            })

        # Calculate class statistics
        total_students = len(custom_data)
        present_count = sum(d['presentDays'] for d in custom_data)
        total_possible = total_students * total_days
        class_percentage = min((present_count / total_possible * 100), 100) if total_possible > 0 else 0
        below_threshold = sum(1 for d in custom_data if d['percentage'] < 75)

        return Response({
            'dateRange': {
                'start': start_date,
                'end': end_date,
                'totalDays': total_days
            },
            'class': Classes.objects.get(ClassID=class_id).ClassName,
            'subject': Subject.objects.get(SubjectID=subject_id).SubjectName if subject_id else None,
            'summary': {
                'totalStudents': total_students,
                'averageAttendance': round(class_percentage, 2),
                'belowThreshold': below_threshold
            },
            'studentStats': custom_data
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_subject_attendance(request):
    try:
        class_id = request.GET.get('classId')
        subject_id = request.GET.get('subject_id')
        if not all([class_id, subject_id]):
            return Response({'error': 'classId, subject_id, and date are required'}, 
                          status=status.HTTP_400_BAD_REQUEST)

        base_query = (
            Attendance.objects
            .select_related('StudentID')
            .filter(
                ClassID_id=class_id, 
                SubjectID_id=subject_id
            )
        )

        total_lectures = len(set(base_query.values_list('Date', flat=True)))
        if total_lectures == 0:
            return Response({'error': 'No attendance records found for this month'}, 
                          status=status.HTTP_404_NOT_FOUND)

        students = Student.objects.filter(CurrentClassID_id=class_id).order_by('RollNumber')
        
        monthly_data = []
        for student in students:
            student_attendance = base_query.filter(StudentID=student)
            present_count = student_attendance.filter(Status=True).count()
            # Ensure present_count doesn't exceed total_lectures
            present_count = min(present_count, total_lectures)
            # Calculate percentage capped at 100%
            attendance_percentage = min((present_count / total_lectures * 100), 100) if total_lectures > 0 else 0
            
            monthly_data.append({
                'rollNo': student.RollNumber,
                'name': f"{student.FirstName} {student.LastName}",
                'totalLectures': total_lectures,
                'attended': present_count,
                'absent': total_lectures - present_count,
                'percentage': round(attendance_percentage, 2)
            })

        # Calculate overall statistics
        total_students = len(monthly_data)
        total_attendance = sum(d['attended'] for d in monthly_data)
        max_possible = total_students * total_lectures
        overall_percentage = min((total_attendance / max_possible * 100), 100) if max_possible > 0 else 0
        below_threshold = sum(1 for d in monthly_data if d['percentage'] < 75)

        return Response({

            'class': Classes.objects.get(ClassID=class_id).ClassName,
            'subject': Subject.objects.get(SubjectID=subject_id).SubjectName,
            'totalLectures': total_lectures,
            'overallStats': {
                'totalStudents': total_students,
                'averageAttendance': round(overall_percentage, 2),
                'belowThreshold': below_threshold
            },
            'studentStats': monthly_data
        })
        
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


