# models/vm_user_manager.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class VmUserManager(models.TransientModel):
    """Интерфейс управления пользователями VM Rental"""
    _name = 'vm.user.manager'
    _description = 'VM User Manager'

    # Поля для управления пользователями
    admin_users = fields.Many2many(
        'res.users',
        'vm_user_manager_admin_rel',
        string="VM Administrators",
        domain="[('share', '=', False), ('active', '=', True)]",
        help="Users with full administrative access to VM Rental"
    )

    manager_users = fields.Many2many(
        'res.users',
        'vm_user_manager_manager_rel',
        string="VM Managers",
        domain="[('share', '=', False), ('active', '=', True)]",
        help="Users who can create and manage VMs"
    )

    portal_users = fields.Many2many(
        'res.users',
        'vm_user_manager_portal_rel',
        string="Portal Users with VM Access",
        domain="[('share', '=', True), ('active', '=', True)]",
        help="Portal users who can access their VMs"
    )

    # Статистика
    total_internal_users = fields.Integer(
        string="Total Internal Users",
        compute='_compute_statistics'
    )

    total_portal_users = fields.Integer(
        string="Total Portal Users",
        compute='_compute_statistics'
    )

    users_without_access = fields.Integer(
        string="Users without VM Access",
        compute='_compute_statistics'
    )

    access_coverage = fields.Float(
        string="Access Coverage (%)",
        compute='_compute_statistics'
    )

    @api.model
    def default_get(self, fields_list):
        """Загружаем текущих пользователей из групп"""
        res = super().default_get(fields_list)

        # Получаем группы VM Rental
        admin_group = self.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)
        manager_group = self.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)

        if admin_group:
            res['admin_users'] = [(6, 0, admin_group.users.ids)]
        if manager_group:
            res['manager_users'] = [(6, 0, manager_group.users.ids)]

        return res

    @api.depends('admin_users', 'manager_users')
    def _compute_statistics(self):
        """Вычисляет статистику пользователей"""
        for record in self:
            # Общее количество пользователей
            total_internal = self.env['res.users'].search_count([
                ('share', '=', False),
                ('active', '=', True)
            ])
            total_portal = self.env['res.users'].search_count([
                ('share', '=', True),
                ('active', '=', True)
            ])

            # Пользователи с VM доступом
            vm_users_count = len(record.admin_users) + len(record.manager_users)
            users_without = total_internal - vm_users_count

            # Процент покрытия
            coverage = (vm_users_count / total_internal * 100) if total_internal > 0 else 0

            record.total_internal_users = total_internal
            record.total_portal_users = total_portal
            record.users_without_access = max(0, users_without)
            record.access_coverage = coverage

    def action_apply_changes(self):
        """Применяет изменения в группах пользователей"""
        self.ensure_one()

        # Получаем группы
        admin_group = self.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)
        manager_group = self.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)

        if not admin_group or not manager_group:
            raise UserError(_("VM Rental security groups not found"))

        try:
            # Обновляем группу администраторов
            admin_group.users = [(6, 0, self.admin_users.ids)]

            # Обновляем группу менеджеров (исключаем админов чтобы избежать дублирования)
            manager_only_users = self.manager_users.filtered(lambda u: u not in self.admin_users)
            manager_group.users = [(6, 0, (self.admin_users + manager_only_users).ids)]

            # Логируем изменения
            self.env['vm_rental.audit_log'].sudo().create({
                'vm_id': False,
                'action': 'user_groups_updated',
                'success': True,
                'metadata': f'VM user groups updated by {self.env.user.name}. '
                            f'Admins: {len(self.admin_users)}, Managers: {len(self.manager_users)}'
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('VM user access has been updated successfully!'),
                    'type': 'success',
                }
            }

        except Exception as e:
            raise UserError(_("Error updating user groups: %s") % str(e))

    def action_bulk_assign_managers(self):
        """Массовое назначение роли менеджера всем внутренним пользователям"""
        self.ensure_one()

        all_internal_users = self.env['res.users'].search([
            ('share', '=', False),
            ('active', '=', True),
            ('id', '!=', 1)  # Исключаем OdooBot
        ])

        # Добавляем всех к менеджерам (кроме уже назначенных админов)
        new_managers = all_internal_users.filtered(lambda u: u not in self.admin_users)
        self.manager_users = [(6, 0, new_managers.ids)]

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk Assignment'),
                'message': _('All internal users have been assigned VM Manager role. Click "Apply Changes" to save.'),
                'type': 'info',
            }
        }

    def action_clear_all_access(self):
        """Удаляет VM доступ у всех пользователей"""
        self.ensure_one()

        self.admin_users = [(5, 0, 0)]  # Очистить все
        self.manager_users = [(5, 0, 0)]  # Очистить все

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Access Cleared'),
                'message': _('VM access has been removed from all users. Click "Apply Changes" to save.'),
                'type': 'warning',
            }
        }

    def action_reset_to_current(self):
        """Сбрасывает изменения к текущему состоянию групп"""
        # Просто пересоздаем визард с текущими данными
        return {
            'type': 'ir.actions.act_window',
            'name': _('VM User Manager'),
            'res_model': 'vm.user.manager',
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context
        }

    def action_view_user_report(self):
        """Показывает детальный отчет по пользователям"""
        return self.env['vm.user.management'].get_detailed_user_report()

    def action_open_user_dashboard(self):
        """Открывает дашборд пользователей VM"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('VM Users Dashboard'),
            'res_model': 'res.users',
            'view_mode': 'tree,form',
            'domain': [('share', '=', False), ('active', '=', True)],
            'context': {
                'search_default_vm_admins': 1,
                'search_default_vm_managers': 1
            }
        }