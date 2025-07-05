# vm_rental/services/vmware_service.py
# -*- coding: utf-8 -*-
from pyVim import connect
from pyVmomi import vim, vmodl
from .base_service import BaseHypervisorService, HypervisorOperationError
from odoo.exceptions import UserError
import logging
import ssl
import time

_logger = logging.getLogger(__name__)

class VmwareService(BaseHypervisorService):

    def __init__(self, server_record):
        super().__init__(server_record)
        self.content = self.connection.RetrieveContent()

    def _connect(self):
        try:
            si = connect.SmartConnectNoSSL(
                host=self.server.host,
                user=self.server.vmware_user,
                pwd=self.server.vmware_password,
                port=443
            )
            if not si:
                raise ConnectionError("Could not connect to vCenter.")
            return si
        except Exception as e:
            _logger.error(f"VMware connection failed: {e}")
            raise ConnectionError(f"Could not connect to vCenter {self.server.host}.") from e

    # --- Вспомогательные методы ---
    
    def _wait_for_task(self, task):
        """Ожидает завершения задачи VMware."""
        while task.info.state in [vim.TaskInfo.State.running, vim.TaskInfo.State.queued]:
            time.sleep(2)
        
        if task.info.state == vim.TaskInfo.State.success:
            return task.info.result
        else:
            error_msg = task.info.error.msg if task.info.error else "Unknown VMware task error"
            _logger.error(f"VMware task failed: {error_msg}")
            raise UserError(f"VMware task failed: {error_msg}")

    def _get_vm_by_uuid(self, vm_uuid):
        """Находит объект ВМ по ее instanceUuid."""
        vm = self.content.searchIndex.FindByUuid(uuid=vm_uuid, vmSearch=True, instanceUuid=True)
        if not vm:
            raise UserError(f"VMware VM with UUID {vm_uuid} not found.")
        return vm
        
    def _get_snapshot_in_tree(self, snapshots, snap_name):
        """Рекурсивно ищет снапшот по имени в дереве снапшотов."""
        for s in snapshots:
            if s.name == snap_name:
                return s.snapshot
            res = self._get_snapshot_in_tree(s.childSnapshotList, snap_name)
            if res:
                return res
        return None

    # --- Реализация базовых методов ---

    def get_version(self):
        return self.content.about.fullName

    def list_nodes(self):
        """
        ИСПРАВЛЕНИЕ: Возвращаем "чистые" имена без суффиксов.
        """
        nodes = []
        # Ищем кластеры
        container = self.content.viewManager.CreateContainerView(self.content.rootFolder, [vim.ClusterComputeResource], True)
        for cluster in container.view:
            nodes.append({'id': cluster.name, 'name': cluster.name})
        container.Destroy()

        # Ищем хосты, которые не в кластере
        container = self.content.viewManager.CreateContainerView(self.content.rootFolder, [vim.HostSystem], True)
        for host in container.view:
            if not isinstance(host.parent, vim.ClusterComputeResource):
                # Добавляем чистое имя хоста
                nodes.append({'id': host.name, 'name': host.name})
        container.Destroy()
        
        return [dict(t) for t in {tuple(d.items()) for d in nodes}]

    # ... все остальные методы (list_storages, create_vm и т.д.) остаются без изменений ...
    # Они уже ожидают "чистое" имя ноды, поэтому теперь все должно работать
    def list_storages(self, node_id):
        if not node_id: return []
        target_node = None
        container = self.content.viewManager.CreateContainerView(self.content.rootFolder, [vim.ComputeResource], True)
        for compute_resource in container.view:
            if compute_resource.name == node_id:
                target_node = compute_resource
                break
        container.Destroy()
        if not target_node:
            _logger.warning(f"Could not find node '{node_id}' to list its storages.")
            return []
        storages = []
        for datastore in target_node.datastore:
            storages.append({'id': datastore.name, 'name': datastore.name})
        return storages

    def list_os_templates(self, node_id=None):
        # Этот метод ищет все шаблоны, он также не зависит от ноды
        container = self.content.viewManager.CreateContainerView(self.content.rootFolder, [vim.VirtualMachine], True)
        templates = []
        for vm in container.view:
            if vm.config.template:
                templates.append({
                    'id': vm.summary.config.instanceUuid, 
                    'name': vm.name,
                    'vmid': vm.summary.config.instanceUuid
                })
        container.Destroy()
        return templates

    
    def list_all_vms(self, node_id):
        """
        ИСПРАВЛЕНИЕ: Правильно обходим иерархию ComputeResource -> HostSystem -> VM.
        """
        if not node_id:
            return []
        
        target_node = None
        container = self.content.viewManager.CreateContainerView(self.content.rootFolder, [vim.ComputeResource], True)
        for compute_resource in container.view:
            if compute_resource.name == node_id:
                target_node = compute_resource
                break
        container.Destroy()
        
        if not target_node:
            _logger.warning(f"Could not find node '{node_id}' to list its VMs.")
            return []
            
        vms = []
        # Проверяем, есть ли у ComputeResource свойство .host
        if hasattr(target_node, 'host'):
            # Итерируем по хостам внутри ComputeResource
            for host in target_node.host:
                # И уже у хоста берем список его ВМ
                for vm in host.vm:
                    if not vm.config.template:
                        vms.append({
                            'vmid': vm.summary.config.instanceUuid,
                            'name': vm.name,
                            'status': vm.summary.runtime.powerState,
                        })
        return vms

    def get_next_vmid(self):
        """Для VMware ID генерируется при создании, возвращаем None."""
        return None

    # --- Управление жизненным циклом ВМ ---

    def start_vm(self, node, vm_uuid):
        vm = self._get_vm_by_uuid(vm_uuid)
        if vm.runtime.powerState != 'poweredOn':
            task = vm.PowerOnVM_Task()
            self._wait_for_task(task)
        return True

    def stop_vm(self, node, vm_uuid):
        vm = self._get_vm_by_uuid(vm_uuid)
        if vm.runtime.powerState != 'poweredOff':
            task = vm.PowerOffVM_Task()
            self._wait_for_task(task)
        return True

    def reboot_vm(self, node, vm_uuid):
        vm = self._get_vm_by_uuid(vm_uuid)
        try:
            vm.RebootGuest()
            return True
        except Exception as e:
            # Если гостевые утилиты не установлены, RebootGuest не сработает.
            # Можно сделать Reset, но это "жесткая" перезагрузка.
            _logger.warning(f"Could not reboot guest for VM {vm_uuid}, attempting reset: {e}")
            task = vm.ResetVM_Task()
            self._wait_for_task(task)
            return True

    def suspend_vm(self, node, vm_uuid):
        vm = self._get_vm_by_uuid(vm_uuid)
        if vm.runtime.powerState == 'poweredOn':
            task = vm.SuspendVM_Task()
            self._wait_for_task(task)
        return True

    def create_vm(self, node, name, template_vmid, cores, memory, disk, storage, **kwargs):
        template = self._get_vm_by_uuid(template_vmid)
        if not template: raise UserError(f"VMware Template with UUID {template_vmid} not found.")
        
        datastore = None
        container = self.content.viewManager.CreateContainerView(self.content.rootFolder, [vim.Datastore], True)
        for ds in container.view:
            if ds.name == storage:
                datastore = ds
                break
        container.Destroy()
        if not datastore: raise UserError(f"Datastore '{storage}' not found.")
        
        # --- ФИНАЛЬНОЕ ИСПРАВЛЕНИЕ: Ищем конкретные типы ---
        target_node = None
        # Ищем среди хостов и кластеров
        view_types = [vim.HostSystem, vim.ClusterComputeResource]
        container = self.content.viewManager.CreateContainerView(self.content.rootFolder, view_types, True)
        for res in container.view:
            if res.name == node:
                target_node = res
                break
        container.Destroy()
        
        if not target_node: raise UserError(f"Target node (Cluster or Host) '{node}' not found.")
        # --- КОД ДЛЯ ГЛУБОКОГО ЛОГИРОВАНИЯ ---
        _logger.info("--- DEBUGGING TARGET NODE ---")
        _logger.info(f"Node Name from Odoo: {node}")
        _logger.info(f"Found vSphere Object: {target_node}")
        _logger.info(f"Type of vSphere Object: {type(target_node)}")
        
        _logger.info("--- DUMPING ALL ATTRIBUTES ---")
        for prop in sorted(dir(target_node)):
            if not prop.startswith('_'): # Пропускаем служебные атрибуты
                try:
                    value = getattr(target_node, prop)
                    _logger.info(f"  - Attribute '{prop}': {value}")
                except Exception as e:
                    _logger.info(f"  - Attribute '{prop}': Could not read value ({e})")
        _logger.info("--- END DEBUGGING ---")
        # --- КОНЕЦ КОДА ДЛЯ ЛОГИРОВАНИЯ ---
   
                
        # Создаем спецификацию с пулом. Для standalone хоста это его корневой пул.
        relospec = vim.vm.RelocateSpec(datastore=datastore)      
        if isinstance(target_node, vim.HostSystem):
            # Для хоста пул ресурсов находится у его родителя
            pool = target_node.parent.resourcePool
            if not pool: raise UserError(f"Could not find a Resource Pool on the parent of host '{node}'.")
            relospec.pool = pool
            relospec.host = target_node # Указываем сам хост
        elif isinstance(target_node, vim.ClusterComputeResource):
            # Для кластера пул ресурсов находится у него самого
            pool = target_node.resourcePool
            if not pool: raise UserError(f"The selected cluster '{node}' does not have a Resource Pool.")
            relospec.pool = pool

  
        clonespec = vim.vm.CloneSpec(location=relospec, powerOn=False, template=False)
        
        task = template.Clone(folder=template.parent, name=name, spec=clonespec)
        new_vm = self._wait_for_task(task)
        if not new_vm: raise UserError("VMware clone task failed to return a new VM object.")
        
        config_spec = vim.vm.ConfigSpec(numCPUs=cores, memoryMB=memory)
        disk_spec = vim.vm.device.VirtualDeviceSpec()
        disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
        
        for device in new_vm.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualDisk):
                disk_spec.device = device
                disk_spec.device.capacityInKB = disk * 1024 * 1024
                break
        if disk_spec.device:
            config_spec.deviceChange = [disk_spec]
            
        task = new_vm.ReconfigVM_Task(spec=config_spec)
        self._wait_for_task(task)
        
        task = new_vm.PowerOnVM_Task()
        self._wait_for_task(task)
        
        return new_vm.summary.config.instanceUuid


    # --- Управление снапшотами ---

    def create_snapshot(self, node, vm_uuid, snap_name, description):
        vm = self._get_vm_by_uuid(vm_uuid)
        task = vm.CreateSnapshot_Task(name=snap_name, description=description, memory=False, quiesce=True)
        self._wait_for_task(task)
        return True

    def rollback_snapshot(self, node, vm_uuid, snap_name):
        vm = self._get_vm_by_uuid(vm_uuid)
        snapshot = self._get_snapshot_in_tree(vm.snapshot.rootSnapshotList, snap_name)
        if not snapshot:
            raise UserError(f"Snapshot '{snap_name}' not found.")
        
        task = snapshot.RevertToSnapshot_Task()
        self._wait_for_task(task)
        return True

    def delete_snapshot(self, node, vm_uuid, snap_name):
        vm = self._get_vm_by_uuid(vm_uuid)
        snapshot = self._get_snapshot_in_tree(vm.snapshot.rootSnapshotList, snap_name)
        if not snapshot:
            raise UserError(f"Snapshot '{snap_name}' not found.")
        
        task = snapshot.RemoveSnapshot_Task(removeChildren=False)
        self._wait_for_task(task)
        return True

    # --- Консоль ---

    def get_console_url(self, node, vm_uuid):
        vm = self._get_vm_by_uuid(vm_uuid)
        
        # Получаем тикет для HTML5 консоли (WebMKS)
        mks_ticket = vm.AcquireMksTicket()
        
        # Конструируем URL для iframe
        host = self.server.host
        # Для современных версий vCenter (6.7+) URL выглядит так
        return (
            f"https://{host}/ui/webconsole.html?"
            f"vmId={vm._moId}&"  # Внутренний Managed Object ID
            f"vmName={vm.name}&"
            f"serverGuid={self.content.about.instanceUuid}&"
            f"host={mks_ticket.host}:{mks_ticket.port}&"
            f"ticket={mks_ticket.ticket}"
        )

    def delete_vm(self, node, vm_uuid):
        """
        Deletes a virtual machine from vCenter.
        It must be powered off first.
        """
        vm = self._get_vm_by_uuid(vm_uuid)

        # Power off the VM if it is running
        if vm.runtime.powerState != 'poweredOff':
            task = vm.PowerOffVM_Task()
            self._wait_for_task(task)

        # Destroy the VM
        task = vm.Destroy_Task()
        self._wait_for_task(task)
        return True

    def get_vm_config(self, vm_uuid):
        """Получает конфигурацию существующей VM в VMware"""
        try:
            vm = self._get_vm_by_uuid(vm_uuid)
            if not vm:
                raise HypervisorOperationError(f"VM with UUID {vm_uuid} not found")

            # Получаем конфигурацию
            config = vm.summary.config

            # Вычисляем размер диска (сумма всех дисков)
            total_disk_gb = 0
            for device in vm.config.hardware.device:
                if hasattr(device, 'capacityInKB'):
                    total_disk_gb += int(device.capacityInKB / 1024 / 1024)  # KB -> GB

            return {
                'cores': config.numCpu,
                'memory': config.memorySizeMB,
                'disk': total_disk_gb or 20,  # Если не удалось вычислить, берем 20GB
                'vm_type': 'vmware'
            }
        except Exception as e:
            _logger.error(f"Failed to get VMware VM config for {vm_uuid}: {e}")
            raise HypervisorOperationError(f"Cannot get VM {vm_uuid} configuration: {e}")
