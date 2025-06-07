# controllers/portal_vm.py
import logging
import json
import uuid
from odoo import http, fields
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

class PortalVM(CustomerPortal):

    @http.route(['/my/vms'], type='http', auth='user', website=True)
    def portal_my_vms(self, **kwargs):
        user = request.env.user
        vms = request.env['vm.instance'].sudo().search([('user_id', '=', user.id)])

        # Получение списка шаблонов ОС и конфигураций
        service = request.env['vm.instance'].sudo()._get_proxmox_service()
        os_templates = []
        try:
            os_templates = service.list_os_templates()
        except Exception as e:
            _logger.warning("list_os_templates() failed: %s", e)

        config_json = request.env['ir.config_parameter'].sudo().get_param('vm_rental.config_templates')
        config_options = {}
        try:
            config_options = json.loads(config_json or '{}')
        except Exception as e:
            _logger.warning("Invalid JSON for VM config templates: %s", e)

        return request.render("vm_rental.portal_create_vm", {
            'vms': vms,
            'os_templates': os_templates,
            'config_options': config_options,
        })

    @http.route(['/my/vms/create'], type='http', auth='user', methods=['POST'], csrf=True, website=True)
    def create_vm(self, **post):
        vm_name = post.get('vm_name')
        config_name = post.get('config_name')
        os_template = post.get('os_template')

        if not vm_name or not config_name or not os_template:
            request.session.flash("All fields are required.", "danger")
            return request.redirect("/my/vms")

        last_vm = request.env['vm.instance'].sudo().search([], order='vmid desc', limit=1)
        vm_id = request.env['ir.sequence'].next_by_code('vm.instance')
        vm_id_int = int(vm_id.replace("VM", ""))  # если нужна числовая часть



        proxmox_service = request.env['vm.instance'].sudo()._get_proxmox_service()
        try:
            result = proxmox_service.create_vm(
                vm_id=vm_id_int,
                name=vm_name,
                template=os_template,
                config_name=config_name
            )
        except Exception as e:
            _logger.error("Failed to create VM: %s", e)
            result = False

        if result:
            request.env['vm.instance'].sudo().create({
                'name': vm_name,
                'vmid': vm_id,
                'user_id': request.env.user.id,
                'config_name': config_name,
                'os_template': os_template,
                'start_date': fields.Date.today(),
                'state': 'active',
            })
            request.session.flash('VM created successfully.', 'success')
        else:
            request.session.flash('VM creation failed.', 'danger')

        return request.redirect('/my/vms')

    @http.route(['/my/vms/console/<int:vm_id>'], type='http', auth='user', website=True)
    def portal_vm_console(self, vm_id, **kwargs):
        vm = request.env['vm.instance'].sudo().search([
            ('id', '=', vm_id),
            ('user_id', '=', request.env.user.id)
        ], limit=1)
    
    service = request.env['vm.instance'].sudo()._get_proxmox_service()
    console_url = service.generate_console_url(vm.proxmox_vm_id)

        if not vm:
            return request.not_found()

        return request.render("VM.portal_vm_console", { # Используйте VM, а не vm_rental
        'vm': vm,
        'console_url': console_url
})
