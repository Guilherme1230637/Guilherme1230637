from datetime import datetime, time

from awaken.engine.habits import Habit, HabitType
from awaken.services.reminders import due_reminders


def habit(hid, at, archived=False):
    h = Habit(f"H{hid}", HabitType.CHECK, "C", {"STR": 1.0}, reminder=at, archived=archived)
    h.id = hid
    return h


def test_fires_once_in_the_window_and_only_if_not_done():
    habits = [habit(1, time(8, 0)), habit(2, time(8, 0)), habit(3, time(9, 0)), habit(4, None),
              habit(5, time(8, 0), archived=True)]
    ratios = {1: 0.0, 2: 1.0, 3: 0.0, 4: 0.0, 5: 0.0}
    due = due_reminders(habits, datetime(2026, 9, 28, 7, 59), datetime(2026, 9, 28, 8, 0, 30), ratios.get)
    assert [h.id for h in due] == [1]                  # 2 já cumprido, 3 ainda não é hora, 4 sem lembrete, 5 arquivado
    again = due_reminders(habits, datetime(2026, 9, 28, 8, 0, 30), datetime(2026, 9, 28, 8, 1), ratios.get)
    assert again == []                                 # não repete no minuto seguinte


def test_app_opened_after_reminder_time_does_not_spam_old_reminders():
    # a app abre às 10:00; a última verificação é "agora", logo o lembrete das 08:00 já não dispara
    now = datetime(2026, 9, 28, 10, 0)
    assert due_reminders([habit(1, time(8, 0))], now, now, lambda _: 0.0) == []
