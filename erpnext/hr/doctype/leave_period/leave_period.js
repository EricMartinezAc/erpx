// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt


frappe.ui.form.on('Leave Period', {
	refresh: (frm)=>{
		frm.set_df_property("grant_leaves", "hidden", frm.doc.__islocal ? 1:0);
		if(!frm.is_new()) {
			frm.add_custom_button(__('Grant Leaves'), function () {
				frm.trigger("grant_leaves");
			});
		}
	},
	from_date: (frm)=>{
		if (frm.doc.from_date && !frm.doc.to_date) {
			var a_year_from_start = frappe.datetime.add_months(frm.doc.from_date, 12);
			frm.set_value("to_date", frappe.datetime.add_days(a_year_from_start, -1));
		}
	},
	onload: (frm) => {
		frm.set_query("department", function() {
			return {
				"filters": {
					"company": frm.doc.company,
				}
			}
		})
	},
	grant_leaves: function(frm) {
		var d = new frappe.ui.form.MultiSelectDialog({
			doctype: "Employee",
			target: cur_frm,
			setters: {
				company: cur_frm.doc.company,
				department: '',
				employee_name: '',
				grade: ''
			},
			data_fields:[
				{
					"label": "Add unused leaves from previous allocations",
					"fieldname": "carry_forward",
					"fieldtype": "Check"
				}
			],
			get_query() {
				return {
					filters: { status: ['=', "Active"] }
				};
			},
			add_filters_group: 1,
			primary_action_label: "Get Employee",
			action(employees, data, field_filters, standard_filters) {
				if(employees.length){
					frappe.call({
						doc: frm.doc,
						method: "grant_leave_allocation",
						args: {
							employees: employees,
							company: data["company"],
						},
						callback: function(r) {
							if(r.docs[0].employees.length){
								cur_dialog.hide();
							}
						}
					});
				}else{
					frappe.msgprint(__("Please Select Employees."));
				}
			}
		});
		// var d = new frappe.ui.Dialog({
		// 	title: __('Grant Leaves'),
		// 	fields: [
		// 		{
		// 			"label": "Filter Employees By (Optional)",
		// 			"fieldname": "sec_break",
		// 			"fieldtype": "Section Break",
		// 		},
		// 		{
		// 			"label": "Employee Grade",
		// 			"fieldname": "grade",
		// 			"fieldtype": "Link",
		// 			"options": "Employee Grade"
		// 		},
		// 		{
		// 			"label": "Department",
		// 			"fieldname": "department",
		// 			"fieldtype": "Link",
		// 			"options": "Department"
		// 		},
		// 		{
		// 			"fieldname": "col_break",
		// 			"fieldtype": "Column Break",
		// 		},
		// 		{
		// 			"label": "Designation",
		// 			"fieldname": "designation",
		// 			"fieldtype": "Link",
		// 			"options": "Designation"
		// 		},
		// 		{
		// 			"label": "Employee",
		// 			"fieldname": "employee",
		// 			"fieldtype": "Link",
		// 			"options": "Employee"
		// 		},
		// 		{
		// 			"fieldname": "sec_break",
		// 			"fieldtype": "Section Break",
		// 		},
		//
		// 	],
		// 	primary_action: function() {
		// 		var data = d.get_values();

		// 		frappe.call({
		// 			doc: frm.doc,
		// 			method: "grant_leave_allocation",
		// 			args: data,
		// 			callback: function(r) {
		// 				if(!r.exc) {
		// 					d.hide();
		// 					frm.reload_doc();
		// 				}
		// 			}
		// 		});
		// 	},
		// 	primary_action_label: __('Grant')
		// });
		// d.show();
	}
});
