# vm_rental/wizards/link_existing_vm_wizard.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..services.base_service import HypervisorOperationError
import logging

_logger = logging.getLogger(__name__)


# ИЗМЕНЕНИЕ: TransientModel -> Model
class VmLinkingJob(models.Model):
    _name = 'vm_rental.linking_job'
    _description = 'VM Linking Job'

    name = fields.Char(string="Job Name", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('fetched', 'VMs Fetched'),  # Новое состояние
        ('done', 'Done')
    ], string="Status", default='draft', readonly=True)

    hypervisor_server_id = fields.Many2one('hypervisor.server', string="Hypervisor Server", required=True,
                                           readonly=True, states={'draft': [('readonly', False)]})
    partner_id = fields.Many2one('res.partner', string="Customer", required=True, readonly=True,
                                 states={'draft': [('readonly', False)]})

    line_ids = fields.One2many('vm_rental.linking_job.line', 'job_id', string="Available VMs")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('vm_rental.linking_job') or _('New')
        return super(VmLinkingJob, self).create(vals_list)

    def action_fetch_vms(self):
        """Получение VM и контейнеров с определением типа"""
        self.ensure_one()
        self.line_ids.unlink()  # Очищаем старые строки

        service = self.hypervisor_server_id._get_service_manager()
        all_vms_on_server = []

        nodes = self.env['hypervisor.node'].search([
            ('server_id', '=', self.hypervisor_server_id.id)
        ])

        for node in nodes:
            vms_on_node = service.list_all_vms(node.name)
            if vms_on_node:
                for vm_data in vms_on_node:
                    vm_data['node'] = node.name
                    # Определяем тип VM по наличию полей
                    if 'type' in vm_data:
                        vm_data['vm_type'] = vm_data['type']
                    elif 'hostname' in vm_data and 'name' not in vm_data:
                        vm_data['vm_type'] = 'lxc'
                        vm_data['name'] = vm_data.get('hostname', f"Container-{vm_data.get('vmid')}")
                    else:
                        vm_data['vm_type'] = 'qemu'
                all_vms_on_server.extend(vms_on_node)

        # Исключаем уже привязанные VM
        linked_vm_refs = self.env['vm_rental.machine'].search([
            ('hypervisor_server_id', '=', self.hypervisor_server_id.id)
        ]).mapped('hypervisor_vm_ref')

        lines_vals = []
        for vm_data in all_vms_on_server:
            vm_name = vm_data.get('name')
            vm_id = vm_data.get('vmid')

            if not vm_name or not vm_id or str(vm_id) in linked_vm_refs:
                continue

            lines_vals.append({
                'name': vm_name,
                'vmid': str(vm_id),
                'node': vm_data.get('node'),
                'status': vm_data.get('status'),
                'vm_type': vm_data.get('vm_type', 'unknown'),
                'job_id': self.id,
            })

        self.env['vm_rental.linking_job.line'].create(lines_vals)
        return True

    def action_link_vms(self):
        """Привязка выбранных VM с передачей типа VM"""
        self.ensure_one()

        if not self.partner_id:
            raise UserError(_("Please select a Customer before linking VMs."))

        vms_to_link = self.line_ids.filtered(lambda l: l.should_link)
        if not vms_to_link:
            raise UserError(_("Please select at least one VM to link."))

        service = self.hypervisor_server_id._get_service_manager()
        created_vms = self.env['vm_rental.machine']

        for vm_line in vms_to_link:
            try:
                # ИСПРАВЛЕНИЕ: Передаем тип VM в метод get_vm_config
                if self.hypervisor_server_id.hypervisor_type == 'proxmox':
                    vm_config = service.get_vm_config(vm_line.node, vm_line.vmid, vm_line.vm_type)
                else:  # VMware
                    vm_config = service.get_vm_config(vm_line.vmid)

                vals = {
                    'name': vm_line.name,
                    'partner_id': self.partner_id.id,
                    'hypervisor_server_id': self.hypervisor_server_id.id,
                    'hypervisor_vm_ref': vm_line.vmid,
                    'hypervisor_node_name': vm_line.node,
                    'state': 'active' if vm_line.status in ['running', 'poweredOn'] else 'stopped',
                    'start_date': fields.Date.today(),
                    # ИСПРАВЛЕНИЕ: Используем реальные ресурсы VM
                    'cores': vm_config['cores'],
                    'memory': vm_config['memory'],
                    'disk': vm_config['disk'],
                    # НОВОЕ: Сохраняем тип VM
                    'vm_type': vm_config.get('vm_type', 'unknown'),
                }

                _logger.info(
                    f"Linking {vm_config.get('vm_type', 'unknown').upper()} {vm_line.name} with config: {vm_config}")

            except HypervisorOperationError as e:
                _logger.error(f"Failed to get config for {vm_line.vm_type.upper()} {vm_line.name}: {e}")
                # Fallback к значениям по умолчанию
                vals = {
                    'name': vm_line.name,
                    'partner_id': self.partner_id.id,
                    'hypervisor_server_id': self.hypervisor_server_id.id,
                    'hypervisor_vm_ref': vm_line.vmid,
                    'hypervisor_node_name': vm_line.node,
                    'state': 'active' if vm_line.status in ['running', 'poweredOn'] else 'stopped',
                    'start_date': fields.Date.today(),
                    # Значения по умолчанию в зависимости от типа
                    'cores': 1,
                    'memory': 1024 if vm_line.vm_type == 'qemu' else 512,
                    'disk': 10 if vm_line.vm_type == 'qemu' else 8,
                    'vm_type': vm_line.vm_type,
                }
                _logger.warning(
                    f"Using default resources for {vm_line.vm_type.upper()} {vm_line.name} due to error: {e}")

            created_vms |= self.env['vm_rental.machine'].create(vals)

        self.write({'state': 'done'})

        action = self.env['ir.actions.act_window']._for_xml_id('vm_rental.action_vm_instance')
        action['domain'] = [('id', 'in', created_vms.ids)]
        return action


# ИЗМЕНЕНИЕ: TransientModel -> Model
class VmLinkingJobLine(models.Model):
    _name = 'vm_rental.linking_job.line'
    _description = 'VM Linking Job Line'

    job_id = fields.Many2one('vm_rental.linking_job', ondelete='cascade')
    should_link = fields.Boolean(string="Link?")
    name = fields.Char(string="VM Name", readonly=True)
    vmid = fields.Char(string="VM ID", readonly=True)
    node = fields.Char(string="Node", readonly=True)
    status = fields.Char(string="Status", readonly=True)

    # НОВОЕ ПОЛЕ: Тип VM/LXC
    vm_type = fields.Selection([
        ('qemu', 'KVM'),
        ('lxc', 'LXC'),
        ('unknown', 'Unknown')
    ], string="Type", default='unknown', readonly=True)