# -*- coding: utf-8 -*-

from odoo import api, fields, models,exceptions,_
from odoo.addons import decimal_precision as dp
from datetime import datetime
import odoo.addons.decimal_precision as dp
from odoo.exceptions import Warning
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare
import time
import math

from odoo.osv import expression
from odoo.tools.float_utils import float_round as round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError, ValidationError
_STATES = [
  ('draft', 'Draft'),
  ('to_approve', 'To be approved'),
  ('approved', 'Approved'),
  ('rejected', 'Rejected')
]

class PurchaseRequest(models.Model):
  _name = 'purchase.request'
  _description = 'Purchase Request'
  _inherit = ['mail.thread']

  @api.model
  def _company_get(self):
      company_id = self.env['res.company']._company_default_get(self._name)
      return self.env['res.company'].browse(company_id.id)

  @api.model
  def _get_default_requested_by(self):
      return self.env['res.users'].browse(self.env.uid)

  @api.model
  def _get_default_name(self):
      return self.env['ir.sequence'].get('purchase.request')

  @api.model
  def _default_picking_type(self):
      type_obj = self.env['stock.picking.type']
      company_id = self.env.context.get('company_id') or \
          self.env.user.company_id.id
      types = type_obj.search([('code', '=', 'incoming'),
                               ('warehouse_id.company_id', '=', company_id)])
      if not types:
          types = type_obj.search([('code', '=', 'incoming'),
                                   ('warehouse_id', '=', False)])
      return types[:1]

  @api.multi
  @api.depends('state')
  def _compute_is_editable(self):
      for rec in self:
          if rec.state in ('to_approve', 'approved', 'rejected'):
              rec.is_editable = False
          else:
              rec.is_editable = True

  @api.multi
  def _track_subtype(self, init_values):
      for rec in self:
          if 'state' in init_values and rec.state == 'to_approve':
              return 'skit_po_request.purchase_request_approve'
          elif 'state' in init_values and rec.state == 'approved':
              return 'skit_po_request.purchase_request_approved'
          elif 'state' in init_values and rec.state == 'rejected':
              return 'skit_po_request.purchase_request_rejected'
      return super(PurchaseRequest, self)._track_subtype(init_values)

  @api.multi
  def copy(self, default=None):
      default = dict(default or {})
      self.ensure_one()
      default.update({
          'state': 'draft',
          'name': self.env['ir.sequence'].get('purchase.request'),
      })
      return super(PurchaseRequest, self).copy(default)

  @api.model
  def create(self, vals):
      request = super(PurchaseRequest, self).create(vals)
      if vals.get('assigned_to'):
          request.message_subscribe(request.assigned_to.ids)
      return request

  @api.multi
  def write(self, vals):
      res = super(PurchaseRequest, self).write(vals)
      for request in self:
          if vals.get('assigned_to'):
              self.message_subscribe(request.assigned_to.ids)
      return res

  @api.multi
  def button_draft(self):
      for rec in self:
          rec.state = 'draft'
      return True

  @api.multi
  def button_to_approve(self):
      for rec in self:
          rec.state = 'to_approve'
      return True

  @api.multi
  def button_approved(self):
      for rec in self:
          rec.state = 'approved'
      return True

  @api.multi
  def button_rejected(self):
      for rec in self:
          rec.state = 'rejected'
      return True

  @api.multi
  def button_confirm(self):
      for order in self:
          if order.state not in ['draft', 'sent']:
              continue
          order._add_supplier_to_product()
          # Deal with double validation process
          if order.company_id.po_double_validation == 'one_step'\
                  or (order.company_id.po_double_validation == 'two_step'\
                      and order.amount_total < self.env.user.company_id.currency_id.compute(order.company_id.po_double_validation_amount, order.currency_id))\
                  or order.user_has_groups('purchase.group_purchase_manager'):
              order.button_approve()
          else:
              order.write({'state': 'to approve'})
      return True

  name = fields.Char('Request Reference', size=32, required=True,default=_get_default_name,track_visibility='onchange')
  origin = fields.Char('Source Document', size=32)
  date_start = fields.Datetime('Creation date',help="Date when the user initiated the request.",default=fields.Datetime.now(),track_visibility='onchange')
  requested_by = fields.Many2one('res.users','Requested by',required=True,track_visibility='onchange',default=_get_default_requested_by)
  assigned_to = fields.Many2one('res.users', 'Approver',domain=lambda self: [("groups_id", "=", self.env.ref( "skit_po_request.group_purchase_request_manager").id)],
                                track_visibility='onchange')
  description = fields.Text('Description')
  company_id = fields.Many2one('res.company', 'Company',required=True,default=_company_get,track_visibility='onchange')
  line_ids = fields.One2many('purchase.request.line', 'request_id','Products to Purchase',readonly=False,copy=True,
                             track_visibility='onchange')
  state = fields.Selection(selection=_STATES,string='Status',index=True,track_visibility='onchange',required=True,copy=False,
                           default='draft')
  is_editable = fields.Boolean(string="Is editable",compute="_compute_is_editable",readonly=True)

  picking_type_id = fields.Many2one('stock.picking.type','Picking Type', required=True, default=_default_picking_type)
  purchase_type = fields.Many2one('purchase.type',string = 'Purchase Request Type',store = True)
  z_check_order = fields.Char(store = True,compute = '_check_line',string = 'Status')
  z_check_order_1 = fields.Char(store = True,string = 'Status',compute = "_check_close")
  z_analytic_account = fields.Many2one('account.analytic.account',string = 'Account Analytic',store = True)
  @api.multi
  @api.depends('line_ids.check_boolean')
  def _check_line(self):
    for line in self:
      for l in line.line_ids:
        if l.check_boolean == False:
          line.z_check_order = "Open"
  @api.multi
  @api.depends('line_ids.check_boolean','z_check_order')
  def _check_close(self):
    for line in self:
      if not line.z_check_order:
        line.z_check_order_1 = "Close"
  

class PurchaseRequestLine(models.Model):

  _name = "purchase.request.line"
  _description = "Purchase Request Line"
  _inherit = ['mail.thread']

  @api.multi
  @api.depends('product_id', 'name', 'product_uom_id', 'product_qty',
               'analytic_account_id', 'date_required', 'specifications')
  def _compute_is_editable(self):
      for rec in self:
          if rec.request_id.state in ('to_approve', 'approved', 'rejected'):
              rec.is_editable = False
          else:
              rec.is_editable = True

  @api.depends('product_id')
  def _compute_supplier_id(self):
      for rec in self:
          if rec.product_id:
              if rec.product_id.seller_ids:
                  rec.supplier_id = rec.product_id.seller_ids[0].name

  @api.onchange('product_id', 'product_uom_id')
  def onchange_product_id(self):
      if self.product_id:
          name = self.product_id.name
          if self.product_id.code:
              name = '[%s] %s' % (name, self.product_id.code)
          if self.product_id.description_purchase:
              name += '\n' + self.product_id.description_purchase
          self.product_uom_id = self.product_id.uom_id.id
          self.product_qty = 1
          self.name = name

  product_id = fields.Many2one('product.product', 'Product',domain=[('purchase_ok', '=', True)],track_visibility='onchange')
  name = fields.Char('Description', size=256,track_visibility='onchange')
  product_uom_id = fields.Many2one('uom.uom', 'Unit of Measure',track_visibility='onchange')
  product_qty = fields.Float('Quantity', track_visibility='onchange',digits_compute=dp.get_precision('Product Unit of Measure'))
  request_id = fields.Many2one('purchase.request','Purchase Request',ondelete='cascade', readonly=True)
  company_id = fields.Many2one('res.company',related='request_id.company_id',string='Company',store=True, readonly=True)
  analytic_account_id = fields.Many2one('account.analytic.account','Analytic Account',related = 'request_id.z_analytic_account',track_visibility='onchange')
  requested_by = fields.Many2one('res.users',related='request_id.requested_by',string='Requested by',store=True, readonly=True)
  assigned_to = fields.Many2one('res.users',related='request_id.assigned_to',string='Assigned to',store=True, readonly=True)
  date_start = fields.Datetime(related='request_id.date_start',string='Request Date', readonly=True,store=True)
  description = fields.Text(related='request_id.description',string='Description', readonly=True, store=True)
  origin = fields.Char(related='request_id.origin',size=32, string='Source Document', readonly=True,store=True)
  date_required = fields.Datetime(string='Request Date', required=True,track_visibility='onchange',default=fields.Datetime.now())
  is_editable = fields.Boolean(string='Is editable',compute="_compute_is_editable",readonly=True)
  specifications = fields.Text(string='Specifications')
  request_state = fields.Selection(string='Request state',readonly=True,related='request_id.state',selection=_STATES,store=True)
  supplier_id = fields.Many2one('res.partner',string='Preferred supplier',compute="_compute_supplier_id")

  procurement_id = fields.Many2one('procurement.order','Procurement Order',readonly=True)
  purchase_id = fields.Many2one('purchase.order',"Purchase Order",invisible = True)
  z_balance_quantity = fields.Float('Balance Quantity',store = True)
  z_balance_quantity_order = fields.Float('Purchase order Quantity',store = True)
  check_boolean = fields.Boolean('Status',store = True)
  check_status = fields.Char('Check Status',store = True)
  categ_types = fields.Selection([('products','Products'),('services','Services'),('assets','Assets'),('charge','Charges')],'Category',default='products')
  @api.onchange('categ_types')
  def onchange_use_insurance(self):
    res = {}
    if self.categ_types == 'charge':
      res['domain'] = {'product_id': [('purchase_ok', '=', True),'&',('type', '=', 'service'),('categ_charge', '=', True)]}
    elif self.categ_types == 'services':
      res['domain'] = {'product_id': [('purchase_ok', '=', True),'&',('type', '=', 'service'),('categ_service', '=', True)]}
    elif self.categ_types == 'assets':
      res['domain'] = {'product_id': [('purchase_ok', '=', True),'&',('type', '=', ['product','consu']),('categ_assets', '=', True)]}
    else:
      res['domain'] = {'product_id': [('purchase_ok', '=', True),'&',('type', '=', ['product','consu']),('categ_product', '=', True)]}
    return res
  @api.onchange('check_boolean')
  def _change_check_status(self):
    for lit in self:
      count = self.env['purchase.request.line'].search_count([('check_boolean','=',lit.check_boolean)])
      lit.check_status = str(count)
