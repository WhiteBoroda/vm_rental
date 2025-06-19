# vm_rental/__manifest__.py
{
    'name': 'VM Rental (Universal)',
    'version': '1.2.3',
    'summary': 'Rent and manage virtual machines from multiple hypervisors',
    'author': 'Yuri Varaksin',
    'website': 'http://iodoo.info',
    'category': 'Tools',
    'depends': [
        'base', 'product', 'sale', 'website', 'portal', 'website_sale', 'payment'
    ],
    'data': [
        # 1. Безопасность
        'security/ir.model.access.csv',
        'security/vm_security.xml',
        
        # 2. ВСЕ файлы с видами (views) и действиями (actions)
        'views/vm_instance_view.xml', # Определяет базовый вид
        'views/vm_report_view.xml', # Наследуется от базового вида
        'views/hypervisor_server_views.xml',
        'wizards/link_existing_vm_wizard_view.xml',
        'views/product_template_view.xml',
        'views/product_attribute_view.xml',
        'views/sale_order_vm_view.xml',
        'views/portal_my_vms_template.xml',
        'views/portal_vm_console.xml',
        'views/portal_vm_snapshots.xml',
        'views/res_config_settings_views.xml',

        # 3. Файл с МЕНЮ должен идти ПОСЛЕ всех видов и действий
        'views/menus.xml',

        # 4. Данные и cron для Odoo 16
        'data/vm_sequence.xml',
        'data/mail_templates.xml',
        'data/cron_jobs.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'vm_rental/static/src/js/vm_rental_settings.js',
        ],
        'web.assets_frontend': [
            'vm_rental/static/src/js/vm_actions.js',
            'vm_rental/static/src/js/vm_snapshot_actions.js',
        ],
    },
    'installable': True,
    'application': True,
}
