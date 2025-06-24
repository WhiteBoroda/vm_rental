# vm_rental/models/hypervisor_resources.py
# -*- coding: utf-8 -*-
from odoo import models, fields

class HypervisorNode(models.Model):
    _name = 'hypervisor.node'
    _description = 'Hypervisor Node or Cluster'
    _order = 'name'

    name = fields.Char(string="Node/Cluster Name", required=True)
    server_id = fields.Many2one('hypervisor.server', string='Server', required=True, ondelete='cascade', index=True)

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
    server_id = fields.Many2one('hypervisor.server', string='Server', required=True, ondelete='cascade', index=True)

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


# vm_rental/models/hypervisor_resources.py
# ИСПРАВЛЕННАЯ модель HypervisorTemplate

class HypervisorTemplate(models.Model):
    _name = 'hypervisor.template'
    _description = 'Hypervisor VM Template'
    _order = 'name'

    name = fields.Char(string='Template Name', required=True)
    vmid = fields.Char(string="Template ID / VolID", required=True, index=True,
                       help="The unique identifier for the template in the hypervisor (VMID for KVM, VolID for LXC).")
    server_id = fields.Many2one('hypervisor.server', string='Server', required=True, ondelete='cascade', index=True)

    # НОВОЕ ПОЛЕ: Тип шаблона
    template_type = fields.Selection([
        ('qemu', 'KVM (Virtual Machine)'),
        ('lxc', 'LXC (Container)')
    ], string="Template Type", required=True, default='qemu')

    _sql_constraints = [
        ('server_vmid_uniq', 'unique(server_id, vmid)', 'Template ID/VolID must be unique per server!')
    ]

    @api.model
    def create(self, vals):
        """ИСПРАВЛЕННЫЙ метод create с проверкой дубликатов"""
        # Проверяем, существует ли уже такой шаблон
        existing = self.search([
            ('server_id', '=', vals.get('server_id')),
            ('vmid', '=', vals.get('vmid'))
        ], limit=1)

        if existing:
            _logger.warning(f"Template with vmid {vals.get('vmid')} already exists for server {vals.get('server_id')}")
            # Возвращаем существующий шаблон вместо создания нового
            return existing

        return super().create(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """ИСПРАВЛЕННЫЙ метод create_multi с проверкой дубликатов"""
        unique_vals_list = []

        for vals in vals_list:
            # Проверяем, существует ли уже такой шаблон
            existing = self.search([
                ('server_id', '=', vals.get('server_id')),
                ('vmid', '=', vals.get('vmid'))
            ], limit=1)

            if not existing:
                unique_vals_list.append(vals)
            else:
                _logger.warning(
                    f"Skipping duplicate template: server_id={vals.get('server_id')}, vmid={vals.get('vmid')}")

        if unique_vals_list:
            return super().create(unique_vals_list)
        else:
            # Возвращаем пустой recordset если все шаблоны уже существуют
            return self.browse([])

    def name_get(self):
        result = []
        for rec in self:
            # Исправлено: используем dict для получения названия типа
            type_names = dict(self._fields['template_type'].selection)
            type_display = type_names.get(rec.template_type, rec.template_type)
            name = f"{rec.name} ({type_display})"
            result.append((rec.id, name))
        return result