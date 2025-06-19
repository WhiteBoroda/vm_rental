# vm_rental/controllers/portal_vm.py
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.tools import ormcache
import logging

#        return request.env['vm_rental.machine'].search_count([
#            ('partner_id', 'child_of', partner_id)
#        ])

# Указываем имя логгера, чтобы его было легче найти
# _logger = logging.getLogger("vm_rental_portal_debug")

class PortalVM(CustomerPortal):
    _items_per_page = 20

    def _get_vm_count(self, partner_id):
        domain = [('partner_id', 'child_of', partner_id)]
        try:
            count = request.env['vm_rental.machine'].search_count(domain)
        except Exception as e:
            count = 0
        return count
    
    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        values['vms_count'] = self._get_vm_count(partner.commercial_partner_id.id)

        return values
   
    @http.route(['/my/vms', '/my/vms/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_vms(self, page=1, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        VmInstance = request.env['vm_rental.machine']

        domain = [('partner_id', 'child_of', partner.commercial_partner_id.id)]
        vm_count = values.get('vms_count', 0)

        pager = portal_pager(
            url="/my/vms",
            total=vm_count,
            page=page,
            step=self._items_per_page
        )

        try:
            vms = VmInstance.search(domain, limit=self._items_per_page, offset=pager['offset'])
        except Exception as e:
            vms = VmInstance.browse([])


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
            # Пытаемся получить URL консоли
            service = vm._get_hypervisor_service()
            console_url = service.get_console_url(vm.hypervisor_node_name, vm.hypervisor_vm_ref)

            # Если все успешно, рендерим шаблон с консолью
            return request.render("vm_rental.portal_vm_console", {
                'vm': vm,
                'console_url': console_url
            })

        except Exception as e:
            # ИСПРАВЛЕНИЕ: Логируем НАСТОЯЩУЮ ошибку от гипервизора
            _logger.error(f"Could not generate console URL for VM {vm.id}. Hypervisor Error: {e}", exc_info=True)

            # ИСПРАВЛЕНИЕ: Рендерим наш собственный, надежный шаблон ошибки
            return request.render("vm_rental.portal_error_page", {
                'status_code': 'Console Error',
                'status_message': 'Could not generate a console URL for this virtual machine. Please check if the VM is running and contact support.'
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

    @http.route(['/my/home'], type='http', auth="user", website=True)
    def home(self, **kw):
        values = self._prepare_home_portal_values()
        # Добавляем счетчик VM в главную страницу портала
        partner = request.env.user.partner_id
        values['vms_count'] = self._get_vm_count(partner.commercial_partner_id.id)
        return request.render("portal.portal_my_home", values)

    def _get_vms_domain(self):
        """Вспомогательный метод для получения домена поиска ВМ."""
        partner = self.env.user.partner_id
        return [('partner_id', 'child_of', partner.commercial_partner_id.id)]