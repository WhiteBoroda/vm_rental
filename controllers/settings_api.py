# vm_rental/controllers/settings_api.py
from odoo import http
from odoo.http import request

class VmRentalSettingsAPI(http.Controller):

    @http.route('/vm_rental/settings/test_server', type='json', auth='user', methods=['POST'])
    def test_server_connection(self, server_id):
        # Проверяем права доступа пользователя (должен быть администратором)
        if not request.env.user.has_group('base.group_system'):
            return {'success': False, 'message': 'Access Denied.'}

        # ИСПРАВЛЕНИЕ: Используем универсальную модель 'hypervisor.server'
        server = request.env['hypervisor.server'].browse(int(server_id))
        if not server.exists():
            return {'success': False, 'message': 'Server not found.'}

        # Метод test_and_fetch_resources() уже является универсальным
        try:
            server.test_and_fetch_resources()
            # Возвращаем успешный результат, так как метод сам обновляет статус
            return {'success': True, 'message': server.status_message}
        except Exception as e:
            # В случае ошибки метод сам запишет ее в status_message
            return {'success': False, 'message': str(e)}