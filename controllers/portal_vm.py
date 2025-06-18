# vm_rental/controllers/portal_vm.py
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
import logging

_logger = logging.getLogger(__name__)


class PortalVM(CustomerPortal):
    # Добавляем количество элементов на страницу
    _items_per_page = 20

    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()
        partner = request.env.user.partner_id

        # Убираем sudo() - теперь есть правила доступа
        values['vm_count'] = request.env['vm_rental.machine'].search_count([
            ('partner_id', 'child_of', partner.commercial_partner_id.id)
        ])

        return values

    @http.route(['/my/vms', '/my/vms/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_vms(self, page=1, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        VmInstance = request.env['vm_rental.machine']

        domain = [('partner_id', 'child_of', partner.commercial_partner_id.id)]
        vm_count = values.get('vm_count', 0)

        pager = portal_pager(
            url="/my/vms",
            total=vm_count,
            page=page,
            step=self._items_per_page
        )

        # Убираем sudo() - используем правила доступа
        vms = VmInstance.search(domain, limit=self._items_per_page, offset=pager['offset'])

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

    @http.route(['/my/vm/<int:vm_id>/snapshots'], type='http', auth='user', website=True)
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