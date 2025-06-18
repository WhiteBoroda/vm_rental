# vm_rental/models/hypervisor_server.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class HypervisorServer(models.Model):
    _name = 'hypervisor.server'
    _description = 'Hypervisor Server Connection'

    # ... все поля модели до метода test_and_fetch_resources без изменений ...
    name = fields.Char(string="Server Name", required=True)
    hypervisor_type = fields.Selection([('proxmox', 'Proxmox VE'), ('vmware', 'VMware vCenter')], string="Hypervisor Type", required=True, default='proxmox')
    host = fields.Char(string="Hostname or IP", required=True)
    verify_ssl = fields.Boolean(string="Verify SSL Certificate", default=True)
    user = fields.Char(string="Proxmox User")
    token_name = fields.Char(string="API Token Name")
    token_value = fields.Char(string="API Token Value")
    vmware_user = fields.Char(string="vCenter User")
    vmware_password = fields.Char(string="vCenter Password")
    status = fields.Selection([('not_tested', 'Not Tested'), ('connecting', 'Connecting...'), ('connected', 'Connected'), ('failed', 'Failed')], string="Status", default='not_tested', readonly=True)
    status_message = fields.Text(string="Status Message", readonly=True)
    node_ids = fields.One2many('hypervisor.node', 'server_id', string="Nodes/Clusters")
    storage_ids = fields.One2many('hypervisor.storage', 'server_id', string="Storages/Datastores")
    template_ids = fields.One2many('hypervisor.template', 'server_id', string="VM Templates")

    def _get_service_manager(self):
        self.ensure_one()
        if self.hypervisor_type == 'proxmox':
            from ..services.proxmox_service import ProxmoxService
            return ProxmoxService(self)
        elif self.hypervisor_type == 'vmware':
            from ..services.vmware_service import VmwareService
            return VmwareService(self)
        raise UserError(_(f"No service manager found for hypervisor type '{self.hypervisor_type}'."))

    def test_and_fetch_resources(self):
        self.ensure_one()
        self.write({'status': 'connecting', 'status_message': 'Connecting and fetching resources...'})
        self.env.cr.commit()

        try:
            service = self._get_service_manager()
            version = service.get_version()

            # --- ИСПРАВЛЕНИЕ: НОВАЯ, НЕРАЗРУШАЮЩАЯ ЛОГИКА СИНХРОНИЗАЦИИ ---
            
            # 1. Синхронизация Нод
            api_nodes_data = service.list_nodes()
            api_node_names = {n['name'] for n in api_nodes_data}
            
            odoo_nodes = self.node_ids
            odoo_node_names = {n.name for n in odoo_nodes}
            
            # Ноды к добавлению
            nodes_to_add_names = api_node_names - odoo_node_names
            if nodes_to_add_names:
                self.env['hypervisor.node'].create([
                    {'name': name, 'server_id': self.id} for name in nodes_to_add_names
                ])

            # Ноды к удалению
            nodes_to_remove = odoo_nodes.filtered(lambda n: n.name not in api_node_names)
            if nodes_to_remove:
                nodes_to_remove.unlink()

            self.invalidate_recordset(['node_ids'])
            
            # 2. Синхронизация Хранилищ и их связей с нодами
            Storage = self.env['hypervisor.storage']
            all_odoo_storages = self.storage_ids
            api_storages_map = {}  # Карта: { 'имя_хранилища': {множество_имен_нод} }

            for node in self.node_ids:
                storages_on_node = service.list_storages(node.name)
                for storage_data in storages_on_node:
                    s_name = storage_data['name']
                    if s_name not in api_storages_map:
                        api_storages_map[s_name] = set()
                    api_storages_map[s_name].add(node.name)

            # Обновляем или создаем хранилища и их связи
            for s_name, node_names in api_storages_map.items():
                storage = all_odoo_storages.filtered(lambda s: s.name == s_name)
                if not storage:
                    storage = Storage.create({'name': s_name, 'server_id': self.id})
                
                nodes_to_link = self.node_ids.filtered(lambda n: n.name in node_names)
                storage.node_ids = [(6, 0, nodes_to_link.ids)] # (6,0,...) заменяет список связей

            # Хранилища к удалению
            api_storage_names = set(api_storages_map.keys())
            storages_to_remove = all_odoo_storages.filtered(lambda s: s.name not in api_storage_names)
            if storages_to_remove:
                storages_to_remove.unlink()

            # 3. Синхронизация Шаблонов (аналогично нодам)
            api_templates_data = []
            for node in self.node_ids:
                api_templates_data.extend(service.list_os_templates(node.name))

            api_template_map = {t['vmid']: t for t in api_templates_data} # Уникальные по vmid
            
            odoo_templates = self.template_ids
            odoo_template_vmids = {t.vmid for t in odoo_templates}
            
            # Шаблоны к добавлению
            templates_to_add_vmids = set(api_template_map.keys()) - odoo_template_vmids
            if templates_to_add_vmids:
                self.env['hypervisor.template'].create([
                    {
                        'name': api_template_map[vmid]['name'],
                        'vmid': vmid,
                        'server_id': self.id,
                        'template_type': api_template_map[vmid].get('template_type', 'qemu')
                    } for vmid in templates_to_add_vmids
                ])
                
            # Шаблоны к удалению
            templates_to_remove = odoo_templates.filtered(lambda t: t.vmid not in api_template_map)
            if templates_to_remove:
                templates_to_remove.unlink()

            # --- КОНЕЦ НОВОЙ ЛОГИКИ ---

            self.write({
                'status': 'connected',
                'status_message': f"Success! Connected to {self.hypervisor_type.capitalize()}. Version: {version}"
            })
        except Exception as e:
            _logger.error("Failed to fetch resources for server %s: %s", self.name, e, exc_info=True)
            error_message = str(e)
            self.write({'status': 'failed', 'status_message': error_message})
            raise UserError(_("Connection Test Failed!\n\nReason: %s", error_message))
        
        return True