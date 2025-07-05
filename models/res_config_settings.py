# models/res_config_settings.py
# Файл оставляем пустым или удаляем совсем

# Если хотите оставить файл, то можно добавить только базовый import:
from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Убираем все VM Rental поля - они теперь в vm.rental.config
    pass