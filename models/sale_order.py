from odoo import models, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    vm_instance_id = fields.Many2one(
        'vm.instance',
        string='Virtual Machine',
        help='Виртуальная машина, к которой относится этот заказ'
    )

def _action_confirm(self):
    res = super()._action_confirm()
    for order in self.filtered(lambda o: o.state == 'sale'):
        for line in order.order_line.filtered(lambda l: l.product_id.vm_template_id):
            # Логика создания новой ВМ
            self.env['vm.instance'].create_from_template(
                template=line.product_id.vm_template_id,
                partner=order.partner_id,
                order=order
            )
    return res