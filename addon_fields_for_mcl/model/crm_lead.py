from odoo import api, fields, models,_

class Lead(models.Model):
    _inherit = "crm.lead"

    z_project_site = fields.Many2one('site.name',string="Project Site")
    mobile = fields.Char(string="Mobile",required=True)
    zip = fields.Char(required=True)

