# ДОБАВИТЬ В КОНЕЦ models/__init__.py:
# from . import vm_config_wizard  # убрать эту строку из __init__.py в wizards
# from . import vm_bulk_operations_wizard  # убрать эту строку из __init__.py в wizards

# =============================================================================
# СОЗДАТЬ НОВЫЙ ФАЙЛ: models/vm_wizards.py
# =============================================================================
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from .vm_traits import VmResourceTrait, VmOperationTrait


class VmConfigWizard(models.TransientModel):
    """Визард для быстрой настройки VM с использованием traits"""
    _name = 'vm.config.wizard'
    _description = 'VM Configuration Wizard'

    config_type = fields.Selection([
        ('predefined', 'Predefined Configuration'),
        ('recommended', 'OS-based Recommendation'),
        ('custom', 'Custom Configuration'),
    ], string="Configuration Type", required=True, default='predefined')

    predefined_config = fields.Selection([
        ('nano', 'Nano (1 CPU, 512MB, 5GB)'),
        ('micro', 'Micro (1 CPU, 1GB, 10GB)'),
        ('small', 'Small (2 CPU, 2GB, 20GB)'),
        ('medium', 'Medium (4 CPU, 4GB, 50GB)'),
        ('large', 'Large (8 CPU, 8GB, 100GB)'),
        ('xlarge', 'XLarge (16 CPU, 16GB, 200GB)'),
    ], string="Predefined Configuration")

    os_type = fields.Selection([
        ('ubuntu', 'Ubuntu'),
        ('debian', 'Debian'),
        ('centos', 'CentOS'),
        ('windows', 'Windows'),
        ('docker', 'Docker'),
    ], string="Operating System")

    # Custom configuration fields
    cores = fields.Integer(string="CPU Cores", default=1)
    memory = fields.Integer(string="Memory (MiB)", default=1024)
    disk = fields.Integer(string="Disk (GiB)", default=10)

    # Preview fields
    resource_summary = fields.Char(string="Resource Summary", compute='_compute_preview_fields')
    resource_category = fields.Char(string="Category", compute='_compute_preview_fields')
    estimated_boot_time = fields.Integer(string="Est. Boot Time (sec)", compute='_compute_preview_fields')
    estimated_price = fields.Float(string="Estimated Price", compute='_compute_preview_fields')

    @api.depends('config_type', 'predefined_config', 'os_type', 'cores', 'memory', 'disk')
    def _compute_preview_fields(self):
        """Вычисляет preview поля используя traits"""
        for wizard in self:
            cores, memory, disk = wizard._get_final_config()

            wizard.resource_summary = VmResourceTrait.get_resource_summary(cores, memory, disk, detailed=True)
            wizard.resource_category = VmResourceTrait.get_resource_category(cores, memory, disk)

            os_type = wizard.os_type or 'linux'
            wizard.estimated_boot_time = VmOperationTrait.estimate_boot_time(cores, memory, disk, os_type)
            wizard.estimated_price = VmResourceTrait.calculate_price_multiplier(cores, memory, disk) * 10

    def _get_final_config(self):
        """Возвращает финальную конфигурацию в зависимости от типа"""
        self.ensure_one()

        if self.config_type == 'predefined' and self.predefined_config:
            configs = VmResourceTrait.get_predefined_configs()
            config = configs.get(self.predefined_config, VmResourceTrait.get_default_config())
            return config['cores'], config['memory'], config['disk']

        elif self.config_type == 'recommended' and self.os_type:
            config = VmOperationTrait.get_recommended_specs_for_os(self.os_type)
            return config['cores'], config['memory'], config['disk']

        else:  # custom
            return self.cores, self.memory, self.disk

    def apply_configuration(self):
        """Применяет конфигурацию к записи"""
        self.ensure_one()

        cores, memory, disk = self._get_final_config()

        # Валидация через traits
        try:
            VmResourceTrait.validate_resources(cores, memory, disk, self.env)
        except Exception as e:
            raise UserError(str(e))

        # Получаем активную запись из контекста
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')

        if active_model and active_id:
            record = self.env[active_model].browse(active_id)
            record.write({
                'cores': cores,
                'memory': memory,
                'disk': disk,
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('VM configuration applied successfully!'),
                    'type': 'success',
                }
            }

        return {'type': 'ir.actions.act_window_close'}


class VmBulkOperationsWizard(models.TransientModel):
    """Визард для массовых операций с VM"""
    _name = 'vm.bulk.operations.wizard'
    _description = 'VM Bulk Operations Wizard'

    operation_type = fields.Selection([
        ('normalize_resources', 'Normalize Resources'),
        ('apply_config', 'Apply Configuration'),
        ('change_state', 'Change State'),
        ('extend_subscription', 'Extend Subscription'),
    ], string="Operation", required=True)

    # Для apply_config
    target_category = fields.Selection([
        ('nano', 'Nano'),
        ('micro', 'Micro'),
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
        ('xlarge', 'XLarge'),
    ], string="Target Configuration")

    # Для change_state
    target_state = fields.Selection([
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('stopped', 'Stopped'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
    ], string="Target State")

    # Для extend_subscription
    extend_months = fields.Integer(string="Extend by Months", default=1)

    # Информация о выбранных VM
    vm_ids = fields.Many2many('vm_rental.machine', string="Selected VMs")
    vm_count = fields.Integer(string="VM Count", compute='_compute_vm_count')

    @api.depends('vm_ids')
    def _compute_vm_count(self):
        for wizard in self:
            wizard.vm_count = len(wizard.vm_ids)

    @api.model
    def default_get(self, fields_list):
        """Получаем выбранные VM из контекста"""
        res = super().default_get(fields_list)

        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            res['vm_ids'] = [(6, 0, active_ids)]

        return res

    def execute_operation(self):
        """Выполняет выбранную операцию"""
        self.ensure_one()

        if not self.vm_ids:
            raise UserError(_("No VMs selected for the operation"))

        success_count = 0
        error_count = 0
        messages = []

        for vm in self.vm_ids:
            try:
                if self.operation_type == 'normalize_resources':
                    self._normalize_vm_resources(vm)
                elif self.operation_type == 'apply_config':
                    self._apply_config_to_vm(vm)
                elif self.operation_type == 'change_state':
                    self._change_vm_state(vm)
                elif self.operation_type == 'extend_subscription':
                    self._extend_vm_subscription(vm)

                success_count += 1

            except Exception as e:
                error_count += 1
                messages.append(f"VM {vm.name}: {str(e)}")

        # Показываем результат
        if error_count == 0:
            message = _("Operation completed successfully for %d VMs") % success_count
            message_type = 'success'
        else:
            message = _("Operation completed with %d successes and %d errors") % (success_count, error_count)
            if messages:
                message += "\n\nErrors:\n" + "\n".join(messages[:5])
            message_type = 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk Operation Result'),
                'message': message,
                'type': message_type,
                'sticky': True,
            }
        }

    def _normalize_vm_resources(self, vm):
        """Нормализует ресурсы VM"""
        if vm.state == 'pending':
            vm.normalize_vm_resources()
        else:
            raise UserError(_("Can only normalize resources for pending VMs"))

    def _apply_config_to_vm(self, vm):
        """Применяет конфигурацию к VM"""
        if vm.state != 'pending':
            raise UserError(_("Can only change configuration for pending VMs"))

        if not self.target_category:
            raise UserError(_("Target configuration not specified"))

        configs = VmResourceTrait.get_predefined_configs()
        config = configs[self.target_category]
        vm.write(config)

    def _change_vm_state(self, vm):
        """Изменяет состояние VM"""
        if not self.target_state:
            raise UserError(_("Target state not specified"))

        vm.write({'state': self.target_state})

    def _extend_vm_subscription(self, vm):
        """Продлевает подписку VM"""
        if not self.extend_months or self.extend_months <= 0:
            raise UserError(_("Invalid extension period"))

        vm.extend_period(months=self.extend_months)