# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE


import frappe

from erpnext.accounts.doctype.closing_balance.closing_balance import make_closing_entries
from erpnext.accounts.utils import get_fiscal_year


def execute():
	company_wise_order = {}
	for pcv in frappe.db.get_all(
		"Period Closing Voucher",
		fields=["company", "posting_date", "name"],
		filters={"docstatus": 1},
		order_by="posting_date",
	):

		company_wise_order.setdefault(pcv.company, [])
		if pcv.posting_date not in company_wise_order[pcv.company]:
			pcv_doc = frappe.get_doc("Period Closing Voucher", pcv.name)
			pcv_doc.year_start_date = get_fiscal_year(
				pcv.posting_date, pcv.fiscal_year, company=pcv.company
			)[1]
			pcv_doc.make_closing_entries()
			gl_entries = pcv_doc.get_gl_entries()
			make_closing_entries(gl_entries, is_period_closing_voucher_entry=True)
			company_wise_order[pcv.company].append(pcv.posting_date)
