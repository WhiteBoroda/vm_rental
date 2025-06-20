# vm_rental/controllers/portal_vm.py (ОБНОВЛЕННАЯ ВЕРСИЯ)
from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
import logging

_logger = logging.getLogger(__name__)


class PortalVM(CustomerPortal):
    _items_per_page = 20

    def _get_vm_count(self, partner_id):
        """Получает количество VM для партнера"""
        domain = [('partner_id', 'child_of', partner_id)]
        try:
            count = request.env['vm_rental.machine'].search_count(domain)
        except Exception as e:
            _logger.error(f"Error counting VMs for partner {partner_id}: {e}")
            count = 0
        return count

    def _prepare_portal_layout_values(self):
        """Добавляет счетчик VM в портал"""
        values = super()._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        values['vms_count'] = self._get_vm_count(partner.commercial_partner_id.id)
        return values

    def _get_vm_domain(self):
        """Возвращает домен для поиска VM текущего пользователя"""
        partner = request.env.user.partner_id
        return [('partner_id', 'child_of', partner.commercial_partner_id.id)]

    def _vm_check_access(self, vm_id, access_token=None):
        """Проверяет доступ к VM и возвращает объект VM"""
        vm = request.env['vm_rental.machine'].browse([vm_id])
        vm_sudo = vm.sudo()

        try:
            # Проверяем, что VM существует и пользователь имеет к ней доступ
            vm.check_access_rights('read')
            vm.check_access_rule('read')
        except (AccessError, MissingError):
            return None

        # Дополнительная проверка владения VM
        partner = request.env.user.partner_id
        if vm_sudo.partner_id.id not in partner.commercial_partner_id.child_ids.ids + [
            partner.commercial_partner_id.id]:
            return None

        return vm_sudo

    @http.route(['/my/vms', '/my/vms/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_vms(self, page=1, sortby=None, filterby=None, search=None, search_in='name', **kw):
        """Главная страница VM в портале"""
        values = self._prepare_portal_layout_values()
        VmInstance = request.env['vm_rental.machine']

        # Базовый домен
        domain = self._get_vm_domain()

        # Поисковые опции
        searchbar_sortings = {
            'name': {'label': _('Name'), 'order': 'name'},
            'date': {'label': _('Creation Date'), 'order': 'create_date desc'},
            'state': {'label': _('Status'), 'order': 'state'},
            'end_date': {'label': _('Expiry Date'), 'order': 'end_date desc'},
        }

        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'active': {'label': _('Active'), 'domain': [('state', '=', 'active')]},
            'stopped': {'label': _('Stopped'), 'domain': [('state', '=', 'stopped')]},
            'pending': {'label': _('Pending'), 'domain': [('state', '=', 'pending')]},
            'suspended': {'label': _('Suspended'), 'domain': [('state', '=', 'suspended')]},
            'trial': {'label': _('Trial'), 'domain': [('is_trial', '=', True)]},
        }

        searchbar_inputs = {
            'name': {'input': 'name', 'label': _('Search in VM Name')},
            'vm_ref': {'input': 'vm_ref', 'label': _('Search in VM ID')},
        }

        # Применяем сортировку по умолчанию
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']

        # Применяем фильтрацию по умолчанию
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        # Применяем поиск
        if search and search_in:
            if search_in == 'name':
                domain += [('name', 'ilike', search)]
            elif search_in == 'vm_ref':
                domain += [('hypervisor_vm_ref', 'ilike', search)]

        # Подсчет и пагинация
        vm_count = VmInstance.search_count(domain)
        pager = portal_pager(
            url="/my/vms",
            url_args={'sortby': sortby, 'filterby': filterby, 'search_in': search_in, 'search': search},
            total=vm_count,
            page=page,
            step=self._items_per_page
        )

        # Получаем VM
        try:
            vms = VmInstance.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        except Exception as e:
            _logger.error(f"Error searching VMs: {e}")
            vms = VmInstance.browse([])

        values.update({
            'vms': vms,
            'page_name': 'vms',
            'pager': pager,
            'default_url': '/my/vms',
            'searchbar_sortings': searchbar_sortings,
            'searchbar_filters': searchbar_filters,
            'searchbar_inputs': searchbar_inputs,
            'sortby': sortby,
            'filterby': filterby,
            'search_in': search_in,
            'search': search,
        })
        return request.render("vm_rental.portal_my_vms", values)

    @http.route(['/my/vms/<int:vm_id>'], type='http', auth='user', website=True)
    def portal_vm_detail(self, vm_id, access_token=None, **kwargs):
        """Детальная страница VM"""
        vm = self._vm_check_access(vm_id, access_token)
        if not vm:
            return request.not_found()

        values = {
            'vm': vm,
            'page_name': 'vm_detail',
        }
        return request.render("vm_rental.portal_vm_detail", values)

    @http.route(['/my/vms/console/<int:vm_id>'], type='http', auth='user', website=True)
    def portal_vm_console(self, vm_id, **kwargs):
        """Страница консоли VM"""
        vm = self._vm_check_access(vm_id)
        if not vm:
            return request.not_found()

        # Проверяем, что VM активна и имеет ссылку
        if vm.state != 'active' or not vm.hypervisor_vm_ref:
            return request.render("vm_rental.portal_error_page", {
                'status_code': 'Console Unavailable',
                'status_message': 'Console is only available for active virtual machines.'
            })

        try:
            # Получаем URL консоли
            service = vm._get_hypervisor_service()
            console_url = service.get_console_url(vm.hypervisor_node_name, vm.hypervisor_vm_ref)

            return request.render("vm_rental.portal_vm_console", {
                'vm': vm,
                'console_url': console_url
            })

        except Exception as e:
            _logger.error(f"Could not generate console URL for VM {vm.id}: {e}", exc_info=True)
            return request.render("vm_rental.portal_error_page", {
                'status_code': 'Console Error',
                'status_message': 'Could not generate console URL. Please contact support if the problem persists.'
            })

    @http.route(['/my/vms/<int:vm_id>/snapshots'], type='http', auth='user', website=True)
    def portal_vm_snapshots(self, vm_id, **kwargs):
        """Страница снапшотов VM"""
        vm = self._vm_check_access(vm_id)
        if not vm:
            return request.not_found()

        # Получаем снапшоты, отсортированные по дате создания
        snapshots = vm.snapshot_ids.sorted('create_date', reverse=True)

        return request.render("vm_rental.portal_vm_snapshots_template", {
            'vm': vm,
            'snapshots': snapshots,
            'page_name': 'vm_snapshots',
        })

    def _prepare_home_portal_values(self, counters):
        """Добавляем счетчик VM на главную страницу портала"""
        values = super()._prepare_home_portal_values(counters)

        if 'vms_count' in counters:
            partner = request.env.user.partner_id
            values['vms_count'] = self._get_vm_count(partner.commercial_partner_id.id)

        return values

    # Переопределяем главную страницу портала для добавления VM
    @http.route()
    def home(self, **kw):
        values = self._prepare_home_portal_values(['vms_count'])
        return request.render("portal.portal_my_home", values)


# Добавляем VM в главное меню портала
class PortalAccount(CustomerPortal):
    OPTIONAL_BILLING_FIELDS = ["zipcode", "state_id", "vat", "company_name"]
    MANDATORY_BILLING_FIELDS = ["name", "phone", "email", "street", "city", "country_id"]

    def details_form_validate(self, data):
        error, error_message = super().details_form_validate(data)
        # Можно добавить дополнительную валидацию для VM-related полей
        return error, error_message