from odoo import models, fields, api, _
from odoo.exceptions import UserError
from ..models.vm_traits import VmResourceTrait, VmOperationTrait


class VmConfigWizard(models.TransientModel):
    """Визард для быстрой настройки VM с использованием traits"""
    _name = 'vm.config.wizard'
    _description = 'VM Configuration Wizard'

    config_type = fields.Selection([
        ('predefined', 'Predefined Configuration'),
        ('recommended', 'OS-based Recommendation'),
        ('custom', 'Custom Configuration'),
    ], string="Configuration Type", required=True, default='predefined')

    predefined_config = fields.Selection([
        ('nano', 'Nano (1 CPU, 512MB, 5GB)'),
        ('micro', 'Micro (1 CPU, 1GB, 10GB)'),
        ('small', 'Small (2 CPU, 2GB, 20GB)'),
        ('medium', 'Medium (4 CPU, 4GB, 50GB)'),
        ('large', 'Large (8 CPU, 8GB, 100GB)'),
        ('xlarge', 'XLarge (16 CPU, 16GB, 200GB)'),
    ], string="Predefined Configuration")

    os_type = fields.Selection([
        ('ubuntu', 'Ubuntu'),
        ('debian', 'Debian'),
        ('centos', 'CentOS'),
        ('windows', 'Windows'),
        ('docker', 'Docker'),
    ], string="Operating System")

    # Custom configuration fields
    cores = fields.Integer(string="CPU Cores", default=1)
    memory = fields.Integer(string="Memory (MiB)", default=1024)
    disk = fields.Integer(string="Disk (GiB)", default=10)

    # Preview fields
    resource_summary = fields.Char(string="Resource Summary", compute='_compute_preview_fields')
    resource_category = fields.Char(string="Category", compute='_compute_preview_fields')
    estimated_boot_time = fields.Integer(string="Est. Boot Time (sec)", compute='_compute_preview_fields')
    estimated_price = fields.Float(string="Estimated Price", compute='_compute_preview_fields')

    @api.depends('config_type', 'predefined_config', 'os_type', 'cores', 'memory', 'disk')
    def _compute_preview_fields(self):
        """Вычисляет preview поля используя traits"""
        for wizard in self:
            cores, memory, disk = wizard._get_final_config()

            wizard.resource_summary = VmResourceTrait.get_resource_summary(cores, memory, disk, detailed=True)
            wizard.resource_category = VmResourceTrait.get_resource_category(cores, memory, disk)

            os_type = wizard.os_type or 'linux'
            wizard.estimated_boot_time = VmOperationTrait.estimate_boot_time(cores, memory, disk, os_type)
            wizard.estimated_price = VmResourceTrait.calculate_price_multiplier(cores, memory, disk) * 10

    def _get_final_config(self):
        """Возвращает финальную конфигурацию в зависимости от типа"""
        self.ensure_one()

        if self.config_type == 'predefined' and self.predefined_config:
            configs = VmResourceTrait.get_predefined_configs()
            config = configs.get(self.predefined_config, VmResourceTrait.get_default_config())
            return config['cores'], config['memory'], config['disk']

        elif self.config_type == 'recommended' and self.os_type:
            config = VmOperationTrait.get_recommended_specs_for_os(self.os_type)
            return config['cores'], config['memory'], config['disk']

        else:  # custom
            return self.cores, self.memory, self.disk

    def apply_configuration(self):
        """Применяет конфигурацию к записи"""
        self.ensure_one()

        cores, memory, disk = self._get_final_config()

        # Валидация через traits
        try:
            VmResourceTrait.validate_resources(cores, memory, disk, self.env)
        except Exception as e:
            raise UserError(str(e))

        # Получаем активную запись из контекста
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')

        if active_model and active_id:
            record = self.env[active_model].browse(active_id)
            record.write({
                'cores': cores,
                'memory': memory,
                'disk': disk,
            })

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('VM configuration applied successfully!'),
                    'type': 'success',
                }
            }

        return {'type': 'ir.actions.act_window_close'}

    @api.onchange('config_type')
    def _onchange_config_type(self):
        """Сброс полей при смене типа конфигурации"""
        if self.config_type == 'predefined':
            self.predefined_config = 'micro'
        elif self.config_type == 'recommended':
            self.os_type = 'ubuntu'
        else:  # custom
            default_config = VmResourceTrait.get_default_config()
            self.cores = default_config['cores']
            self.memory = default_config['memory']
            self.disk = default_config['disk']