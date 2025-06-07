# controllers/vm_api.py
from odoo import http
from odoo.http import request

class VMAPIController(http.Controller):

    def _get_user_vm(self, vm_id):
        """Проверка: ВМ должна принадлежать текущему пользователю"""
        vm = request.env['vm.instance'].sudo().search([
            ('id', '=', int(vm_id)),
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        return vm

    @http.route('/vm/start/<int:vm_id>', type='json', auth='user')
    def start_vm(self, vm_id):
        vm = self._get_user_vm(vm_id)
        if not vm:
            return {"error": "Access denied."}

        service = vm._get_proxmox_service()
        success = service.start_vm(vm.vmid)
        return {"status": "started" if success else "failed"}

    @http.route('/vm/stop/<int:vm_id>', type='json', auth='user')
    def stop_vm(self, vm_id):
        vm = self._get_user_vm(vm_id)
        if not vm:
            return {"error": "Access denied."}

        service = vm._get_proxmox_service()
        success = service.stop_vm(vm.vmid)
        return {"status": "stopped" if success else "failed"}

@http.route('/vm/suspend/<int:vmid>', type='json', auth='user')
def suspend_vm(self, vmid):
    user_id = request.env.user.id
    vm = request.env['vm.instance'].sudo().search([
        ('vmid', '=', vmid),
        ('user_id', '=', user_id)
    ], limit=1)

    if not vm:
        return {'error': 'VM not found or permission denied.'}

    service = request.env['vm.instance'].sudo()._get_proxmox_service()
    success = service.suspend_vm(vmid)
    if success:
        vm.write({'state': 'suspended'})
        return {'status': 'VM suspended'}
    return {'error': 'Failed to suspend VM'}
    
    @http.route('/vm/reboot/<int:vm_id>', type='json', auth='user')
    def reboot_vm(self, vm_id):
        vm = self._get_user_vm(vm_id)
        if not vm:
            return {"error": "Access denied."}

        service = vm._get_proxmox_service()
        success = service.reboot_vm(vm.vmid)
        return {"status": "rebooted" if success else "failed"}

    @http.route('/vm/extend/<int:vm_id>', type='json', auth='user')
    def extend_vm(self, vm_id):
        vm = self._get_user_vm(vm_id)
        if not vm:
            return {"error": "Access denied."}

        vm.extend_period()
        return {"status": "extended"}
