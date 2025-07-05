# models/vm_rental_config.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class VmRentalConfig(models.Model):
    """Конфигурация VM Rental модуля"""
    _name = 'vm.rental.config'
    _description = 'VM Rental Configuration'
    _rec_name = 'name'

    name = fields.Char(
        string="Configuration Name",
        required=True,
        default="VM Rental Settings"
    )

    # Основные настройки
    default_trial_days = fields.Integer(
        string="Default Trial Period (Days)",
        default=7,
        help="Default number of days for trial periods"
    )

    auto_suspend_expired = fields.Boolean(
        string="Auto-suspend Expired VMs",
        default=True,
        help="Automatically suspend VMs when subscription expires"
    )

    # Лимиты ресурсов
    max_cores_per_vm = fields.Integer(
        string="Maximum CPU Cores per VM",
        default=64,
        help="Maximum number of CPU cores per VM"
    )

    max_memory_per_vm = fields.Integer(
        string="Maximum Memory per VM (MiB)",
        default=131072,  # 128GB
        help="Maximum memory per VM in MiB"
    )

    max_disk_per_vm = fields.Integer(
        string="Maximum Disk per VM (GiB)",
        default=10240,  # 10TB
        help="Maximum disk size per VM in GiB"
    )

    # Backup настройки
    enable_auto_backup = fields.Boolean(
        string="Enable Auto Backup",
        default=False,
        help="Enable automatic configuration backups"
    )

    backup_retention_days = fields.Integer(
        string="Backup Retention (Days)",
        default=30,
        help="How long to keep backup files"
    )

    # Уведомления
    send_notifications = fields.Boolean(
        string="Send Email Notifications",
        default=True,
        help="Send email notifications for VM events"
    )

    notification_template_id = fields.Many2one(
        'mail.template',
        string="Notification Template",
        help="Email template for notifications"
    )

    # Аудит
    enable_audit_logging = fields.Boolean(
        string="Enable Audit Logging",
        default=True,
        help="Log all VM operations for audit purposes"
    )

    audit_retention_days = fields.Integer(
        string="Audit Log Retention (Days)",
        default=365,
        help="How long to keep audit logs"
    )

    # Системные настройки
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Whether this configuration is active"
    )

    create_date = fields.Datetime(
        string="Created",
        readonly=True
    )

    write_date = fields.Datetime(
        string="Last Modified",
        readonly=True
    )

    @api.constrains('default_trial_days')
    def _check_trial_days(self):
        for record in self:
            if record.default_trial_days < 0:
                raise ValidationError(_("Trial days cannot be negative"))
            if record.default_trial_days > 365:
                raise ValidationError(_("Trial days cannot exceed 365 days"))

    @api.constrains('max_cores_per_vm', 'max_memory_per_vm', 'max_disk_per_vm')
    def _check_resource_limits(self):
        for record in self:
            if record.max_cores_per_vm < 1:
                raise ValidationError(_("Maximum cores must be at least 1"))
            if record.max_memory_per_vm < 512:
                raise ValidationError(_("Maximum memory must be at least 512 MiB"))
            if record.max_disk_per_vm < 1:
                raise ValidationError(_("Maximum disk must be at least 1 GiB"))

    @api.model
    def get_config(self):
        """Получает активную конфигурацию"""
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            # Создаем конфигурацию по умолчанию
            config = self.create({
                'name': 'Default VM Rental Configuration',
                'active': True
            })
            _logger.info("Created default VM Rental configuration")
        return config

    @api.model
    def set_config_value(self, field_name, value):
        """Устанавливает значение конфигурации"""
        config = self.get_config()
        if hasattr(config, field_name):
            config.write({field_name: value})
            _logger.info(f"Updated VM Rental config: {field_name} = {value}")
            return True
        else:
            _logger.warning(f"Unknown config field: {field_name}")
            return False

    @api.model
    def get_config_value(self, field_name, default=None):
        """Получает значение конфигурации"""
        config = self.get_config()
        return getattr(config, field_name, default)

    def action_reset_to_defaults(self):
        """Сбрасывает настройки к значениям по умолчанию"""
        self.ensure_one()
        defaults = self.default_get(list(self._fields.keys()))
        # Исключаем системные поля
        excluded = ['id', 'name', 'create_date', 'write_date', 'create_uid', 'write_uid']
        for field in excluded:
            defaults.pop(field, None)

        self.write(defaults)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Settings Reset'),
                'message': _('VM Rental settings have been reset to defaults'),
                'type': 'success',
            }
        }

    def action_export_config(self):
        """Экспортирует конфигурацию"""
        self.ensure_one()

        config_data = f"""VM Rental Configuration Export

Configuration: {self.name}
Created: {self.create_date}
Last Modified: {self.write_date}

=== GENERAL SETTINGS ===
Trial Period: {self.default_trial_days} days
Auto-suspend Expired: {self.auto_suspend_expired}
Send Notifications: {self.send_notifications}

=== RESOURCE LIMITS ===
Max CPU Cores: {self.max_cores_per_vm}
Max Memory: {self.max_memory_per_vm} MiB
Max Disk: {self.max_disk_per_vm} GiB

=== BACKUP & AUDIT ===
Auto Backup: {self.enable_auto_backup}
Backup Retention: {self.backup_retention_days} days
Audit Logging: {self.enable_audit_logging}
Audit Retention: {self.audit_retention_days} days

=== EXPORT INFO ===
Exported by: {self.env.user.name}
Export Date: {fields.Datetime.now()}
"""

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Configuration Export'),
                'message': config_data,
                'type': 'info',
                'sticky': True,
            }
        }