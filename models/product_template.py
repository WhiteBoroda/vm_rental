from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from .vm_traits import VmResourceTrait, VmOperationTrait


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Поля ресурсов VM (без миксина - прямое определение)
    cores = fields.Integer(
        string="CPU Cores",
        default=lambda self: VmResourceTrait.DEFAULT_CORES,
        help="Number of CPU cores for the virtual machine"
    )
    memory = fields.Integer(
        string="Memory (MiB)",
        default=lambda self: VmResourceTrait.DEFAULT_MEMORY,
        help="Amount of RAM in MiB (Mebibytes)"
    )
    disk = fields.Integer(
        string="Disk (GiB)",
        default=lambda self: VmResourceTrait.DEFAULT_DISK,
        help="Disk size in GiB (Gibibytes)"
    )

    # Поля гипервизора
    hypervisor_server_id = fields.Many2one('hypervisor.server', string="Hypervisor Server")
    hypervisor_node_id = fields.Many2one('hypervisor.node', string="Node/Cluster",
                                         domain="[('server_id', '=?', hypervisor_server_id)]")
    hypervisor_storage_id = fields.Many2one('hypervisor.storage', string="Storage/Datastore",
                                            domain="[('server_id', '=?', hypervisor_server_id)]")
    hypervisor_template_id = fields.Many2one('hypervisor.template', string="Base Template",
                                             domain="[('server_id', '=?', hypervisor_server_id)]")

    # Trial settings
    has_trial_period = fields.Boolean(string="Offer Trial Period")
    trial_period_days = fields.Integer(string="Trial Duration (Days)", default=7)

    # Computed поля с использованием traits
    vm_resource_summary = fields.Char(string="Resource Summary", compute='_compute_vm_resource_summary', store=True)
    vm_resource_category = fields.Char(string="Resource Category", compute='_compute_vm_resource_category', store=True)
    vm_estimated_boot_time = fields.Integer(string="Estimated Boot Time (sec)",
                                            compute='_compute_vm_estimated_boot_time')

    @api.depends('cores', 'memory', 'disk')
    def _compute_vm_resource_summary(self):
        """Использует trait для создания сводки ресурсов"""
        for product in self:
            if product.hypervisor_server_id:
                product.vm_resource_summary = VmResourceTrait.get_resource_summary(
                    product.cores, product.memory, product.disk, detailed=True
                )
            else:
                product.vm_resource_summary = ""

    @api.depends('cores', 'memory', 'disk')
    def _compute_vm_resource_category(self):
        """Использует trait для определения категории"""
        for product in self:
            if product.hypervisor_server_id:
                product.vm_resource_category = VmResourceTrait.get_resource_category(
                    product.cores, product.memory, product.disk
                )
            else:
                product.vm_resource_category = ""

    @api.depends('cores', 'memory', 'disk', 'hypervisor_template_id')
    def _compute_vm_estimated_boot_time(self):
        """Использует trait для оценки времени загрузки"""
        for product in self:
            if product.hypervisor_server_id:
                os_type = 'linux'  # По умолчанию
                if product.hypervisor_template_id and 'windows' in product.hypervisor_template_id.name.lower():
                    os_type = 'windows'

                product.vm_estimated_boot_time = VmOperationTrait.estimate_boot_time(
                    product.cores, product.memory, product.disk, os_type
                )
            else:
                product.vm_estimated_boot_time = 0

    @api.constrains('cores', 'memory', 'disk')
    def _check_vm_resources(self):
        """Использует trait для валидации ресурсов"""
        for product in self:
            # Проверяем только продукты с настроенным гипервизором
            if product.hypervisor_server_id:
                VmResourceTrait.validate_resources(
                    product.cores, product.memory, product.disk, self.env
                )

    @api.onchange('hypervisor_server_id')
    def _onchange_hypervisor_server_id(self):
        """Сбрасывает значения дочерних полей при смене сервера"""
        self.hypervisor_node_id = False
        self.hypervisor_storage_id = False
        self.hypervisor_template_id = False

    def get_vm_resource_summary(self):
        """Публичный метод для получения сводки ресурсов"""
        self.ensure_one()
        if not self.hypervisor_server_id:
            return ""
        return VmResourceTrait.get_resource_summary(self.cores, self.memory, self.disk)

    def normalize_vm_resources(self):
        """Нормализует ресурсы VM к стандартным значениям"""
        self.ensure_one()
        if self.hypervisor_server_id:
            normalized = VmResourceTrait.normalize_resources(self.cores, self.memory, self.disk)
            self.write(normalized)
            return normalized
        return {}

    @api.model
    def create_vm_product_variants(self):
        """Создает варианты продукта для разных конфигураций VM"""
        configs = VmResourceTrait.get_predefined_configs()
        created_products = self.env['product.template']

        for name, config in configs.items():
            product_name = f"VM {name.capitalize()}"
            existing = self.search([('name', '=', product_name)], limit=1)

            if not existing:
                product = self.create({
                    'name': product_name,
                    'type': 'service',
                    'cores': config['cores'],
                    'memory': config['memory'],
                    'disk': config['disk'],
                    'list_price': VmResourceTrait.calculate_price_multiplier(**config) * 10,  # базовая цена 10
                })
                created_products |= product

        return created_products