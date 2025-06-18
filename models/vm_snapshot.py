# VM/models/vm_snapshot.py
from odoo import models, fields

class VmSnapshot(models.Model):
    _name = 'vm.snapshot'
    _description = 'Virtual Machine Snapshot'
    _order = 'create_date desc'

    name = fields.Char(string="Snapshot Name", required=True)
    description = fields.Text(string="Description")

    vm_instance_id = fields.Many2one(
        'vm_rental.machine',
        string="Virtual Machine",
        required=True,
        ondelete='cascade'
    )
    # Имя снапшота в Proxmox, по нему будем удалять/откатывать
    proxmox_name = fields.Char(string="Proxmox Name", required=True, index=True)