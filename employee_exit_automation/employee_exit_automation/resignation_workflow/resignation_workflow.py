import frappe
from collections import defaultdict
from frappe.utils import get_url_to_form

def handle_employee_resignation(doc):
    """
        Main orchestration function called after
        Resignation Letter is submitted.
    """

    if not doc.resignation_date or not doc.employee:
        return

    update_employee_resignation_date(doc)
    send_reminder_alert_to_manager(doc)
    check_open_salary_slips(doc.employee)

def update_employee_resignation_date(doc):
    if not doc.employee or not doc.resignation_date:
        return

    frappe.db.set_value(
        "Employee",
        doc.employee,
        "resignation_letter_date",
        doc.resignation_date
    )

def block_task_assignment(doc, method=None):
    """
        Prevent the employee from receiving new task assignments.
    """
    if not doc.allocated_to:
        return

    if not frappe.db.exists("Employee", {"user_id": doc.allocated_to}):
        return

    emp = frappe.get_doc("Employee", {"user_id": doc.allocated_to})
    if not emp.resignation_letter_date:
        return

    frappe.throw(
        f"New task assignments blocked for user {doc.allocated_to}"
    )

def send_reminder_alert_to_manager(doc):
    """
        Send a handover reminder to the employee's manager.
    """

    if not doc.employee:
        return

    emp = frappe.get_doc("Employee", doc.employee)
    manager = emp.reports_to

    if not manager:
        message = (
            f"Reporting manager not found for employee "
            f"{doc.employee_name}."
        )

        frappe.log_error(
            message=message,
            title="Resignation Handover Reminder",
        )

        return

    manager_user = frappe.db.get_value("Employee", manager, "user_id")
    if not manager_user:
        message = (
            f"No user account found for reporting manager {manager}. "
            f"Reminder email was not sent."
        )

        frappe.log_error(
            message=message,
            title="Resignation Handover Reminder",
        )

        return

    subject = f"Handover Required - {doc.employee_name}"

    resignation_url = get_url_to_form(
        doc.doctype,
        doc.name,
    )

    message = f"""
        <p>Hello,</p>

        <p>
            Employee <b>{doc.employee_name}</b> has submitted
            a resignation letter.
        </p>

        <p>
            Please complete the required handover and transition activities.
        </p>

        <p>
            <b>Resignation Date:</b> {doc.resignation_date}
        </p>

        <p>
            <a href="{resignation_url}">
                View Resignation Letter
            </a>
        </p>
    """

    # 1. Send email notification
    frappe.sendmail(
        recipients=[manager_user],
        subject=subject,
        message=message
    )

    # Create an in-app notification
    frappe.get_doc({
        "doctype": "Notification Log",
        "subject": subject,
        "for_user": manager_user,
        "type": "Alert",
        "document_type": doc.doctype,
        "document_name": doc.name,
        "from_user": frappe.session.user,
        "email_content": message
    }).insert(ignore_permissions=True)

def block_salary_slip_for_resigned_employee(doc, method=None):
    """
        This validation is optional and should remain disabled because
        employees may still require salary slips during their final settlement.
    """

    if not doc.employee:
        return

    resignation_date = frappe.db.get_value(
        "Employee",
        doc.employee,
        "resignation_letter_date",
    )

    if resignation_date and doc.start_date >= resignation_date:
        frappe.throw(
            f"Salary Slip cannot be created for resigned employee {doc.employee} "
            f"for the period starting {doc.start_date}."
        )

def check_open_salary_slips(employee=None):
    """
        Find open Salary Slips for employees who have
        a resignation date.

        Open Salary Slip means:
        docstatus = 0, which means Draft.
    """

    conditions = f"""
        WHERE
        s.docstatus = 0
        AND emp.resignation_letter_date IS NOT NULL
        AND emp.resignation_letter_date != ''
    """

    if employee:
        conditions += f" AND s.employee = '{employee}'"

    open_salary_slips = frappe.db.sql(f"""
        SELECT
            s.name AS salary_slip, s.employee, s.start_date, s.end_date, s.posting_date,

            emp.employee_name, emp.reports_to AS reporting_manager

        FROM `tabSalary Slip` AS s

        INNER JOIN `tabEmployee` AS emp
            ON emp.name = s.employee

        {conditions}

        ORDER BY
            emp.reports_to,
            emp.employee_name,
            s.start_date
    """, as_dict=True)

    if not len(open_salary_slips):
        return

    notify_reporting_managers_about_open_salary_slips(open_salary_slips)

def notify_reporting_managers_about_open_salary_slips(open_salary_slips):
    """
        Daily scheduler:
        Find employees with resignation dates and open Salary Slips,
        then notify their reporting managers.
    """

    if not open_salary_slips:
        return

    manager_salary_slips = defaultdict(list)

    for slip in open_salary_slips:
        reporting_manager = slip.get("reporting_manager")

        if not reporting_manager:
            frappe.log_error(
                message=(
                    f"No reporting manager found for employee "
                    f"{slip.get('employee')}."
                ),
                title="Missing Reporting Manager",
            )
            continue

        manager_salary_slips[reporting_manager].append(slip)
    
    for reporting_manager, salary_slips in manager_salary_slips.items():

        # Adjust this field based on your Employee doctype.
        manager_user = frappe.db.get_value(
            "Employee",
            reporting_manager,
            "user_id",
        )

        if not manager_user:
            frappe.log_error(
                message=(
                    f"Reporting Manager {reporting_manager} "
                    f"does not have a linked user account."
                ),
                title="Missing Reporting Manager User",
            )
            continue

        employee_rows = ""

        for slip in salary_slips:
            employee_rows += f"""
                <tr>
                    <td>{slip.employee}</td>
                    <td>{slip.employee_name}</td>
                    <td>{slip.salary_slip}</td>
                    <td>{slip.start_date}</td>
                    <td>{slip.end_date}</td>
                </tr>
            """

        message = f"""
            <p>
                The following employees have open Salary Slips
                and resignation dates:
            </p>

            <table border="1" cellpadding="5" cellspacing="0">
                <thead>
                    <tr>
                        <th>Employee ID</th>
                        <th>Employee Name</th>
                        <th>Salary Slip</th>
                        <th>Start Date</th>
                        <th>End Date</th>
                    </tr>
                </thead>
                <tbody>
                    {employee_rows}
                </tbody>
            </table>

            <p>
                Please review and process the open Salary Slips.
            </p>
        """
        
        frappe.sendmail(
            recipients=[manager_user],
            subject="Open Salary Slips for Resigned Employees",
            message=message,
        )

        frappe.db.commit()

def daily_check_open_salary_slips():
    """
    Daily scheduler method to check open salary slips
    for employees who have submitted resignation.
    """
    
    check_open_salary_slips()