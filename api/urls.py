from django.urls import path
from . import views

urlpatterns = [
    path('login', views.login, name='api-login'),
    path('timetable', views.get_timetable, name='api-timetable'),
    path('class-timetable/', views.get_class_timetable, name='class-timetable'),
    path('student', views.get_student, name='api-student'),
    path('slots', views.get_slots, name='api-slots'),
    path('teacher-lectures/', views.get_teacher_lectures, name='teacher-lectures'),
    path('lecture-students/', views.get_lecture_students, name='lecture-students'),
    path('submit-attendance/', views.submit_attendance, name='submit-attendance'),
    path('attendance-report/', views.get_attendance_report, name='attendance-report'),
    path('teacher-subjects/', views.get_teacher_subjects, name='teacher-subjects'),
    path('department-classes/', views.get_department_classes, name='department-classes'),
    path('attendance/daily/', views.get_daily_attendance, name='daily_attendance'),
    path('attendance/weekly/', views.get_weekly_attendance, name='weekly_attendance'),
    path('attendance/subject/', views.get_subject_attendance, name='subject_attendance'),
    path('attendance/custom/', views.get_custom_attendance, name='custom_attendance'),
    path('attendance/monthly/', views.get_monthly_attendance, name='monthly_attendance'),
    path('notices/', views.notices, name='notices'),
    path('notices/<int:notice_id>/delete/', views.delete_notice, name='delete_notice'),
    path('notices/<int:notice_id>/publish/', views.publish_notice, name='publish_notice'),
    path('class-report/', views.get_class_report, name='class_report'),

    # Leave Management URLs
    path('leave/balance/', views.get_leave_balance, name='leave-balance'),
    path('leave/applications/', views.get_leave_applications, name='leave-applications'),
    path('leave/submit/', views.submit_leave_request, name='submit-leave'),
    path('leave/<int:leave_id>/cancel/', views.cancel_leave_request, name='cancel-leave'),
    path('leave/<int:leave_id>/', views.get_leave_request_details, name='leave-details'),
    path('leave/<int:leave_id>/approve/', views.approve_leave_request, name='approve-leave'),
    path('leave/<int:leave_id>/reject/', views.reject_leave_request, name='reject-leave'),
]