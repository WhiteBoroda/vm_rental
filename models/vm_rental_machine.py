# vm_rental/models/vm_rental_machine.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import ormcache
from dateutil.relativedelta import relativedelta
from functools import wraps
import logging, uuid, time

_logger = logging.getLogger(__name__)

def log_vm_action(action_type):
    """Декоратор для автоматического логирования действий с ВМ"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start_time = time.time()
            error = None
            result = None
            
            try:
                result = func(self, *args, **kwargs)
                success = True
            except Exception as e:
                error = str(e)
                success = False
                raise
            finally:
                duration = time.time() - start_time
                if hasattr(self, 'id') and self.id:
                    self.env['vm_rental.audit_log'].log_action(
                        vm_id=self.id,
                        action=action_type,
                        success=success,
                        error_message=error,
                        duration=duration,
                        metadata={'args': str(args), 'kwargs': str(kwargs)}
                    )
            
            return result
        return wrapper
    return decorator

class VmInstance(models.Model):
    """
    Represents a Virtual Machine instance, handling its lifecycle from creation
    (manual or via sale) to expiration and management, using a generic hypervisor service layer.
    """
    _name = 'vm_rental.machine'
    _description = 'Virtual Machine Instance'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # === Fields Definition ===

    name = fields.Char(string="VM Name", required=True, tracking=True)
    
    # --- РЕФАКТОРИНГ: Старые поля Proxmox заменены на универсальные ---
    hypervisor_vm_ref = fields.Char(string="Hypervisor VM Reference", readonly=True, copy=False, index=True, help="The unique identifier for the VM in the hypervisor (e.g., a numeric ID for Proxmox, a UUID for VMware).")
    hypervisor_node_name = fields.Char(string="Node/Cluster Name", readonly=True, copy=False, help="The actual node/cluster name where the VM is running.")

    state = fields.Selection([
        ('pending', 'Draft'),
        ('active', 'Active'),
        ('stopped', 'Stopped'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
        ('archived', 'Archived'),
        ('failed', 'Failed')
    ], string="State", default='pending', readonly=True, copy=False, tracking=True, index=True)
    
    start_date = fields.Date(string="Start Date", readonly=True, copy=False)
    end_date = fields.Date(string="End Date", readonly=True, tracking=True, copy=False, index=True)
    
    partner_id = fields.Many2one('res.partner', string="Customer", required=True, tracking=True, index=True)

    sale_order_ids = fields.One2many('sale.order', 'vm_instance_id', string="Sale Orders")
    snapshot_ids = fields.One2many('vm.snapshot', 'vm_instance_id', string="Snapshots")
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Currency")
    total_amount = fields.Monetary(string="Total Paid", compute="_compute_total_amount", store=True)
    
    config_backup_ids = fields.One2many('vm_rental.config_backup', 'vm_id', string="Configuration Backups")

    # --- Поля для конфигурации гипервизора ---
    hypervisor_server_id = fields.Many2one('hypervisor.server', string="Hypervisor Server", tracking=True, index=True)
    hypervisor_node_id = fields.Many2one('hypervisor.node', string="Node/Cluster", domain="[('server_id', '=?', hypervisor_server_id)]")
    hypervisor_storage_id = fields.Many2one(
        'hypervisor.storage',
        string="Storage/Datastore",
        domain="[('server_id', '=?', hypervisor_server_id), ('node_ids', 'in', hypervisor_node_id)]"
    )
    hypervisor_template_id = fields.Many2one('hypervisor.template', string="Template", domain="[('server_id', '=?', hypervisor_server_id)]")
    
    cores = fields.Integer(string="CPU Cores", default=1)
    memory = fields.Integer(string="Memory (MiB)", default=1024)
    disk = fields.Integer(string="Disk (GiB)", default=10)
    is_trial = fields.Boolean(string="Is Trial Period", readonly=True, default=False)

    user_id = fields.Many2one('res.users', string="User", compute='_compute_user_id', store=True, readonly=True)

    @api.depends('partner_id', 'partner_id.user_ids')
    def _compute_user_id(self):
        for vm in self:
            if vm.partner_id and vm.partner_id.user_ids:
               # Берем первого активного пользователя
#                active_users = vm.partner_id.user_ids.filtered(lambda u: u.active and not u.share)
                vm.user_id = vm.partner_id.user_ids[0].id
            else:
                vm.user_id = False

    # === Onchange Methods ===
    
    @api.onchange('hypervisor_server_id')
    def _onchange_hypervisor_server(self):
        """Resets related fields when the server is changed."""
        self.hypervisor_node_id = False
        self.hypervisor_storage_id = False
        self.hypervisor_template_id = False

    # === Compute Methods ===

    @api.depends('sale_order_ids.state', 'sale_order_ids.amount_total')
    def _compute_total_amount(self):
        """Computes the total amount paid across all confirmed orders."""
        for rec in self:
            paid_orders = rec.sale_order_ids.filtered(lambda o: o.state in ['sale', 'done'])
            rec.total_amount = sum(paid_orders.mapped('amount_total'))

    # === Helper & Service Methods ===

    def _get_hypervisor_service(self):
        """Возвращает правильный экземпляр сервиса (Proxmox или VMware)."""
        self.ensure_one()
        if not self.hypervisor_server_id:
            raise UserError(_("Hypervisor server is not configured for this VM."))
        return self.hypervisor_server_id._get_service_manager()

    # === Actions ===
    
    @log_vm_action('create')
    def action_provision_vm(self):
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_("You can only provision VMs that are in the 'Draft' state."))
        if not all([self.hypervisor_node_id, self.hypervisor_storage_id, self.hypervisor_template_id]):
            raise ValidationError(_("Please select a Node/Cluster, Storage/Datastore, and Template before provisioning."))
            
        hypervisor_service = self._get_hypervisor_service()
        vmid = hypervisor_service.get_next_vmid()
        if not vmid and self.hypervisor_server_id.hypervisor_type != 'vmware':
             raise UserError(_("Could not fetch the next available ID from the hypervisor."))
        
        # ИСПРАВЛЕНИЕ: Вызываем нужный метод в зависимости от типа шаблона
        provisioning_result = None
        template = self.hypervisor_template_id
        
        if template.template_type == 'qemu':
            provisioning_result = hypervisor_service.create_vm(
                node=self.hypervisor_node_id.name,
                vm_id=vmid,
                name=self.name,
                template_vmid=template.vmid,
                cores=self.cores,
                memory=self.memory,
                disk=self.disk,
                storage=self.hypervisor_storage_id.name
            )
        elif template.template_type == 'lxc':
            # Генерируем случайный пароль для контейнера
            password = str(uuid.uuid4())
            provisioning_result = hypervisor_service.create_container(
                node=self.hypervisor_node_id.name,
                vm_id=vmid,
                name=self.name,
                template_volid=template.vmid, # здесь хранится volid
                cores=self.cores,
                memory=self.memory,
                disk=self.disk,
                storage=self.hypervisor_storage_id.name,
                password=password
            )
            # Сохраняем пароль в chatter для администратора
            self.message_post(body=_(f"LXC container root password: <strong>{password}</strong>"))

        if not provisioning_result:
             raise UserError(_("API call to create instance failed. Check hypervisor logs for task details."))
        
        today = fields.Date.today()
        if self.is_trial:
            trial_days = int(self.env['ir.config_parameter'].sudo().get_param('vm_rental.default_trial_days', 7))
            end_date = today + relativedelta(days=trial_days)
        else:
            end_date = today + relativedelta(months=1)

        # --- РЕФАКТОРИНГ: Запись в новые универсальные поля ---
        self.write({
            'hypervisor_vm_ref': vmid,
            'state': 'active',
            'hypervisor_node_name': self.hypervisor_node_id.name,
            'start_date': today,
            'end_date': end_date
        })
        self.message_post(body=_(f"Virtual machine <strong>{self.name}</strong> (ID: {self.hypervisor_vm_ref}) was created successfully on {self.hypervisor_server_id.hypervisor_type}."))
        return True
    
    @log_vm_action('extend')
    def extend_period(self, months=1):
        """Extends the subscription period and re-activates the VM if suspended."""
        self.ensure_one()
        new_end_date = self.end_date if self.end_date and self.end_date > fields.Date.today() else fields.Date.today()
        new_end_date += relativedelta(months=months)
        
        self.write({'end_date': new_end_date})
        
        # --- РЕФАКТОРИНГ: Используем универсальный сервис и поля ---
        if self.state == 'suspended' and self.hypervisor_vm_ref:
            service = self._get_hypervisor_service()
            if service.start_vm(self.hypervisor_node_name, self.hypervisor_vm_ref):
                self.write({'state': 'active'})
            else:
                 _logger.warning(f"Failed to start VM {self.name} via extend_period.")
        
        _logger.info(f"VM {self.name} extended until {self.end_date}")

    # === Cron & Automation ===

    @api.model
    def _cron_check_expiry(self):
        """
        Cron job to automatically suspend VMs that have passed their end date.
        """
        _logger.info("Running VM expiry check cron job...")
        expired_vms = self.search([('end_date', '<', fields.Date.today()), ('state', '=', 'active')])
        for vm in expired_vms:
            _logger.info(f"VM {vm.name} (ID: {vm.hypervisor_vm_ref}) has expired. Suspending.")
            try:
                # --- РЕФАКТОРИНГ: Используем универсальный сервис и поля ---
                if vm.hypervisor_vm_ref:
                    hypervisor_service = vm._get_hypervisor_service()
                    hypervisor_service.suspend_vm(vm.hypervisor_node_name, vm.hypervisor_vm_ref)
                
                vm.write({'state': 'suspended'})
                vm.message_post(body=_(f"The virtual machine was automatically suspended due to rental expiration on {vm.end_date}."))
            except Exception as e:
                _logger.error("Failed to suspend VM %s (ID: %s): %s", vm.name, vm.hypervisor_vm_ref, e, exc_info=True)
                vm.message_post(body=_(f"Failed to automatically suspend the VM. Error: {e}"))

    # === Business Logic ===

    @api.model
    def create_from_order(self, order, line, vm_config):
        """
        Creates a VM record from a confirmed sales order line.
        """
        product = line.product_id
        hypervisor_server = product.hypervisor_server_id
        if not hypervisor_server:
            raise UserError(_(f"Hypervisor server is not configured for product '{product.name}'."))

        new_vm = self.create({
            'name': f"{order.name}-{line.name.replace(' ', '-')}",
            'state': 'pending',
            'partner_id': order.partner_id.id,
            'sale_order_ids': [(4, order.id)],
            'hypervisor_server_id': hypervisor_server.id,
            'hypervisor_node_id': product.hypervisor_node_id.id,
            'hypervisor_storage_id': product.hypervisor_storage_id.id,
            'hypervisor_template_id': product.hypervisor_template_id.id,
            'cores': vm_config.get('cores'),
            'memory': vm_config.get('memory'),
            'disk': vm_config.get('disk'),
            'is_trial': product.has_trial_period,
        })

        # Сразу привязываем ВМ к заказу, даже если создание не удастся
        order.write({'vm_instance_id': new_vm.id})

        try:
            new_vm.action_provision_vm()
            return new_vm
        except Exception as e:
            _logger.error(f"Failed to create VM for order {order.name}: {e}", exc_info=True)
            order.message_post(body=_(f"<strong>ERROR:</strong> Could not create virtual machine. Reason: {e}"))
            # Вместо удаления, меняем статус на "Сбой"
            if new_vm.exists():
                new_vm.write({'state': 'failed'})
            return False
    
    @api.constrains('cores', 'memory', 'disk')
    def _check_resources(self):
        """Проверка валидности ресурсов ВМ"""
        for vm in self:
            if vm.cores <= 0:
                raise ValidationError(_("CPU cores must be greater than 0"))
            if vm.memory < 128:
                raise ValidationError(_("Memory must be at least 128 MiB"))
            if vm.disk <= 0:
                raise ValidationError(_("Disk size must be greater than 0 GiB"))
            
            # Проверка лимитов (настраиваемые через системные параметры)
            max_cores = int(self.env['ir.config_parameter'].sudo().get_param('vm_rental.max_cores', 64))
            max_memory = int(self.env['ir.config_parameter'].sudo().get_param('vm_rental.max_memory', 131072))  # 128GB
            max_disk = int(self.env['ir.config_parameter'].sudo().get_param('vm_rental.max_disk', 10240))  # 10TB
            
            if vm.cores > max_cores:
                raise ValidationError(_("CPU cores cannot exceed %d") % max_cores)
            if vm.memory > max_memory:
                raise ValidationError(_("Memory cannot exceed %d MiB") % max_memory)
            if vm.disk > max_disk:
                raise ValidationError(_("Disk size cannot exceed %d GiB") % max_disk)
    
    @api.constrains('end_date', 'start_date')
    def _check_dates(self):
        """Проверка корректности дат"""
        for vm in self:
            if vm.start_date and vm.end_date and vm.end_date < vm.start_date:
                raise ValidationError(_("End date cannot be before start date"))

    @api.model
    @ormcache('partner_id')
    def get_vm_count_for_partner(self, partner_id):
        """Кешированный подсчет ВМ для партнера"""
        return self.search_count([
            ('partner_id', 'child_of', partner_id),
            ('state', 'not in', ['terminated', 'archived'])
        ])
    
    @api.model
    def create(self, vals):
        res = super().create(vals)
        # Очищаем кеш при создании новой ВМ
        if 'partner_id' in vals:
            self.get_vm_count_for_partner.clear_cache(self)
        return res
    
    def write(self, vals):
        critical_fields = {'cores', 'memory', 'disk', 'hypervisor_node_id', 'hypervisor_storage_id'}
        
        if any(field in vals for field in critical_fields):
            for vm in self:
                self.env['vm_rental.config_backup'].create_backup(vm, backup_type='pre_change')
        
        # Очищаем кеш при изменении партнера
        if 'partner_id' in vals:
            self.get_vm_count_for_partner.clear_cache(self)
        return super().write(vals)

    def action_retry_provisioning(self):
        self.ensure_one()
        if self.state != 'failed':
            raise UserError(_("You can only retry provisioning for VMs in the 'Failed' state."))
        try:
            # Просто повторно вызываем основной метод создания
            return self.action_provision_vm()
        except Exception as e:
            self.message_post(body=_("Retry provisioning failed again. Reason: %s") % e)
            return False