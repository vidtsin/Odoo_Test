from odoo.addons import decimal_precision as dp
from collections import namedtuple
import json
import time
from odoo.exceptions import UserError, ValidationError,Warning
from itertools import groupby
from odoo import api, fields, models,_,exceptions
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import UserError
from odoo.addons.stock.models.stock_move import PROCUREMENT_PRIORITIES
from operator import itemgetter

class Stockmoveline(models.Model):
	_inherit = "stock.move.line"
	qunatity_on_hand = fields.Char(string = 'Quantity on Hand',compute = "quantity_line")
	#heloo  = fields.Char('hello')
	z_qunatity_on_hand = fields.Char(string = 'Quantity on Hand',store = True,compute = "quantity_line")
	@api.multi
	@api.depends('product_id','lot_id','location_id')
	def quantity_line(self):
		for line in self:
			invoice_ids = self.env['stock.quant'].search([('product_id','=',line.product_id.id),('location_id','=',line.location_id.id),('lot_id','=',line.lot_id.id)])
			for run in invoice_ids:
				line.qunatity_on_hand = run.quantity
				line.z_qunatity_on_hand = run.quantity
 
