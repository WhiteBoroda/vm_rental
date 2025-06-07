{
    'name': 'VM Rental',
    'version': '1.0',
    'summary': 'Rent and manage Proxmox virtual machines',
    'author': 'Custom Dev',
    'website': 'http://example.com',
    'category': 'Tools',
    'depends': ['base', 'website', 'portal', 'sale', 'website_sale', 'payment'],
    'data': [
        'data/cron_jobs.xml',
        'data/mail_templates.xml',
        'data/vm_sequence.xml'
        'views/portal_my_vms_template.xml',
        'views/portal_vm_console.xml',
	    'views/vm_report_view.xml',
	    'views/res_config_settings_view.xml',
        'security/ir.model.access.csv',
        'security/vm_security.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'vm_rental/static/src/js/vm_actions.js',
        ],
    },
    'installable': True,
    'application': True,

}
