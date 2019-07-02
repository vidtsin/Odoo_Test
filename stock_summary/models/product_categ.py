from odoo import api, fields, models, _

class StockQuantInherit(models.Model):
	_inherit = 'stock.quant'

	boxes = fields.Float(string="Boxes",compute="calc_boxes")

	@api.multi
	@api.depends('quantity')
	def calc_boxes(self):
		for line in self:

			qty = 0

			for package in line.product_id.packaging_ids:
				if "BOX" in package.name:
					qty = package.qty

			if line.quantity>0 and qty >0:
				line.boxes = line.quantity / qty