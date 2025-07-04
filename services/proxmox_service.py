# vm_rental/services/proxmox_service.py
# -*- coding: utf-8 -*-
from proxmoxer import ProxmoxAPI
from .base_service import BaseHypervisorService, HypervisorConnectionError, HypervisorOperationError
import logging
import time

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
        """Выполнение операции с улучшенной обработкой ошибок"""
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                return action(*args, **kwargs)
            except Exception as e:
                error_msg = str(e)
                _logger.error(f"Proxmox API error (attempt {attempt + 1}/{max_retries}): {error_msg}", exc_info=True)
                
                # Проверка на временные ошибки
                if any(temp_err in error_msg.lower() for temp_err in ['timeout', 'connection reset', 'temporary']):
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                
                # Проверка на критические ошибки
                if any(crit_err in error_msg.lower() for crit_err in ['authentication', 'unauthorized', 'forbidden']):
                    raise HypervisorConnectionError(f"Authentication failed: {error_msg}")
                
                # Для последней попытки или некритических ошибок
                if attempt == max_retries - 1:
                    raise HypervisorOperationError(f"Operation failed after {max_retries} attempts: {error_msg}")
        
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
        """Универсальный метод запуска VM/LXC с правильным определением типа"""
        vm_type = self._get_vm_type(node, vm_id)
        _logger.info(f"Starting {vm_type.upper()} {vm_id} on node {node}")

        try:
            if vm_type == 'qemu':
                return self._execute(self.connection.nodes(node).qemu(vm_id).status.start.post)
            else:  # lxc
                return self._execute(self.connection.nodes(node).lxc(vm_id).status.start.post)
        except Exception as e:
            _logger.error(f"Failed to start {vm_type.upper()} {vm_id}: {e}")
            raise HypervisorOperationError(f"Cannot start {vm_type.upper()} {vm_id}: {e}")

    def stop_vm(self, node, vm_id):
        """Универсальный метод остановки VM/LXC с правильным определением типа"""
        vm_type = self._get_vm_type(node, vm_id)
        _logger.info(f"Stopping {vm_type.upper()} {vm_id} on node {node}")

        try:
            if vm_type == 'qemu':
                return self._execute(self.connection.nodes(node).qemu(vm_id).status.stop.post)
            else:  # lxc
                return self._execute(self.connection.nodes(node).lxc(vm_id).status.stop.post)
        except Exception as e:
            _logger.error(f"Failed to stop {vm_type.upper()} {vm_id}: {e}")
            raise HypervisorOperationError(f"Cannot stop {vm_type.upper()} {vm_id}: {e}")

    def reboot_vm(self, node, vm_id):
        """Перезагрузка VM/LXC с правильным определением типа"""
        vm_type = self._get_vm_type(node, vm_id)
        _logger.info(f"Rebooting {vm_type.upper()} {vm_id} on node {node}")

        try:
            if vm_type == 'qemu':
                return self._execute(self.connection.nodes(node).qemu(vm_id).status.reboot.post)
            else:  # lxc
                return self._execute(self.connection.nodes(node).lxc(vm_id).status.reboot.post)
        except Exception as e:
            _logger.error(f"Failed to reboot {vm_type.upper()} {vm_id}: {e}")
            raise HypervisorOperationError(f"Cannot reboot {vm_type.upper()} {vm_id}: {e}")

    def suspend_vm(self, node, vm_id):
        return self._execute(self.connection.nodes(node).qemu(vm_id).status.suspend.post)

    def list_all_vms(self, node):
        """Получает список всех VM и LXC контейнеров с отладкой"""
        all_vms = []

        # 1. Получаем QEMU VM
        try:
            qemu_vms = self._execute(self.connection.nodes(node).qemu.get) or []
            _logger.info(f"Found {len(qemu_vms)} QEMU VMs on node {node}")
            for vm in qemu_vms:
                _logger.debug(f"QEMU VM: {vm}")
            all_vms.extend(qemu_vms)
        except Exception as e:
            _logger.error(f"Failed to get QEMU VMs on node {node}: {e}")

        # 2. Получаем LXC контейнеры
        try:
            lxc_containers = self._execute(self.connection.nodes(node).lxc.get) or []
            _logger.info(f"Found {len(lxc_containers)} LXC containers on node {node}")
            for container in lxc_containers:
                _logger.debug(f"LXC container: {container}")
                # Убеждаемся, что структура данных совпадает с QEMU
                if 'name' not in container and 'hostname' in container:
                    container['name'] = container['hostname']
            all_vms.extend(lxc_containers)
        except Exception as e:
            _logger.error(f"Failed to get LXC containers on node {node}: {e}")

        _logger.info(f"Total VMs/containers found on node {node}: {len(all_vms)}")
        return all_vms

    def create_snapshot(self, node, vm_id, snap_name, description):
        """Создание снапшота (только для QEMU VM)"""
        vm_type = self._get_vm_type(node, vm_id)

        if vm_type != 'qemu':
            raise HypervisorOperationError(f"Snapshots are not supported for LXC containers (ID: {vm_id})")

        _logger.info(f"Creating snapshot '{snap_name}' for QEMU VM {vm_id}")
        params = {'snapname': snap_name, 'description': description}

        try:
            return self._execute(self.connection.nodes(node).qemu(vm_id).snapshot.post, **params)
        except Exception as e:
            _logger.error(f"Failed to create snapshot for VM {vm_id}: {e}")
            raise HypervisorOperationError(f"Cannot create snapshot for VM {vm_id}: {e}")

    def rollback_snapshot(self, node, vm_id, snap_name):
        """Откат к снапшоту (только для QEMU VM)"""
        vm_type = self._get_vm_type(node, vm_id)

        if vm_type != 'qemu':
            raise HypervisorOperationError(f"Snapshots are not supported for LXC containers (ID: {vm_id})")

        _logger.info(f"Rolling back to snapshot '{snap_name}' for QEMU VM {vm_id}")

        try:
            return self._execute(self.connection.nodes(node).qemu(vm_id).snapshot(snap_name).rollback.post)
        except Exception as e:
            _logger.error(f"Failed to rollback snapshot for VM {vm_id}: {e}")
            raise HypervisorOperationError(f"Cannot rollback snapshot for VM {vm_id}: {e}")

    def delete_snapshot(self, node, vm_id, snap_name):
        """Удаление снапшота (только для QEMU VM)"""
        vm_type = self._get_vm_type(node, vm_id)

        if vm_type != 'qemu':
            raise HypervisorOperationError(f"Snapshots are not supported for LXC containers (ID: {vm_id})")

        _logger.info(f"Deleting snapshot '{snap_name}' for QEMU VM {vm_id}")

        try:
            return self._execute(self.connection.nodes(node).qemu(vm_id).snapshot(snap_name).delete)
        except Exception as e:
            _logger.error(f"Failed to delete snapshot for VM {vm_id}: {e}")
            raise HypervisorOperationError(f"Cannot delete snapshot for VM {vm_id}: {e}")

    def get_console_url(self, node, vm_id):
        """Генерация URL консоли с правильным определением типа"""
        vm_type = self._get_vm_type(node, vm_id)

        try:
            if vm_type == 'qemu':
                console_info = self._execute(self.connection.nodes(node).qemu(vm_id).vncproxy.post)
                console_type = 'kvm'
            else:  # lxc
                console_info = self._execute(self.connection.nodes(node).lxc(vm_id).vncproxy.post)
                console_type = 'lxc'

            if not console_info:
                raise ConnectionError(f"Could not get VNC proxy info for {vm_type.upper()} {vm_id}")

            host = self.server.host
            ticket = console_info['ticket']
            port = console_info['port']
            return f"https://{host}:8006/?console={console_type}&vmid={vm_id}&node={node}&vnc_ticket={ticket}"

        except Exception as e:
            _logger.error(f"Failed to get console URL for {vm_type.upper()} {vm_id}: {e}")
            raise HypervisorOperationError(f"Cannot get console URL for {vm_type.upper()} {vm_id}: {e}")

    def delete_vm(self, node, vm_id):
        """Удаление VM/LXC с правильным определением типа"""
        vm_type = self._get_vm_type(node, vm_id)
        _logger.info(f"Deleting {vm_type.upper()} {vm_id} on node {node}")

        try:
            if vm_type == 'qemu':
                return self._execute(self.connection.nodes(node).qemu(vm_id).delete)
            else:  # lxc
                return self._execute(self.connection.nodes(node).lxc(vm_id).delete)
        except Exception as e:
            _logger.error(f"Failed to delete {vm_type.upper()} {vm_id}: {e}")
            raise HypervisorOperationError(f"Cannot delete {vm_type.upper()} {vm_id}: {e}")

    def get_vm_config(self, node, vm_id, vm_type=None):
        """Получает конфигурацию существующей VM с опциональным типом"""

        # Если тип не передан, определяем его
        if vm_type is None:
            vm_type = self._get_vm_type(node, vm_id)

        _logger.info(f"Getting config for {vm_type.upper()} {vm_id} on node {node}")

        try:
            if vm_type == 'qemu':
                # Получаем конфигурацию QEMU VM
                config = self._execute(self.connection.nodes(node).qemu(vm_id).config.get)
                if config:
                    return {
                        'cores': int(config.get('cores', 1)),
                        'memory': int(config.get('memory', 1024)),
                        'disk': self._extract_disk_size(config),
                        'vm_type': 'qemu'
                    }
            elif vm_type == 'lxc':
                # Получаем конфигурацию LXC контейнера
                config = self._execute(self.connection.nodes(node).lxc(vm_id).config.get)
                if config:
                    return {
                        'cores': int(config.get('cores', 1)),
                        'memory': int(config.get('memory', 512)),
                        'disk': self._extract_lxc_disk_size(config),
                        'vm_type': 'lxc'
                    }
            else:
                raise HypervisorOperationError(f"Unsupported VM type: {vm_type}")

        except Exception as e:
            _logger.error(f"Failed to get {vm_type.upper()} config for {vm_id}: {e}")
            raise HypervisorOperationError(f"Cannot get {vm_type.upper()} {vm_id} configuration: {e}")

        # Fallback - возвращаем значения по умолчанию
        _logger.warning(f"Could not get config for {vm_type.upper()} {vm_id}, using defaults")
        return {
            'cores': 1,
            'memory': 1024 if vm_type == 'qemu' else 512,
            'disk': 10 if vm_type == 'qemu' else 8,
            'vm_type': vm_type
        }

    def _extract_disk_size(self, config):
        """Извлекает размер диска из конфигурации QEMU VM"""
        for key, value in config.items():
            if key.startswith(('scsi', 'ide', 'sata', 'virtio')):
                # Формат: "storage:size" или "storage:vm-xxx-disk-x,size=xxG"
                if 'size=' in str(value):
                    size_part = str(value).split('size=')[1].split(',')[0]
                    if size_part.endswith('G'):
                        return int(size_part[:-1])
                elif ':' in str(value):
                    parts = str(value).split(':')
                    if len(parts) > 1 and parts[1].endswith('G'):
                        return int(parts[1][:-1])
        return 10  # Значение по умолчанию

    def _extract_lxc_disk_size(self, config):
        """Извлекает размер диска из конфигурации LXC контейнера"""
        rootfs = config.get('rootfs', '')
        if 'size=' in rootfs:
            size_part = rootfs.split('size=')[1].split(',')[0]
            if size_part.endswith('G'):
                return int(size_part[:-1])
        return 8  # Значение по умолчанию для LXC


    def _get_vm_type(self, node, vm_id):
        """Определяет тип VM (qemu или lxc) по VMID"""
        try:
            # Получаем список QEMU VM
            qemu_vms = self._execute(self.connection.nodes(node).qemu.get) or []
            for vm in qemu_vms:
                if str(vm.get('vmid')) == str(vm_id):
                    return 'qemu'
        except Exception:
            pass

        try:
            # Получаем список LXC контейнеров
            lxc_containers = self._execute(self.connection.nodes(node).lxc.get) or []
            for container in lxc_containers:
                if str(container.get('vmid')) == str(vm_id):
                    return 'lxc'
        except Exception:
            pass

        # По умолчанию считаем QEMU VM
        return 'qemu'


