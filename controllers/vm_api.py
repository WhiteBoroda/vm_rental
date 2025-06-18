# controllers/vm_api.py
from odoo import http, fields
from odoo.http import request

class VMAPIController(http.Controller):

    def _get_user_vm(self, vm_id):
        """Проверка: ВМ должна принадлежать текущему пользователю"""
        # ИСПРАВЛЕНИЕ: Используем `sudo()` для обхода правил доступа,
        # так как принадлежность проверяется по `user_id` вручную.
        vm = request.env['vm_rental.machine'].sudo().search([
            ('id', '=', int(vm_id)),
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        return vm
    
    def _vm_action(self, vm_id, action, state_after, state_text):
        """
        Общий метод для выполнения действий с ВМ (start, stop, etc.).
        """
        vm = self._get_user_vm(vm_id)
        if not vm:
            return {"error": "Access denied or VM not found.", "success": False}

        # ИСПРАВЛЕНИЕ: Вызываем универсальный сервис
        service = vm._get_hypervisor_service()
        
        # Вызываем нужный метод сервиса (start_vm, stop_vm, etc.)
        hypervisor_method = getattr(service, action)
        # ИСПРАВЛЕНИЕ: Передаем универсальные поля
        success = hypervisor_method(vm.hypervisor_node_name, vm.hypervisor_vm_ref)

        if success:
            if state_after:
                vm.write({'state': state_after})
            return {"success": True, "new_state": state_after or vm.state, "state_text": state_text}
        
        return {"success": False, "error": f"Failed to {action.replace('_', ' ')}"}


    @http.route('/vm/start/<int:vm_id>', type='json', auth='user')
    def start_vm(self, vm_id):
        return self._vm_action(vm_id, 'start_vm', 'active', 'Active')

    @http.route('/vm/stop/<int:vm_id>', type='json', auth='user')
    def stop_vm(self, vm_id):
        return self._vm_action(vm_id, 'stop_vm', 'stopped', 'Stopped')

    @http.route('/vm/suspend/<int:vm_id>', type='json', auth='user')
    def suspend_vm(self, vm_id):
        return self._vm_action(vm_id, 'suspend_vm', 'suspended', 'Suspended')

    @http.route('/vm/reboot/<int:vm_id>', type='json', auth='user')
    def reboot_vm(self, vm_id):
        return self._vm_action(vm_id, 'reboot_vm', None, 'Active')

    @http.route('/vm/<int:vm_id>/snapshot/create', type='json', auth='user', methods=['POST'])
    def create_vm_snapshot(self, vm_id, name, description=''):
        vm = self._get_user_vm(vm_id)
        if not vm:
            return {'success': False, 'error': 'Access Denied'}
        
        snap_name = f"snap_{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"
        # ИСПРАВЛЕНИЕ: Вызываем универсальный сервис
        service = vm._get_hypervisor_service()
        # ИСПРАВЛЕНИЕ: Передаем универсальные поля и вызываем новый метод сервиса
        result = service.create_snapshot(vm.hypervisor_node_name, vm.hypervisor_vm_ref, snap_name, description)

        if result:
            new_snap = request.env['vm.snapshot'].sudo().create({
                'name': name, 'description': description,
                'vm_instance_id': vm.id, 'proxmox_name': snap_name,
            })
            # ИСПРАВЛЕНИЕ: Возвращаем данные в правильном формате для JS
            return {'success': True, 'snapshot': {
                'id': new_snap.id, 
                'name': name, 
                'description': description, 
                'create_date': fields.Date.today().strftime('%Y-%m-%d'),
                'proxmox_name': new_snap.proxmox_name,
             }}
        return {'success': False, 'error': 'Failed to create snapshot in Hypervisor.'}

    @http.route('/vm/<int:vm_id>/snapshot/<string:proxmox_name>/rollback', type='json', auth='user', methods=['POST'])
    def rollback_vm_snapshot(self, vm_id, proxmox_name):
        vm = self._get_user_vm(vm_id)
        if not vm:
            return {'success': False, 'error': 'Access Denied'}

        # ИСПРАВЛЕНИЕ: Вызываем универсальный сервис и поля
        service = vm._get_hypervisor_service()
        result = service.rollback_snapshot(vm.hypervisor_node_name, vm.hypervisor_vm_ref, proxmox_name)

        return {'success': True if result else False, 'error': 'Rollback failed' if not result else ''}

    @http.route('/vm/<int:vm_id>/snapshot/<string:proxmox_name>/delete', type='json', auth='user', methods=['POST'])
    def delete_vm_snapshot(self, vm_id, proxmox_name):
        vm = self._get_user_vm(vm_id)
        # Проверка снапшота в Odoo
        snap = request.env['vm.snapshot'].sudo().search([('proxmox_name', '=', proxmox_name), ('vm_instance_id', '=', vm.id)], limit=1)
        if not vm or not snap:
            return {'success': False, 'error': 'Access Denied or Snapshot not found'}

        # ИСПРАВЛЕНИЕ: Вызываем универсальный сервис и поля
        service = vm._get_hypervisor_service()
        result = service.delete_snapshot(vm.hypervisor_node_name, vm.hypervisor_vm_ref, proxmox_name)

        if result:
            snap.sudo().unlink()
            return {'success': True}
        return {'success': False, 'error': 'Failed to delete snapshot in Hypervisor.'}