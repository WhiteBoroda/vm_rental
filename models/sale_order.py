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

    def _action_confirm(self):
        res = super()._action_confirm()
        for order in self.filtered(lambda o: o.state == 'sale' and not o.vm_instance_id):
            for line in order.order_line:
                product = line.product_id
                # Проверяем, является ли продукт товаром для аренды ВМ
                if not product.hypervisor_server_id:
                    continue

                # Собираем конфигурацию из атрибутов варианта
                vm_config = {}
                if product.product_template_attribute_value_ids:
                    for attr_line in product.product_template_attribute_value_ids:
                        attribute_name = attr_line.attribute_id.name.lower()
                        attr_value = attr_line.product_attribute_value_id
                        
                        # ИСПРАВЛЕНИЕ: Извлекаем только цифры из строки перед преобразованием в int
                        value_name = attr_value.name or ''
                        numeric_part = re.search(r'\d+', value_name)
                        
                        if numeric_part:
                            numeric_value = int(numeric_part.group(0))
                            if 'cpu' in attribute_name or 'core' in attribute_name:
                                vm_config['cores'] = numeric_value
                            elif 'ram' in attribute_name or 'memory' in attribute_name:
                                vm_config['memory'] = numeric_value * 1024 
                            elif 'disk' in attribute_name:
                                vm_config['disk'] = numeric_value
                
                # Если конфигурация не была собрана из атрибутов, берем ее из самого продукта
                if not vm_config.get('cores'):
                    vm_config['cores'] = product.cores
                if not vm_config.get('memory'):
                    vm_config['memory'] = product.memory
                if not vm_config.get('disk'):
                    vm_config['disk'] = product.disk

                _logger.info(f"Preparing to create VM for order {order.name} with config: {vm_config}")
                
                self.env['vm_rental.machine'].create_from_order(order, line, vm_config)
                    
        return res