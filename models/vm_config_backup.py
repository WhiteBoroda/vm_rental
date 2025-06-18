# models/vm_config_backup.py

from odoo import models, fields, api
import json
from datetime import datetime, timedelta

class VmConfigBackup(models.Model):
    _name = 'vm_rental.config_backup'
    _description = 'VM Configuration Backup'
    _order = 'create_date desc'
    
    vm_id = fields.Many2one('vm_rental.machine', string="VM", required=True, ondelete='cascade', index=True)
    name = fields.Char(string="Backup Name", required=True)
    config_data = fields.Text(string="Configuration Data", required=True)
    backup_type = fields.Selection([
        ('manual', 'Manual'),
        ('auto', 'Automatic'),
        ('pre_change', 'Before Change'),
    ], string="Backup Type", default='manual')
    
    @api.model
    def create_backup(self, vm, backup_type='manual', name=None):
        """Создание резервной копии конфигурации ВМ"""
        config = {
            'name': vm.name,
            'hypervisor_server_id': vm.hypervisor_server_id.id,
            'hypervisor_node_id': vm.hypervisor_node_id.id,
            'hypervisor_storage_id': vm.hypervisor_storage_id.id,
            'hypervisor_template_id': vm.hypervisor_template_id.id,
            'cores': vm.cores,
            'memory': vm.memory,
            'disk': vm.disk,
            'partner_id': vm.partner_id.id,
            'state': vm.state,
            'end_date': vm.end_date.isoformat() if vm.end_date else None,
        }
        
        if not name:
            name = f"Backup {vm.name} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        return self.create({
            'vm_id': vm.id,
            'name': name,
            'config_data': json.dumps(config),
            'backup_type': backup_type,
        })
    
    def restore_config(self):
        """Восстановление конфигурации из резервной копии"""
        self.ensure_one()
        config = json.loads(self.config_data)
        
        # Убираем поля, которые не должны изменяться при восстановлении
        restore_fields = ['cores', 'memory', 'disk', 'end_date']
        vals = {k: v for k, v in config.items() if k in restore_fields}
        
        self.vm_id.write(vals)
        return True
    
    @api.model
    def cleanup_old_backups(self, days=30):
        """Удаление старых автоматических резервных копий"""
        cutoff_date = datetime.now() - timedelta(days=days)
        old_backups = self.search([
            ('create_date', '<', cutoff_date),
            ('backup_type', '=', 'auto')
        ])
        old_backups.unlink()
        return len(old_backups)
