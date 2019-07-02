from datetime import datetime
from dateutil import relativedelta
from itertools import groupby
from operator import itemgetter

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_round, float_is_zero

class StockMove(models.Model):
	_inherit = "stock.move"

	def _action_done(self):
		self.filtered(lambda move: move.state == 'draft')._action_confirm()  # MRP allows scrapping draft moves
		moves = self.exists().filtered(lambda x: x.state not in ('done', 'cancel'))
		moves_todo = self.env['stock.move']

		# Cancel moves where necessary ; we should do it before creating the extra moves because
		# this operation could trigger a merge of moves.
		for move in moves:
			if move.quantity_done <= 0:
				if float_compare(move.product_uom_qty, 0.0, precision_rounding=move.product_uom.rounding) == 0:
					move._action_cancel()

		# Create extra moves where necessary
		for move in moves:
			if move.state == 'cancel' or move.quantity_done <= 0:
				continue
			# extra move will not be merged in mrp
			if not move.picking_id:
				moves_todo |= move
			#moves_todo |= move._create_extra_move()

		# Split moves where necessary and move quants
		for move in moves_todo:
			# To know whether we need to create a backorder or not, round to the general product's
			# decimal precision and not the product's UOM.
			rounding = self.env['decimal.precision'].precision_get('Product Unit of Measure')
			if float_compare(move.quantity_done, move.product_uom_qty, precision_digits=rounding) < 0:
				# Need to do some kind of conversion here
				qty_split = move.product_uom._compute_quantity(move.product_uom_qty - move.quantity_done, move.product_id.uom_id, rounding_method='HALF-UP')
				new_move = move._split(qty_split)
				for move_line in move.move_line_ids:
					if move_line.product_qty and move_line.qty_done:
						# FIXME: there will be an issue if the move was partially available
						# By decreasing `product_qty`, we free the reservation.
						# FIXME: if qty_done > product_qty, this could raise if nothing is in stock
						try:
							move_line.write({'product_uom_qty': move_line.qty_done})
						except UserError:
							pass
				move._unreserve_initial_demand(new_move)
		moves_todo.mapped('move_line_ids')._action_done()
		# Check the consistency of the result packages; there should be an unique location across
		# the contained quants.
		for result_package in moves_todo\
				.mapped('move_line_ids.result_package_id')\
				.filtered(lambda p: p.quant_ids and len(p.quant_ids) > 1):
			if len(result_package.quant_ids.mapped('location_id')) > 1:
				raise UserError(_('You cannot move the same package content more than once in the same transfer or split the same package into two location.'))
		picking = moves_todo and moves_todo[0].picking_id or False
		moves_todo.write({'state': 'done', 'date': fields.Datetime.now()})
		moves_todo.mapped('move_dest_ids')._action_assign()

		# We don't want to create back order for scrap moves
		if all(move_todo.scrapped for move_todo in moves_todo):
			return moves_todo

		if picking:
			picking._create_backorder()
		return moves_todo

