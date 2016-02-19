# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _, throw
from frappe.utils import flt

def get_company_currency(company):
	currency = frappe.db.get_value("Company", company, "default_currency", cache=True)
	if not currency:
		currency = frappe.db.get_default("currency")
	if not currency:
		throw(_('Please specify Default Currency in Company Master and Global Defaults'))

	return currency

def get_root_of(doctype):
	"""Get root element of a DocType with a tree structure"""
	result = frappe.db.sql_list("""select name from `tab%s`
		where lft=1 and rgt=(select max(rgt) from `tab%s` where docstatus < 2)""" %
		(doctype, doctype))
	return result[0] if result else None

def get_ancestors_of(doctype, name):
	"""Get ancestor elements of a DocType with a tree structure"""
	lft, rgt = frappe.db.get_value(doctype, name, ["lft", "rgt"])
	result = frappe.db.sql_list("""select name from `tab%s`
		where lft<%s and rgt>%s order by lft desc""" % (doctype, "%s", "%s"), (lft, rgt))
	return result or []

def before_tests():
	frappe.clear_cache()
	# complete setup if missing
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete
	if not frappe.get_list("Company"):
		setup_complete({
			"currency"			:"USD",
			"first_name"		:"Test",
			"last_name"			:"User",
			"company_name"		:"Wind Power LLC",
			"timezone"			:"America/New_York",
			"company_abbr"		:"WP",
			"industry"			:"Manufacturing",
			"country"			:"United States",
			"fy_start_date"		:"2014-01-01",
			"fy_end_date"		:"2014-12-31",
			"language"			:"english",
			"company_tagline"	:"Testing",
			"email"				:"test@erpnext.com",
			"password"			:"test",
			"chart_of_accounts" : "Standard"
		})

	frappe.db.sql("delete from `tabLeave Allocation`")
	frappe.db.sql("delete from `tabLeave Application`")
	frappe.db.sql("delete from `tabSalary Slip`")
	frappe.db.sql("delete from `tabItem Price`")

	frappe.db.set_value("Stock Settings", None, "auto_insert_price_list_rate_if_missing", 0)

	frappe.db.commit()

@frappe.whitelist()
def get_exchange_rate(from_currency, to_currency, posting_date=None):	
	if from_currency == to_currency:
		return 1
	
	if not posting_date:
		posting_date = frappe.utils.nowdate()
		
	value = flt(frappe.db.get_value("Currency Exchange", 
		{"from_currency": from_currency, "to_currency": to_currency,
			"date": posting_date}, "exchange_rate"))
	if not value:
		try:
			cache = frappe.cache()
			key = "currency_exchange_rate:{0}:{1}:{2}".format(from_currency, to_currency, posting_date)
			value = cache.get(key)
			if not value:
				import requests
				response = requests.get("http://api.fixer.io/latest", params={
					"base": from_currency,
					"symbols": to_currency
				})
				# expire in 6 hours
				response.raise_for_status()
				value = response.json()["rates"][to_currency]
				cache.setex(key, value, 6 * 60 * 60)
				
				create_exchange_rate_record(from_currency, to_currency, posting_date, value)

			return flt(value)
		except:
			frappe.msgprint(_("Unable to find exchange rate for {0} to {1}").format(from_currency, to_currency))
			return 0.0
	else:
		return value
	
def create_exchange_rate_record(from_currency, to_currency, posting_date, value):
	doc = frappe.new_doc("Currency Exchange")
	doc.update({"from_currency": from_currency, 
		"to_currency": to_currency, 
		"date": posting_date,
		"exchange_rate": value
	}).insert(ignore_permissions=True)
