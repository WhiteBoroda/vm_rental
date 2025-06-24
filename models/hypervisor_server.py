# vm_rental/models/hypervisor_server.py
# -*- coding: utf-8 -*-
from odoo.tools import ormcache
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
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
    pricing_ids = fields.One2many('hypervisor.server.pricing', 'server_id', string="Pricing Plans")
    current_pricing_id = fields.Many2one('hypervisor.server.pricing', string="Current Pricing",
                                         compute='_compute_current_pricing', store=False)

    @api.depends('pricing_ids.active', 'pricing_ids.date_start', 'pricing_ids.date_end')
    def _compute_current_pricing(self):
        """Вычисляет текущий активный план ценообразования"""
        for server in self:
            pricing = self.env['hypervisor.server.pricing'].search([
                ('server_id', '=', server.id),
                ('active', '=', True),
                ('date_start', '<=', fields.Date.today()),
                '|', ('date_end', '=', False), ('date_end', '>=', fields.Date.today())
            ], order='priority', limit=1)
            server.current_pricing_id = pricing

    def _get_service_manager(self):
        self.ensure_one()
        if self.hypervisor_type == 'proxmox':
            from ..services.proxmox_service import ProxmoxService
            return ProxmoxService(self)
        elif self.hypervisor_type == 'vmware':
            from ..services.vmware_service import VmwareService
            return VmwareService(self)
        raise UserError(_(f"No service manager found for hypervisor type '{self.hypervisor_type}'."))

    # vm_rental/models/hypervisor_server.py
    # ИСПРАВЛЕННЫЙ метод test_and_fetch_resources

    def test_and_fetch_resources(self):
        self.ensure_one()
        self.write({'status': 'connecting', 'status_message': 'Connecting and fetching resources...'})

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

            # 3. ИСПРАВЛЕННАЯ Синхронизация Шаблонов
            api_templates_data = []
            for node in self.node_ids:
                try:
                    templates_on_node = service.list_os_templates(node.name)
                    api_templates_data.extend(templates_on_node)
                except Exception as e:
                    _logger.warning(f"Could not fetch templates from node {node.name}: {e}")
                    continue

            # ИСПРАВЛЕНИЕ: Используем составной ключ (server_id, vmid) для уникальности
            api_template_map = {}
            for t in api_templates_data:
                # Создаем уникальный ключ: server_id + vmid
                unique_key = f"{self.id}_{t['vmid']}"
                # Если vmid уже есть для этого сервера, пропускаем дубликат
                if unique_key not in api_template_map:
                    api_template_map[unique_key] = t

            # Получаем существующие шаблоны для этого сервера
            existing_templates = Template.search([('server_id', '=', self.id)])
            odoo_template_map = {}
            for t in existing_templates:
                unique_key = f"{self.id}_{t.vmid}"
                odoo_template_map[unique_key] = t

            # Batch create для новых шаблонов
            templates_to_create = []
            for unique_key, template_data in api_template_map.items():
                if unique_key not in odoo_template_map:
                    # ИСПРАВЛЕНИЕ: Проверяем, что vmid не пустой
                    vmid = template_data.get('vmid')
                    if not vmid:
                        _logger.warning(f"Skipping template with empty vmid: {template_data}")
                        continue

                    templates_to_create.append({
                        'name': template_data.get('name', f"Template {vmid}"),
                        'vmid': str(vmid),  # Приводим к строке для безопасности
                        'server_id': self.id,
                        'template_type': template_data.get('template_type', 'qemu')
                    })

            if templates_to_create:
                try:
                    Template.create(templates_to_create)
                except Exception as e:
                    _logger.error(f"Failed to create templates: {e}")
                    # Если batch создание не удалось, пробуем по одному
                    for template_vals in templates_to_create:
                        try:
                            Template.create(template_vals)
                        except Exception as create_error:
                            _logger.error(f"Failed to create template {template_vals}: {create_error}")

            # Batch unlink для удаленных шаблонов
            templates_to_remove_ids = []
            for unique_key, template in odoo_template_map.items():
                if unique_key not in api_template_map:
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

    def write(self, vals):
        # Очищаем кеш при изменении критических полей
        critical_fields = {'host', 'user', 'token_name', 'token_value', 'vmware_user', 'vmware_password'}
        if any(field in vals for field in critical_fields):
            for record in self:
                record.clear_service_cache()
        return super().write(vals)

    # vm_rental/models/hypervisor_server.py
    # НОВЫЙ метод для очистки дубликатов

    def cleanup_duplicate_templates(self):
        """Очищает дубликаты шаблонов для этого сервера"""
        self.ensure_one()

        # Находим все шаблоны для этого сервера
        all_templates = self.env['hypervisor.template'].search([
            ('server_id', '=', self.id)
        ], order='id')

        # Группируем по vmid
        vmid_groups = {}
        for template in all_templates:
            vmid = template.vmid
            if vmid not in vmid_groups:
                vmid_groups[vmid] = []
            vmid_groups[vmid].append(template)

        # Удаляем дубликаты (оставляем первый, удаляем остальные)
        duplicates_removed = 0
        for vmid, templates in vmid_groups.items():
            if len(templates) > 1:
                # Оставляем первый шаблон, удаляем остальные
                templates_to_remove = templates[1:]
                for template in templates_to_remove:
                    _logger.info(f"Removing duplicate template: {template.name} (vmid: {template.vmid})")
                    template.unlink()
                    duplicates_removed += 1

        if duplicates_removed > 0:
            _logger.info(f"Removed {duplicates_removed} duplicate templates for server {self.name}")

        return duplicates_removed

    # НОВЫЙ метод в модели hypervisor.server для использования из UI
    def action_cleanup_duplicates(self):
        """Действие для очистки дубликатов (вызывается из UI)"""
        self.ensure_one()
        removed_count = self.cleanup_duplicate_templates()

        if removed_count > 0:
            message = f"Removed {removed_count} duplicate templates"
            message_type = 'success'
        else:
            message = "No duplicate templates found"
            message_type = 'info'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Cleanup Complete',
                'message': message,
                'type': message_type,
            }
        }