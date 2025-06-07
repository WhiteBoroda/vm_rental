from odoo import models, fields

class VmTemplate(models.Model):
    _name = 'vm.template'
    _description = 'VM Template'

    name = fields.Char(required=True)
    cpu = fields.Integer(string="vCPU", required=True)
    ram = fields.Integer(string="RAM (MB)", required=True)
    disk = fields.Integer(string="Disk Size (GB)", required=True)
    os_image = fields.Selection([
        ('ubuntu_22', 'Ubuntu 22.04'),
        ('debian_12', 'Debian 12'),
        ('centos_7', 'CentOS 7'),
        ('windows11', 'Windows11'),
    ], string="Operating System", required=True)
    price_monthly = fields.Float(string="Price per Month", required=True)
    proxmox_template_id = fields.Char(string="Proxmox Template ID")