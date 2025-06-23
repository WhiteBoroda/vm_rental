# vm_rental/controllers/vm_user_stats.py
# НОВЫЙ ФАЙЛ

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
import json


class VmUserStatsController(http.Controller):

    @http.route('/vm_rental/user_stats', type='json', auth='user', methods=['POST'])
    def get_vm_user_statistics(self):
        """Получение статистики пользователей VM Rental"""

        # Проверяем права доступа
        if not request.env.user.has_group('base.group_user'):
            return {'error': 'Access denied'}

        try:
            # Получаем группы VM Rental
            vm_admin_group = request.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)
            vm_manager_group = request.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)

            # Подсчитываем пользователей
            vm_admins = len(vm_admin_group.users) if vm_admin_group else 0
            vm_managers = len(vm_manager_group.users) if vm_manager_group else 0

            # Общая статистика пользователей
            total_internal = request.env['res.users'].search_count([
                ('share', '=', False),
                ('active', '=', True)
            ])

            total_portal = request.env['res.users'].search_count([
                ('share', '=', True),
                ('active', '=', True)
            ])

            # Портальные пользователи с VM
            portal_with_vms = request.env['res.users'].search_count([
                ('share', '=', True),
                ('active', '=', True),
                ('partner_id.vm_instance_ids', '!=', False)
            ])

            # Статистика VM
            total_vms = request.env['vm_rental.machine'].search_count([])
            active_vms = request.env['vm_rental.machine'].search_count([('state', '=', 'active')])

            return {
                'vm_admins': vm_admins,
                'vm_managers': vm_managers,
                'total_internal': total_internal,
                'total_portal': total_portal,
                'portal_with_vms': portal_with_vms,
                'users_without_vm_access': total_internal - vm_admins - vm_managers,
                'total_vms': total_vms,
                'active_vms': active_vms,
                'access_coverage': ((vm_admins + vm_managers) / total_internal * 100) if total_internal > 0 else 0
            }

        except Exception as e:
            return {'error': str(e)}

    @http.route('/vm_rental/user_roles', type='json', auth='user', methods=['POST'])
    def get_user_roles_matrix(self):
        """Получение матрицы ролей пользователей"""

        if not request.env.user.has_group('base.group_system'):
            return {'error': 'Admin access required'}

        try:
            # Получаем все внутренние пользователи
            users = request.env['res.users'].search([
                ('share', '=', False),
                ('active', '=', True),
                ('id', '!=', 1)  # Исключаем OdooBot
            ])

            user_roles = []
            vm_admin_group = request.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)
            vm_manager_group = request.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)

            for user in users:
                role = 'none'
                if vm_admin_group and vm_admin_group in user.groups_id:
                    role = 'admin'
                elif vm_manager_group and vm_manager_group in user.groups_id:
                    role = 'manager'
                elif user.has_group('base.group_user'):
                    role = 'user'

                user_roles.append({
                    'id': user.id,
                    'name': user.name,
                    'login': user.login,
                    'role': role,
                    'last_login': user.login_date.isoformat() if user.login_date else None,
                    'vm_count': request.env['vm_rental.machine'].search_count([
                        ('partner_id', '=', user.partner_id.id)
                    ])
                })

            return {
                'users': user_roles,
                'total_count': len(user_roles)
            }

        except Exception as e:
            return {'error': str(e)}

    @http.route('/vm_rental/assign_user_role', type='json', auth='user', methods=['POST'])
    def assign_user_role(self, user_id, role):
        """Назначение роли пользователю"""

        if not request.env.user.has_group('base.group_system'):
            return {'error': 'Admin access required'}

        try:
            user = request.env['res.users'].browse(user_id)
            if not user.exists():
                return {'error': 'User not found'}

            vm_admin_group = request.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)
            vm_manager_group = request.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)

            # Удаляем пользователя из всех VM групп
            if vm_admin_group and vm_admin_group in user.groups_id:
                user.groups_id = [(3, vm_admin_group.id)]
            if vm_manager_group and vm_manager_group in user.groups_id:
                user.groups_id = [(3, vm_manager_group.id)]

            # Назначаем новую роль
            if role == 'admin' and vm_admin_group:
                user.groups_id = [(4, vm_admin_group.id)]
            elif role == 'manager' and vm_manager_group:
                user.groups_id = [(4, vm_manager_group.id)]

            # Логируем изменение
            request.env['vm_rental.audit_log'].sudo().create({
                'vm_id': False,
                'action': 'user_role_changed',
                'success': True,
                'metadata': f'User {user.name} role changed to {role} by {request.env.user.name}'
            })

            return {'success': True, 'message': f'Role {role} assigned to {user.name}'}

        except Exception as e:
            return {'error': str(e)}

    @http.route('/vm_rental/bulk_assign_roles', type='json', auth='user', methods=['POST'])
    def bulk_assign_roles(self, user_ids, role):
        """Массовое назначение ролей"""

        if not request.env.user.has_group('base.group_system'):
            return {'error': 'Admin access required'}

        try:
            users = request.env['res.users'].browse(user_ids)
            vm_admin_group = request.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)
            vm_manager_group = request.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)

            success_count = 0
            for user in users:
                if not user.exists() or user.share:  # Пропускаем портальных пользователей
                    continue

                # Удаляем из всех VM групп
                if vm_admin_group and vm_admin_group in user.groups_id:
                    user.groups_id = [(3, vm_admin_group.id)]
                if vm_manager_group and vm_manager_group in user.groups_id:
                    user.groups_id = [(3, vm_manager_group.id)]

                # Назначаем новую роль
                if role == 'admin' and vm_admin_group:
                    user.groups_id = [(4, vm_admin_group.id)]
                elif role == 'manager' and vm_manager_group:
                    user.groups_id = [(4, vm_manager_group.id)]

                success_count += 1

            # Логируем массовое изменение
            request.env['vm_rental.audit_log'].sudo().create({
                'vm_id': False,
                'action': 'bulk_role_assignment',
                'success': True,
                'metadata': f'Bulk assigned {role} role to {success_count} users by {request.env.user.name}'
            })

            return {
                'success': True,
                'message': f'Successfully assigned {role} role to {success_count} users'
            }

        except Exception as e:
            return {'error': str(e)}

    @http.route('/vm_rental/user_access_report', type='http', auth='user', methods=['GET'])
    def generate_user_access_report(self):
        """Генерация отчета по доступу пользователей"""

        if not request.env.user.has_group('base.group_system'):
            return request.render('vm_rental.access_denied_template')

        try:
            # Собираем данные для отчета
            vm_admin_group = request.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)
            vm_manager_group = request.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)

            admin_users = vm_admin_group.users if vm_admin_group else request.env['res.users']
            manager_users = vm_manager_group.users if vm_manager_group else request.env['res.users']

            # Пользователи без VM доступа
            all_internal_users = request.env['res.users'].search([
                ('share', '=', False),
                ('active', '=', True)
            ])

            users_without_access = all_internal_users.filtered(
                lambda u: vm_admin_group not in u.groups_id and vm_manager_group not in u.groups_id
            )

            # Статистика VM
            vm_stats = request.env['vm_rental.machine'].read_group(
                [('state', '!=', 'terminated')],
                ['state'],
                ['state']
            )

            values = {
                'admin_users': admin_users,
                'manager_users': manager_users,
                'users_without_access': users_without_access,
                'vm_stats': vm_stats,
                'total_internal_users': len(all_internal_users),
                'access_coverage': ((len(admin_users) + len(manager_users)) / len(
                    all_internal_users) * 100) if all_internal_users else 0
            }

            return request.render('vm_rental.user_access_report_template', values)

        except Exception as e:
            return request.render('vm_rental.error_template', {'error': str(e)})