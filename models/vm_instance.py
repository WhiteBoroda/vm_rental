# Файл: /models/vm_instance.py

# FIX: Добавлен 'api' для работы декораторов.
from odoo import models, fields, api
# FIX: 'date' и 'timedelta' заменены на 'relativedelta' для корректной работы с месяцами.
from dateutil.relativedelta import relativedelta
# RECOMMENDATION: Импорт ProxmoxService здесь понадобится для реальной интеграции.
from .proxmox_api import ProxmoxService
import logging

_logger = logging.getLogger(__name__)

class VmInstance(models.Model):
    _name = 'vm.instance'
    _description = 'Virtual Machine Instance'
    def _get_proxmox_service(self):
    return ProxmoxService(self.env)

    name = fields.Char(string="VM Name", required=True)
    proxmox_vm_id = fields.Char(string="Proxmox VM ID", readonly=True)
    state = fields.Selection([
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated')
    ], string="State", default="pending", readonly=True, copy=False)
    start_date = fields.Date(string="Start Date", readonly=True)
    end_date = fields.Date(string="End Date", readonly=True)
    
    # RECOMMENDATION: Замените partner_id на user_id для большей безопасности в портале.
    # Если оставляете partner_id, убедитесь, что у партнера есть связанный пользователь.
    partner_id = fields.Many2one('res.partner', string="Customer", required=True)
    user_id = fields.Many2one('res.users', string="User", related='partner_id.user_ids', store=True, readonly=True)

    # FIX: Это правильный способ связать заказы с ВМ.
    sale_order_ids = fields.One2many('sale.order', 'vm_instance_id', string="Orders")
    
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Currency")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    total_amount = fields.Monetary(string="Total Paid", compute="_compute_total_amount", store=True)

    @api.depends('sale_order_ids.state', 'sale_order_ids.amount_total')
    def _compute_total_amount(self):
        for rec in self:
            # Считаем только оплаченные или подтвержденные заказы
            paid_orders = rec.sale_order_ids.filtered(lambda o: o.state in ['sale', 'done'])
            rec.total_amount = sum(paid_orders.mapped('amount_total'))

    def extend_period(self, months=1):
        """ Продлевает срок действия ВМ и активирует ее. """
        self.ensure_one()
        # FIX: Используем relativedelta для корректного добавления месяцев.
        new_end_date = self.end_date if self.end_date else fields.Date.today()
        new_end_date += relativedelta(months=months)
        
        self.write({
            'end_date': new_end_date,
            'state': 'active'
        })
        if self.state == 'suspended' and self.proxmox_vm_id:
             service = self._get_proxmox_service()
             service.start_vm(self.proxmox_vm_id)
        
        _logger.info(f"VM {self.name} extended until {self.end_date}")

    @api.model
    def _cron_check_expiry(self):
        """
        CRON-задача для приостановки просроченных ВМ.
        """
        _logger.info("Running VM expiry check cron job...")
        today = fields.Date.today()
        
        # Находим ВМ, которые активны, но их срок истек
        expired_vms = self.search([('end_date', '<', today), ('state', '=', 'active')])
        if not expired_vms:
            return

        # FIX: Инициализируем сервис для работы с API
        try:
            proxmox_service = ProxmoxService(self.env)
        except Exception as e:
            _logger.error("Failed to initialize ProxmoxService in cron job: %s", e)
            return

        for vm in expired_vms:
            _logger.info(f"VM {vm.name} (ID: {vm.proxmox_vm_id}) has expired. Suspending.")
            try:
                # FIX: Добавлен реальный вызов API для остановки ВМ
                if vm.proxmox_vm_id:
                    proxmox_service.stop_vm(vm.proxmox_vm_id)

                # Меняем статус в Odoo только после успешного вызова API
                vm.write({'state': 'suspended'})
                vm.message_post(body=f"Виртуальная машина была автоматически приостановлена из-за истечения срока аренды {vm.end_date}.")
            
            except Exception as e:
                _logger.error("Failed to suspend VM %s (ID: %s): %s", vm.name, vm.proxmox_vm_id, e)
                vm.message_post(body=f"Ошибка автоматической приостановки ВМ: {e}")