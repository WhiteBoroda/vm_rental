# vm_rental/wizards/link_existing_vm_wizard.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

# ИЗМЕНЕНИЕ: TransientModel -> Model
class VmLinkingJob(models.Model):
    _name = 'vm_rental.linking_job'
    _description = 'VM Linking Job'

    name = fields.Char(string="Job Name", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], string="Status", default='draft', readonly=True)
    
    hypervisor_server_id = fields.Many2one('hypervisor.server', string="Hypervisor Server", required=True, readonly=True, states={'draft': [('readonly', False)]})
    partner_id = fields.Many2one('res.partner', string="Customer", required=True, readonly=True, states={'draft': [('readonly', False)]})
    
    line_ids = fields.One2many('vm_rental.linking_job.line', 'job_id', string="Available VMs")

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('vm_rental.linking_job') or _('New')
        return super(VmLinkingJob, self).create(vals)

    def action_fetch_vms(self):
        """
        ИЗМЕНЕНИЕ: Бывший onchange, теперь - метод кнопки.
        """
        self.ensure_one()
        self.line_ids.unlink() # Очищаем старые строки перед новым поиском

        service = self.hypervisor_server_id._get_service_manager()
        
        all_vms_on_server = []
        nodes = self.env['hypervisor.node'].search([('server_id', '=', self.hypervisor_server_id.id)])
        for node in nodes:
            vms_on_node = service.list_all_vms(node.name)
            if vms_on_node:
                for vm_data in vms_on_node:
                    vm_data['node'] = node.name
                all_vms_on_server.extend(vms_on_node)

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
                'job_id': self.id,
            })
        
        self.env['vm_rental.linking_job.line'].create(lines_vals)
        return True

    def action_link_vms(self):
        self.ensure_one()
        vms_to_link = self.line_ids.filtered(lambda l: l.should_link)
        if not vms_to_link:
            raise UserError(_("Please select at least one VM to link."))

        created_vms = self.env['vm_rental.machine']
        for vm_line in vms_to_link:
            vals = {
                'name': vm_line.name,
                'partner_id': self.partner_id.id,
                'hypervisor_server_id': self.hypervisor_server_id.id,
                'hypervisor_vm_ref': vm_line.vmid,
                'hypervisor_node_name': vm_line.node,
                'state': 'active' if vm_line.status in ['running', 'poweredOn'] else 'stopped',
                'start_date': fields.Date.today(),
            }
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
    vmid = fields.Char(string="VM Ref", readonly=True)
    node = fields.Char(string="Node", readonly=True)
    status = fields.Char(string="Status", readonly=True)