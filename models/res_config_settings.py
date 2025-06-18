# Создайте файл models/res_config_settings.py

from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    # Trial Period Settings
    vm_rental_default_trial_days = fields.Integer(
        string="Default Trial Days",
        default=7,
        config_parameter='vm_rental.default_trial_days'
    )
    
    vm_rental_auto_suspend = fields.Boolean(
        string="Auto Suspend on Expiry",
        default=True,
        config_parameter='vm_rental.auto_suspend'
    )
    
    # Resource Limits
    vm_rental_max_cores = fields.Integer(
        string="Max CPU Cores",
        default=64,
        config_parameter='vm_rental.max_cores'
    )
    
    vm_rental_max_memory = fields.Integer(
        string="Max Memory (MiB)",
        default=131072,  # 128 GB
        config_parameter='vm_rental.max_memory'
    )
    
    vm_rental_max_disk = fields.Integer(
        string="Max Disk (GiB)",
        default=10240,  # 10 TB
        config_parameter='vm_rental.max_disk'
    )
    
    # Backup Settings
    vm_rental_auto_backup = fields.Boolean(
        string="Enable Auto Backup",
        default=False,
        config_parameter='vm_rental.auto_backup'
    )
    
    vm_rental_backup_retention_days = fields.Integer(
        string="Backup Retention Days",
        default=30,
        config_parameter='vm_rental.backup_retention_days'
    )
