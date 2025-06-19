# vm_rental/models/product_template.py
from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    vm_cores = fields.Integer(string="Default CPU Cores", default=1)
    vm_memory = fields.Integer(string="Default Memory (MiB)", default=1024)
    vm_disk = fields.Integer(string="Default Disk (GiB)", default=10)

    # --- РЕФАКТОРИНГ: Поля полностью переименованы для универсальности ---
    hypervisor_server_id = fields.Many2one(
        'hypervisor.server',
        string="Hypervisor Server",
        help="The Hypervisor server on which to provision the VM for this product."
    )
    hypervisor_node_id = fields.Many2one(
        'hypervisor.node', string="Node/Cluster",
        domain="[('server_id', '=?', hypervisor_server_id)]",
        help="The specific node or cluster within the selected server."
    )
    hypervisor_storage_id = fields.Many2one(
        'hypervisor.storage', string="Storage/Datastore",
        domain="[('server_id', '=?', hypervisor_server_id)]",
        help="The specific storage or datastore to use for the VM's disk."
    )
    hypervisor_template_id = fields.Many2one(
        'hypervisor.template', string="Base Template",
        domain="[('server_id', '=?', hypervisor_server_id)]",
        help="The base VM template to clone from."
    )
    
    # --- Поля для тестового периода (без изменений) ---
    has_trial_period = fields.Boolean(string="Offer Trial Period")
    trial_period_days = fields.Integer(string="Trial Duration (Days)", default=7, help="Duration of the trial period in days.")

    @api.onchange('hypervisor_server_id')
    def _onchange_hypervisor_server_id(self):
        """Сбрасывает значения дочерних полей при смене сервера."""
        # Это стандартный и правильный способ обработки таких зависимостей в Odoo
        self.hypervisor_node_id = False
        self.hypervisor_storage_id = False
        self.hypervisor_template_id = False