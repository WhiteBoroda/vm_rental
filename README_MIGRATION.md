"""
ИНСТРУКЦИИ ПО МИГРАЦИИ:

1. РЕЗЕРВНОЕ КОПИРОВАНИЕ:
   - Обязательно создайте резервную копию базы данных перед обновлением
   - Остановите Odoo сервер

2. ОБНОВЛЕНИЕ КОДА:
   - Скопируйте все новые файлы в директорию модуля
   - Убедитесь, что новый файл vm_mixin.py находится в models/
   - Проверьте, что __init__.py в models/ обновлен

3. ПРИМЕНЕНИЕ МИГРАЦИИ:
   - Запустите Odoo с параметром -u vm_rental
   - Odoo автоматически выполнит миграцию при обновлении модуля

4. ПРОВЕРКА ПОСЛЕ МИГРАЦИИ:
   - Убедитесь, что все существующие VM имеют корректные значения cores, memory, disk
   - Проверьте, что продукты теперь имеют поля ресурсов
   - Создайте тестовую VM для проверки функциональности

5. ОТКАТ В СЛУЧАЕ ПРОБЛЕМ:
   - Восстановите базу данных из резервной копии
   - Вернитесь к предыдущей версии кода модуля

КОМАНДЫ ДЛЯ ОБНОВЛЕНИЯ:
./odoo-bin -d your_database -u vm_rental --stop-after-init
./odoo-bin -d your_database  # Запуск после обновления

ЛОГИ МИГРАЦИИ:
Проверьте логи Odoo на предмет сообщений миграции:
grep "VM Rental migration" /var/log/odoo/odoo.log
"""
"""
# VM Rental Module - Migration Guide v1.2.4

## Overview
This migration introduces `vm.resource.mixin` to centralize VM resource management across multiple models.

## What's New
- **vm.resource.mixin**: Abstract model with cores, memory, disk fields and validation
- **Enhanced Portal**: Improved VM management interface with detailed resource information
- **Better Search**: Advanced filtering and search capabilities in portal
- **Improved UX**: Better error handling and user feedback

## Breaking Changes
None - this is a backward-compatible update.

## Migration Steps

### 1. Pre-Migration Checklist
- [ ] Backup your database
- [ ] Stop Odoo service
- [ ] Update module files
- [ ] Verify Python dependencies

### 2. Run Migration
```bash
# Update the module
./odoo-bin -d your_database -u vm_rental --stop-after-init

# Check logs for migration messages
grep "VM Rental migration" /var/log/odoo/odoo.log
```

### 3. Post-Migration Verification
- [ ] Check that all VMs have resource values (cores, memory, disk)
- [ ] Verify products now have resource fields
- [ ] Test VM creation from sales orders
- [ ] Check portal functionality
- [ ] Verify all hypervisor operations work

### 4. Rollback (if needed)
```bash
# Restore database from backup
pg_restore -d your_database backup_file.sql

# Revert to previous module version
git checkout v1.2.3
```

## New Features Usage

### VM Resource Mixin
```python
# Any model can now inherit resource management
class MyModel(models.Model):
    _inherit = ['base.model', 'vm.resource.mixin']
    
    # Automatically gets cores, memory, disk fields with validation
```

### Enhanced Portal
- Visit `/my/vms` for improved VM management
- Filter by status, search by name/ID
- Detailed resource information display
- Better mobile responsiveness

### Product Configuration
- Products now have VM resource fields in Sales tab
- Default values can be set per product
- Attributes can override default values

## Troubleshooting

### Common Issues

**1. Missing Resource Fields**
```sql
-- Check if fields exist
SELECT cores, memory, disk FROM vm_rental_machine LIMIT 1;
SELECT cores, memory, disk FROM product_template WHERE hypervisor_server_id IS NOT NULL LIMIT 1;
```

**2. Portal Access Issues**
- Clear browser cache
- Check user portal permissions
- Verify VM ownership rules

**3. Migration Errors**
- Check Odoo logs for detailed error messages
- Ensure all Python dependencies are installed
- Verify database permissions

### Support
For issues contact: support@iodoo.info

## Changelog

### v1.2.4 (Current)
- Added vm.resource.mixin for centralized resource management
- Enhanced portal interface with detailed VM information
- Improved search and filtering capabilities
- Better error handling and user experience
- Added comprehensive migration scripts

### v1.2.3 (Previous)
- Basic VM management functionality
- Proxmox and VMware support
- Simple portal interface
"""