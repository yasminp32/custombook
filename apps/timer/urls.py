from django.urls import path

from apps.timer.views import (
    TimerFormView,
    TimerHistoryView,
    TimerPauseView,
    TimerStartView,
    TimerStopView,
    TimerView,
)

urlpatterns = [
    path("", TimerView.as_view(), name="timer"),
    path("form/", TimerFormView.as_view(), name="timer-form"),
    path("options/", TimerFormView.as_view(), name="timer-options"),
    path("start/", TimerStartView.as_view(), name="timer-start"),
    path("pause/", TimerPauseView.as_view(), name="timer-pause"),
    path("stop/", TimerStopView.as_view(), name="timer-stop"),
    path("history/", TimerHistoryView.as_view(), name="timer-history"),
]
