# vm_rental/models/sale_order.py
from odoo import models, fields, api, _
import logging
import re # <-- Добавлен импорт

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    vm_instance_id = fields.Many2one(
        'vm_rental.machine',
        string='Virtual Machine',
        copy=False,
        help='Виртуальная машина, к которой относится этот заказ'
    )
    vm_instance_id_state = fields.Selection(related='vm_instance_id.state', string="VM State", readonly=True)

    # Добавляем этот метод для вызова из кнопки
    def action_retry_vm_creation(self):
        self.ensure_one()
        if self.vm_instance_id:
            self.vm_instance_id.action_retry_provisioning()
        return True

    def _action_confirm(self):
        res = super()._action_confirm()
        for order in self.filtered(lambda o: o.state == 'sale' and not o.vm_instance_id):
            for line in order.order_line:
                product = line.product_id
                if not product.hypervisor_server_id:
                    continue

                # ИСПРАВЛЕНИЕ: Правильная обработка конфигурации
                vm_config = {'cores': 1, 'memory': 1024, 'disk': 10}  # Значения по умолчанию

                # Сначала пытаемся взять из атрибутов продукта
                if product.product_template_attribute_value_ids:
                    for attr_line in product.product_template_attribute_value_ids:
                        attribute_name = attr_line.attribute_id.name.lower()
                        attr_value = attr_line.product_attribute_value_id

                        if attr_value.proxmox_value:  # Используем специальное поле
                            try:
                                numeric_value = int(attr_value.proxmox_value)
                                if 'cpu' in attribute_name or 'core' in attribute_name:
                                    vm_config['cores'] = numeric_value
                                elif 'ram' in attribute_name or 'memory' in attribute_name:
                                    vm_config['memory'] = numeric_value
                                elif 'disk' in attribute_name:
                                    vm_config['disk'] = numeric_value
                            except (ValueError, TypeError):
                                _logger.warning(
                                    f"Invalid proxmox_value for attribute {attribute_name}: {attr_value.proxmox_value}")

                # Если конфигурация не была собрана из атрибутов, берем из полей продукта
                if vm_config['cores'] == 1 and hasattr(product, 'vm_cores'):
                    vm_config['cores'] = product.vm_cores or 1
                if vm_config['memory'] == 1024 and hasattr(product, 'vm_memory'):
                    vm_config['memory'] = product.vm_memory or 1024
                if vm_config['disk'] == 10 and hasattr(product, 'vm_disk'):
                    vm_config['disk'] = product.vm_disk or 10

                self.env['vm_rental.machine'].create_from_order(order, line, vm_config)
        return res