#  models/vm_audit_log.py

from odoo import models, fields, api
import json

class VmAuditLog(models.Model):
    _name = 'vm_rental.audit_log'
    _description = 'VM Operation Audit Log'
    _order = 'create_date desc'
    _rec_name = 'action'
    
    vm_id = fields.Many2one('vm_rental.machine', string="VM", required=True, ondelete='cascade', index=True)
    user_id = fields.Many2one('res.users', string="User", required=True, default=lambda self: self.env.user)
    action = fields.Selection([
        ('create', 'Created'),
        ('start', 'Started'),
        ('stop', 'Stopped'),
        ('suspend', 'Suspended'),
        ('reboot', 'Rebooted'),
        ('snapshot_create', 'Snapshot Created'),
        ('snapshot_delete', 'Snapshot Deleted'),
        ('snapshot_rollback', 'Snapshot Rollback'),
        ('extend', 'Period Extended'),
        ('terminate', 'Terminated'),
        ('user_group_update', 'User Group Updated'),
    ], string="Action", required=True, index=True)
    
    success = fields.Boolean(string="Success", default=True)
    error_message = fields.Text(string="Error Message")
    duration = fields.Float(string="Duration (seconds)", digits=(10, 3))
    metadata = fields.Text(string="Metadata")
    
    @api.model
    def log_action(self, vm_id, action, success=True, error_message=None, duration=None, metadata=None):
        """Удобный метод для логирования действий"""
        vals = {
            'vm_id': vm_id,
            'action': action,
            'success': success,
            'error_message': error_message,
            'duration': duration,
        }
        if metadata:
            vals['metadata'] = json.dumps(metadata) if isinstance(metadata, dict) else metadata
        
        return self.create(vals)
