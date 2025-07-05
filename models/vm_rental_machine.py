from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import ormcache
from dateutil.relativedelta import relativedelta
from functools import wraps
from .vm_traits import VmResourceTrait, VmOperationTrait
import logging, uuid, time

_logger = logging.getLogger(__name__)


class VmInstance(models.Model):
    """Virtual Machine Instance с использованием VM Traits"""
    _name = 'vm_rental.machine'
    _description = 'Virtual Machine Instance'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # === Fields Definition ===
    name = fields.Char(string="VM Name", required=True, tracking=True)

    # Поля ресурсов VM (используем traits для валидации и операций)
    cores = fields.Integer(
        string="CPU Cores",
        default=lambda self: VmResourceTrait.DEFAULT_CORES,
        required=True,
        help="Number of CPU cores for the virtual machine"
    )
    memory = fields.Integer(
        string="Memory (MiB)",
        default=lambda self: VmResourceTrait.DEFAULT_MEMORY,
        required=True,
        help="Amount of RAM in MiB (Mebibytes)"
    )
    disk = fields.Integer(
        string="Disk (GiB)",
        default=lambda self: VmResourceTrait.DEFAULT_DISK,
        required=True,
        help="Disk size in GiB (Gibibytes)"
    )

    # Остальные поля VM (без изменений)
    hypervisor_vm_ref = fields.Char(string="Hypervisor VM Reference", readonly=True, copy=False, index=True)
    hypervisor_node_name = fields.Char(string="Node/Cluster Name", readonly=True, copy=False)

    state = fields.Selection([
        ('pending', 'Draft'),
        ('active', 'Active'),
        ('stopped', 'Stopped'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
        ('archived', 'Archived'),
        ('failed', 'Failed')
    ], string="State", default='pending', readonly=True, copy=False, tracking=True, index=True)

    start_date = fields.Date(string="Start Date", readonly=True, copy=False)
    end_date = fields.Date(string="End Date", readonly=True, tracking=True, copy=False, index=True)
    partner_id = fields.Many2one('res.partner', string="Customer", required=True, tracking=True, index=True)

    # Конфигурация гипервизора
    hypervisor_server_id = fields.Many2one('hypervisor.server', string="Hypervisor Server", tracking=True, index=True)
    hypervisor_node_id = fields.Many2one('hypervisor.node', string="Node/Cluster")
    hypervisor_storage_id = fields.Many2one('hypervisor.storage', string="Storage/Datastore")
    hypervisor_template_id = fields.Many2one('hypervisor.template', string="Template")

    is_trial = fields.Boolean(string="Is Trial Period", readonly=True, default=False)

    # Связанные записи
    sale_order_ids = fields.One2many('sale.order', 'vm_instance_id', string="Sale Orders")
    snapshot_ids = fields.One2many('vm.snapshot', 'vm_instance_id', string="Snapshots")
    config_backup_ids = fields.One2many('vm_rental.config_backup', 'vm_id', string="Configuration Backups")

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Currency")
    total_amount = fields.Monetary(string="Total Paid", compute="_compute_total_amount", store=True)
    user_id = fields.Many2one('res.users', string="User", compute='_compute_user_id', store=True, readonly=True)

    # Computed поля с использованием traits
    vm_resource_summary = fields.Char(string="Resource Summary", compute='_compute_vm_resource_summary', store=True)
    vm_resource_category = fields.Char(string="Resource Category", compute='_compute_vm_resource_category', store=True)
    vm_estimated_boot_time = fields.Integer(string="Estimated Boot Time (sec)",
                                            compute='_compute_vm_estimated_boot_time')

    @api.depends('cores', 'memory', 'disk')
    def _compute_vm_resource_summary(self):
        """Использует trait для создания сводки ресурсов"""
        for vm in self:
            vm.vm_resource_summary = VmResourceTrait.get_resource_summary(
                vm.cores, vm.memory, vm.disk, detailed=True
            )

    @api.depends('cores', 'memory', 'disk')
    def _compute_vm_resource_category(self):
        """Использует trait для определения категории"""
        for vm in self:
            vm.vm_resource_category = VmResourceTrait.get_resource_category(
                vm.cores, vm.memory, vm.disk
            )

    @api.depends('cores', 'memory', 'disk', 'hypervisor_template_id')
    def _compute_vm_estimated_boot_time(self):
        """Использует trait для оценки времени загрузки"""
        for vm in self:
            os_type = 'linux'  # По умолчанию
            if vm.hypervisor_template_id and 'windows' in vm.hypervisor_template_id.name.lower():
                os_type = 'windows'

            vm.vm_estimated_boot_time = VmOperationTrait.estimate_boot_time(
                vm.cores, vm.memory, vm.disk, os_type
            )

    @api.constrains('cores', 'memory', 'disk')
    def _check_vm_resources(self):
        """Использует trait для валидации ресурсов VM"""
        for vm in self:
            VmResourceTrait.validate_resources(vm.cores, vm.memory, vm.disk, self.env)

    def get_vm_resource_summary(self):
        """Публичный метод для получения сводки ресурсов"""
        self.ensure_one()
        return VmResourceTrait.get_resource_summary(self.cores, self.memory, self.disk)

    @api.depends('partner_id', 'partner_id.user_ids')
    def _compute_user_id(self):
        for vm in self:
            if vm.partner_id and vm.partner_id.user_ids:
                vm.user_id = vm.partner_id.user_ids[0].id
            else:
                vm.user_id = False

    @api.onchange('hypervisor_server_id')
    def _onchange_hypervisor_server(self):
        """Resets related fields when the server is changed."""
        self.hypervisor_node_id = False
        self.hypervisor_storage_id = False
        self.hypervisor_template_id = False

    @api.depends('sale_order_ids.state', 'sale_order_ids.amount_total')
    def _compute_total_amount(self):
        """Computes the total amount paid across all confirmed orders."""
        for rec in self:
            paid_orders = rec.sale_order_ids.filtered(lambda o: o.state in ['sale', 'done'])
            rec.total_amount = sum(paid_orders.mapped('amount_total'))

    def _get_hypervisor_service(self):
        """Возвращает правильный экземпляр сервиса (Proxmox или VMware)."""
        self.ensure_one()
        if not self.hypervisor_server_id:
            raise UserError(_("Hypervisor server is not configured for this VM."))
        return self.hypervisor_server_id._get_service_manager()

    # === Computed Fields для кнопок ===

    snapshot_count = fields.Integer(string="Snapshot Count", compute='_compute_snapshot_count')
    sale_order_count = fields.Integer(string="Sale Order Count", compute='_compute_sale_order_count')

    @api.depends('snapshot_ids')
    def _compute_snapshot_count(self):
        """Подсчитывает количество снапшотов"""
        for vm in self:
            vm.snapshot_count = len(vm.snapshot_ids)

    @api.depends('sale_order_ids')
    def _compute_sale_order_count(self):
        """Подсчитывает количество заказов"""
        for vm in self:
            vm.sale_order_count = len(vm.sale_order_ids)

    # === Методы для быстрых кнопок конфигурации ===

    def set_nano_config(self):
        """Устанавливает nano конфигурацию"""
        self.ensure_one()
        config = VmResourceTrait.get_predefined_configs()['nano']
        self.write(config)
        return True

    def set_micro_config(self):
        """Устанавливает micro конфигурацию"""
        self.ensure_one()
        config = VmResourceTrait.get_predefined_configs()['micro']
        self.write(config)
        return True

    def set_small_config(self):
        """Устанавливает small конфигурацию"""
        self.ensure_one()
        config = VmResourceTrait.get_predefined_configs()['small']
        self.write(config)
        return True

    def set_medium_config(self):
        """Устанавливает medium конфигурацию"""
        self.ensure_one()
        config = VmResourceTrait.get_predefined_configs()['medium']
        self.write(config)
        return True

    def set_large_config(self):
        """Устанавливает large конфигурацию"""
        self.ensure_one()
        config = VmResourceTrait.get_predefined_configs()['large']
        self.write(config)
        return True

    # === Методы для действий из кнопок ===

    def action_view_snapshots(self):
        """Открывает список снапшотов VM"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Snapshots for {self.name}',
            'res_model': 'vm.snapshot',
            'view_mode': 'tree,form',
            'domain': [('vm_instance_id', '=', self.id)],
            'context': {
                'default_vm_instance_id': self.id,
                'search_default_vm_instance_id': self.id,
            },
            'target': 'current',
        }

    def action_view_sale_orders(self):
        """Открывает список заказов VM"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Sale Orders for {self.name}',
            'res_model': 'sale.order',
            'view_mode': 'tree,form',
            'domain': [('vm_instance_id', '=', self.id)],
            'context': {
                'default_vm_instance_id': self.id,
                'search_default_vm_instance_id': self.id,
            },
            'target': 'current',
        }

    # === Улучшенный метод нормализации ===

    def normalize_vm_resources(self):
        """
        Нормализует ресурсы VM к стандартным значениям используя traits
        Переопределяем для показа уведомления
        """
        self.ensure_one()
        old_config = f"{self.cores}C/{self.memory}M/{self.disk}G"
        normalized = VmResourceTrait.normalize_resources(self.cores, self.memory, self.disk)

        if (normalized['cores'] != self.cores or
                normalized['memory'] != self.memory or
                normalized['disk'] != self.disk):

            self.write(normalized)
            new_config = f"{normalized['cores']}C/{normalized['memory']}M/{normalized['disk']}G"

            self.message_post(
                body=_("VM resources normalized from %s to %s") % (old_config, new_config),
                message_type='notification'
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Resources Normalized'),
                    'message': _('VM resources updated from %s to %s') % (old_config, new_config),
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Changes'),
                    'message': _('VM resources are already at standard values'),
                    'type': 'info',
                    'sticky': False,
                }
            }

    # === Методы для расширенной функциональности ===

    def get_recommended_upgrades(self):
        """Возвращает рекомендации по улучшению конфигурации"""
        self.ensure_one()
        current_category = self.vm_resource_category
        configs = VmResourceTrait.get_predefined_configs()

        # Находим следующий уровень
        categories = ['nano', 'micro', 'small', 'medium', 'large', 'xlarge']
        try:
            current_index = categories.index(current_category)
            if current_index < len(categories) - 1:
                next_category = categories[current_index + 1]
                return {
                    'current': current_category,
                    'recommended': next_category,
                    'config': configs[next_category]
                }
        except ValueError:
            pass

        return None

    def apply_upgrade_recommendation(self):
        """Применяет рекомендованное улучшение"""
        self.ensure_one()
        upgrade = self.get_recommended_upgrades()

        if upgrade and self.state == 'pending':
            self.write(upgrade['config'])
            self.message_post(
                body=_("VM upgraded from %s to %s configuration") %
                     (upgrade['current'], upgrade['recommended'])
            )
            return True
        return False

    def get_performance_metrics(self):
        """Возвращает метрики производительности на основе конфигурации"""
        self.ensure_one()

        # Простые метрики на основе ресурсов
        cpu_score = self.cores * 100
        memory_score = self.memory / 1024 * 100  # GB * 100
        disk_score = self.disk * 10

        total_score = (cpu_score + memory_score + disk_score) / 3

        return {
            'cpu_score': cpu_score,
            'memory_score': memory_score,
            'disk_score': disk_score,
            'total_score': total_score,
            'category': self.vm_resource_category,
            'boot_time': self.vm_estimated_boot_time,
        }

    # === Дополнительные constrains ===

    @api.constrains('end_date', 'start_date')
    def _check_dates(self):
        """Проверка корректности дат"""
        for vm in self:
            if vm.start_date and vm.end_date and vm.end_date < vm.start_date:
                raise ValidationError(_("End date cannot be before start date"))

    @api.constrains('hypervisor_server_id', 'hypervisor_node_id', 'hypervisor_storage_id', 'hypervisor_template_id')
    def _check_hypervisor_consistency(self):
        """Проверка согласованности настроек гипервизора"""
        for vm in self:
            if vm.state == 'pending' and vm.hypervisor_server_id:
                # Проверяем, что нода принадлежит выбранному серверу
                if vm.hypervisor_node_id and vm.hypervisor_node_id.server_id != vm.hypervisor_server_id:
                    raise ValidationError(_("Selected node does not belong to the chosen hypervisor server"))

                # Проверяем, что хранилище принадлежит выбранному серверу
                if vm.hypervisor_storage_id and vm.hypervisor_storage_id.server_id != vm.hypervisor_server_id:
                    raise ValidationError(_("Selected storage does not belong to the chosen hypervisor server"))

                # Проверяем, что шаблон принадлежит выбранному серверу
                if vm.hypervisor_template_id and vm.hypervisor_template_id.server_id != vm.hypervisor_server_id:
                    raise ValidationError(_("Selected template does not belong to the chosen hypervisor server"))

    # === Методы для автоматизации ===

    @api.model
    def auto_provision_pending_vms(self):
        """Автоматически создает pending VMs (для cron)"""
        pending_vms = self.search([
            ('state', '=', 'pending'),
            ('hypervisor_server_id', '!=', False),
            ('hypervisor_node_id', '!=', False),
            ('hypervisor_storage_id', '!=', False),
            ('hypervisor_template_id', '!=', False),
        ])

        success_count = 0
        error_count = 0

        for vm in pending_vms:
            try:
                vm.action_provision_vm()
                success_count += 1
            except Exception as e:
                _logger.error(f"Auto-provision failed for VM {vm.name}: {e}")
                vm.message_post(
                    body=_("Auto-provision failed: %s") % str(e),
                    message_type='notification'
                )
                error_count += 1

        if success_count or error_count:
            _logger.info(f"Auto-provision completed: {success_count} success, {error_count} errors")

        return {'success': success_count, 'errors': error_count}

    @api.model
    def cleanup_terminated_vms(self, days_old=30):
        """Очищает старые terminated VMs (для cron)"""
        cutoff_date = fields.Date.today() - relativedelta(days=days_old)
        old_terminated_vms = self.search([
            ('state', '=', 'terminated'),
            ('write_date', '<', cutoff_date)
        ])

        if old_terminated_vms:
            count = len(old_terminated_vms)
            old_terminated_vms.write({'state': 'archived'})
            _logger.info(f"Archived {count} old terminated VMs")
            return count

        return 0

    # === Методы для отчетности ===

    @api.model
    def get_resource_utilization_stats(self):
        """Возвращает статистику использования ресурсов"""
        active_vms = self.search([('state', '=', 'active')])

        if not active_vms:
            return {}

        total_cores = sum(active_vms.mapped('cores'))
        total_memory = sum(active_vms.mapped('memory'))
        total_disk = sum(active_vms.mapped('disk'))

        # Группировка по категориям
        categories = {}
        for vm in active_vms:
            category = vm.vm_resource_category
            if category not in categories:
                categories[category] = {'count': 0, 'cores': 0, 'memory': 0, 'disk': 0}

            categories[category]['count'] += 1
            categories[category]['cores'] += vm.cores
            categories[category]['memory'] += vm.memory
            categories[category]['disk'] += vm.disk

        return {
            'total_vms': len(active_vms),
            'total_cores': total_cores,
            'total_memory_gb': round(total_memory / 1024, 2),
            'total_disk_gb': total_disk,
            'avg_cores': round(total_cores / len(active_vms), 2),
            'avg_memory_mb': round(total_memory / len(active_vms), 2),
            'avg_disk_gb': round(total_disk / len(active_vms), 2),
            'categories': categories,
        }

    @api.model
    def get_hypervisor_distribution(self):
        """Возвращает распределение VM по гипервизорам"""
        active_vms = self.search([('state', '=', 'active')])

        distribution = {}
        for vm in active_vms:
            server_name = vm.hypervisor_server_id.name if vm.hypervisor_server_id else 'Unknown'
            if server_name not in distribution:
                distribution[server_name] = {
                    'count': 0,
                    'cores': 0,
                    'memory': 0,
                    'disk': 0,
                    'hypervisor_type': vm.hypervisor_server_id.hypervisor_type if vm.hypervisor_server_id else 'unknown'
                }

            distribution[server_name]['count'] += 1
            distribution[server_name]['cores'] += vm.cores
            distribution[server_name]['memory'] += vm.memory
            distribution[server_name]['disk'] += vm.disk

        return distribution

    # === Интеграция с traits для продуктов ===

    def create_product_from_vm(self):
        """Создает продукт на основе текущей конфигурации VM"""
        self.ensure_one()

        product_name = f"VM {self.vm_resource_category.capitalize()} - {self.get_vm_resource_summary()}"

        # Рассчитываем цену на основе ресурсов
        base_price = 10  # базовая цена
        price_multiplier = VmResourceTrait.calculate_price_multiplier(
            self.cores, self.memory, self.disk
        )
        calculated_price = base_price * price_multiplier

        product_vals = {
            'name': product_name,
            'type': 'service',
            'list_price': calculated_price,
            'cores': self.cores,
            'memory': self.memory,
            'disk': self.disk,
            'hypervisor_server_id': self.hypervisor_server_id.id,
            'hypervisor_node_id': self.hypervisor_node_id.id,
            'hypervisor_storage_id': self.hypervisor_storage_id.id,
            'hypervisor_template_id': self.hypervisor_template_id.id,
        }

        product = self.env['product.template'].create(product_vals)

        self.message_post(
            body=_("Created product '%s' based on this VM configuration") % product.name,
            message_type='notification'
        )

        return {
            'type': 'ir.actions.act_window',
            'name': 'Created Product',
            'res_model': 'product.template',
            'res_id': product.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # === Методы для мониторинга состояния ===

    def check_vm_health(self):
        """Проверяет состояние VM на гипервизоре"""
        self.ensure_one()

        if not self.hypervisor_vm_ref:
            return {'status': 'no_ref', 'message': 'VM not provisioned yet'}

        try:
            service = self._get_hypervisor_service()
            # Здесь можно добавить методы для проверки состояния VM на гипервизоре
            # Например, service.get_vm_status(self.hypervisor_node_name, self.hypervisor_vm_ref)

            return {'status': 'healthy', 'message': 'VM is accessible'}

        except Exception as e:
            _logger.error(f"Health check failed for VM {self.name}: {e}")
            return {'status': 'error', 'message': str(e)}

    @api.model
    def run_health_checks(self):
        """Запускает проверку состояния всех активных VM"""
        active_vms = self.search([('state', 'in', ['active', 'stopped'])])

        results = {
            'healthy': 0,
            'unhealthy': 0,
            'unreachable': 0
        }

        for vm in active_vms:
            health = vm.check_vm_health()
            if health['status'] == 'healthy':
                results['healthy'] += 1
            elif health['status'] == 'error':
                results['unhealthy'] += 1
                vm.message_post(
                    body=_("Health check failed: %s") % health['message'],
                    message_type='notification'
                )
            else:
                results['unreachable'] += 1

        return results

    # === Утилиты для работы с конфигурациями ===

    def suggest_optimal_config_for_workload(self, workload_type):
        """Предлагает оптимальную конфигурацию для типа рабочей нагрузки"""
        self.ensure_one()

        workload_configs = {
            'web_server': {'cores': 2, 'memory': 2048, 'disk': 20},
            'database': {'cores': 4, 'memory': 8192, 'disk': 100},
            'development': {'cores': 2, 'memory': 4096, 'disk': 50},
            'testing': {'cores': 1, 'memory': 1024, 'disk': 20},
            'production': {'cores': 8, 'memory': 16384, 'disk': 200},
            'microservice': {'cores': 1, 'memory': 512, 'disk': 10},
        }

        suggested = workload_configs.get(workload_type)
        if suggested:
            # Валидируем через traits
            try:
                VmResourceTrait.validate_resources(
                    suggested['cores'], suggested['memory'], suggested['disk'], self.env
                )
                return suggested
            except ValidationError:
                # Если предложенная конфигурация превышает лимиты, нормализуем
                return VmResourceTrait.normalize_resources(
                    suggested['cores'], suggested['memory'], suggested['disk']
                )

        return VmResourceTrait.get_default_config()

    def apply_workload_config(self, workload_type):
        """Применяет конфигурацию для указанного типа рабочей нагрузки"""
        self.ensure_one()

        if self.state != 'pending':
            raise UserError(_("Can only modify configuration for pending VMs"))

        config = self.suggest_optimal_config_for_workload(workload_type)
        old_summary = self.get_vm_resource_summary()

        self.write(config)
        new_summary = self.get_vm_resource_summary()

        self.message_post(
            body=_("Applied %s workload configuration: %s → %s") %
                 (workload_type, old_summary, new_summary),
            message_type='notification'
        )

        return True

    def action_provision_vm(self):
        """Провижининг VM на гипервизоре"""
        self.ensure_one()

        if self.state != 'pending':
            raise UserError(_("Can only provision pending VMs"))

        if not all([self.hypervisor_server_id, self.hypervisor_node_id,
                    self.hypervisor_storage_id, self.hypervisor_template_id]):
            raise UserError(_("Please configure all hypervisor settings before provisioning"))

        try:
            service = self._get_hypervisor_service()

            # Получаем следующий доступный ID
            vm_id = service.get_next_vmid()
            if not vm_id:
                vm_id = str(int(time.time()))  # Fallback ID

            # Создаем VM на гипервизоре
            task_result = service.create_vm(
                node=self.hypervisor_node_id.name,
                vm_id=vm_id,
                name=self.name,
                template_vmid=self.hypervisor_template_id.vmid,
                cores=self.cores,
                memory=self.memory,
                disk=self.disk,
                storage=self.hypervisor_storage_id.name
            )

            if task_result:
                # Обновляем запись VM
                self.write({
                    'state': 'active',
                    'hypervisor_vm_ref': vm_id,
                    'hypervisor_node_name': self.hypervisor_node_id.name,
                    'start_date': fields.Date.today(),
                    'end_date': fields.Date.today() + relativedelta(months=1),
                })

                self.message_post(
                    body=_("VM successfully provisioned with ID: %s") % vm_id,
                    message_type='notification'
                )

                return True
            else:
                self.write({'state': 'failed'})
                raise UserError(_("VM provisioning failed"))

        except Exception as e:
            self.write({'state': 'failed'})
            self.message_post(
                body=_("VM provisioning failed: %s") % str(e),
                message_type='notification'
            )
            raise UserError(_("VM provisioning failed: %s") % str(e))

    def action_retry_provisioning(self):
        """Повторная попытка провижининга"""
        self.ensure_one()
        self.write({'state': 'pending'})
        return self.action_provision_vm()

    def action_terminate_vm(self):
        """Удаление VM с гипервизора"""
        self.ensure_one()

        if self.state in ['terminated', 'archived']:
            raise UserError(_("VM is already terminated"))

        try:
            if self.hypervisor_vm_ref:
                service = self._get_hypervisor_service()
                service.delete_vm(self.hypervisor_node_name, self.hypervisor_vm_ref)

            self.write({'state': 'terminated'})
            self.message_post(
                body=_("VM terminated and removed from hypervisor"),
                message_type='notification'
            )

        except Exception as e:
            _logger.error(f"Failed to terminate VM {self.name}: {e}")
            self.message_post(
                body=_("VM terminated in Odoo but may still exist on hypervisor: %s") % str(e),
                message_type='notification'
            )
            self.write({'state': 'terminated'})

    def extend_period(self, months=1):
        """Продление периода подписки"""
        self.ensure_one()

        if not self.end_date:
            self.end_date = fields.Date.today()

        new_end_date = self.end_date + relativedelta(months=months)
        self.write({'end_date': new_end_date})

        self.message_post(
            body=_("Subscription extended by %d months until %s") % (months, new_end_date),
            message_type='notification'
        )

    @api.model
    def create_from_order(self, order, order_line, vm_config):
        """Создание VM из заказа продажи"""
        product = order_line.product_id

        # Проверяем, что продукт настроен для VM
        if not product.hypervisor_server_id:
            _logger.warning(f"Product {product.name} is not configured for VM rental")
            return False

        # Создаем VM
        vm_vals = {
            'name': f"{product.name} for {order.partner_id.name}",
            'partner_id': order.partner_id.id,
            'hypervisor_server_id': product.hypervisor_server_id.id,
            'hypervisor_node_id': product.hypervisor_node_id.id if product.hypervisor_node_id else False,
            'hypervisor_storage_id': product.hypervisor_storage_id.id if product.hypervisor_storage_id else False,
            'hypervisor_template_id': product.hypervisor_template_id.id if product.hypervisor_template_id else False,
            'cores': vm_config.get('cores', 1),
            'memory': vm_config.get('memory', 1024),
            'disk': vm_config.get('disk', 10),
            'is_trial': product.has_trial_period,
            'state': 'pending',
        }

        vm = self.create(vm_vals)

        # Привязываем к заказу
        order.write({'vm_instance_id': vm.id})

        _logger.info(f"Created VM {vm.name} for order {order.name}")
        return vm

    @api.model
    def _cron_check_expiry(self):
        """CRON задача проверки истечения срока"""
        today = fields.Date.today()
        expired_vms = self.search([
            ('state', '=', 'active'),
            ('end_date', '<', today)
        ])

        for vm in expired_vms:
            try:
                service = vm._get_hypervisor_service()
                service.suspend_vm(vm.hypervisor_node_name, vm.hypervisor_vm_ref)
                vm.write({'state': 'suspended'})

                # Отправляем уведомление
                template = self.env.ref('vm_rental.mail_vm_expired', raise_if_not_found=False)
                if template:
                    template.send_mail(vm.id, force_send=True)

            except Exception as e:
                _logger.error(f"Failed to suspend expired VM {vm.name}: {e}")

    def action_linking_job(self):
        """Действие для создания задания привязки VM"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Link Existing VMs',
            'res_model': 'vm_rental.linking_job',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_hypervisor_server_id': self.env.context.get('active_id')},
        }

    def update_resources_from_hypervisor(self):
        """Обновляет ресурсы VM из конфигурации гипервизора"""
        self.ensure_one()

        if not self.hypervisor_server_id or not self.hypervisor_vm_ref:
            raise UserError(_("VM is not linked to hypervisor"))

        try:
            service = self._get_hypervisor_service()

            if self.hypervisor_server_id.hypervisor_type == 'proxmox':
                vm_config = service.get_vm_config(self.hypervisor_node_name, self.hypervisor_vm_ref)
            else:  # VMware
                vm_config = service.get_vm_config(self.hypervisor_vm_ref)

            old_summary = self.get_vm_resource_summary()

            self.write({
                'cores': vm_config['cores'],
                'memory': vm_config['memory'],
                'disk': vm_config['disk'],
            })

            new_summary = self.get_vm_resource_summary()

            self.message_post(
                body=_("VM resources updated from hypervisor: %s → %s") % (old_summary, new_summary),
                message_type='notification'
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Resources Updated'),
                    'message': _('VM resources synchronized from hypervisor: %s') % new_summary,
                    'type': 'success',
                    'sticky': False,
                }
            }

        except Exception as e:
            _logger.error(f"Failed to update resources for VM {self.name}: {e}")
            raise UserError(_("Failed to update VM resources: %s") % str(e))