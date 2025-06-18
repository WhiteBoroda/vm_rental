# vm_rental/services/proxmox_service.py
# -*- coding: utf-8 -*-
from proxmoxer import ProxmoxAPI
from .base_service import BaseHypervisorService
import logging

_logger = logging.getLogger(__name__)

class ProxmoxService(BaseHypervisorService):

    def _connect(self):
        try:
            return ProxmoxAPI(
                self.server.host,
                user=self.server.user,
                token_name=self.server.token_name,
                token_value=self.server.token_value,
                verify_ssl=self.server.verify_ssl,
                port=8006
            )
        except Exception as e:
            _logger.error(f"Proxmox connection failed: {e}")
            raise ConnectionError(f"Could not connect to Proxmox host {self.server.host}.") from e

    def _execute(self, action, *args, **kwargs):
        try:
            return action(*args, **kwargs)
        except Exception as e:
            _logger.error(f"Proxmox API error: {e}", exc_info=True)
            return None
    
    def get_version(self):
        version_info = self._execute(self.connection.version.get)
        return version_info.get('version') if version_info else "N/A"

    def list_nodes(self):
        nodes = self._execute(self.connection.nodes.get)
        return [{'id': n['node'], 'name': n['node']} for n in nodes] if nodes else []

    def list_storages(self, node_id):
        storages = self._execute(self.connection.nodes(node_id).storage.get) or []
        # Возвращаем все активные хранилища
        return [{'id': s['storage'], 'name': s['storage']} for s in storages if s.get('active', 0) == 1]
    
    def list_os_templates(self, node_id):
        """
        ИСПРАВЛЕНИЕ: Ищем и KVM, и LXC шаблоны, возвращаем их тип.
        """
        templates = []
        # 1. Ищем KVM шаблоны (полноценные ВМ)
        all_vms = self._execute(self.connection.nodes(node_id).qemu.get) or []
        for vm_data in all_vms:
            if vm_data.get('template') and vm_data.get('template') == 1:
                templates.append({
                    'id': vm_data.get('vmid'),
                    'name': f"{vm_data.get('name')} (ID: {vm_data.get('vmid')})",
                    'vmid': vm_data.get('vmid'),
                    'template_type': 'qemu' # Указываем тип
                })

        # 2. Ищем LXC шаблоны (файлы в хранилище)
        all_storages = self._execute(self.connection.nodes(node_id).storage.get) or []
        for storage in all_storages:
            storage_name = storage['storage']
            if 'vztmpl' in storage.get('content', ''):
                contents = self._execute(self.connection.nodes(node_id).storage(storage_name).content.get) or []
                for content_item in contents:
                    templates.append({
                        'id': content_item.get('volid'),
                        'name': content_item.get('volid').split('/')[-1], # Берем имя файла
                        'vmid': content_item.get('volid'), # Сохраняем volid для создания
                        'template_type': 'lxc' # Указываем тип
                    })
        return templates

    def create_container(self, node, vm_id, name, template_volid, cores, memory, disk, storage, password):
        """Создает LXC контейнер."""
        lxc_params = {
            'vmid': vm_id,
            'hostname': name,
            'ostemplate': template_volid,
            'storage': storage,
            'password': password,
            'cores': cores,
            'memory': memory,
            'rootfs': disk, # Для LXC размер диска указывается так
            'net0': 'name=eth0,bridge=vmbr0,ip=dhcp' # Пример сетевой конфигурации
        }
        return self._execute(self.connection.nodes(node).lxc.create, **lxc_params)


    def get_next_vmid(self):
        return self._execute(self.connection.cluster.nextid.get)

    def create_vm(self, node, vm_id, name, template_vmid, cores, memory, disk, storage):
        clone_params = {
            'newid': vm_id,
            'name': name,
            'full': True,
            'storage': storage,
            'target': node,
        }
        task_id = self._execute(self.connection.nodes(node).qemu(template_vmid).clone.post, **clone_params)
        if not task_id: return None

        config_params = {'cores': cores, 'memory': memory}
        self._execute(self.connection.nodes(node).qemu(vm_id).config.post, **config_params)
        
        self._execute(self.connection.nodes(node).qemu(vm_id).resize.put, disk='scsi0', size=f'+{disk}G')
        
        return task_id

    # ... остальные методы без изменений ...
    def start_vm(self, node, vm_id):
        return self._execute(self.connection.nodes(node).qemu(vm_id).status.start.post)

    def stop_vm(self, node, vm_id):
        return self._execute(self.connection.nodes(node).qemu(vm_id).status.stop.post)

    def reboot_vm(self, node, vm_id):
        return self._execute(self.connection.nodes(node).qemu(vm_id).status.reboot.post)

    def suspend_vm(self, node, vm_id):
        return self._execute(self.connection.nodes(node).qemu(vm_id).status.suspend.post)
    
    def list_all_vms(self, node):
        return self._execute(self.connection.nodes(node).qemu.get)

    def create_snapshot(self, node, vm_id, snap_name, description):
        params = {'snapname': snap_name, 'description': description}
        return self._execute(self.connection.nodes(node).qemu(vm_id).snapshot.post, **params)

    def rollback_snapshot(self, node, vm_id, snap_name):
        return self._execute(self.connection.nodes(node).qemu(vm_id).snapshot(snap_name).rollback.post)

    def delete_snapshot(self, node, vm_id, snap_name):
        return self._execute(self.connection.nodes(node).qemu(vm_id).snapshot(snap_name).delete)

    def get_console_url(self, node, vm_id):
        console_info = self._execute(self.connection.nodes(node).qemu(vm_id).vncproxy.post)
        if not console_info:
            raise ConnectionError("Could not get VNC proxy info from Proxmox.")
        host = self.server.host
        ticket = console_info['ticket']
        port = console_info['port']
        return f"https://{host}:8006/?console=kvm&vmid={vm_id}&node={node}&vnc_ticket={ticket}"