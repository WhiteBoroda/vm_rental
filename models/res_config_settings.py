# models/res_config_settings.py
from odoo import fields, models


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