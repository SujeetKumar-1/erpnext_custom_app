# Copyright (c) 2026, Sujeet and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from ...resignation_workflow.resignation_workflow import (
    handle_employee_resignation,
	block_task_assignment,
	send_reminder_alert_to_manager,
	check_open_salary_slips
)

class ResignationLetter(Document):
    def on_submit(self):
        if self.resignation_date and self.employee:
            handle_employee_resignation(self)

	

