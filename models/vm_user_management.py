# vm_rental/models/vm_user_management.py
from odoo import models, api
from datetime import timedelta


class VmUserManagement(models.TransientModel):
    """Модель для сложных операций управления пользователями VM Rental"""
    _name = 'vm.user.management'
    _description = 'VM User Management Helper'

    @api.model
    def get_detailed_user_report(self):
        """Детальный отчет по пользователям"""
        vm_admin_group = self.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)
        vm_manager_group = self.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)

        admin_count = len(vm_admin_group.users) if vm_admin_group else 0
        manager_count = len(vm_manager_group.users) if vm_manager_group else 0
        total_internal = self.env['res.users'].search_count([('share', '=', False), ('active', '=', True)])
        total_portal = self.env['res.users'].search_count([('share', '=', True), ('active', '=', True)])

        # VM статистика
        active_vms = self.env['vm_rental.machine'].search_count([('state', '=', 'active')])
        total_vms = self.env['vm_rental.machine'].search_count([])

        # Пользователи без VM доступа
        users_without_access = total_internal - admin_count - manager_count
        access_coverage = (admin_count + manager_count) / total_internal * 100 if total_internal > 0 else 0

        # Рекомендации
        if access_coverage >= 75:
            recommendation = "✓ Good access coverage"
        elif access_coverage >= 50:
            recommendation = "⚠ Consider assigning VM access to more users"
        else:
            recommendation = "❌ Low access coverage - many users lack VM access"

        report = """VM Rental User Access Report:

=== USER GROUPS ===
• VM Administrators: %d users
• VM Managers: %d users
• Internal Users (total): %d users
• Portal Users: %d users

=== ACCESS ANALYSIS ===
• Users with VM access: %d
• Users without VM access: %d
• Access coverage: %.1f%%

=== VM STATISTICS ===
• Total VMs: %d
• Active VMs: %d

=== RECOMMENDATIONS ===
%s

Generated: %s
""" % (
            admin_count, manager_count, total_internal, total_portal,
            admin_count + manager_count, users_without_access, access_coverage,
            total_vms, active_vms,
            recommendation,
            self.env['ir.fields'].now().strftime('%Y-%m-%d %H:%M:%S')
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Detailed VM User Report',
                'message': report,
                'type': 'info',
                'sticky': True,
            }
        }

    @api.model
    def bulk_assign_vm_manager_role(self, user_ids=None):
        """Массовое назначение роли VM Manager"""
        vm_manager_group = self.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)
        if not vm_manager_group:
            return False

        if user_ids:
            users = self.env['res.users'].browse(user_ids)
        else:
            users = self.env['res.users'].search([('share', '=', False), ('active', '=', True)])

        assigned_count = 0
        for user in users:
            if vm_manager_group not in user.groups_id:
                user.groups_id = [(4, vm_manager_group.id)]
                assigned_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'VM Manager Role Assigned',
                'message': f'Assigned VM Manager role to {assigned_count} users',
                'type': 'success' if assigned_count > 0 else 'info',
            }
        }

    @api.model
    def get_activity_statistics(self):
        """Статистика активности пользователей"""
        # Пользователи, которые входили в систему за последние 30 дней
        recent_logins = self.env['res.users'].search_count([
            ('login_date', '>=', self.env['ir.fields'].now() - timedelta(days=30)),
            ('active', '=', True)
        ])

        # Пользователи, которые создали VM за последние 30 дней
        vm_creators = self.env['vm_rental.machine'].read_group(
            [('create_date', '>=', self.env['ir.fields'].now() - timedelta(days=30))],
            ['create_uid'],
            ['create_uid']
        )

        total_internal = self.env['res.users'].search_count([('share', '=', False), ('active', '=', True)])
        total_portal = self.env['res.users'].search_count([('share', '=', True), ('active', '=', True)])

        activity_rate = (recent_logins / (total_internal + total_portal) * 100) if (total_internal + total_portal) > 0 else 0

        return {
            'recent_logins': recent_logins,
            'vm_creators': len(vm_creators),
            'activity_rate': activity_rate,
            'total_users': total_internal + total_portal
        }