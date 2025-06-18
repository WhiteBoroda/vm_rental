# vm_rental/models/hypervisor_resources.py
# -*- coding: utf-8 -*-
from odoo import models, fields

class HypervisorNode(models.Model):
    _name = 'hypervisor.node'
    _description = 'Hypervisor Node or Cluster'
    _order = 'name'

    name = fields.Char(string="Node/Cluster Name", required=True)
    server_id = fields.Many2one('hypervisor.server', string='Server', required=True, ondelete='cascade')

    # ИСПРАВЛЕНИЕ: Явно определяем связь
    storage_ids = fields.Many2many(
        comodel_name='hypervisor.storage',
        relation='hypervisor_node_storage_rel',
        column1='node_id',
        column2='storage_id',
        string="Storages"
    )

    _sql_constraints = [
        ('server_name_uniq', 'unique(server_id, name)', 'Node name must be unique per server!')
    ]

class HypervisorStorage(models.Model):
    _name = 'hypervisor.storage'
    _description = 'Hypervisor Storage or Datastore'
    _order = 'name'
    
    name = fields.Char(string="Storage/Datastore Name", required=True)
    server_id = fields.Many2one('hypervisor.server', string='Server', required=True, ondelete='cascade')

    # ИСПРАВЛЕНИЕ: Явно определяем связь (с теми же параметрами)
    node_ids = fields.Many2many(
        comodel_name='hypervisor.node',
        relation='hypervisor_node_storage_rel',
        column1='storage_id',
        column2='node_id',
        string="Available on Nodes"
    )

    _sql_constraints = [
        ('server_name_uniq', 'unique(server_id, name)', 'Storage name must be unique per server!')
    ]

class HypervisorTemplate(models.Model):
    _name = 'hypervisor.template'
    _description = 'Hypervisor VM Template'
    _order = 'name'

    name = fields.Char(string='Template Name', required=True)
    vmid = fields.Char(string="Template ID / VolID", required=True, help="The unique identifier for the template in the hypervisor (VMID for KVM, VolID for LXC).")
    server_id = fields.Many2one('hypervisor.server', string='Server', required=True, ondelete='cascade')
    
    # НОВОЕ ПОЛЕ: Тип шаблона
    template_type = fields.Selection([
        ('qemu', 'KVM (Virtual Machine)'),
        ('lxc', 'LXC (Container)')
    ], string="Template Type", required=True, default='qemu')
    
    _sql_constraints = [
        ('server_vmid_uniq', 'unique(server_id, vmid)', 'Template ID/VolID must be unique per server!')
    ]

    def name_get(self):
        result = []
        for rec in self:
            # Отображаем тип в названии для удобства
            name = f"{rec.name} ({rec.get_template_type_display()})"
            result.append((rec.id, name))
        return result