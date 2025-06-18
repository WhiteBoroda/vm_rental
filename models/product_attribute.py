# VM/models/product_attribute.py
from odoo import models, fields

class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'

    # Добавляем поле для хранения значения, понятного для Proxmox API
    proxmox_value = fields.Char(
        string="Proxmox API Value",
        help="The value to be passed to the Proxmox API. E.g., for RAM '8GB', this could be '8192'. For disk '100 GB', this could be '100'."
    )