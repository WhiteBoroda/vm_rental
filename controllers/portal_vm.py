# vm_rental/controllers/portal_vm.py
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.tools import ormcache
import logging

_logger = logging.getLogger(__name__)


class PortalVM(CustomerPortal):
    # Добавляем количество элементов на страницу
    _items_per_page = 20

    # ИСПРАВЛЕНИЕ: Убран декоратор @ormcache с этого метода контроллера
    def _get_vm_count(self, partner_id):
        """Подсчет ВМ"""
        return request.env['vm_rental.machine'].search_count([
            ('partner_id', 'child_of', partner_id)
        ])
    
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
import logging

# Указываем имя логгера, чтобы его было легче найти
_logger = logging.getLogger("vm_rental_portal_debug")


class PortalVM(CustomerPortal):
    _items_per_page = 20

    def _get_vm_count(self, partner_id):
        domain = [('partner_id', 'child_of', partner_id)]
        
        _logger.info(f"--- ДЕБАГ: ПОИСК КОЛИЧЕСТВА ВМ ---")
        _logger.info(f"Пользователь: {request.env.user.name}")
        _logger.info(f"ID партнера для поиска: {partner_id}")
        _logger.info(f"Условие поиска (domain): {domain}")
        
        try:
            count = request.env['vm_rental.machine'].search_count(domain)
            _logger.info(f"Результат search_count: Найдено {count} ВМ.")
        except Exception as e:
            _logger.error(f"Ошибка при выполнении search_count: {e}")
            count = 0
            
        _logger.info(f"--- КОНЕЦ ДЕБАГА ---")
        return count
    
    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()
        partner = request.env.user.partner_id
<<<<<<< HEAD
        
        _logger.info(f"--- ДЕБАГ: ПОДГОТОВКА СТРАНИЦЫ ПОРТАЛА ---")
        _logger.info(f"Текущий пользователь: {request.env.user.name} (ID: {request.env.user.id})")
        _logger.info(f"Партнер пользователя: {partner.name} (ID: {partner.id})")
        _logger.info(f"Коммерческий партнер: {partner.commercial_partner_id.name} (ID: {partner.commercial_partner_id.id})")
        
        values['vms_count'] = self._get_vm_count(partner.commercial_partner_id.id)
=======

        # ИСПРАВЛЕНИЕ: Вызываем обычный метод вместо кэшированного
        values['vms_count'] = self._get_vm_count(partner.commercial_partner_id.id)

>>>>>>> 102a2852fdfe5965b5e91f554bd27e03fea9139c
        return values
   
    @http.route(['/my/vms', '/my/vms/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_vms(self, page=1, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        VmInstance = request.env['vm_rental.machine']

        domain = [('partner_id', 'child_of', partner.commercial_partner_id.id)]
        
        _logger.info(f"--- ДЕБАГ: ПОЛУЧЕНИЕ СПИСКА ВМ ---")
        _logger.info(f"Загрузка страницы {page} для пользователя {request.env.user.name}")
        _logger.info(f"Условие поиска (domain): {domain}")

        vm_count = values.get('vms_count', 0)

        pager = portal_pager(
            url="/my/vms",
            total=vm_count,
            page=page,
            step=self._items_per_page
        )

        try:
            vms = VmInstance.search(domain, limit=self._items_per_page, offset=pager['offset'])
            _logger.info(f"Результат search: Найдены ID виртуальных машин: {vms.ids}")
        except Exception as e:
            _logger.error(f"Ошибка при выполнении search: {e}")
            vms = VmInstance.browse([])

        _logger.info(f"--- КОНЕЦ ДЕБАГА ---")

        values.update({
            'vms': vms,
            'page_name': 'vms',
            'pager': pager,
            'default_url': '/my/vms',
        })
        return request.render("vm_rental.portal_my_vms", values)

    @http.route(['/my/vms/console/<int:vm_id>'], type='http', auth='user', website=True)
    def portal_vm_console(self, vm_id, **kwargs):
        # Используем правила доступа вместо sudo()
        partner = request.env.user.partner_id
        vm = request.env['vm_rental.machine'].search([
            ('id', '=', vm_id),
            ('partner_id', 'child_of', partner.commercial_partner_id.id)
        ], limit=1)

        if not vm:
            return request.not_found()

        try:
            service = vm._get_hypervisor_service()
            console_url = service.get_console_url(vm.hypervisor_node_name, vm.hypervisor_vm_ref)
        except Exception as e:
            _logger.error(f"Could not generate console URL for VM {vm.id}: {e}")
            return request.render("website.http_error", {
                'status_code': 'Console Error',
                'status_message': 'Could not generate a console URL for this virtual machine.'
            })

        return request.render("vm_rental.portal_vm_console", {
            'vm': vm,
            'console_url': console_url
        })

    @http.route(['/my/vms/<int:vm_id>/snapshots'], type='http', auth='user', website=True)
    def portal_vm_snapshots(self, vm_id, **kwargs):
        # Используем правила доступа вместо sudo()
        partner = request.env.user.partner_id
        vm = request.env['vm_rental.machine'].search([
            ('id', '=', vm_id),
            ('partner_id', 'child_of', partner.commercial_partner_id.id)
        ], limit=1)

        if not vm:
            return request.not_found()

        return request.render("vm_rental.portal_vm_snapshots_template", {
            'vm': vm,
            'snapshots': vm.snapshot_ids
        })