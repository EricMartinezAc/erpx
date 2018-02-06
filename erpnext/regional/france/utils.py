# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from erpnext import get_region

def create_transaction_log(doc, method):
	region = get_region()
	if region not in ["France"]:
		return

	else:

		data = str(doc.as_dict())

		frappe.get_doc({
			"doctype": "Transaction Log",
			"reference_doctype": doc.doctype,
			"document_name": doc.name,
			"data": data
		}).insert(ignore_permissions=True)

def check_deletion_permission(doc, method):
	region = get_region()
	if region not in ["France"]:
		return

	else:
		frappe.throw(_("Deletion is not permitted for country {0}".format("France")))
