# VM Rental Module for Odoo

## Overview
The VM Rental module enables rental and management of virtual machines through Odoo, supporting multiple hypervisors (Proxmox VE and VMware vCenter).

## Features
- **Multi-hypervisor support**: Proxmox VE and VMware vCenter
- **VM lifecycle management**: Create, start, stop, suspend, and terminate VMs
- **Automated provisioning**: VMs are automatically created upon sales order confirmation
- **Customer portal**: Customers can manage their VMs through the web portal
- **Snapshot management**: Create, restore, and delete VM snapshots
- **Subscription management**: Automatic suspension on expiry with configurable trial periods
- **Audit logging**: Track all VM operations
- **Resource management**: Define CPU, memory, and disk configurations

## Installation

### Prerequisites
1. Odoo 16.0 or later
2. Python dependencies:
   ```bash
   pip install proxmoxer pyvmomi requests
   ```

### Module Installation
1. Copy the `vm_rental` folder to your Odoo addons directory
2. Update the addons list in Odoo
3. Install the module through the Apps menu

## Configuration

### Hypervisor Setup
1. Navigate to **VM Rental → Hypervisor Servers**
2. Create a new server record:
   - For Proxmox: Provide API token credentials
   - For VMware: Provide vCenter username and password
3. Click **Test & Fetch Resources** to verify connection

### Product Configuration
1. Create products with VM specifications
2. In product form, configure:
   - Hypervisor server
   - Node/Cluster
   - Storage/Datastore
   - Base template
   - Trial period (optional)

## Usage

### Admin Interface
- **VM Instances**: View and manage all virtual machines
- **Link Existing VMs**: Import existing VMs from hypervisors
- **Reports**: Monitor VM usage and revenue

### Customer Portal
Customers can:
- View their VMs at `/my/vms`
- Start/stop/reboot VMs
- Access VM console
- Manage snapshots
- View subscription status

### API Endpoints
- `/vm/start/<vm_id>` - Start a VM
- `/vm/stop/<vm_id>` - Stop a VM
- `/vm/reboot/<vm_id>` - Reboot a VM
- `/vm/<vm_id>/snapshot/create` - Create snapshot
- `/vm/<vm_id>/snapshot/<name>/rollback` - Rollback to snapshot
- `/vm/<vm_id>/snapshot/<name>/delete` - Delete snapshot

## Security
- Role-based access control
- Portal users can only access their own VMs
- API endpoints require authentication
- Audit logging for all operations

## Troubleshooting

### Common Issues

1. **Connection Failed**
   - Verify hypervisor credentials
   - Check network connectivity
   - Ensure API access is enabled on hypervisor

2. **VM Creation Failed**
   - Check available resources on hypervisor
   - Verify template exists and is accessible
   - Check storage permissions

3. **Console Access Issues**
   - Ensure VNC/WebMKS is enabled on hypervisor
   - Check firewall rules
   - Verify SSL certificates

### Logs
- Check Odoo logs: `/var/log/odoo/odoo.log`
- VM operation logs: **VM Rental → Reports → Audit Logs**

## Development

### Module Structure
```
vm_rental/
├── controllers/        # HTTP controllers and API endpoints
├── models/            # Business logic and data models
├── services/          # Hypervisor service implementations
├── static/            # JavaScript and CSS assets
├── views/             # XML views and templates
├── wizards/           # Transient models and wizards
├── security/          # Access rules and groups
└── tests/             # Unit tests
```

### Adding New Hypervisor Support
1. Create service class inheriting from `BaseHypervisorService`
2. Implement all abstract methods
3. Add hypervisor type to selection field
4. Update `_get_service_manager` method

## License
This module is licensed under Apache License 2.0.

## Support
For issues and feature requests, please contact: support@iodoo.info
