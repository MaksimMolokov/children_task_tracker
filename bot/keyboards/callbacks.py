"""
Централизованные callback_data константы.
Снижает риск коллизий и упрощает поддержку.
"""
# Карточки заданий - префикс REWARD_ для избежания коллизий
REWARD_REPORT_YES = "REWARD_REPORT_YES"
REWARD_REPORT_NO = "REWARD_REPORT_NO"
REWARD_NOTIFY_YES = "REWARD_NOTIFY_YES"
REWARD_NOTIFY_NO = "REWARD_NOTIFY_NO"
REWARD_CONFIRM_CREATE = "REWARD_CONFIRM_CREATE"
REWARD_RESTART = "REWARD_RESTART"

# Задачи (children)
TASK_COMPLETE = "task_complete"
