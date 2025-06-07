from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    vm_template_id = fields.Many2one('vm.template', string='VM Template')