from odoo import models, fields, api
from odoo.exceptions import UserError
from .proxmox_api import ProxmoxService

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    proxmox_host = fields.Char(string="Proxmox Host")
    proxmox_user = fields.Char(string="Proxmox User")
    proxmox_token_name = fields.Char(string="Proxmox Token Name")
    proxmox_token_value = fields.Char(string="Proxmox Token Value")
    proxmox_node = fields.Selection([], string="Proxmox Node")
    proxmox_storage = fields.Selection([], string="Proxmox Storage")
    default_os_template = fields.Selection([], string="Default OS Template")
    vm_config_options = fields.Text(string="VM Config Options (JSON)")

    def get_values(self):
        res = super().get_values()
        Param = self.env['ir.config_parameter'].sudo()
        res.update({
            'proxmox_host': Param.get_param('vm_rental.proxmox_host', ''),
            'proxmox_user': Param.get_param('vm_rental.proxmox_user', ''),
            'proxmox_token_name': Param.get_param('vm_rental.proxmox_token_name', ''),
            'proxmox_token_value': Param.get_param('vm_rental.proxmox_token_value', ''),
            'proxmox_node': Param.get_param('vm_rental.proxmox_node', ''),
            'proxmox_storage': Param.get_param('vm_rental.proxmox_storage', ''),
            'default_os_template': Param.get_param('vm_rental.default_os_template', ''),
            'vm_config_options': Param.get_param('vm_rental.config_templates', '{}'),
        })
        return res

    def set_values(self):
        super().set_values()
        Param = self.env['ir.config_parameter'].sudo()
        Param.set_param('vm_rental.proxmox_host', self.proxmox_host or '')
        Param.set_param('vm_rental.proxmox_user', self.proxmox_user or '')
        Param.set_param('vm_rental.proxmox_token_name', self.proxmox_token_name or '')
        Param.set_param('vm_rental.proxmox_token_value', self.proxmox_token_value or '')
        Param.set_param('vm_rental.proxmox_node', self.proxmox_node or '')
        Param.set_param('vm_rental.proxmox_storage', self.proxmox_storage or '')
        Param.set_param('vm_rental.default_os_template', self.default_os_template or '')
        Param.set_param('vm_rental.config_templates', self.vm_config_options or '{}')

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)

        try:
            service = ProxmoxService(self.env)
            nodes = [(n, n) for n in service.list_nodes()]
            storages = [(s, s) for s in service.list_storages()]
            templates = [(t, t) for t in service.list_os_templates()]
        except Exception:
            nodes = []
            storages = []
            templates = []

        for field_name, field in res['fields'].items():
            if field_name == 'proxmox_node':
                field['selection'] = nodes
            elif field_name == 'proxmox_storage':
                field['selection'] = storages
            elif field_name == 'default_os_template':
                field['selection'] = templates

        return res

    def test_proxmox_connection(self):
        try:
            service = ProxmoxService(self.env)
            nodes = service.list_nodes()
            if nodes:
                raise UserError("Connection successful. Found nodes: %s" % ', '.join(nodes))
            raise UserError("Connected, but no nodes found.")
        except Exception as e:
            raise UserError("Connection failed: %s" % str(e))
