# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from functools import partial
from itertools import groupby

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang
from odoo.osv import expression
from odoo.tools import float_is_zero, float_compare


from odoo.addons import decimal_precision as dp

from werkzeug.urls import url_encode

import time
from odoo.exceptions import UserError


class SaleOrder(models.Model):
	_inherit = "sale.order"

	#inherited field to make readonly false
	analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', store=True,help="The analytic account related to a sales order.", oldname='project_id')


	@api.multi
	def action_confirm(self):
		if self.state =='approved' or self.state == 'to_confirm':
			if not self.analytic_account_id:
				raise UserError(_('Kindly select the Analytic Account before confirming this Sale order'))
		return super(SaleOrder, self).action_confirm()

class SaleOrderLine(models.Model):
	_inherit = "sale.order.line"

	#new field added.. account_analytic_id is used to display in the front end. But the value is flowing in the function create_invoices
	analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account',help="The analytic account related to a sales order.", copy=False)
	analytic_tag_ids = fields.Many2many('account.analytic.tag', string='Analytic Tags',copy=False)

	

class SaleAdvancePaymentInv(models.TransientModel):
	_inherit = "sale.advance.payment.inv"
	_description = "Sales Advance Payment Invoice"

	@api.multi
	def _create_invoice(self, order, so_line, amount):
		inv_obj = self.env['account.invoice']
		ir_property_obj = self.env['ir.property']

		account_id = False
		if self.product_id.id:
			account_id = self.product_id.property_account_income_id.id or self.product_id.categ_id.property_account_income_categ_id.id
		if not account_id:
			inc_acc = ir_property_obj.get('property_account_income_categ_id', 'product.category')
			account_id = order.fiscal_position_id.map_account(inc_acc).id if inc_acc else False
		if not account_id:
			raise UserError(
				_('There is no income account defined for this product: "%s". You may have to install a chart of account from Accounting app, settings menu.') %
				(self.product_id.name,))

		if self.amount <= 0.00:
			raise UserError(_('The value of the down payment amount must be positive.'))
		context = {'lang': order.partner_id.lang}
		if self.advance_payment_method == 'percentage':
			amount = order.amount_untaxed * self.amount / 100
			name = _("Down payment of %s%%") % (self.amount,)
		else:
			amount = self.amount
			name = _('Down Payment')
		del context
		taxes = self.product_id.taxes_id.filtered(lambda r: not order.company_id or r.company_id == order.company_id)
		if order.fiscal_position_id and taxes:
			tax_ids = order.fiscal_position_id.map_tax(taxes, self.product_id, order.partner_shipping_id).ids
		else:
			tax_ids = taxes.ids

		invoice = inv_obj.create({
            'name': order.client_order_ref or order.name,
            'origin': order.name,
            'type': 'out_invoice',
            'reference': False,
            'account_id': order.partner_id.property_account_receivable_id.id,
            'partner_id': order.partner_invoice_id.id,
            'partner_shipping_id': order.partner_shipping_id.id,
            'z_analytic_account_id':order.analytic_account_id.id,
            'invoice_line_ids': [(0, 0, {
                'name': name,
                'origin': order.name,
                'account_id': account_id,
                'price_unit': amount,
                'quantity': 1.0,
                'discount': 0.0,
                'uom_id': self.product_id.uom_id.id,
                'product_id': self.product_id.id,
                'sale_line_ids': [(6, 0, [so_line.id])],
                'invoice_line_tax_ids': [(6, 0, tax_ids)],
                'analytic_tag_ids': [(6, 0, so_line.analytic_tag_ids.ids)],
                #'account_analytic_id': order.analytic_account_id.id or False,
            })],
            'currency_id': order.pricelist_id.currency_id.id,
            'payment_term_id': order.payment_term_id.id,
            'fiscal_position_id': order.fiscal_position_id.id or order.partner_id.property_account_position_id.id,
            'team_id': order.team_id.id,
            'user_id': order.user_id.id,
            'comment': order.note,
        })
		invoice.compute_taxes()
		invoice.message_post_with_view('mail.message_origin_link',
			values={'self': invoice, 'origin': order},
			subtype_id=self.env.ref('mail.mt_note').id)
		return invoice
