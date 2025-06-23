# models/res_config_settings.py
from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # VM Rental Settings
    vm_rental_default_trial_days = fields.Integer(
        string="Default Trial Period (Days)",
        default=7,
        config_parameter='vm_rental.default_trial_days',
        help="Default number of days for trial periods"
    )

    vm_rental_auto_suspend = fields.Boolean(
        string="Auto-suspend Expired VMs",
        default=True,
        config_parameter='vm_rental.auto_suspend',
        help="Automatically suspend VMs when subscription expires"
    )

    # Resource Limits
    vm_rental_max_cores = fields.Integer(
        string="Maximum CPU Cores",
        default=64,
        config_parameter='vm_rental.max_cores',
        help="Maximum number of CPU cores per VM"
    )

    vm_rental_max_memory = fields.Integer(
        string="Maximum Memory (MiB)",
        default=131072,  # 128GB
        config_parameter='vm_rental.max_memory',
        help="Maximum memory per VM in MiB"
    )

    vm_rental_max_disk = fields.Integer(
        string="Maximum Disk (GiB)",
        default=10240,  # 10TB
        config_parameter='vm_rental.max_disk',
        help="Maximum disk size per VM in GiB"
    )

    # Backup Settings
    vm_rental_auto_backup = fields.Boolean(
        string="Enable Auto Backup",
        default=False,
        config_parameter='vm_rental.auto_backup',
        help="Enable automatic configuration backups"
    )

    vm_rental_backup_retention_days = fields.Integer(
        string="Backup Retention (Days)",
        default=30,
        config_parameter='vm_rental.backup_retention_days',
        help="Number of days to keep automatic backups"
    )

    # Module version field
    vm_rental_module_version = fields.Char(
        string="Module Version",
        compute='_compute_vm_rental_module_version',
        help="Current version of VM Rental module"
    )

    # System statistics field
    vm_rental_system_stats = fields.Char(
        string="System Statistics",
        compute='_compute_vm_rental_system_stats',
        help="Basic system statistics"
    )

    @api.depends()
    def _compute_vm_rental_module_version(self):
        """Получает версию модуля из манифеста"""
        for record in self:
            try:
                module = self.env['ir.module.module'].search([
                    ('name', '=', 'vm_rental'),
                    ('state', '=', 'installed')
                ], limit=1)

                if module:
                    # Получаем версию из latest_version или из installed_version
                    version = module.latest_version or module.installed_version
                    record.vm_rental_module_version = f"VM Rental v{version}" if version else "VM Rental (Unknown Version)"
                else:
                    record.vm_rental_module_version = "VM Rental (Not Installed)"
            except Exception:
                record.vm_rental_module_version = "VM Rental v1.3.0"

    @api.depends()
    def _compute_vm_rental_system_stats(self):
        """Получает базовую статистику системы"""
        for record in self:
            try:
                # Подсчитываем основные метрики
                total_vms = self.env['vm_rental.machine'].search_count([])
                active_vms = self.env['vm_rental.machine'].search_count([('state', '=', 'active')])
                hypervisors = self.env['hypervisor.server'].search_count([])

                record.vm_rental_system_stats = f"{total_vms} VMs total, {active_vms} active\n{hypervisors} hypervisor(s) configured"
            except Exception:
                record.vm_rental_system_stats = "Statistics unavailable"

    vm_rental_manager_users = fields.Many2many(
        'res.users',
        'vm_rental_manager_users_rel',
        'config_id',
        'user_id',
        string="VM Rental Managers",
        help="Users who can manage VMs, pricing plans, and hypervisors"
    )

    vm_rental_admin_users = fields.Many2many(
        'res.users',
        'vm_rental_admin_users_rel',
        'config_id',
        'user_id',
        string="VM Rental Administrators",
        help="Users with full administrative access to VM Rental module"
    )

    vm_portal_users = fields.Many2many(
        'res.users',
        'vm_rental_portal_users_rel',
        'config_id',
        'user_id',
        string="VM Portal Users",
        help="Portal users who can manage their own VMs"
    )

    # Автоматическое добавление новых пользователей в группы
    auto_assign_vm_access = fields.Boolean(
        string="Auto-assign VM Access",
        default=False,
        config_parameter='vm_rental.auto_assign_access',
        help="Automatically assign basic VM access to new internal users"
    )

    # Настройки по умолчанию для новых пользователей
    default_vm_user_type = fields.Selection([
        ('none', 'No VM Access'),
        ('user', 'Basic User'),
        ('manager', 'VM Manager'),
        ('admin', 'VM Administrator')
    ], string="Default VM Access for New Users",
        default='none',
        config_parameter='vm_rental.default_user_type',
        help="Default VM access level for newly created internal users")

    @api.model
    def get_values(self):
        """Получение текущих значений для пользователей в группах"""
        res = super(ResConfigSettings, self).get_values()

        # Получаем группы VM Rental
        vm_manager_group = self.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)
        vm_admin_group = self.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)

        # Получаем пользователей из групп
        manager_users = vm_manager_group.users.ids if vm_manager_group else []
        admin_users = vm_admin_group.users.ids if vm_admin_group else []

        # Портальные пользователи с VM доступом (у которых есть VM)
        portal_users_with_vms = []
        if portal_group:
            portal_users_with_vms = self.env['res.users'].search([
                ('groups_id', 'in', [portal_group.id]),
                ('partner_id.vm_instance_ids', '!=', False)
            ]).ids

        res.update({
            'vm_rental_manager_users': [(6, 0, manager_users)],
            'vm_rental_admin_users': [(6, 0, admin_users)],
            'vm_portal_users': [(6, 0, portal_users_with_vms)],
        })

        return res

    def set_values(self):
        """Применение изменений в группах пользователей"""
        super(ResConfigSettings, self).set_values()

        # Получаем группы
        vm_manager_group = self.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)
        vm_admin_group = self.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)

        if vm_manager_group:
            # Обновляем группу менеджеров VM
            current_managers = set(vm_manager_group.users.ids)
            new_managers = set(self.vm_rental_manager_users.ids)

            # Удаляем пользователей, которых больше нет в списке
            users_to_remove = current_managers - new_managers
            if users_to_remove:
                vm_manager_group.users = [(3, uid) for uid in users_to_remove]

            # Добавляем новых пользователей
            users_to_add = new_managers - current_managers
            if users_to_add:
                vm_manager_group.users = [(4, uid) for uid in users_to_add]

        if vm_admin_group:
            # Обновляем группу администраторов VM
            current_admins = set(vm_admin_group.users.ids)
            new_admins = set(self.vm_rental_admin_users.ids)

            # Удаляем пользователей
            users_to_remove = current_admins - new_admins
            if users_to_remove:
                vm_admin_group.users = [(3, uid) for uid in users_to_remove]

            # Добавляем новых пользователей
            users_to_add = new_admins - current_admins
            if users_to_add:
                vm_admin_group.users = [(4, uid) for uid in users_to_add]

        # Логируем изменения
        self._log_group_changes()

    def _log_group_changes(self):
        """Логирование изменений в группах для аудита"""
        message = "VM Rental user groups updated:\n"
        message += f"- VM Managers: {len(self.vm_rental_manager_users)} users\n"
        message += f"- VM Administrators: {len(self.vm_rental_admin_users)} users\n"
        message += f"- Portal Users with VMs: {len(self.vm_portal_users)} users"

        # Записываем в лог изменений
        self.env['vm_rental.audit_log'].sudo().create({
            'vm_id': False,  # Системное действие
            'action': 'user_groups_updated',
            'success': True,
            'metadata': message,
        })

    def action_sync_portal_users(self):
        """Синхронизация портальных пользователей с VM"""
        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)
        if not portal_group:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'Portal group not found',
                    'type': 'danger',
                }
            }

        # Находим всех портальных пользователей с VM
        portal_users_with_vms = self.env['res.users'].search([
            ('groups_id', 'in', [portal_group.id]),
            ('partner_id.vm_instance_ids', '!=', False)
        ])

        # Обновляем поле
        self.vm_portal_users = [(6, 0, portal_users_with_vms.ids)]

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Synchronized {len(portal_users_with_vms)} portal users with VMs',
                'type': 'success',
            }
        }

    def action_assign_vm_access_to_users(self):
        """Массовое назначение VM доступа пользователям"""
        if not self.default_vm_user_type or self.default_vm_user_type == 'none':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Warning',
                    'message': 'Please select default VM access type first',
                    'type': 'warning',
                }
            }

        # Находим внутренних пользователей без VM доступа
        internal_users = self.env['res.users'].search([
            ('share', '=', False),  # Внутренние пользователи
            ('active', '=', True),
            ('id', '!=', 1),  # Исключаем пользователя OdooBot
        ])

        vm_manager_group = self.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)
        vm_admin_group = self.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)

        # Фильтруем пользователей, у которых еще нет VM доступа
        users_without_vm_access = internal_users.filtered(
            lambda u: vm_manager_group not in u.groups_id and vm_admin_group not in u.groups_id
        )

        if not users_without_vm_access:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Info',
                    'message': 'All internal users already have VM access',
                    'type': 'info',
                }
            }

        # Назначаем доступ в зависимости от выбранного типа
        assigned_count = 0
        if self.default_vm_user_type == 'manager' and vm_manager_group:
            vm_manager_group.users = [(4, uid) for uid in users_without_vm_access.ids]
            assigned_count = len(users_without_vm_access)
        elif self.default_vm_user_type == 'admin' and vm_admin_group:
            vm_admin_group.users = [(4, uid) for uid in users_without_vm_access.ids]
            assigned_count = len(users_without_vm_access)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Assigned VM {self.default_vm_user_type} access to {assigned_count} users',
                'type': 'success',
            }
        }

    def action_remove_all_vm_access(self):
        """Удаление VM доступа у всех пользователей (кроме администраторов)"""
        vm_manager_group = self.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)

        if vm_manager_group:
            removed_count = len(vm_manager_group.users)
            vm_manager_group.users = [(5, 0, 0)]  # Удаляем всех пользователей

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Removed VM access from {removed_count} users',
                    'type': 'success',
                }
            }

    @api.model
    def auto_assign_vm_access_to_new_user(self, user_id):
        """Автоматическое назначение VM доступа новому пользователю"""
        auto_assign = self.env['ir.config_parameter'].sudo().get_param('vm_rental.auto_assign_access', False)
        default_type = self.env['ir.config_parameter'].sudo().get_param('vm_rental.default_user_type', 'none')

        if not auto_assign or default_type == 'none':
            return

        user = self.env['res.users'].browse(user_id)
        if user.share:  # Портальный пользователь
            return

        vm_manager_group = self.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)
        vm_admin_group = self.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)

        if default_type == 'manager' and vm_manager_group:
            vm_manager_group.users = [(4, user_id)]
        elif default_type == 'admin' and vm_admin_group:
            vm_admin_group.users = [(4, user_id)]


# Расширяем модель res.users для автоматического назначения доступа
class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        """Автоматическое назначение VM доступа при создании пользователя"""
        users = super(ResUsers, self).create(vals_list)

        # Проверяем каждого созданного пользователя
        for user in users:
            if not user.share:  # Только для внутренних пользователей
                self.env['res.config.settings'].auto_assign_vm_access_to_new_user(user.id)

        return users

    # Добавляем поле для отображения VM групп в профиле пользователя
    vm_rental_role = fields.Selection([
        ('none', 'No VM Access'),
        ('user', 'Basic User'),
        ('manager', 'VM Manager'),
        ('admin', 'VM Administrator')
    ], string="VM Rental Role", compute='_compute_vm_rental_role', store=False)

    @api.depends('groups_id')
    def _compute_vm_rental_role(self):
        """Определение роли пользователя в VM Rental"""
        vm_manager_group = self.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)
        vm_admin_group = self.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)

        for user in self:
            if vm_admin_group and vm_admin_group in user.groups_id:
                user.vm_rental_role = 'admin'
            elif vm_manager_group and vm_manager_group in user.groups_id:
                user.vm_rental_role = 'manager'
            elif user.has_group('base.group_user'):
                user.vm_rental_role = 'user'
            else:
                user.vm_rental_role = 'none'