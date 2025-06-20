from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..models.vm_traits import VmResourceTrait


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

    # Для normalize_resources
    # (не требует дополнительных параметров)

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
                message += "\n\nErrors:\n" + "\n".join(messages[:5])  # Показываем первые 5 ошибок
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

        # Простое изменение состояния (без вызова гипервизора)
        vm.write({'state': self.target_state})

    def _extend_vm_subscription(self, vm):
        """Продлевает подписку VM"""
        if not self.extend_months or self.extend_months <= 0:
            raise UserError(_("Invalid extension period"))

        vm.extend_period(months=self.extend_months)