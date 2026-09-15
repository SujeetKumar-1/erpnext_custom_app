## Employee Exit Automation

Handle Employee resignation and document handovers

A Frappe-based employee exit automation module that manages resignation-related workflows, manager notifications, task-assignment restrictions, and open salary-slip monitoring.

This project demonstrates how to implement business automation using:

- Frappe document events
- Frappe ORM and SQL queries
- Email notifications
- In-app notification logs
- Scheduler events
- Employee and Salary Slip relationships
- Validation hooks
- Grouping and aggregation with Python

---

## Features

### 1. Resignation Submission Automation

When a resignation letter is submitted, the system:

1. Updates the employee's resignation date.
2. Sends a handover reminder to the reporting manager.
3. Checks whether the employee has any open Salary Slips.

### 2. Employee Resignation Date Synchronization

The resignation date from the resignation document is copied to the linked Employee record.

This allows other processes to identify employees who are currently in the exit process.

### 3. Manager Handover Notification

The reporting manager receives:

- An email notification
- An in-app Frappe notification
- A link to the submitted resignation document
- The employee's resignation date

The system also handles missing reporting managers and missing manager user accounts through Frappe Error Logs.

### 4. Task Assignment Restriction

New task assignments can be blocked for employees who have submitted a resignation.

The validation checks:

- Whether the task is assigned to a valid Employee user.
- Whether the employee has a resignation date.
- If the employee is in the exit process, the assignment is rejected.

> This function can be connected to the appropriate Task Assignment or ToDo document event through `hooks.py`.

### 5. Open Salary Slip Monitoring

The system identifies draft Salary Slips for employees who have a resignation date.

In this implementation, an open Salary Slip means:

```text
docstatus = 0
```

The system then:

1. Finds matching draft Salary Slips.
2. Groups them by reporting manager.
3. Generates an HTML table containing the Salary Slip details.
4. Sends one consolidated email to each reporting manager.

### 6. Daily Scheduler

A daily scheduler method runs the open Salary Slip check automatically:

```python
def daily_check_open_salary_slips():
    check_open_salary_slips()
```

---

## Workflow

```text
Resignation Letter Submitted
            |
            v
handle_employee_resignation()
            |
            +------------------------------+
            |                              |
            v                              v
Update Employee                    Send Manager Handover
Resignation Date                   Email + Notification Log
            |
            v
Check Open Salary Slips
            |
            v
Find Draft Salary Slips
            |
            v
Group Slips by Reporting Manager
            |
            v
Send Consolidated Manager Emails
```

The daily scheduler follows this flow:

```text
Daily Scheduler
      |
      v
check_open_salary_slips()
      |
      v
Find Draft Salary Slips for Resigned Employees
      |
      v
Group Results by Reporting Manager
      |
      v
Send Email Notifications
```

---

## Main Functions

| Function | Responsibility |
|---|---|
| `handle_employee_resignation(doc)` | Main orchestration function after resignation submission |
| `update_employee_resignation_date(doc)` | Updates the linked Employee record |
| `block_task_assignment(doc, method=None)` | Prevents new task assignments for resigned employees |
| `send_reminder_alert_to_manager(doc)` | Sends handover email and in-app notification |
| `block_salary_slip_for_resigned_employee(doc, method=None)` | Optional Salary Slip validation |
| `check_open_salary_slips(employee=None)` | Finds draft Salary Slips for resigned employees |
| `notify_reporting_managers_about_open_salary_slips(open_salary_slips)` | Groups Salary Slips and emails reporting managers |
| `daily_check_open_salary_slips()` | Scheduler entry point |

---

## Suggested File Structure

```text
employee_exit_automation/
├── employee_exit_automation/
│   ├── resignation_workflow/
│   │   ├── __init__.py
│   │   └── resignation_workflow.py
│   ├── hooks.py
│   └── ...
├── README.md
└── ...
```

---

## Installation

### 1. Get the App

From your Frappe bench directory:

```bash
bench get-app https://github.com/<your-username>/employee-exit-automation.git
```

### 2. Install the App on a Site

```bash
bench --site <your-site-name> install-app employee_exit_automation
```

### 3. Apply Database and Code Changes

```bash
bench --site <your-site-name> migrate
bench --site <your-site-name> clear-cache
bench restart
```

Replace the repository URL and app name with the actual values used in your project.

---

## Hooks Configuration

The exact hooks depend on the DocTypes used in the implementation.

Example:

```python
doc_events = {
    "Resignation Letter": {
        "on_submit": "employee_exit_automation.employee_exit_automation.resignation_workflow.resignation_workflow.handle_employee_resignation"
    },
    "ToDo": {
        "before_insert": "employee_exit_automation.employee_exit_automation.resignation_workflow.resignation_workflow.block_task_assignment"
    }
}
```

For the daily scheduler:

```python
scheduler_events = {
    "daily": [
        "employee_exit_automation.employee_exit_automation.resignation_workflow.resignation_workflow.daily_check_open_salary_slips"
    ]
}
```

> Confirm the actual DocType event and field names in your Frappe/ERPNext implementation before enabling the hooks.

After modifying `hooks.py`, run:

```bash
bench --site <your-site-name> clear-cache
bench restart
```

---

## Data Relationships

The implementation uses the following relationships:

```text
Resignation Letter
    |
    | employee
    v
Employee
    |
    +── resignation_letter_date
    +── reports_to
    +── user_id
```

```text
Employee
    |
    | employee
    v
Salary Slip
    |
    +── docstatus
    +── start_date
    +── end_date
    +── posting_date
```

The reporting manager is resolved through:

```text
Salary Slip → Employee → reports_to → Employee → user_id
```

---

## Example SQL Query

The open Salary Slip query joins Salary Slip and Employee records:

```sql
SELECT
    s.name AS salary_slip,
    s.employee,
    s.start_date,
    s.end_date,
    s.posting_date,
    emp.employee_name,
    emp.reports_to AS reporting_manager
FROM `tabSalary Slip` AS s
INNER JOIN `tabEmployee` AS emp
    ON emp.name = s.employee
WHERE
    s.docstatus = 0
    AND emp.resignation_letter_date IS NOT NULL
    AND emp.resignation_letter_date != ''
ORDER BY
    emp.reports_to,
    emp.employee_name,
    s.start_date;
```

The important alias is:

```sql
emp.reports_to AS reporting_manager
```

This matches the Python access:

```python
slip.get("reporting_manager")
```

---

## Email Notification Behavior

### Handover Email

The manager receives an email similar to:

```text
Subject: Handover Required - Employee Name
```

The email includes:

- Employee name
- Resignation date
- Link to the Resignation Letter document

### Open Salary Slip Email

The manager receives a consolidated email with a table containing:

| Employee ID | Employee Name | Salary Slip | Start Date | End Date |
|---|---|---|---|---|

One email is sent per reporting manager rather than one email per Salary Slip.

This avoids sending multiple separate emails to the same manager.

---

## Error Handling

The implementation handles the following cases:

### Missing Reporting Manager

If an employee does not have a reporting manager, the system records an Error Log entry and skips the notification.

### Missing Manager User Account

If the reporting manager does not have a linked Frappe user account, the system records an Error Log entry and skips the email.

### Missing Employee or Resignation Date

The resignation orchestration exits early if the required employee or resignation date is unavailable.

---

## Testing from the Frappe Console

Open the Frappe console:

```bash
bench --site <your-site-name> console
```

Import the scheduler method:

```python
from employee_exit_automation.employee_exit_automation.resignation_workflow.resignation_workflow import daily_check_open_salary_slips
```

Run it:

```python
daily_check_open_salary_slips()
```

Alternatively, execute it through Frappe's method resolver:

```python
frappe.call(
    "employee_exit_automation.employee_exit_automation.resignation_workflow.resignation_workflow.daily_check_open_salary_slips"
)
```

To test the open Salary Slip query directly:

```python
check_open_salary_slips()
```

To test a specific employee:

```python
check_open_salary_slips("EMPLOYEE-ID")
```

---

## Email Queue Verification

After running the notification function, verify whether an email was queued:

```python
frappe.get_all(
    "Email Queue",
    fields=[
        "name",
        "status",
        "recipients",
        "subject",
        "error",
        "creation"
    ],
    order_by="creation desc",
    limit=10
)
```

Check the following fields:

- `status`
- `recipients`
- `subject`
- `error`
- `creation`

If the email is queued but not delivered, check the site's outgoing email configuration and background email worker.

---

## Scheduler Verification

Check the scheduler status:

```bash
bench --site <your-site-name> doctor
```

After changing scheduler hooks:

```bash
bench --site <your-site-name> clear-cache
bench restart
```

For background processing, ensure that the scheduler and worker processes are running correctly.

---

## Important Implementation Notes

### Salary Slip Validation Is Optional

The function:

```python
block_salary_slip_for_resigned_employee(doc, method=None)
```

is intentionally optional.

Employees may still require Salary Slips during:

- Notice period
- Final settlement
- Full and final payroll processing
- Statutory or accounting requirements

Therefore, this validation should remain disabled unless the organization's payroll policy explicitly requires it.

### Draft Salary Slips

The current implementation treats only draft Salary Slips as open:

```sql
s.docstatus = 0
```

This can be extended if the business requires monitoring of other statuses or payroll states.

### Notification Grouping

Salary Slips are grouped using:

```python
manager_salary_slips = defaultdict(list)
```

This ensures that each manager receives a consolidated notification containing all relevant employees and Salary Slips.

### User Account Requirement

Email delivery depends on the reporting manager having a valid linked Frappe User in the Employee record's `user_id` field.

---

## Potential Improvements

The current implementation can be extended with the following improvements:

- Use parameterized SQL instead of string interpolation for employee filters.
- Add duplicate-notification prevention.
- Track the last notification date for each Salary Slip.
- Add configurable notification recipients.
- Use Email Templates instead of inline HTML.
- Add links to each Salary Slip in the email table.
- Add unit tests for each business function.
- Add structured logging for scheduler execution.
- Add a notification status or audit log DocType.
- Add configurable grace periods after resignation.
- Support final settlement and payroll completion statuses.
- Add role-based permission checks.
- Add automated tests for missing managers and missing user accounts.

---

## Technical Concepts Demonstrated

This project demonstrates practical Frappe development concepts:

- Document event hooks
- Scheduler events
- Frappe ORM
- Direct SQL queries using `frappe.db.sql`
- Document retrieval using `frappe.get_doc`
- Field updates using `frappe.db.set_value`
- Email delivery using `frappe.sendmail`
- In-app notifications using `Notification Log`
- Error tracking using `frappe.log_error`
- Background job and scheduler integration
- Python data grouping with `defaultdict`
- Business workflow automation
- Cross-DocType data relationships

---

## Disclaimer

This project is intended as a demonstration of Frappe workflow automation and may require customization based on the installed Frappe/ERPNext version, custom DocTypes, field names, email configuration, and organizational payroll policies.

#### License

MIT