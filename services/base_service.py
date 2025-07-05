# -*- coding: utf-8 -*-
import logging
_logger = logging.getLogger(__name__)

class HypervisorException(Exception):
    """Базовое исключение для ошибок гипервизора"""
    pass

class HypervisorConnectionError(HypervisorException):
    """Ошибка подключения к гипервизору"""
    pass

class HypervisorOperationError(HypervisorException):
    """Ошибка операции гипервизора"""
    pass
    
class BaseHypervisorService:
    """
    Abstract base class for all hypervisor services.
    It defines a common interface for the Odoo module to interact with.
    Each method must be implemented by a concrete service class.
    """
    def __init__(self, server_record):
        """
        Initializes the service with the Odoo server record.
        :param server_record: An Odoo record of 'hypervisor.server'.
        """
        if not server_record:
            raise ValueError("Server record cannot be empty.")
        self.server = server_record
        self.connection = self._connect()

    def _connect(self):
        """
        Establishes a connection to the hypervisor.
        Must be implemented by subclasses.
        :return: A connection object.
        """
        raise NotImplementedError()

    def get_version(self):
        """
        Gets the hypervisor version.
        :return: string (e.g., "7.4-1")
        """
        raise NotImplementedError()

    def list_nodes(self):
        """
        Gets a list of nodes/clusters.
        :return: list of dicts, e.g., [{'id': 'pve', 'name': 'Proxmox Host 1'}]
        """
        raise NotImplementedError()
        
    def list_storages(self, node_id):
        """
        Gets a list of storages/datastores for a given node.
        :param node_id: The unique identifier of the node/cluster.
        :return: list of dicts, e.g., [{'id': 'local-lvm', 'name': 'local-lvm'}]
        """
        raise NotImplementedError()

    def list_os_templates(self, node_id):
        """
        Gets a list of available VM templates.
        :param node_id: The unique identifier of the node/cluster.
        :return: list of dicts, e.g., [{'id': '101', 'name': 'ubuntu-22.04-template', 'vmid': 101}]
        """
        raise NotImplementedError()

    def get_next_vmid(self):
        """
        Gets the next available VM ID from the hypervisor.
        :return: int
        """
        raise NotImplementedError()

    def create_vm(self, node, vm_id, name, template_vmid, cores, memory, disk, storage):
        """
        Creates a new virtual machine.
        :return: A task ID or boolean indicating success.
        """
        raise NotImplementedError()

    def create_container(self, node, vm_id, name, template_volid, cores, memory, disk, storage, password):
        """Creates a new container."""
        raise NotImplementedError()

    def start_vm(self, node, vm_id):
        raise NotImplementedError()

    def stop_vm(self, node, vm_id):
        raise NotImplementedError()

    def reboot_vm(self, node, vm_id):
        raise NotImplementedError()

    def suspend_vm(self, node, vm_id):
        raise NotImplementedError()
        
    def list_all_vms(self, node):
        """
        Gets a list of all VMs on a specific node/cluster.
        :return: list of dicts with vm info (vmid, name, node, status).
        """
        raise NotImplementedError()
    # --- НОВЫЕ АБСТРАКТНЫЕ МЕТОДЫ ---
    def create_snapshot(self, node, vm_id, snap_name, description):
        """Creates a new snapshot for a VM."""
        raise NotImplementedError()

    def rollback_snapshot(self, node, vm_id, snap_name):
        """Rolls back a VM to a snapshot state."""
        raise NotImplementedError()

    def delete_snapshot(self, node, vm_id, snap_name):
        """Deletes a snapshot from a VM."""
        raise NotImplementedError()

    def get_console_url(self, node, vm_id):
        """Generates a one-time use console URL."""
        raise NotImplementedError()

    def delete_vm(self, node, vm_id):
        """Deletes a virtual machine from the hypervisor."""
        raise NotImplementedError()

    # --- НОВЫЕ АБСТРАКТНЫЕ МЕТОДЫ ---":

    def get_vm_config(self, node_or_uuid, vm_id=None):
        """
        Получает конфигурацию существующей VM

        Args:
            node_or_uuid: Для Proxmox - имя ноды, для VMware - UUID VM
            vm_id: Для Proxmox - ID VM, для VMware не используется

        Returns:
            dict: Словарь с ключами cores, memory, disk, vm_type
        """
        raise NotImplementedError()
