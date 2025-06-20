import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Пре-миграция для подготовки к внедрению миксина
    """
    _logger.info("Starting VM Rental pre-migration to version 1.2.4")

    # Проверяем, нужна ли миграция (есть ли поля cores, memory, disk в product.template)
    if not _check_product_fields_exist(cr):
        _logger.info("Product resource fields don't exist yet - migration needed")
    else:
        _logger.info("Product resource fields already exist - skipping migration")

    _logger.info("VM Rental pre-migration completed")


def _check_product_fields_exist(cr):
    """Проверяем, существуют ли поля ресурсов в product.template"""
    cr.execute("""
               SELECT column_name
               FROM information_schema.columns
               WHERE table_name = 'product_template'
                 AND column_name IN ('cores', 'memory', 'disk')
               """)

    existing_fields = [row[0] for row in cr.fetchall()]
    return len(existing_fields) == 3
