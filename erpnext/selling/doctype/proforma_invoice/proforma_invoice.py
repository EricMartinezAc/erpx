# Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
# from frappe import _
from frappe.model.document import Document

# from frappe.utils import flt

# from erpnext.selling.doctype.sales_order.sales_order import SalesOrder


class ProformaInvoice(Document):
	pass
	# def __init__(self, *args, **kwargs):
	# 	super(ProformaInvoice, self).__init__(*args, **kwargs)

	# def before_save(self):
	# 	total_rate = 0
	# 	total_qty = 0
	# 	total = 0

	# 	for d in self.items:
	# 		total_qty += flt(d.qty)
	# 		total_rate += flt(d.rate)
	# 		total += flt(d.qty) * flt(d.rate)
	# 		d.amount = flt(d.qty) * flt(d.rate)
	# 		q = frappe.db.get_all(
	# 			"Sales Order Item",
	# 			filters={"name":d.so_item,"parent":d.sales_order},
	# 			fields=["qty"],
	# 		)
	# 		print("REMM",d.so_item,d.sales_order,d.rem_qty,q)
	# 		# d.rem_qty = flt(q[0]['qty']) - flt(d.qty)

	# 		if d.rem_qty:
	# 			d.rem_qty -= d.qty

	# 		elif d.qty > q[0]['qty']:
	# 				frappe.throw(_(f"Quantity unavailable at row {d.idx}"))

	# 		else:
	# 			d.rem_qty = flt(q[0]['qty']) - flt(d.qty)

	# 	self.total_qty = total_qty
	# 	self.base_total = total

	# def on_submit(self):
	# 	pass
