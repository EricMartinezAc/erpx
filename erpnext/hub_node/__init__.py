# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, requests, json
from frappe.utils import now, nowdate, cint
from frappe.utils.nestedset import get_root_of
from frappe.contacts.doctype.contact.contact import get_default_contact

@frappe.whitelist()
def enable_hub():
	hub_settings = frappe.get_doc('Hub Settings')
	hub_settings.register()
	frappe.db.commit()
	return hub_settings

@frappe.whitelist()
def get_items(start=0, limit=20, category=None, order_by=None, text=None):
	connection = get_connection()
	filters = {
		'hub_category': category,
	}
	if text:
		filters.update({'item_name': ('like', '%' + text + '%')})
	response = connection.get_list('Hub Item',
		limit_start=start, limit_page_length=limit,
		filters=filters)
	return response

@frappe.whitelist()
def get_categories():
	connection = get_connection()
	response = connection.get_list('Hub Category')
	return response

@frappe.whitelist()
def get_item_details(hub_sync_id):
	connection = get_connection()
	return connection.get_doc('Hub Item', hub_sync_id)

@frappe.whitelist()
def get_company_details(hub_sync_id):
	connection = get_connection()
	return connection.get_doc('Hub Company', hub_sync_id)

def get_connection():
	hub_connector = frappe.get_doc(
		'Data Migration Connector', 'Hub Connector')
	hub_connection = hub_connector.get_connection()
	# frappeclient connection
	return hub_connection.connection

def make_opportunity(buyer_name, email_id):
	buyer_name = "HUB-" + buyer_name

	if not frappe.db.exists('Lead', {'email_id': email_id}):
		lead = frappe.new_doc("Lead")
		lead.lead_name = buyer_name
		lead.email_id = email_id
		lead.save(ignore_permissions=True)

	o = frappe.new_doc("Opportunity")
	o.enquiry_from = "Lead"
	o.lead = frappe.get_all("Lead", filters={"email_id": email_id}, fields = ["name"])[0]["name"]
	o.save(ignore_permissions=True)

# @frappe.whitelist()
# def get_items(text='', by_item_codes=0, start=0, limit=20, order_by='', category=None, company_name=None, country=None):
# 	item_codes = []
# 	if cint(by_item_codes):
# 		item_codes = [d["item_code"] for d in frappe.get_all("Item", fields=["item_code"], filters={"is_hub_item": "1"},
# 			limit_start = start, limit_page_length = limit)]
# 		if not item_codes:
# 			return []

# 	args = {
# 		"text": text,
# 		"item_codes": item_codes,
# 		"category": category,
# 		"company_name": company_name,
# 		"country": country,
# 		"order_by": order_by,
# 		"start": start,
# 		"limit": limit
# 	}
# 	return hub_request('get_items', data=json.dumps(args))

# @frappe.whitelist()
# def get_all_companies():
# 	return hub_request('get_all_companies')

# @frappe.whitelist()
# def get_item_details(item_code):
# 	args = {
# 		"item_code": item_code,
# 	}
# 	return hub_request('get_item_details', data=json.dumps(args))

# @frappe.whitelist()
# def get_company_details(company_id):
# 	args = {
# 		"company_id": company_id,
# 	}
# 	return hub_request('get_company_details', data=json.dumps(args))

# @frappe.whitelist()
# def get_categories():
# 	# update_local_hub_categories()
# 	return hub_request('get_categories')

# def update_local_hub_categories():
# 	categories = get_categories()
# 	categories_to_remove = []
# 	categories_to_add = []
# 	old_categories = frappe.db.sql_list("select category_name from from `tabHub Category`")
# 	new_categories = [d.category_name for d in categories]
# 	for old_category in old_categories:
# 		if old_category not in new_categories:
# 			categories_to_remove.append(old_category)

# 	for new_category in new_categories:
# 		if new_category not in old_categories:
# 			categories_to_add.append(new_category)

# 	for d in categories_to_remove:
# 		docname = frappe.get_list('Hub Category', filters = {"category_name": d})[0]["name"]
# 		frappe.delete_doc("Hub Category", docname)

# 	for d in categories_to_add:
# 		doc = frappe.new_doc("Hub Category")
# 		doc.category_name = d
# 		doc.save()


# @frappe.whitelist()
# def get_items_seen_states(items):
# 	items = json.loads(items)
# 	for d in items:
# 		local_item_code = "HUB-" + d["item_code"]
# 		if frappe.db.exists("Item", {"item_code": local_item_code}):
# 			d["seen"] = 1
# 		else:
# 			d["seen"] = 0
# 	return items

# @frappe.whitelist()
# def get_local_hub_item_codes():
# 	item_codes = []
# 	for d in frappe.get_all("Item", fields=["item_code"], filters={"is_hub_item": 1}):
# 		item_codes.append(d["item_code"][4:])
# 	return item_codes

# @frappe.whitelist()
# def hub_item_request_action(item):
# 	item = json.loads(item)
# 	rfq = make_rfq(item)
# 	# , send click count and say requested
# 	send_opportunity_details(supplier_name, supplier_email)
# 	make_opportunities()
# 	return rfq

# def send_opportunity_details(supplier_name, supplier_email):
# 	connection = get_connection()
# 	params = {
# 		"buyer_name": supplier_name,
# 		"email_id": supplier_email
# 	}
# 	args = frappe._dict(dict(
# 		doctype="Hub Document",
# 		type="Opportunity",
# 		document_data=json.dumps(params),
# 		user=supplier_email
# 	))
# 	response = connection.insert("Hub Document", args)

@frappe.whitelist()
def make_rfq_and_send_opportunity(item, supplier):
	supplier = make_supplier(supplier)
	contact = make_contact(supplier)
	item = make_item(item)
	rfq = make_rfq(item, supplier, contact)
	status = send_opportunity(contact)

	return {
		'rfq': rfq,
		'hub_document_created': status
	}

def make_supplier(supplier):
	# make supplier if not already exists
	supplier = frappe._dict(json.loads(supplier))

	if not frappe.db.exists('Supplier', {'supplier_name': supplier.supplier_name}):
		supplier_doc = frappe.get_doc({
			'doctype': 'Supplier',
			'supplier_name': supplier.supplier_name,
			'supplier_type': supplier.supplier_type,
			'supplier_email': supplier.supplier_email
		}).insert()
	else:
		supplier_doc = frappe.get_doc('Supplier', supplier.supplier_name)

	return supplier_doc

def make_contact(supplier):
	contact_name = get_default_contact('Supplier', supplier.supplier_name)
	# make contact if not already exists
	if not contact_name:
		contact = frappe.get_doc({
			'doctype': 'Contact',
			'first_name': supplier.supplier_name,
			'email_id': supplier.supplier_email,
			'is_primary_contact': 1,
			'links': [
				{'link_doctype': 'Supplier', 'link_name': supplier.supplier_name}
			]
		}).insert()
	else:
		contact = frappe.get_doc('Contact', contact_name)

	return contact

def make_item(item):
	# make item if not already exists
	item = frappe._dict(json.loads(item))

	if not frappe.db.exists('Item', {'item_code': item.item_code}):
		item_doc = frappe.get_doc({
			'doctype': 'Item',
			'item_code': item.item_code,
			'item_group': item.item_group,
			'is_hub_item': 1
		}).insert()
	else:
		item_doc = frappe.get_doc('Item', item.item_code)

	return item_doc

def make_rfq(item, supplier, contact):
	# make rfq
	rfq = frappe.get_doc({
		'doctype': 'Request for Quotation',
		'transaction_date': nowdate(),
		'status': 'Draft',
		'company': frappe.db.get_single_value('Hub Settings', 'company'),
		'message_for_supplier': 'Please supply the specified items at the best possible rates',
		'suppliers': [
			{ 'supplier': supplier.name, 'contact': contact.name }
		],
		'items': [
			{
				'item_code': item.item_code,
				'qty': 1,
				'schedule_date': nowdate(),
				'warehouse': item.default_warehouse or get_root_of("Warehouse"),
				'description': item.description,
				'uom': item.stock_uom
			}
		]
	}).insert()

	rfq.save()
	rfq.submit()
	return rfq

def send_opportunity(contact):
	# Make Hub Message on Hub with lead data
	doc = {
		'doctype': 'Lead',
		'lead_name': frappe.db.get_single_value('Hub Settings', 'company'),
		'email_id': frappe.db.get_single_value('Hub Settings', 'user')
	}

	args = frappe._dict(dict(
		doctype='Hub Message',
		reference_doctype='Lead',
		data=json.dumps(doc),
		user=contact.email_id
	))

	connection = get_connection()
	response = connection.insert('Hub Message', args)

	return response.ok
