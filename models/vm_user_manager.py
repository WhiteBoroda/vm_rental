# models/vm_user_manager.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


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
        """ИСПРАВЛЕНИЕ: Загружаем текущих пользователей из групп"""
        res = super().default_get(fields_list)

        try:
            # Получаем группы VM Rental
            admin_group = self.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)
            manager_group = self.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)

            _logger.info(f"Loading VM groups - Admin: {admin_group}, Manager: {manager_group}")

            if admin_group and 'admin_users' in fields_list:
                admin_user_ids = admin_group.users.ids
                res['admin_users'] = [(6, 0, admin_user_ids)]
                _logger.info(f"Loaded {len(admin_user_ids)} admin users")

            if manager_group and 'manager_users' in fields_list:
                # Получаем всех менеджеров (включая админов, т.к. админы наследуют права менеджеров)
                manager_user_ids = manager_group.users.ids
                res['manager_users'] = [(6, 0, manager_user_ids)]
                _logger.info(f"Loaded {len(manager_user_ids)} manager users")

        except Exception as e:
            _logger.error(f"Error loading user groups: {e}")

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

            # Пользователи с VM доступом (без дублирования)
            all_vm_users = record.admin_users | record.manager_users
            vm_users_count = len(all_vm_users)
            users_without = total_internal - vm_users_count

            # Процент покрытия
            coverage = (vm_users_count / total_internal * 100) if total_internal > 0 else 0

            record.total_internal_users = total_internal
            record.total_portal_users = total_portal
            record.users_without_access = max(0, users_without)
            record.access_coverage = coverage

    def action_apply_changes(self):
        """ИСПРАВЛЕНИЕ: Применяет изменения в группах пользователей"""
        self.ensure_one()

        try:
            # Получаем группы
            admin_group = self.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)
            manager_group = self.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)

            if not admin_group or not manager_group:
                raise UserError(_("VM Rental security groups not found. Please check module installation."))

            _logger.info(f"Applying changes - Admins: {len(self.admin_users)}, Managers: {len(self.manager_users)}")

            # ИСПРАВЛЕНИЕ: Правильно обновляем группы

            # 1. Обновляем группу администраторов
            admin_group.write({'users': [(6, 0, self.admin_users.ids)]})
            _logger.info(f"Updated admin group with {len(self.admin_users)} users")

            # 2. Обновляем группу менеджеров
            # Включаем всех выбранных менеджеров (админы автоматически наследуют права через implied_ids)
            manager_group.write({'users': [(6, 0, self.manager_users.ids)]})
            _logger.info(f"Updated manager group with {len(self.manager_users)} users")

            # Логируем изменения в аудит
            try:
                self.env['vm_rental.audit_log'].sudo().create({
                    'vm_id': False,
                    'action': 'user_group_update',
                    'success': True,
                    'metadata': f'VM user groups updated by {self.env.user.name}. '
                                f'Admins: {len(self.admin_users)}, Managers: {len(self.manager_users)}'
                })
            except Exception as audit_error:
                _logger.warning(f"Failed to create audit log: {audit_error}")

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
            _logger.error(f"Error applying VM user changes: {e}")
            raise UserError(_("Error updating user groups: %s") % str(e))

    def action_bulk_assign_managers(self):
        """Массовое назначение роли менеджера всем внутренним пользователям"""
        self.ensure_one()

        all_internal_users = self.env['res.users'].search([
            ('share', '=', False),
            ('active', '=', True),
            ('id', '!=', 1)  # Исключаем OdooBot
        ])

        # Добавляем всех к менеджерам
        self.manager_users = [(6, 0, all_internal_users.ids)]

        # Сохраняем админов как есть
        current_admin_ids = self.admin_users.ids
        overlap_users = set(current_admin_ids) & set(all_internal_users.ids)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bulk Assignment'),
                'message': _(
                    'All %d internal users have been assigned VM Manager role. %d users have both Admin and Manager roles. Click "Apply Changes" to save.') % (
                               len(all_internal_users), len(overlap_users)
                           ),
                'type': 'info',
            }
        }

    def action_clear_all_access(self):
        """Удаляет VM доступ у всех пользователей"""
        self.ensure_one()

        # Очищаем все поля
        self.admin_users = [(5, 0, 0)]  # Удаляем все связи
        self.manager_users = [(5, 0, 0)]
        self.portal_users = [(5, 0, 0)]

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Access Cleared'),
                'message': _('VM access removed from all users. Click "Apply Changes" to save.'),
                'type': 'warning',
            }
        }

    def action_open_user_dashboard(self):
        """Открывает dashboard пользователей"""
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

    def action_generate_detailed_report(self):
        """Генерирует детальный отчет по пользователям"""
        return self.env['vm.user.management'].get_detailed_user_report()

    def action_debug_groups(self):
        """Отладочный метод для проверки групп"""
        self.ensure_one()

        admin_group = self.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)
        manager_group = self.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)

        debug_info = f"""
        DEBUG INFO:
        - Admin Group: {admin_group} (ID: {admin_group.id if admin_group else 'Not Found'})
        - Manager Group: {manager_group} (ID: {manager_group.id if manager_group else 'Not Found'})
        - Current Admin Users: {len(self.admin_users)} ({[u.name for u in self.admin_users]})
        - Current Manager Users: {len(self.manager_users)} ({[u.name for u in self.manager_users]})
        - Current User: {self.env.user.name} (Has System Group: {self.env.user.has_group('base.group_system')})
        """

        _logger.info(debug_info)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Debug Info',
                'message': debug_info,
                'type': 'info',
                'sticky': True
            }
        }

    @api.model
    def create(self, vals):
        """Override create to log creation"""
        _logger.info(f"Creating vm.user.manager with vals: {vals}")
        record = super().create(vals)
        _logger.info(f"Created vm.user.manager record: {record.id}")
        return record

    def write(self, vals):
        """Override write to log updates"""
        _logger.info(f"Updating vm.user.manager {self.ids} with vals: {vals}")
        result = super().write(vals)
        _logger.info(f"Updated vm.user.manager successfully")
        return result