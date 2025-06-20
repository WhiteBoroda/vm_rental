import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Миграция для внедрения миксина vm.resource.mixin
    Эта миграция обеспечивает совместимость существующих данных
    """
    _logger.info("Starting VM Rental migration to version 1.2.4 with vm.resource.mixin")

    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Проверяем существующие VM без ресурсов и устанавливаем значения по умолчанию
    _migrate_vm_resources(env)

    # 2. Проверяем существующие продукты и добавляем ресурсы по умолчанию
    _migrate_product_resources(env)

    # 3. Очищаем кеш для правильной загрузки новых полей
    _clear_model_cache(env)

    _logger.info("VM Rental migration completed successfully")


def _migrate_vm_resources(env):
    """Миграция ресурсов для существующих VM"""
    _logger.info("Migrating VM resource fields...")

    # Получаем все VM без установленных ресурсов
    vms_to_update = env['vm_rental.machine'].search([
        '|', '|',
        ('cores', '=', 0),
        ('memory', '=', 0),
        ('disk', '=', 0)
    ])

    if vms_to_update:
        _logger.info(f"Found {len(vms_to_update)} VMs to update with default resources")

        # Устанавливаем значения по умолчанию
        vms_to_update.write({
            'cores': 1,
            'memory': 1024,
            'disk': 10
        })

        _logger.info(f"Updated {len(vms_to_update)} VMs with default resource values")
    else:
        _logger.info("No VMs found requiring resource migration")


def _migrate_product_resources(env):
    """Миграция ресурсов для существующих продуктов"""
    _logger.info("Migrating product resource fields...")

    # Получаем все продукты с настроенным гипервизором, но без ресурсов
    products_to_update = env['product.template'].search([
        ('hypervisor_server_id', '!=', False),
        '|', '|',
        ('cores', '=', 0),
        ('memory', '=', 0),
        ('disk', '=', 0)
    ])

    if products_to_update:
        _logger.info(f"Found {len(products_to_update)} products to update with default resources")

        # Устанавливаем значения по умолчанию для продуктов VM
        products_to_update.write({
            'cores': 1,
            'memory': 1024,
            'disk': 10
        })

        _logger.info(f"Updated {len(products_to_update)} products with default resource values")
    else:
        _logger.info("No products found requiring resource migration")


def _clear_model_cache(env):
    """Очищаем кеш моделей для правильной загрузки новых полей"""
    _logger.info("Clearing model cache...")

    # Очищаем кеш для моделей, которые теперь используют миксин
    env.registry.clear_cache()

    # Принудительно обновляем поля моделей
    env['vm_rental.machine'].clear_caches()
    env['product.template'].clear_caches()

    _logger.info("Model cache cleared successfully")
