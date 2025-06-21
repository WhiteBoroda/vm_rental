{
    'name': 'VM Rental (Universal with Traits)',
    'version': '1.3.3',
    'summary': 'Advanced VM rental system with composition-based traits architecture',
    'description': """
VM Rental Module with Advanced Traits Architecture
==================================================

Enterprise-grade virtual machine rental and management system featuring:

🚀 **Traits Architecture**
* Composition-based design for maximum flexibility
* VmResourceTrait and VmOperationTrait as static utility classes
* Clean separation of concerns without inheritance conflicts
* High performance through static methods

🎯 **Smart Resource Management**
* Automatic categorization (nano → micro → small → medium → large → xlarge)
* OS-specific recommendations (Ubuntu, Windows, Docker, CentOS)
* Resource normalization to standard values
* Boot time estimation and intelligent price calculation

🛠️ **Advanced Features**
* Configuration wizard with predefined templates
* Bulk operations for efficient mass VM management
* Health monitoring and automated system checks
* Comprehensive reporting and analytics dashboard
* Workload-specific configuration suggestions

⚡ **Automation & Monitoring**
* Auto-provisioning of pending VMs with smart queuing
* Health checks for active VMs with alerting
* Automatic cleanup of old terminated VMs
* Real-time resource utilization statistics

🎨 **Enhanced UI/UX**
* Modern kanban and dashboard views with filtering
* Smart categorization and advanced search
* Resource visualization and interactive reporting
* Mobile-responsive portal interface for customers

📊 **Business Intelligence**
* Detailed resource utilization reports
* Hypervisor distribution analytics
* Revenue tracking and forecasting tools
* Performance metrics and KPI dashboards

🔧 **Multi-Hypervisor Support**
* Proxmox VE integration with full API support
* VMware vCenter compatibility
* Extensible architecture for additional hypervisors
* Unified management interface

🌐 **Customer Portal**
* Self-service VM management for customers
* Real-time console access through web interface
* Snapshot management with restore capabilities
* Subscription tracking and renewal notifications

Version 1.3.0 features a revolutionary traits-based architecture that provides
unprecedented flexibility while maintaining high performance and code clarity.
""",
    'author': 'Yuri Varaksin',
    'website': 'http://iodoo.info',
    'category': 'Tools',
    'license': 'LGPL-3',
    'depends': [
        'base', 'product', 'sale', 'website', 'portal', 'website_sale', 'payment'
    ],
    'external_dependencies': {
        'python': ['proxmoxer', 'pyvmomi', 'requests'],
    },
    'data': [
        # Security
        'security/vm_security.xml',
        'security/vm_pricing_security.xml',
        'security/ir.model.access.csv',

        # Data and sequences
        'data/vm_sequence.xml',
        'data/mail_templates.xml',

        # Views (ordered by dependency)
        'views/hypervisor_server_views.xml',
        'views/vm_wizard_view.xml',
        'views/vm_instance_view.xml',
        'views/vm_report_view.xml',
        'views/product_template_view.xml',
        'views/product_attribute_view.xml',
        'views/sale_order_vm_view.xml',

        # Portal templates
        'views/portal_my_vms_template.xml',
        'views/portal_vm_console.xml',
        'views/portal_vm_snapshots.xml',
        'views/portal_menu_templates.xml',

        # Wizards
        'wizards/link_existing_vm_wizard_view.xml',

        # Settings and menus
        'views/res_config_settings_views.xml',
        'views/vm_settings_actions.xml',
        # Pricing system views and security
        'views/vm_pricing_views.xml',
        'views/vm_pricing_menus.xml',
        'views/menus.xml',

        # Demo data
        'data/vm_traits_demo.xml',
        'data/vm_pricing_demo.xml',

        # Cron jobs
        'data/cron_jobs.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'vm_rental/static/src/js/vm_rental_settings.js',
            'vm_rental/static/src/css/vm_settings.css',
        ],
        'web.assets_frontend': [
            'vm_rental/static/src/css/portal.css',
            'vm_rental/static/src/js/vm_actions.js',
            'vm_rental/static/src/js/vm_snapshot_actions.js',
        ],
    },
    'demo': [
        'data/vm_traits_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 10,

    # Technical metadata
    'version_info': {
        'major': 1,
        'minor': 3,
        'patch': 1,
        'stage': 'stable',
    },

    'technical_features': [
        'traits_architecture',
        'composition_over_inheritance',
        'static_method_performance',
        'multi_hypervisor_support',
        'bulk_operations',
        'health_monitoring',
        'resource_analytics',
        'workload_optimization',
        'automated_provisioning',
    ],

    'business_features': [
        'customer_portal',
        'trial_periods',
        'subscription_management',
        'resource_categorization',
        'price_calculation',
        'reporting_dashboard',
        'snapshot_management',
        'console_access',
        'revenue_tracking',
    ],
}