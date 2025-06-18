# vm_rental/models/hypervisor_server.py
# -*- coding: utf-8 -*-
from odoo.tools import ormcache
from datetime import datetime, timedelta
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
        
        # Убираем commit для лучшей производительности и транзакционной целостности
        # self.env.cr.commit() 
    
        try:
            service = self._get_service_manager()
            version = service.get_version()
    
            # Используем batch операции для улучшения производительности
            Node = self.env['hypervisor.node']
            Storage = self.env['hypervisor.storage']
            Template = self.env['hypervisor.template']
            
            # 1. Синхронизация Нод (с batch операциями)
            api_nodes_data = service.list_nodes()
            api_node_names = {n['name'] for n in api_nodes_data}
            
            odoo_nodes = self.node_ids
            odoo_node_names = {n.name: n for n in odoo_nodes}
            
            # Batch create для новых нод
            nodes_to_create = []
            for name in api_node_names - set(odoo_node_names.keys()):
                nodes_to_create.append({'name': name, 'server_id': self.id})
            
            if nodes_to_create:
                Node.create(nodes_to_create)
            
            # Batch unlink для удаленных нод
            nodes_to_remove = odoo_nodes.filtered(lambda n: n.name not in api_node_names)
            if nodes_to_remove:
                nodes_to_remove.unlink()
            
            # Принудительно обновляем кэш
            self.invalidate_recordset(['node_ids'])
            
            # 2. Синхронизация Хранилищ (оптимизированная)
            all_odoo_storages = {s.name: s for s in self.storage_ids}
            api_storages_map = {}
            
            # Собираем все данные о хранилищах за один проход
            for node in self.node_ids:
                storages_on_node = service.list_storages(node.name)
                for storage_data in storages_on_node:
                    s_name = storage_data['name']
                    if s_name not in api_storages_map:
                        api_storages_map[s_name] = set()
                    api_storages_map[s_name].add(node.id)  # Используем ID для оптимизации
            
            # Batch операции для хранилищ
            storages_to_create = []
            for s_name, node_ids in api_storages_map.items():
                if s_name not in all_odoo_storages:
                    storages_to_create.append({
                        'name': s_name,
                        'server_id': self.id,
                        'node_ids': [(6, 0, list(node_ids))]
                    })
                else:
                    # Обновляем связи только если они изменились
                    existing_storage = all_odoo_storages[s_name]
                    if set(existing_storage.node_ids.ids) != node_ids:
                        existing_storage.node_ids = [(6, 0, list(node_ids))]
            
            if storages_to_create:
                Storage.create(storages_to_create)
            
            # Удаляем неиспользуемые хранилища
            storages_to_remove_ids = []
            for s_name, storage in all_odoo_storages.items():
                if s_name not in api_storages_map:
                    storages_to_remove_ids.append(storage.id)
            
            if storages_to_remove_ids:
                Storage.browse(storages_to_remove_ids).unlink()
            
            # 3. Синхронизация Шаблонов (оптимизированная)
            api_templates_data = []
            for node in self.node_ids:
                api_templates_data.extend(service.list_os_templates(node.name))
            
            # Используем словарь для быстрого поиска
            api_template_map = {t['vmid']: t for t in api_templates_data}
            odoo_template_map = {t.vmid: t for t in self.template_ids}
            
            # Batch create для новых шаблонов
            templates_to_create = []
            for vmid, template_data in api_template_map.items():
                if vmid not in odoo_template_map:
                    templates_to_create.append({
                        'name': template_data['name'],
                        'vmid': vmid,
                        'server_id': self.id,
                        'template_type': template_data.get('template_type', 'qemu')
                    })
            
            if templates_to_create:
                Template.create(templates_to_create)
            
            # Batch unlink для удаленных шаблонов
            templates_to_remove_ids = []
            for vmid, template in odoo_template_map.items():
                if vmid not in api_template_map:
                    templates_to_remove_ids.append(template.id)
            
            if templates_to_remove_ids:
                Template.browse(templates_to_remove_ids).unlink()
            
            self.write({
                'status': 'connected',
                'status_message': f"Success! Connected to {self.hypervisor_type.capitalize()}. Version: {version}"
            })
            
        except Exception as e:
            _logger.error("Failed to fetch resources for server %s: %s", self.name, e, exc_info=True)
            error_message = str(e)
            self.write({'status': 'failed', 'status_message': error_message})
            raise UserError(_("Connection Test Failed!\n\nReason: %s") % error_message)
        
        return True

    @api.constrains('host')
    def _check_host(self):
        """Проверка валидности хоста"""
        import re
        for server in self:
            # Проверка на валидный IP или hostname
            ip_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
            hostname_pattern = re.compile(r'^[a-zA-Z0-9.-]+$')
            
            if not (ip_pattern.match(server.host) or hostname_pattern.match(server.host)):
                raise ValidationError(_("Invalid hostname or IP address format"))

    @ormcache('self.id')
    def _get_cached_service_manager(self):
        """Кешированная версия сервис-менеджера"""
        return self._get_service_manager()
    
    def clear_service_cache(self):
        """Очистка кеша при изменении конфигурации"""
        self._get_cached_service_manager.clear_cache(self)
    
    @api.model
    def write(self, vals):
        # Очищаем кеш при изменении критических полей
        critical_fields = {'host', 'user', 'token_name', 'token_value', 'vmware_user', 'vmware_password'}
        if any(field in vals for field in critical_fields):
            for record in self:
                record.clear_service_cache()
        return super().write(vals)
