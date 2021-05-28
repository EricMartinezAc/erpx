# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint, flt, cstr, getdate, today
from frappe.model.utils import get_fetch_values
from frappe.contacts.doctype.address.address import get_address_display, get_default_address
from frappe.contacts.doctype.contact.contact import get_contact_details, get_default_contact
from erpnext.stock.get_item_details import get_item_warehouse, get_item_price, get_default_supplier, get_default_terms
from erpnext.stock.doctype.item.item import get_item_defaults
from erpnext.setup.doctype.item_group.item_group import get_item_group_defaults
from erpnext.setup.doctype.brand.brand import get_brand_defaults
from erpnext.setup.doctype.item_source.item_source import get_item_source_defaults
from erpnext.vehicles.doctype.vehicle_withholding_tax_rule.vehicle_withholding_tax_rule import get_withholding_tax_amount
from erpnext.setup.doctype.terms_and_conditions.terms_and_conditions import get_terms_and_conditions
from erpnext.controllers.accounts_controller import AccountsController
from six import string_types
import json


address_fields = ['address_line1', 'address_line2', 'city', 'state']

force_fields = [
	'customer_name', 'financer_name', 'lessee_name', 'customer_category',
	'item_name', 'item_group', 'brand', 'variant_of', 'variant_of_name',
	'customer_address',
	'address_display', 'contact_display', 'financer_contact_display', 'contact_email', 'contact_mobile', 'contact_phone',
	'father_name', 'husband_name',
	'tax_id', 'tax_cnic', 'tax_strn', 'tax_status', 'tax_overseas_cnic', 'passport_no',
	'withholding_tax_amount', 'exempt_from_vehicle_withholding_tax'
]
force_fields += address_fields

force_if_not_empty_fields = []


class VehicleBookingController(AccountsController):
	def validate(self):
		if self.get("_action") != "update_after_submit":
			self.set_missing_values(for_validate=True)

		self.validate_date_with_fiscal_year()
		self.validate_customer()
		self.validate_vehicle_item()
		self.validate_vehicle()
		self.validate_allocation()
		self.validate_delivery_date()

		self.calculate_taxes_and_totals()
		self.validate_amounts()

		self.validate_payment_schedule()

		self.clean_remarks()

	def onload(self):
		super(VehicleBookingController, self).onload()

		if self.docstatus == 0:
			self.set_missing_values(for_validate=True)
			self.calculate_taxes_and_totals()
		elif self.docstatus == 1:
			self.set_vehicle_details()

	def set_missing_values(self, for_validate=False):
		customer_details = get_customer_details(self.as_dict(), get_withholding_tax=False)
		for k, v in customer_details.items():
			if self.meta.has_field(k) and not self.get(k) or k in force_fields or (v and k in force_if_not_empty_fields):
				self.set(k, v)

		item_details = get_item_details(self.as_dict())
		for k, v in item_details.items():
			if self.meta.has_field(k) and not self.get(k) or k in force_fields or (v and k in force_if_not_empty_fields):
				self.set(k, v)

		self.set_vehicle_details()

	def set_vehicle_details(self, update=False):
		if self.get('vehicle'):
			values = get_fetch_values(self.doctype, "vehicle", self.vehicle)
			if update:
				self.db_set(values)
			else:
				for k, v in values.items():
					self.set(k, v)

	def validate_customer(self):
		if not self.get('customer') and not self.get('customer_is_company') and not self.get('party_name'):
			frappe.throw(_("Customer is mandatory"))

		self.validate_party()

		if self.get('financer') and not self.get('finance_type'):
			frappe.throw(_("Finance Type is mandatory if Financer is set"))
		if not self.get('financer') and self.meta.has_field('finance_type'):
			self.finance_type = ""

		if self.get('finance_type') and self.get('finance_type') not in ['Financed', 'Leased']:
			frappe.throw(_("Finance Type must be either 'Financed' or 'Leased'"))

		customer = self.get('customer') or (self.get('quotation_to') == "Customer" and self.get('party_name'))
		if customer and self.financer and customer == self.financer:
			frappe.throw(_("Customer and Financer cannot be the same"))

	def validate_vehicle_item(self):
		item = frappe.get_cached_doc("Item", self.item_code)
		validate_vehicle_item(item)

	def validate_vehicle(self):
		if self.get('vehicle'):
			vehicle_item_code = frappe.db.get_value("Vehicle", self.vehicle, "item_code")
			if vehicle_item_code != self.item_code:
				frappe.throw(_("Vehicle {0} is not {1}").format(self.vehicle, frappe.bold(self.item_name or self.item_code)))

	def validate_allocation(self):
		if self.meta.has_field('vehicle_allocation_required'):
			self.vehicle_allocation_required = frappe.get_cached_value("Item", self.item_code, "vehicle_allocation_required")

	def validate_delivery_date(self):
		delivery_date = getdate(self.delivery_date)

		if delivery_date < getdate(self.transaction_date):
			frappe.throw(_("Delivery Due Date cannot be before Booking Date"))

		if self.delivery_period and self.delivery_date:
			from_date, to_date = frappe.get_cached_value("Vehicle Allocation Period", self.delivery_period,
				['from_date', 'to_date'])

			if delivery_date > getdate(to_date) or delivery_date < getdate(from_date):
				frappe.throw(_("Delivery Due Date must be within Delivery Period {0} if Delivery Period is selected")
					.format(self.delivery_period))

	def validate_delivery_period_mandatory(self):
		if not self.delivery_period:
			frappe.throw(_("Delivery Period is mandatory before submission"))

	def calculate_taxes_and_totals(self):
		self.round_floats_in(self, ['vehicle_amount', 'fni_amount', 'withholding_tax_amount'])

		self.invoice_total = flt(self.vehicle_amount + self.fni_amount + self.withholding_tax_amount,
			self.precision('invoice_total'))

		self.calculate_contribution()
		self.set_total_in_words()

	def calculate_contribution(self):
		total = 0.0
		sales_team = self.get("sales_team", [])
		for sales_person in sales_team:
			self.round_floats_in(sales_person)

			sales_person.allocated_amount = flt(
				self.invoice_total * sales_person.allocated_percentage / 100.0,
				self.precision("allocated_amount", sales_person))

			total += sales_person.allocated_percentage

		if sales_team and total != 100.0:
			frappe.throw(_("Total allocated percentage for sales team should be 100"))

	def set_total_in_words(self):
		from frappe.utils import money_in_words
		self.in_words = money_in_words(self.invoice_total, self.company_currency)

	def validate_amounts(self):
		for field in ['vehicle_amount', 'invoice_total']:
			self.validate_value(field, '>', 0)
		for field in ['fni_amount', 'withholding_tax_amount']:
			self.validate_value(field, '>=', 0)

	def validate_payment_schedule(self):
		self.validate_payment_schedule_dates()
		self.set_payment_schedule()
		self.set_due_date()
		self.validate_payment_schedule_amount()
		self.validate_due_date()

	def get_terms_and_conditions(self):
		if self.get('tc_name'):
			self.terms = get_terms_and_conditions(self.tc_name, self.as_dict())

@frappe.whitelist()
def get_customer_details(args, get_withholding_tax=True):
	if isinstance(args, string_types):
		args = json.loads(args)

	args = frappe._dict(args)
	args.customer_is_company = cint(args.customer_is_company)

	if not args.company:
		frappe.throw(_("Company is mandatory"))
	if not args.customer and not args.customer_is_company:
		frappe.throw(_("Customer is mandatory"))
	if args.customer and args.financer and args.customer == args.financer:
		frappe.throw(_("Customer and Financer cannot be the same"))

	out = frappe._dict()

	if args.customer_is_company:
		out.customer = None

	# Determine company or customer and financer
	party_type, party, financer = get_party_doc(args)
	is_leased = financer and args.finance_type == "Leased"

	# Customer and Financer Name
	out.update(get_party_name_and_category(args, party, financer))

	# Tax IDs
	out.update(get_party_tax_ids(args, party, financer))

	# Additional information from custom fields
	out.father_name = party.get('father_name')
	out.husband_name = party.get('husband_name')

	# Address
	out.customer_address = args.customer_address
	if not out.customer_address:
		out.customer_address = get_default_address("Customer", financer.name) if is_leased else get_default_address(party_type, party.name)
	out.update(get_address_details(out.customer_address))

	# Contact
	out.contact_person = args.contact_person or get_default_contact(party_type, party.name)
	out.financer_contact_person = args.financer_contact_person or (get_default_contact("Customer", financer.name) if financer else None)
	out.update(get_customer_contact_details(args, out.contact_person, out.financer_contact_person))

	# Withholding Tax
	if cint(get_withholding_tax) and args.item_code:
		out.exempt_from_vehicle_withholding_tax = cint(frappe.get_cached_value("Item", args.item_code, "exempt_from_vehicle_withholding_tax"))
		out.withholding_tax_amount = get_withholding_tax_amount(args.transaction_date, args.item_code, out.tax_status, args.company)

	default_payment_terms = frappe.get_cached_value("Vehicles Settings", None, "default_payment_terms")
	if default_payment_terms:
		out.payment_terms_template = default_payment_terms

	return out


def get_party_doc(args):
	party_type = "Company" if args.customer_is_company else "Customer"
	party_name = args.company if args.customer_is_company else args.customer

	party = frappe.get_cached_doc(party_type, party_name)
	financer = frappe.get_cached_doc("Customer", args.financer) if args.financer else frappe._dict()

	args.finance_type = args.finance_type or 'Financed' if financer else None

	return party_type, party, financer


def get_party_name_and_category(args, party, financer):
	out = frappe._dict()

	if party.doctype == "Customer":
		out.customer_name = party.customer_name
	else:
		out.customer_name = args.company

	if financer:
		out.financer_name = financer.customer_name
		out.lessee_name = out.customer_name

		if args.finance_type == 'Financed':
			out.customer_name = "{0} HPA {1}".format(out.customer_name, financer.customer_name)
		elif args.finance_type == 'Leased':
			out.customer_name = financer.customer_name
	else:
		out.lessee_name = None
		out.financer_name = None

	# Customer Category
	if party.get('customer_type') == "Individual":
		if args.financer:
			out.customer_category = "Lease" if args.finance_type == "Leased" else "Finance"
		else:
			out.customer_category = "Individual"
	else:
		if args.financer:
			out.customer_category = "Corporate Lease" if args.finance_type == "Leased" else "Finance"
		else:
			out.customer_category = "Corporate"

	return out


def get_party_tax_ids(args, party, financer):
	out = frappe._dict()

	out.tax_id = financer.get('tax_id') if financer else party.get('tax_id')
	out.tax_strn = financer.get('tax_strn') if financer else party.get('tax_strn')

	out.tax_cnic = party.get('tax_cnic')
	out.tax_overseas_cnic = party.get('tax_overseas_cnic')
	out.passport_no = party.get('passport_no')

	is_leased = financer and args.finance_type == "Leased"
	out.tax_status = financer.get('tax_status') if is_leased else party.get('tax_status')

	return out


@frappe.whitelist()
def get_customer_contact_details(args, customer_contact=None, financer_contact=None):
	if isinstance(args, string_types):
		args = json.loads(args)

	args = frappe._dict(args)
	out = frappe._dict()

	customer_contact = get_contact_details(customer_contact) if customer_contact else frappe._dict()
	financer_contact = get_contact_details(financer_contact) if financer_contact else frappe._dict()

	is_leased = args.financer and args.finance_type == "Leased"

	out.contact_display = customer_contact.get('contact_display')
	out.financer_contact_display = financer_contact.get('contact_display')

	out.contact_email = customer_contact.get('contact_email')
	out.contact_mobile = customer_contact.get('contact_mobile') or financer_contact.get('contact_mobile')
	out.contact_phone = financer_contact.get('contact_phone') if is_leased else customer_contact.get('contact_phone')

	return out


@frappe.whitelist()
def get_address_details(address):
	out = frappe._dict()

	address_dict = frappe.db.get_value("Address", address, "*", as_dict=True, cache=True) or {}

	out.address_display = get_address_display(address_dict)
	for f in address_fields:
		out[f] = address_dict.get(f)

	return out


@frappe.whitelist()
def get_item_details(args):
	if isinstance(args, string_types):
		args = json.loads(args)

	args = frappe._dict(args)

	if not args.company:
		frappe.throw(_("Company is mandatory"))
	if not args.item_code:
		frappe.throw(_("Variant Item Code is mandatory"))

	out = frappe._dict()

	item = frappe.get_cached_doc("Item", args.item_code)
	validate_vehicle_item(item)

	out.item_name = item.item_name
	out.item_group = item.item_group
	out.brand = item.brand

	out.variant_of = item.variant_of
	out.variant_of_name = frappe.get_cached_value("Item", item.variant_of, "item_name") if item.variant_of else None

	item_defaults = get_item_defaults(item.name, args.company)
	item_group_defaults = get_item_group_defaults(item.name, args.company)
	brand_defaults = get_brand_defaults(item.name, args.company)
	item_source_defaults = get_item_source_defaults(item.name, args.company)

	if not args.supplier:
		out.supplier = get_default_supplier(args, item_defaults, item_group_defaults, brand_defaults, item_source_defaults, {})

	if not args.warehouse:
		out.warehouse = get_item_warehouse(item, args, overwrite_warehouse=True, item_defaults=item_defaults, item_group_defaults=item_group_defaults,
			brand_defaults=brand_defaults, item_source_defaults=item_source_defaults)

	out.vehicle_price_list = args.vehicle_price_list or get_default_price_list(item, args, item_defaults=item_defaults, item_group_defaults=item_group_defaults,
		brand_defaults=brand_defaults, item_source_defaults=item_source_defaults)

	fni_price_list_settings = frappe.get_cached_value("Vehicles Settings", None, "fni_price_list")
	if fni_price_list_settings:
		out.fni_price_list = fni_price_list_settings

	if args.customer:
		args.tax_status = frappe.get_cached_value("Customer", args.customer, "tax_status")

	out.exempt_from_vehicle_withholding_tax = cint(item.exempt_from_vehicle_withholding_tax)

	if out.vehicle_price_list:
		out.update(get_vehicle_price(args.company, item.name, out.vehicle_price_list, out.fni_price_list, args.transaction_date, args.tax_status))

	if not args.tc_name:
		out.tc_name = get_default_terms(args, item_defaults, item_group_defaults, brand_defaults, item_source_defaults, {})
		if not out.tc_name:
			out.tc_name = frappe.get_cached_value("Vehicles Settings", None, "default_booking_terms")

	return out


@frappe.whitelist()
def get_vehicle_default_supplier(item_code, company):
	if not company:
		frappe.throw(_("Company is mandatory"))
	if not item_code:
		frappe.throw(_("Variant Item Code is mandatory"))

	item = frappe.get_cached_doc("Item", item_code)

	item_defaults = get_item_defaults(item.name, company)
	item_group_defaults = get_item_group_defaults(item.name, company)
	brand_defaults = get_brand_defaults(item.name, company)
	item_source_defaults = get_item_source_defaults(item.name, company)

	default_supplier = get_default_supplier(frappe._dict({"item_code": item_code, "company": company}),
		item_defaults, item_group_defaults, brand_defaults, item_source_defaults, {})

	return default_supplier


@frappe.whitelist()
def get_vehicle_price(company, item_code, vehicle_price_list, fni_price_list=None, transaction_date=None, tax_status=None):
	if not item_code:
		frappe.throw(_("Variant Item Code is mandatory"))
	if not vehicle_price_list:
		frappe.throw(_("Vehicle Price List is mandatory for Vehicle Price"))
	if not company:
		frappe.throw(_("Company is mandatory"))

	transaction_date = getdate(transaction_date)
	item = frappe.get_cached_doc("Item", item_code)

	out = frappe._dict()
	vehicle_price_args = {
		"price_list": vehicle_price_list,
		"transaction_date": transaction_date,
		"uom": item.stock_uom
	}

	vehicle_item_price = get_item_price(vehicle_price_args, item_code, ignore_party=True)
	vehicle_item_price = vehicle_item_price[0][1] if vehicle_item_price else 0
	out.vehicle_amount = flt(vehicle_item_price)

	out.withholding_tax_amount = get_withholding_tax_amount(transaction_date, item_code, tax_status, company)

	if fni_price_list:
		fni_price_args = vehicle_price_args.copy()
		fni_price_args['price_list'] = fni_price_list
		fni_item_price = get_item_price(fni_price_args, item_code, ignore_party=True)
		fni_item_price = fni_item_price[0][1] if fni_item_price else 0
		out.fni_amount = flt(fni_item_price)
	else:
		out.fni_amount = 0

	return out


def get_default_price_list(item, args, item_defaults, item_group_defaults, brand_defaults, item_source_defaults):
		price_list = (item_defaults.get('default_price_list')
			or item_source_defaults.get('default_price_list')
			or brand_defaults.get('default_price_list')
			or item_group_defaults.get('default_price_list')
			or args.get('price_list')
		)

		if not price_list:
			price_list = frappe.get_cached_value("Vehicles Settings", None, "vehicle_price_list")
		if not price_list:
			price_list = frappe.get_cached_value("Buying Settings", None, "buying_price_list")
		if not price_list:
			price_list = frappe.get_cached_value("Selling Settings", None, "selling_price_list")

		return price_list


def validate_vehicle_item(item, validate_in_vehicle_booking=True):
	from erpnext.stock.doctype.item.item import validate_end_of_life
	validate_end_of_life(item.name, item.end_of_life, item.disabled)

	if not item.is_vehicle:
		frappe.throw(_("{0} is not a Vehicle Item").format(item.item_name or item.name))
	if validate_in_vehicle_booking and not item.include_in_vehicle_booking:
		frappe.throw(_("Vehicle Item {0} is not allowed for Vehicle Booking").format(item.item_name or item.name))