---
name: scheduled-task
description: Create, list, update, pause, resume, and delete Advoo scheduled tasks and reminders. Use when the user asks a digital employee to do work later, repeat work on a schedule, set an alarm/reminder, or manage an existing scheduled task.
---

# Scheduled Task

Use this Skill's `scripts/scheduled_task.py`. It calls `ADVOO_OPENPLATFORM_BASE_URL` when set, otherwise `https://open.advoo.ai`, using the existing OpenPlatform credential.

## Identity

Schedule work for the employee requested by the user. For yourself, use the current `employeeId` supplied in the system context. For another employee, use their ID. If the target ID is unknown, run:

```text
<python> <scheduled_task.py> employees
```

Never guess an employee ID.

## Workflow

1. Convert the requested time to an RFC 3339 timestamp with an explicit offset and pass the user's IANA timezone.
2. Create a one-time reminder or recurring task:

```text
<python> <scheduled_task.py> create --employee-id <id> --name "Follow up" --prompt "Check the campaign and report changes" --schedule once --run-at "2026-09-10T09:00:00+08:00" --timezone "Asia/Hong_Kong" --project "/personal/Campaign"
```

For recurring work, add `--interval 12h`, `24h`, or `weekly`; `--end-at` is optional.
Use the user's selected project path with `--project`. Use `--project ""` when no project is selected; the task then runs in the temporary workspace.
3. Use `list`, `update`, `pause`, `resume`, or `delete` to manage tasks. Run `<python> <scheduled_task.py> <command> --help` for exact arguments.
4. Report the returned task ID and next run time. Creation means the task is scheduled, not completed. Explain that the selected employee will execute it in the background when due, and the user can view progress and results in that employee's Schedule. Say "I will" for your own tasks and use the target employee's name for their tasks. Do not promise unsolicited notifications; include any explicitly requested delivery channel in the task requirements.

## Rules

- The task prompt must describe the future deliverable, not the scheduling mechanics.
- Include necessary context, constraints, and delivery requirements; do not assume another employee knows the current conversation.
- Distinguish reminding the user to do something from doing it for them. Do not expand the requested scope.
- For recurring tasks, interpret relative dates against each execution time rather than hardcoding the first occurrence's date.
- Confirm ambiguous dates, times, timezones, or recurrence before creating the task.
- List tasks before modifying one when the task ID is unknown.
- Never retry `create` automatically after a timeout because the task may already exist.
- If the script prints exactly `Advoo OpenPlatform 授权无效`, preserve that message and stop.
