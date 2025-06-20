{
    'name': 'VM Rental (Universal with Traits)',
    'version': '1.3.0',
    'summary': 'Advanced VM rental system with composition-based traits architecture',
    'description': """

                                      VM Rental Module with Advanced Traits Architecture
                                      ==================================================

                                      Enterprise-grade virtual machine rental and management system featuring:

                                      🚀 **Traits Architecture**
                   * Composition-based design eliminates inheritance conflicts
                   * VmResourceTrait and VmOperationTrait for maximum flexibility
                   * Static methods for high performance and easy testing
                   
                   🎯 **Smart Resource Management**
                   * Automatic categorization (nano → micro → small → medium → large → xlarge)
                   * OS-specific recommendations (Ubuntu, Windows, Docker, CentOS)
                   * Resource normalization to standard values
                   * Boot time estimation and price calculation
                   
                   🛠️ **Advanced Features**
                   * Configuration wizard with predefined templates
                   * Bulk operations for mass VM management
                   * Health monitoring and automated checks
                   * Comprehensive reporting and analytics
                   * Workload-specific configuration suggestions
                   
                   ⚡ **Automation & Monitoring**
                   * Auto-provisioning of pending VMs
                   * Health checks for active VMs
                   * Automatic cleanup of old terminated VMs
                   * Resource utilization statistics
                   
                   🎨 **Enhanced UI/UX**
                   * Modern kanban and dashboard views
                   * Smart filtering and categorization
                   * Resource visualization and reporting
                   * Mobile-responsive portal interface
                   
                   📊 **Business Intelligence**
                   * Resource utilization reports
                   * Hypervisor distribution analytics
                   * Revenue tracking and forecasting
                   * Performance metrics and KPIs
                   
                   Version 1.3.0 introduces the revolutionary traits-based architecture that solves
                   all inheritance conflicts while providing unprecedented flexibility and performance.
""",
    'author': 'Yuri Varaksin',
    'website': 'http://iodoo.info',
    'category': 'Tools',
    'license': 'Apache-2.0',
    'depends': [
        'base', 'product', 'sale', 'website', 'portal', 'website_sale', 'payment'
    ],
    'external_dependencies': {
        'python': ['proxmoxer', 'pyvmomi', 'requests'],
    },
    'data': [
        # Security
        'security/vm_security.xml',

        # Data and sequences
        'data/vm_sequence.xml',
        'data/mail_templates.xml',
        'data/vm_traits_demo.xml',

        # Views (ordered by dependency)
        'views/hypervisor_server_views.xml',
        'views/vm_instance_view.xml',
        'views/vm_report_view.xml',
        'views/vm_traits_reports.xml',  # NEW: Advanced reports
        'views/product_template_view.xml',
        'views/product_attribute_view.xml',
        'views/sale_order_vm_view.xml',

        # Portal templates
        'views/portal_my_vms_template.xml',
        'views/portal_vm_console.xml',
        'views/portal_vm_snapshots.xml',
        'views/portal_menu_templates.xml',

        # Wizards
        'views/vm_traits_wizard.xml',
        'views/vm_bulk_operations_wizard.xml',  # NEW: Bulk operations
        'wizards/link_existing_vm_wizard_view.xml',

        # Settings and menus
        'views/res_config_settings_views.xml',
        'views/menus.xml',

        # Cron jobs (enhanced)
        'data/cron_jobs.xml',

        # Access rights (last)
        'security/ir.model.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'vm_rental/static/src/js/vm_rental_settings.js',
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

    # Enhanced metadata
    'version_info': {
        'major': 1,
        'minor': 3,
        'patch': 0,
        'stage': 'stable',
    },

    'technical_features': [
        'traits_architecture',
        'composition_over_inheritance',
        'static_method_performance',
        'no_many2many_conflicts',
        'bulk_operations',
        'health_monitoring',
        'resource_analytics',
        'workload_optimization',
    ],

    'business_features': [
        'multi_hypervisor_support',
        'automated_provisioning',
        'customer_portal',
        'trial_periods',
        'subscription_management',
        'resource_categorization',
        'price_calculation',
        'reporting_dashboard',
    ],
}