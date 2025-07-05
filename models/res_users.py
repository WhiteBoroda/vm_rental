# models/res_users.py
from odoo import models, fields, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    vm_rental_role = fields.Char(
        string="VM Rental Role",
        compute='_compute_vm_rental_role',
        store=False,
        help="Current VM Rental role of the user"
    )

    @api.depends('groups_id')
    def _compute_vm_rental_role(self):
        """Определяет роль пользователя в VM Rental системе"""
        for user in self:
            try:
                # Получаем группы VM Rental
                admin_group = self.env.ref('vm_rental.group_vm_rental_admin', raise_if_not_found=False)
                manager_group = self.env.ref('vm_rental.group_vm_rental_manager', raise_if_not_found=False)

                # Определяем роль пользователя
                if admin_group and admin_group in user.groups_id:
                    user.vm_rental_role = 'Administrator'
                elif manager_group and manager_group in user.groups_id:
                    user.vm_rental_role = 'Manager'
                elif user.has_group('base.group_user'):
                    user.vm_rental_role = 'Internal User'
                elif user.has_group('base.group_portal'):
                    user.vm_rental_role = 'Portal User'
                else:
                    user.vm_rental_role = 'No Access'

            except Exception:
                user.vm_rental_role = 'Unknown'