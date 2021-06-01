# Copyright (c) 2015, ESS LLP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cstr
from frappe import _

class VitalSigns(Document):
	def validate(self):
		self.set_title()

	def set_title(self):
		self.title = _('{0} on {1}').format(self.patient_name or self.patient,
			frappe.utils.format_date(self.signs_date))[:100]

