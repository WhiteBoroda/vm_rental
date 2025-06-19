# vm_rental/models/vm_mixin.py
class VmResourceMixin(models.AbstractModel):
    """Миксин для моделей с ресурсами VM"""
    _name = 'vm.resource.mixin'
    _description = 'VM Resource Mixin'

    cores = fields.Integer(string="CPU Cores", default=1, required=True)
    memory = fields.Integer(string="Memory (MiB)", default=1024, required=True)
    disk = fields.Integer(string="Disk (GiB)", default=10, required=True)

    @api.constrains('cores', 'memory', 'disk')
    def _check_resources(self):
        for rec in self:
            if rec.cores <= 0:
                raise ValidationError(_("CPU cores must be greater than 0"))
            if rec.memory < 128:
                raise ValidationError(_("Memory must be at least 128 MiB"))
            if rec.disk <= 0:
                raise ValidationError(_("Disk size must be greater than 0 GiB"))