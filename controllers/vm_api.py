# controllers/vm_api.py
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import AccessError, MissingError
import logging

_logger = logging.getLogger(__name__)


class VMAPIController(http.Controller):

    def _get_user_vm(self, vm_id):
        """Проверка: ВМ должна принадлежать текущему пользователю"""
        partner = request.env.user.partner_id
        # Ищем ВМ через партнера (более надежно)
        vm = request.env['vm_rental.machine'].search([
            ('id', '=', int(vm_id)),
            ('partner_id', 'child_of', partner.commercial_partner_id.id)
        ], limit=1)
        return vm

    def _check_portal_vm_access(self, vm_id, required_operations=None):
        """
        Улучшенная проверка доступа для портальных пользователей

        Args:
            vm_id: ID виртуальной машины
            required_operations: список операций ['read', 'write', 'state_change']

        Returns:
            vm: объект VM или None если доступ запрещен
        """
        if required_operations is None:
            required_operations = ['read']

        try:
            # Получаем VM с проверкой прав доступа
            vm = request.env['vm_rental.machine'].browse(int(vm_id))

            # Проверяем основные права доступа
            vm.check_access_rights('read')
            vm.check_access_rule('read')

            # Дополнительные проверки для портальных пользователей
            if request.env.user.has_group('base.group_portal'):
                partner = request.env.user.partner_id

                # Проверяем владение VM
                if vm.partner_id.id not in partner.commercial_partner_id.child_ids.ids + [
                    partner.commercial_partner_id.id]:
                    return None

                # Проверяем состояние VM (портальные пользователи не могут работать с terminated/archived)
                if vm.state in ['terminated', 'archived']:
                    return None

                # Проверяем специфичные операции
                if 'write' in required_operations or 'state_change' in required_operations:
                    # Портальные пользователи могут изменять только состояние активных VM
                    if vm.state not in ['active', 'stopped', 'suspended']:
                        return None

                    # Проверяем права на write (должны быть разрешены в security)
                    try:
                        vm.check_access_rights('write')
                        vm.check_access_rule('write')
                    except Exception:
                        return None

            return vm

        except Exception as e:
            _logger.warning(f"VM access check failed for VM {vm_id}, user {request.env.user.name}: {e}")
            return None

    def _vm_action(self, vm_id, action, state_after, state_text):
        """
        ОБНОВЛЕННЫЙ метод с улучшенной проверкой прав
        """
        # Используем новую проверку с требованием прав на изменение состояния
        vm = self._check_portal_vm_access(vm_id, required_operations=['read', 'write', 'state_change'])
        if not vm:
            return {"error": "Access denied or VM not found.", "success": False}

        # Дополнительная проверка: портальные пользователи не могут управлять pending/failed VM
        if (request.env.user.has_group('base.group_portal') and
                vm.state in ['pending', 'failed', 'terminated', 'archived']):
            return {"error": f"Cannot perform this action on VM in '{vm.state}' state.", "success": False}

        try:
            # Вызываем универсальный сервис
            service = vm._get_hypervisor_service()

            # Вызываем нужный метод сервиса
            hypervisor_method = getattr(service, action)
            success = hypervisor_method(vm.hypervisor_node_name, vm.hypervisor_vm_ref)

            if success:
                if state_after:
                    # ИСПРАВЛЕНИЕ: Используем sudo() для обновления состояния,
                    # так как это системная операция, а не пользовательская
                    vm.sudo().write({'state': state_after})

                # Логируем действие пользователя
                request.env['vm_rental.audit_log'].sudo().log_action(
                    vm_id=vm.id,
                    action=action.replace('_vm', ''),  # 'start_vm' -> 'start'
                    success=True,
                    metadata={'user': request.env.user.name, 'portal_action': True}
                )

                return {
                    "success": True,
                    "new_state": state_after or vm.state,
                    "state_text": state_text,
                    "message": f"VM {action.replace('_vm', '').replace('_', ' ')} successful"
                }

            return {"success": False, "error": f"Failed to {action.replace('_', ' ')}"}

        except Exception as e:
            _logger.error(f"VM action {action} failed for VM {vm.id}: {e}")

            # Логируем неудачную попытку
            request.env['vm_rental.audit_log'].sudo().log_action(
                vm_id=vm.id,
                action=action.replace('_vm', ''),
                success=False,
                error_message=str(e),
                metadata={'user': request.env.user.name, 'portal_action': True}
            )

            return {"success": False, "error": "Operation failed. Please try again later."}

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
        """ОБНОВЛЕННЫЙ метод создания снапшотов с улучшенной проверкой прав"""

        # Проверяем доступ с правами на создание снапшотов
        vm = self._check_portal_vm_access(vm_id, required_operations=['read', 'write'])
        if not vm:
            return {'success': False, 'error': 'Access Denied or VM not found'}

        # Дополнительная проверка: снапшоты можно создавать только для активных или остановленных VM
        if vm.state not in ['active', 'stopped']:
            return {'success': False, 'error': f'Cannot create snapshot for VM in {vm.state} state'}

        snap_name = f"snap_{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"

        try:
            service = vm._get_hypervisor_service()
            result = service.create_snapshot(vm.hypervisor_node_name, vm.hypervisor_vm_ref, snap_name, description)

            if result:
                # Используем sudo() для создания записи снапшота
                new_snap = request.env['vm.snapshot'].sudo().create({
                    'name': name,
                    'description': description,
                    'vm_instance_id': vm.id,
                    'proxmox_name': snap_name,
                })

                # Логируем создание снапшота
                request.env['vm_rental.audit_log'].sudo().log_action(
                    vm_id=vm.id,
                    action='snapshot_create',
                    success=True,
                    metadata={
                        'snapshot_name': name,
                        'user': request.env.user.name,
                        'portal_action': True
                    }
                )

                return {
                    'success': True,
                    'snapshot': {
                        'id': new_snap.id,
                        'name': name,
                        'description': description,
                        'create_date': fields.Date.today().strftime('%Y-%m-%d'),
                        'proxmox_name': new_snap.proxmox_name,
                    }
                }

            return {'success': False, 'error': 'Failed to create snapshot in hypervisor.'}

        except Exception as e:
            _logger.error(f"Snapshot creation failed for VM {vm.id}: {e}")
            return {'success': False, 'error': 'Snapshot creation failed. Please try again later.'}

    @http.route('/vm/<int:vm_id>/snapshot/<string:proxmox_name>/rollback', type='json', auth='user', methods=['POST'])
    def rollback_vm_snapshot(self, vm_id, proxmox_name):
        """ОБНОВЛЕННЫЙ метод отката снапшотов"""

        vm = self._check_portal_vm_access(vm_id, required_operations=['read', 'write'])
        if not vm:
            return {'success': False, 'error': 'Access Denied'}

        # Проверяем существование снапшота и права на него
        snap = request.env['vm.snapshot'].search([
            ('proxmox_name', '=', proxmox_name),
            ('vm_instance_id', '=', vm.id)
        ], limit=1)

        if not snap:
            return {'success': False, 'error': 'Snapshot not found or access denied'}

        try:
            service = vm._get_hypervisor_service()
            result = service.rollback_snapshot(vm.hypervisor_node_name, vm.hypervisor_vm_ref, proxmox_name)

            if result:
                # Логируем откат снапшота
                request.env['vm_rental.audit_log'].sudo().log_action(
                    vm_id=vm.id,
                    action='snapshot_rollback',
                    success=True,
                    metadata={
                        'snapshot_name': snap.name,
                        'user': request.env.user.name,
                        'portal_action': True
                    }
                )

            return {'success': result, 'error': 'Rollback failed' if not result else ''}

        except Exception as e:
            _logger.error(f"Snapshot rollback failed for VM {vm.id}: {e}")
            return {'success': False, 'error': 'Rollback failed. Please try again later.'}

    @http.route('/vm/<int:vm_id>/snapshot/<string:proxmox_name>/delete', type='json', auth='user', methods=['POST'])
    def delete_vm_snapshot(self, vm_id, proxmox_name):
        vm = self._check_portal_vm_access(vm_id, required_operations=['read', 'write'])
        if not vm:
            return {'success': False, 'error': 'Access Denied or VM not found'}

        # Проверка снапшота в Odoo
        snap = request.env['vm.snapshot'].sudo().search([
            ('proxmox_name', '=', proxmox_name),
            ('vm_instance_id', '=', vm.id)
        ], limit=1)

        if not snap:
            return {'success': False, 'error': 'Snapshot not found'}

        try:
            # Вызываем универсальный сервис и поля
            service = vm._get_hypervisor_service()
            result = service.delete_snapshot(vm.hypervisor_node_name, vm.hypervisor_vm_ref, proxmox_name)

            if result:
                # Логируем удаление снапшота
                request.env['vm_rental.audit_log'].sudo().log_action(
                    vm_id=vm.id,
                    action='snapshot_delete',
                    success=True,
                    metadata={
                        'snapshot_name': snap.name,
                        'user': request.env.user.name,
                        'portal_action': True
                    }
                )

                snap.sudo().unlink()
                return {'success': True}

            return {'success': False, 'error': 'Failed to delete snapshot in Hypervisor.'}

        except Exception as e:
            _logger.error(f"Snapshot deletion failed for VM {vm.id}: {e}")
            return {'success': False, 'error': 'Snapshot deletion failed. Please try again later.'}