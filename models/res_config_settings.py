# models/res_config_settings.py
from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # VM Rental Settings
    vm_rental_default_trial_days = fields.Integer(
        string="Default Trial Period (Days)",
        default=7,
        config_parameter='vm_rental.default_trial_days',
        help="Default number of days for trial periods"
    )

    vm_rental_auto_suspend = fields.Boolean(
        string="Auto-suspend Expired VMs",
        default=True,
        config_parameter='vm_rental.auto_suspend',
        help="Automatically suspend VMs when subscription expires"
    )

    # Resource Limits
    vm_rental_max_cores = fields.Integer(
        string="Maximum CPU Cores",
        default=64,
        config_parameter='vm_rental.max_cores',
        help="Maximum number of CPU cores per VM"
    )

    vm_rental_max_memory = fields.Integer(
        string="Maximum Memory (MiB)",
        default=131072,  # 128GB
        config_parameter='vm_rental.max_memory',
        help="Maximum memory per VM in MiB"
    )

    vm_rental_max_disk = fields.Integer(
        string="Maximum Disk (GiB)",
        default=10240,  # 10TB
        config_parameter='vm_rental.max_disk',
        help="Maximum disk size per VM in GiB"
    )

    # Backup Settings
    vm_rental_auto_backup = fields.Boolean(
        string="Enable Auto Backup",
        default=False,
        config_parameter='vm_rental.auto_backup',
        help="Enable automatic configuration backups"
    )

    vm_rental_backup_retention_days = fields.Integer(
        string="Backup Retention (Days)",
        default=30,
        config_parameter='vm_rental.backup_retention_days',
        help="Number of days to keep automatic backups"
    )

    # Module version field
    vm_rental_module_version = fields.Char(
        string="Module Version",
        compute='_compute_vm_rental_module_version',
        help="Current version of VM Rental module"
    )

    # System statistics field
    vm_rental_system_stats = fields.Char(
        string="System Statistics",
        compute='_compute_vm_rental_system_stats',
        help="Basic system statistics"
    )

    @api.depends()
    def _compute_vm_rental_module_version(self):
        """Получает версию модуля из манифеста"""
        for record in self:
            try:
                module = self.env['ir.module.module'].search([
                    ('name', '=', 'vm_rental'),
                    ('state', '=', 'installed')
                ], limit=1)

                if module:
                    # Получаем версию из latest_version или из installed_version
                    version = module.latest_version or module.installed_version
                    record.vm_rental_module_version = f"VM Rental v{version}" if version else "VM Rental (Unknown Version)"
                else:
                    record.vm_rental_module_version = "VM Rental (Not Installed)"
            except Exception:
                record.vm_rental_module_version = "VM Rental v1.3.0"

    @api.depends()
    def _compute_vm_rental_system_stats(self):
        """Получает базовую статистику системы"""
        for record in self:
            try:
                # Подсчитываем основные метрики
                total_vms = self.env['vm_rental.machine'].search_count([])
                active_vms = self.env['vm_rental.machine'].search_count([('state', '=', 'active')])
                hypervisors = self.env['hypervisor.server'].search_count([])

                record.vm_rental_system_stats = f"{total_vms} VMs total, {active_vms} active\n{hypervisors} hypervisor(s) configured"
            except Exception:
                record.vm_rental_system_stats = "Statistics unavailable"