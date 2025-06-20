from odoo import models, fields, api, _
import logging
import re

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
                # Проверяем, является ли продукт товаром для аренды ВМ
                if not product.hypervisor_server_id:
                    continue

                # ИСПРАВЛЕНИЕ: Теперь используем поля из миксина
                vm_config = {
                    'cores': product.cores or 1,  # Поле из миксина
                    'memory': product.memory or 1024,  # Поле из миксина
                    'disk': product.disk or 10  # Поле из миксина
                }

                # Дополнительно проверяем атрибуты продукта для переопределения
                if product.product_template_attribute_value_ids:
                    for attr_line in product.product_template_attribute_value_ids:
                        attribute_name = attr_line.attribute_id.name.lower()
                        attr_value = attr_line.product_attribute_value_id

                        # Используем proxmox_value если есть, иначе парсим имя
                        value_to_parse = attr_value.proxmox_value or attr_value.name
                        numeric_match = re.search(r'\d+', str(value_to_parse))

                        if numeric_match:
                            try:
                                numeric_value = int(numeric_match.group(0))
                                if 'cpu' in attribute_name or 'core' in attribute_name:
                                    vm_config['cores'] = numeric_value
                                elif 'ram' in attribute_name or 'memory' in attribute_name:
                                    vm_config[
                                        'memory'] = numeric_value * 1024 if numeric_value < 100 else numeric_value  # Автоматическое преобразование GB в MB
                                elif 'disk' in attribute_name:
                                    vm_config['disk'] = numeric_value
                            except (ValueError, TypeError):
                                _logger.warning(f"Invalid value for attribute {attribute_name}: {value_to_parse}")

                _logger.info(f"Preparing to create VM for order {order.name} with config: {vm_config}")

                self.env['vm_rental.machine'].create_from_order(order, line, vm_config)

        return res