# vm_rental/models/vm_pricing_extensions.py
# Расширения существующих моделей для поддержки ценообразования

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


# Расширяем модель hypervisor.server
class HypervisorServer(models.Model):
    _inherit = 'hypervisor.server'

    pricing_ids = fields.One2many('hypervisor.server.pricing', 'server_id', string="Pricing Plans")
    current_pricing_id = fields.Many2one('hypervisor.server.pricing', string="Current Pricing",
                                         compute='_compute_current_pricing')

    @api.depends('pricing_ids.active', 'pricing_ids.date_start', 'pricing_ids.date_end')
    def _compute_current_pricing(self):
        for server in self:
            pricing = self.env['hypervisor.server.pricing'].search([
                ('server_id', '=', server.id),
                ('active', '=', True),
                ('date_start', '<=', fields.Date.today()),
                '|', ('date_end', '=', False), ('date_end', '>=', fields.Date.today())
            ], order='priority', limit=1)
            server.current_pricing_id = pricing


# Расширяем модель hypervisor.storage
class HypervisorStorage(models.Model):
    _inherit = 'hypervisor.storage'

    storage_type = fields.Selection([
        ('hdd', 'HDD (SATA)'),
        ('ssd', 'SSD (SATA)'),
        ('nvme', 'NVMe SSD'),
        ('network', 'Network Storage'),
        ('backup', 'Backup Storage'),
    ], string="Storage Type", default='hdd')

    pricing_ids = fields.One2many('hypervisor.storage.pricing', 'storage_id', string="Pricing")


# Расширяем модель product.template
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    auto_price_calculation = fields.Boolean(string="Auto Calculate Price", default=False,
                                            help="Automatically calculate price based on VM resources")

    calculated_price = fields.Float(string="Calculated Price", compute='_compute_calculated_price',
                                    digits=(12, 2))
    price_breakdown = fields.Text(string="Price Breakdown", compute='_compute_calculated_price')

    @api.depends('cores', 'memory', 'disk', 'hypervisor_server_id', 'hypervisor_storage_id')
    def _compute_calculated_price(self):
        for product in self:
            if not product.hypervisor_server_id or not product.auto_price_calculation:
                product.calculated_price = 0
                product.price_breakdown = ""
                continue

            pricing_info = self._calculate_vm_price_with_traits(product)
            product.calculated_price = pricing_info['monthly_price']
            product.price_breakdown = pricing_info['breakdown']

    def _calculate_vm_price_with_traits(self, product):
        """Расчет цены VM с использованием traits и новой системы ценообразования"""
        # Получаем текущие цены для сервера
        server_pricing = self.env['hypervisor.server.pricing'].search([
            ('server_id', '=', product.hypervisor_server_id.id),
            ('active', '=', True),
            ('date_start', '<=', fields.Date.today()),
            '|', ('date_end', '=', False), ('date_end', '>=', fields.Date.today())
        ], order='priority', limit=1)

        if not server_pricing:
            return {'monthly_price': 0, 'breakdown': 'No pricing found for server'}

        # Базовые расчеты
        memory_gb = product.memory / 1024.0
        cpu_cost = product.cores * server_pricing.price_per_core
        ram_cost = memory_gb * server_pricing.price_per_gb_ram

        # Стоимость хранилища
        disk_cost = product.disk * server_pricing.price_per_gb_disk
        if product.hypervisor_storage_id:
            storage_pricing = self.env['hypervisor.storage.pricing'].search([
                ('server_pricing_id', '=', server_pricing.id),
                ('storage_id', '=', product.hypervisor_storage_id.id)
            ], limit=1)
            if storage_pricing:
                disk_cost = product.disk * storage_pricing.price_per_gb * storage_pricing.performance_multiplier

        # Доплата за OS (по умолчанию Linux)
        base_cost = cpu_cost + ram_cost + disk_cost
        os_multiplier = 1.0  # По умолчанию Linux
        # Если в названии продукта есть "Windows", применяем множитель
        if 'windows' in product.name.lower():
            os_multiplier = server_pricing.os_multiplier
        os_surcharge = base_cost * (os_multiplier - 1.0)

        monthly_price = base_cost + os_surcharge

        # Детализация
        breakdown = f"CPU: {product.cores} × ${server_pricing.price_per_core:.2f} = ${cpu_cost:.2f}\n"
        breakdown += f"RAM: {memory_gb:.1f}GB × ${server_pricing.price_per_gb_ram:.2f} = ${ram_cost:.2f}\n"
        breakdown += f"Disk: {product.disk}GB × ${disk_cost / product.disk:.4f} = ${disk_cost:.2f}\n"
        if os_surcharge > 0:
            breakdown += f"OS License: ${os_surcharge:.2f}\n"
        breakdown += f"Total: ${monthly_price:.2f}/month"

        return {
            'monthly_price': monthly_price,
            'breakdown': breakdown
        }

    @api.onchange('auto_price_calculation')
    def _onchange_auto_price_calculation(self):
        """Автоматически устанавливает цену при включении авто-расчета"""
        if self.auto_price_calculation and self.calculated_price > 0:
            self.list_price = self.calculated_price

    def action_update_price_from_calculation(self):
        """Обновляет цену продажи из расчета"""
        for product in self:
            if product.calculated_price > 0:
                product.list_price = product.calculated_price
                product.message_post(
                    body=_("Product price updated from calculation: $%.2f/month") % product.calculated_price
                )


# Расширяем VmResourceTrait новыми статическими методами
def calculate_vm_price_extended(cores, memory_mb, disk_gb, server_id, storage_id=None, os_type='linux', env=None):
    """
    НОВЫЙ статический метод для VmResourceTrait
    Расчет цены VM с учетом конфигурации сервера
    """
    if not env:
        return {'monthly_price': 0, 'breakdown': 'Environment not provided'}

    # Получаем текущие цены для сервера
    server_pricing = env['hypervisor.server.pricing'].search([
        ('server_id', '=', server_id),
        ('active', '=', True),
        ('date_start', '<=', fields.Date.today()),
        '|', ('date_end', '=', False), ('date_end', '>=', fields.Date.today())
    ], order='priority', limit=1)

    if not server_pricing:
        return {'monthly_price': 0, 'breakdown': 'No pricing found for server'}

    # Базовые расчеты
    memory_gb = memory_mb / 1024.0
    cpu_cost = cores * server_pricing.price_per_core
    ram_cost = memory_gb * server_pricing.price_per_gb_ram

    # Стоимость хранилища
    disk_cost = disk_gb * server_pricing.price_per_gb_disk
    if storage_id:
        storage_pricing = env['hypervisor.storage.pricing'].search([
            ('server_pricing_id', '=', server_pricing.id),
            ('storage_id', '=', storage_id)
        ], limit=1)
        if storage_pricing:
            disk_cost = disk_gb * storage_pricing.price_per_gb * storage_pricing.performance_multiplier

    # Доплата за OS
    base_cost = cpu_cost + ram_cost + disk_cost
    os_multiplier = server_pricing.os_multiplier if os_type == 'windows' else 1.0
    os_surcharge = base_cost * (os_multiplier - 1.0)

    monthly_price = base_cost + os_surcharge

    # Детализация
    breakdown = f"CPU: {cores} × ${server_pricing.price_per_core:.2f} = ${cpu_cost:.2f}\n"
    breakdown += f"RAM: {memory_gb:.1f}GB × ${server_pricing.price_per_gb_ram:.2f} = ${ram_cost:.2f}\n"
    breakdown += f"Disk: {disk_gb}GB × ${disk_cost / disk_gb:.4f} = ${disk_cost:.2f}\n"
    if os_surcharge > 0:
        breakdown += f"OS License: ${os_surcharge:.2f}\n"
    breakdown += f"Total: ${monthly_price:.2f}/month"

    return {
        'monthly_price': monthly_price,
        'breakdown': breakdown
    }


def get_server_pricing_info(server_id, env):
    """
    НОВЫЙ статический метод для VmResourceTrait
    Получение информации о ценах для сервера
    """
    if not env:
        return {}

    server_pricing = env['hypervisor.server.pricing'].search([
        ('server_id', '=', server_id),
        ('active', '=', True),
        ('date_start', '<=', fields.Date.today()),
        '|', ('date_end', '=', False), ('date_end', '>=', fields.Date.today())
    ], order='priority', limit=1)

    if not server_pricing:
        return {}

    return {
        'name': server_pricing.name,
        'price_per_core': server_pricing.price_per_core,
        'price_per_gb_ram': server_pricing.price_per_gb_ram,
        'price_per_gb_disk': server_pricing.price_per_gb_disk,
        'os_multiplier': server_pricing.os_multiplier,
        'bulk_discount_threshold': server_pricing.bulk_discount_threshold,
        'bulk_discount_percent': server_pricing.bulk_discount_percent,
    }


# Добавляем новые методы к существующему VmResourceTrait
# Это нужно сделать после импорта оригинального VmResourceTrait
try:
    from .vm_traits import VmResourceTrait
except ImportError:
    VmResourceTrait = None

# Расширяем класс VmResourceTrait новыми методами
VmResourceTrait.calculate_vm_price = staticmethod(calculate_vm_price_extended)
VmResourceTrait.get_server_pricing_info = staticmethod(get_server_pricing_info)