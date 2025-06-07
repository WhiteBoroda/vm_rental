from proxmoxer import ProxmoxAPI
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class ProxmoxService:
    def __init__(self, env):
        self.env = env
        settings = env['ir.config_parameter'].sudo()
        self.host = settings.get_param('vm_rental.proxmox_host')
        self.user = settings.get_param('vm_rental.proxmox_user')
        self.token_name = settings.get_param('vm_rental.proxmox_token_name')
        self.token_value = settings.get_param('vm_rental.proxmox_token_value')
        self.verify_ssl = settings.get_param('vm_rental.proxmox_verify_ssl') != '0'
        self.node = settings.get_param('vm_rental.proxmox_node') or 'pve'
        self.storage = settings.get_param('vm_rental.proxmox_storage') or 'local-lvm'
        self.proxmox = self._connect()

    def _connect(self):
        try:
            proxmox = ProxmoxAPI(
                self.host,
                user=self.user,
                token_name=self.token_name,
                token_value=self.token_value,
                verify_ssl=self.verify_ssl
            )
            return proxmox
        except Exception as e:
            _logger.error(f"Failed to connect to Proxmox: {e}")
            return None

    def test_connection(self):
        try:
            self.proxmox.access.users.get()
            return True
        except Exception as e:
            _logger.error(f"Connection test failed: {e}")
            return False

    def list_storages(self):
        try:
            return [s['storage'] for s in self.proxmox.nodes(self.node).storage.get() if s.get('content') and 'images' in s['content']]
        except Exception as e:
            _logger.error(f"Failed to list storages: {e}")
            return []

    def list_nodes(self):
        try:
            return [n['node'] for n in self.proxmox.nodes.get()]
        except Exception as e:
            _logger.error(f"Failed to list nodes: {e}")
            return []

    def list_users(self):
        try:
            return [u['userid'] for u in self.proxmox.access.users.get() if '@' in u['userid']]
        except Exception as e:
            _logger.error(f"Failed to list users: {e}")
            return []

    def list_os_templates(self):
        try:
            templates = []
            for storage in self.list_storages():
                contents = self.proxmox.nodes(self.node).storage(storage).content.get()
                templates.extend([c['volid'] for c in contents if c.get('format') == 'qcow2' or c.get('content') == 'vztmpl'])
            return templates
        except Exception as e:
            _logger.error(f"Failed to list OS templates: {e}")
            return []

    def create_vm(self, vm_id, name, template, cores=1, memory=1024):
        try:
            return self.proxmox.nodes(self.node).qemu.post(
                vmid=vm_id,
                name=name,
                template=0,
                cores=cores,
                memory=memory,
                scsihw='virtio-scsi-pci',
                scsi0=f"{self.storage}:vm-{vm_id}-disk-0",
                net0='virtio,bridge=vmbr0',
                ostype='l26',
                ide2=f"{template},media=cdrom"
            )
        except Exception as e:
            _logger.error(f"Failed to create VM: {e}")
            return None

    def start_vm(self, vm_id):
        try:
            return self.proxmox.nodes(self.node).qemu(vm_id).status.start.post()
        except Exception as e:
            _logger.error(f"Failed to start VM {vm_id}: {e}")
            return None

    def stop_vm(self, vm_id):
        try:
            return self.proxmox.nodes(self.node).qemu(vm_id).status.stop.post()
        except Exception as e:
            _logger.error(f"Failed to stop VM {vm_id}: {e}")
            return None

    def suspend_vm(self, vmid):
        """
        Приостанавливает виртуальную машину с заданным VMID через Proxmox API.
        """
        try:
            node = self._get_node()
            self.proxmox.nodes(node).qemu(vmid).status().suspend.post()
            _logger.info(f"Suspended VM ID {vmid} on node {node}")
            return True
        except Exception as e:
            _logger.error(f"Failed to suspend VM {vmid}: {e}")
            return False

    def delete_vm(self, vm_id):
        try:
            return self.proxmox.nodes(self.node).qemu(vm_id).delete()
        except Exception as e:
            _logger.error(f"Failed to delete VM {vm_id}: {e}")
            return None

    def generate_console_url(self, vm_id):
        return f"https://{self.host}:8006/?console=kvm&novnc=1&vmid={vm_id}&vmname=VM-{vm_id}"