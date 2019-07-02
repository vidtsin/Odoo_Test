from odoo import api, fields, models, _

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"
    z_parent_id = fields.Many2one('product.category', 'Parent Category', index=True,ondelete='cascade',related='product_id.categ_id.parent_id.parent_id')
    z_status = fields.Char('Status Type',store=True,track_visibility="always",compute='_compute_status_type')
    z_product_category = fields.Char('Product Category',store = True,related = 'product_id.categ_id.complete_name')
    @api.multi
    @api.depends('location_dest_id','location_id')
    def _compute_status_type(self):
    	for line in self:
    		if line.location_dest_id.id == 9:
    			line.z_status = 'Sale'
    		if line.location_dest_id.id == 7:
    			line.z_status = 'Consumption'
    		if line.location_id.id == 7:
    			line.z_status = 'Production'
    		if line.location_id.id == 8:
    			line.z_status = 'Purchase'
    		if line.location_id.id == 5:
    			line.z_status = 'Positive Adjustment'
    		if line.location_dest_id.id == 5:
    			line.z_status = 'Negative Adjustment'


class StockQuant(models.Model):
    _inherit = "stock.quant"
    z_parent_id = fields.Many2one('product.category', 'Parent Category', index=True,store = True,ondelete='cascade',related='product_id.categ_id.parent_id')
    z_product_category = fields.Char('Product Category',store = True,related = 'product_id.categ_id.complete_name')

class ProductProduct(models.Model):
    _inherit = "product.product"
    z_parent_id = fields.Many2one('product.category', 'Parent Category', index=True,store = True,ondelete='cascade',related='categ_id.parent_id')
    z_product_category = fields.Char('Product Category',store = True,related = 'categ_id.complete_name')
