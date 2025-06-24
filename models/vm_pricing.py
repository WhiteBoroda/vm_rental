# vm_rental/models/vm_pricing.py
# НОВЫЙ ФАЙЛ - только новые модели ценообразования

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HypervisorServerPricing(models.Model):
    """Ценообразование для серверов гипервизора"""
    _name = 'hypervisor.server.pricing'
    _description = 'Hypervisor Server Pricing'
    _order = 'server_id, priority'

    name = fields.Char(string="Pricing Plan Name", required=True)
    server_id = fields.Many2one('hypervisor.server', string="Hypervisor Server", required=True)

    # Базовые цены за единицу ресурсов (за месяц)
    price_per_core = fields.Float(string="Price per CPU Core/Month", default=5.0, digits=(12, 4))
    price_per_gb_ram = fields.Float(string="Price per GB RAM/Month", default=2.0, digits=(12, 4))
    price_per_gb_disk = fields.Float(string="Price per GB Disk/Month", default=0.1, digits=(12, 4))

    # Дополнительные множители
    os_multiplier = fields.Float(string="OS License Multiplier", default=1.0, digits=(12, 2),
                                 help="Multiplier for OS licensing (e.g., 1.5 for Windows)")

    # Скидки за объем
    bulk_discount_threshold = fields.Integer(string="Bulk Discount Threshold (VMs)", default=10)
    bulk_discount_percent = fields.Float(string="Bulk Discount %", default=10.0)

    # Период действия
    date_start = fields.Date(string="Valid From", default=fields.Date.today)
    date_end = fields.Date(string="Valid Until")

    # Приоритет (для выбора при конфликтах)
    priority = fields.Integer(string="Priority", default=10, help="Lower number = higher priority")

    active = fields.Boolean(string="Active", default=True)

    # Связанные цены для хранилищ
    storage_pricing_ids = fields.One2many('hypervisor.storage.pricing', 'server_pricing_id',
                                          string="Storage Pricing")

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_end and record.date_start > record.date_end:
                raise ValidationError(_("End date must be after start date"))


class HypervisorStoragePricing(models.Model):
    """Ценообразование для разных типов хранилищ"""
    _name = 'hypervisor.storage.pricing'
    _description = 'Hypervisor Storage Pricing'

    server_pricing_id = fields.Many2one('hypervisor.server.pricing', string="Server Pricing",
                                        ondelete='cascade', required=True)
    storage_id = fields.Many2one('hypervisor.storage', string="Storage", required=True)

    # Тип хранилища
    storage_type = fields.Selection([
        ('hdd', 'HDD (SATA)'),
        ('ssd', 'SSD (SATA)'),
        ('nvme', 'NVMe SSD'),
        ('network', 'Network Storage'),
        ('backup', 'Backup Storage'),
    ], string="Storage Type", required=True, default='hdd')

    # Цена за GB в месяц
    price_per_gb = fields.Float(string="Price per GB/Month", required=True, digits=(12, 4))

    # IOPS лимиты и цены
    included_iops = fields.Integer(string="Included IOPS", default=1000)
    price_per_additional_iops = fields.Float(string="Price per Additional IOPS", digits=(12, 6))

    # Множители производительности
    performance_multiplier = fields.Float(string="Performance Multiplier", default=1.0, digits=(12, 2),
                                          help="Multiplier for high-performance storage")


class VmPricingCalculator(models.TransientModel):
    """Калькулятор цен для VM"""
    _name = 'vm.pricing.calculator'
    _description = 'VM Pricing Calculator'

    # Конфигурация VM
    cores = fields.Integer(string="CPU Cores", required=True, default=1)
    memory_gb = fields.Float(string="Memory (GB)", required=True, default=1.0)
    disk_gb = fields.Integer(string="Disk (GB)", required=True, default=10)

    # Выбор инфраструктуры
    server_id = fields.Many2one('hypervisor.server', string="Hypervisor Server", required=True)
    storage_id = fields.Many2one('hypervisor.storage', string="Storage",
                                 domain="[('server_id', '=', server_id)]")

    # Дополнительные параметры
    os_type = fields.Selection([
        ('linux', 'Linux'),
        ('windows', 'Windows'),
        ('custom', 'Custom')
    ], string="Operating System", default='linux')

    vm_count = fields.Integer(string="Number of VMs", default=1, help="For bulk discount calculation")
    billing_period = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly')
    ], string="Billing Period", default='monthly')

    # Расчетные поля
    base_price = fields.Float(string="Base Price", compute='_compute_pricing', digits=(12, 2))
    storage_price = fields.Float(string="Storage Price", compute='_compute_pricing', digits=(12, 2))
    os_surcharge = fields.Float(string="OS Surcharge", compute='_compute_pricing', digits=(12, 2))
    bulk_discount = fields.Float(string="Bulk Discount", compute='_compute_pricing', digits=(12, 2))
    total_monthly = fields.Float(string="Total Monthly Price", compute='_compute_pricing', digits=(12, 2))
    total_price = fields.Float(string="Total Price", compute='_compute_pricing', digits=(12, 2))

    price_breakdown = fields.Text(string="Price Breakdown", compute='_compute_pricing')

    @api.depends('cores', 'memory_gb', 'disk_gb', 'server_id', 'storage_id',
                 'os_type', 'vm_count', 'billing_period')
    def _compute_pricing(self):
        for calc in self:
            if not calc.server_id:
                calc.base_price = calc.storage_price = calc.os_surcharge = 0
                calc.bulk_discount = calc.total_monthly = calc.total_price = 0
                calc.price_breakdown = ""
                continue

            # Получаем текущие цены для сервера
            server_pricing = self.env['hypervisor.server.pricing'].search([
                ('server_id', '=', calc.server_id.id),
                ('active', '=', True),
                ('date_start', '<=', fields.Date.today()),
                '|', ('date_end', '=', False), ('date_end', '>=', fields.Date.today())
            ], order='priority', limit=1)

            if not server_pricing:
                calc.base_price = calc.storage_price = calc.os_surcharge = 0
                calc.bulk_discount = calc.total_monthly = calc.total_price = 0
                calc.price_breakdown = "No pricing configuration found for this server"
                continue

            # Базовые расчеты
            cpu_cost = calc.cores * server_pricing.price_per_core
            ram_cost = calc.memory_gb * server_pricing.price_per_gb_ram
            calc.base_price = cpu_cost + ram_cost

            # Стоимость хранилища
            calc.storage_price = calc._calculate_storage_price(server_pricing)

            # Доплата за OS
            os_multiplier = server_pricing.os_multiplier if calc.os_type == 'windows' else 1.0
            calc.os_surcharge = calc.base_price * (os_multiplier - 1.0)

            # Скидка за объем
            calc.bulk_discount = calc._calculate_bulk_discount(server_pricing)

            # Итоговая месячная цена
            calc.total_monthly = (
                                             calc.base_price + calc.storage_price + calc.os_surcharge - calc.bulk_discount) * calc.vm_count

            # Цена с учетом периода оплаты
            period_multipliers = {'monthly': 1, 'quarterly': 3, 'yearly': 12}
            calc.total_price = calc.total_monthly * period_multipliers.get(calc.billing_period, 1)

            # Детализация расчета
            calc.price_breakdown = calc._generate_breakdown(cpu_cost, ram_cost, server_pricing, os_multiplier)

    def _calculate_storage_price(self, server_pricing):
        """Расчет стоимости хранилища"""
        if not self.storage_id:
            return self.disk_gb * server_pricing.price_per_gb_disk

        storage_pricing = self.env['hypervisor.storage.pricing'].search([
            ('server_pricing_id', '=', server_pricing.id),
            ('storage_id', '=', self.storage_id.id)
        ], limit=1)

        if storage_pricing:
            base_storage_cost = self.disk_gb * storage_pricing.price_per_gb
            return base_storage_cost * storage_pricing.performance_multiplier

        return self.disk_gb * server_pricing.price_per_gb_disk

    def _calculate_bulk_discount(self, server_pricing):
        """Расчет скидки за объем"""
        if self.vm_count >= server_pricing.bulk_discount_threshold:
            base_cost = self.base_price + self.storage_price + self.os_surcharge
            return base_cost * self.vm_count * (server_pricing.bulk_discount_percent / 100.0)
        return 0.0

    def _generate_breakdown(self, cpu_cost, ram_cost, server_pricing, os_multiplier):
        """Генерация детального расчета"""
        breakdown = []
        breakdown.append(f"CPU: {self.cores} cores × ${server_pricing.price_per_core:.2f} = ${cpu_cost:.2f}")
        breakdown.append(f"RAM: {self.memory_gb:.1f} GB × ${server_pricing.price_per_gb_ram:.2f} = ${ram_cost:.2f}")
        breakdown.append(
            f"Disk: {self.disk_gb} GB × ${self._get_disk_rate(server_pricing):.4f} = ${self.storage_price:.2f}")

        if self.os_type == 'windows':
            breakdown.append(f"Windows License: ${self.os_surcharge:.2f} (×{os_multiplier:.1f} multiplier)")

        if self.bulk_discount > 0:
            breakdown.append(f"Bulk Discount ({server_pricing.bulk_discount_percent}%): -${self.bulk_discount:.2f}")

        breakdown.append(f"Subtotal per VM: ${(self.base_price + self.storage_price + self.os_surcharge):.2f}")
        breakdown.append(f"Total for {self.vm_count} VM(s): ${self.total_monthly:.2f}/month")

        return "\n".join(breakdown)

    def _get_disk_rate(self, server_pricing):
        """Получение актуальной ставки за диск"""
        if not self.storage_id:
            return server_pricing.price_per_gb_disk

        storage_pricing = self.env['hypervisor.storage.pricing'].search([
            ('server_pricing_id', '=', server_pricing.id),
            ('storage_id', '=', self.storage_id.id)
        ], limit=1)

        return storage_pricing.price_per_gb if storage_pricing else server_pricing.price_per_gb_disk

    def action_create_product(self):
        """Создание продукта на основе расчета"""
        self.ensure_one()

        if not self.total_monthly:
            raise ValidationError(_("Cannot create product with zero price"))

        product_name = f"VM {self.cores}C/{self.memory_gb:.0f}G/{self.disk_gb}G - {self.server_id.name}"

        # Создаем продукт
        product = self.env['product.template'].create({
            'name': product_name,
            'type': 'service',
            'list_price': self.total_monthly,
            'standard_price': self.total_monthly * 0.7,  # 70% себестоимость
            'cores': self.cores,
            'memory': int(self.memory_gb * 1024),  # Конвертируем в MiB
            'disk': self.disk_gb,
            'hypervisor_server_id': self.server_id.id,
            'hypervisor_storage_id': self.storage_id.id if self.storage_id else False,
            'categ_id': self.env.ref('product.product_category_all').id,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Created Product',
            'res_model': 'product.template',
            'res_id': product.id,
            'view_mode': 'form',
            'target': 'current',
        }


class VmPricingDashboard(models.TransientModel):
    """Модель для дашборда ценообразования"""
    _name = 'vm.pricing.dashboard'
    _description = 'VM Pricing Dashboard'

    # Статистические поля
    servers_with_pricing_count = fields.Integer(string="Servers with Pricing", compute='_compute_dashboard_stats')
    total_servers_count = fields.Integer(string="Total Servers", compute='_compute_dashboard_stats')
    avg_core_price = fields.Float(string="Average Core Price", compute='_compute_dashboard_stats', digits=(12, 2))
    avg_ram_price = fields.Float(string="Average RAM Price", compute='_compute_dashboard_stats', digits=(12, 2))
    avg_disk_price = fields.Float(string="Average Disk Price", compute='_compute_dashboard_stats', digits=(12, 4))

    # Информационные поля
    active_pricing_plans = fields.Text(string="Active Plans", compute='_compute_dashboard_stats')
    server_coverage_info = fields.Text(string="Server Coverage", compute='_compute_dashboard_stats')

    @api.depends()
    def _compute_dashboard_stats(self):
        """Вычисляет статистику для дашборда"""
        for record in self:
            # Получаем активные планы ценообразования
            active_pricing = self.env['hypervisor.server.pricing'].search([
                ('active', '=', True),
                ('date_start', '<=', fields.Date.today()),
                '|', ('date_end', '=', False), ('date_end', '>=', fields.Date.today())
            ])

            # Подсчет серверов с ценообразованием
            servers_with_pricing = set(active_pricing.mapped('server_id.id'))
            record.servers_with_pricing_count = len(servers_with_pricing)

            # Общее количество серверов
            record.total_servers_count = self.env['hypervisor.server'].search_count([])

            if active_pricing:
                # Средние цены
                record.avg_core_price = sum(active_pricing.mapped('price_per_core')) / len(active_pricing)
                record.avg_ram_price = sum(active_pricing.mapped('price_per_gb_ram')) / len(active_pricing)
                record.avg_disk_price = sum(active_pricing.mapped('price_per_gb_disk')) / len(active_pricing)

                # Информация об активных планах
                plans_info = []
                for plan in active_pricing:
                    plans_info.append(f"• {plan.name} ({plan.server_id.name})")
                record.active_pricing_plans = "\n".join(plans_info[:10])  # Показываем первые 10
                if len(active_pricing) > 10:
                    record.active_pricing_plans += f"\n... и еще {len(active_pricing) - 10} планов"
            else:
                record.avg_core_price = 0
                record.avg_ram_price = 0
                record.avg_disk_price = 0
                record.active_pricing_plans = "Нет активных планов ценообразования"

            # Информация о покрытии серверов
            coverage_percentage = (
                        record.servers_with_pricing_count / record.total_servers_count * 100) if record.total_servers_count > 0 else 0
            record.server_coverage_info = f"""Серверов с ценообразованием: {record.servers_with_pricing_count} из {record.total_servers_count}
Покрытие: {coverage_percentage:.1f}%

{'✓ Отличное покрытие' if coverage_percentage >= 80 else
            '⚠ Среднее покрытие' if coverage_percentage >= 50 else
            '❌ Низкое покрытие - настройте ценообразование для большего количества серверов'}"""

    def action_refresh_dashboard(self):
        """Обновляет статистику дашборда"""
        self._compute_dashboard_stats()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Dashboard Refreshed',
                'message': 'Pricing dashboard statistics have been updated',
                'type': 'success',
            }
        }

    @api.model
    def get_dashboard_data(self):
        """API метод для получения данных дашборда"""
        dashboard = self.create({})
        return {
            'servers_with_pricing': dashboard.servers_with_pricing_count,
            'total_servers': dashboard.total_servers_count,
            'avg_core_price': dashboard.avg_core_price,
            'avg_ram_price': dashboard.avg_ram_price,
            'avg_disk_price': dashboard.avg_disk_price,
            'coverage_percentage': (
                        dashboard.servers_with_pricing_count / dashboard.total_servers_count * 100) if dashboard.total_servers_count > 0 else 0
        }