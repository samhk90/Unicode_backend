from django.urls import path
from . import views

urlpatterns = [
    path('login', views.login, name='api-login'),
    path('timetable', views.get_timetable, name='api-timetable'),
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

]