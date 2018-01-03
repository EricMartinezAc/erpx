# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint, getdate
from frappe import msgprint, _

def execute(filters=None):
	if not filters: filters = {}

	if not filters.get("date"):
		frappe.throw(_("Please select date"))
	
	columns = get_columns(filters)
	
	date = filters.get("date")
	
	company = None
	if filters.get("company"):
		company = filters.get("company")

	data = []

	if not filters.get("shareholder"):
		pass
	else:
		transfers = get_all_transfers(date, filters.get("shareholder"), company)
		for transfer in transfers:
			if transfer.transfer_type == 'Transfer':
				if transfer.from_shareholder == filters.get("shareholder"):
					transfer.transfer_type += ' from'
				else:
					transfer.transfer_type += ' to'
			row = [filters.get("shareholder"), transfer.date, transfer.transfer_type,
				transfer.share_type, transfer.no_of_shares, transfer.rate, transfer.amount,
				transfer.company, transfer.name]
			
			data.append(row)

	return columns, data

def get_columns(filters):
	columns = [ 
		_("Shareholder") + ":Link/Shareholder:150", 
		_("Date") + "::100",
		_("Transfer Type") + "::140",
		_("Share Type") + "::90",
		_("No of Shares") + "::90", 
		_("Rate") + "::90",
		_("Amount") + "::90",
		_("Company") + "::150",
		_("Share Transfer") + ":Link/Share Transfer:90"
	]
	return columns

def get_all_transfers(date, shareholder, company):
	if company:
		condition = 'AND company = %(company)s '
	else:
		condition = ' '

	return frappe.db.sql("""SELECT * FROM `tabShare Transfer` 
		WHERE (DATE(date) <= %(date)s AND from_shareholder = %(shareholder)s {condition})
		OR (DATE(date) <= %(date)s AND to_shareholder = %(shareholder)s {condition})
		ORDER BY date""".format(condition=condition), 
		{'date': date, 'shareholder': shareholder, 'company': company}, as_dict=1)
