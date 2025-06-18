# tests/test_vm_rental.py

from odoo.tests import common
from odoo.exceptions import UserError, ValidationError
from unittest.mock import patch, MagicMock

class TestVmRental(common.TransactionCase):
    
    def setUp(self):
        super().setUp()
        
        # Создаем тестовые данные
        self.partner = self.env['res.partner'].create({
            'name': 'Test Customer',
            'email': 'test@example.com',
        })
        
        # Создаем тестовый сервер гипервизора
        self.hypervisor_server = self.env['hypervisor.server'].create({
            'name': 'Test Proxmox Server',
            'hypervisor_type': 'proxmox',
            'host': '192.168.1.100',
            'user': 'root@pam',
            'token_name': 'test_token',
            'token_value': 'test_token_value',
        })
        
        # Создаем тестовые ресурсы
        self.node = self.env['hypervisor.node'].create({
            'name': 'test-node-01',
            'server_id': self.hypervisor_server.id,
        })
        
        self.storage = self.env['hypervisor.storage'].create({
            'name': 'local-lvm',
            'server_id': self.hypervisor_server.id,
            'node_ids': [(4, self.node.id)],
        })
        
        self.template = self.env['hypervisor.template'].create({
            'name': 'Ubuntu 22.04',
            'vmid': '9001',
            'server_id': self.hypervisor_server.id,
            'template_type': 'qemu',
        })
    
    def test_vm_creation_validation(self):
        """Тест валидации при создании ВМ"""
        # Тест с некорректными ресурсами
        with self.assertRaises(ValidationError):
            self.env['vm_rental.machine'].create({
                'name': 'Test VM',
                'partner_id': self.partner.id,
                'hypervisor_server_id': self.hypervisor_server.id,
                'cores': 0,  # Некорректное значение
                'memory': 1024,
                'disk': 10,
            })
        
        with self.assertRaises(ValidationError):
            self.env['vm_rental.machine'].create({
                'name': 'Test VM',
                'partner_id': self.partner.id,
                'hypervisor_server_id': self.hypervisor_server.id,
                'cores': 2,
                'memory': 64,  # Слишком мало памяти
                'disk': 10,
            })
    
    def test_vm_lifecycle(self):
        """Тест жизненного цикла ВМ"""
        # Создаем ВМ
        vm = self.env['vm_rental.machine'].create({
            'name': 'Test VM',
            'partner_id': self.partner.id,
            'hypervisor_server_id': self.hypervisor_server.id,
            'hypervisor_node_id': self.node.id,
            'hypervisor_storage_id': self.storage.id,
            'hypervisor_template_id': self.template.id,
            'cores': 2,
            'memory': 2048,
            'disk': 20,
        })
        
        # Проверяем начальное состояние
        self.assertEqual(vm.state, 'pending')
        self.assertFalse(vm.hypervisor_vm_ref)
        
        # Мокаем сервис гипервизора
        with patch.object(vm, '_get_hypervisor_service') as mock_service:
            mock_service.return_value.get_next_vmid.return_value = '100'
            mock_service.return_value.create_vm.return_value = 'task-123'
            
            # Провижининг ВМ
            vm.action_provision_vm()
            
            # Проверяем изменения состояния
            self.assertEqual(vm.state, 'active')
            self.assertEqual(vm.hypervisor_vm_ref, '100')
            self.assertEqual(vm.hypervisor_node_name, 'test-node-01')
            self.assertTrue(vm.start_date)
            self.assertTrue(vm.end_date)
    
    def test_vm_expiry_cron(self):
        """Тест cron задачи проверки истечения срока"""
        # Создаем ВМ с истекшим сроком
        vm = self.env['vm_rental.machine'].create({
            'name': 'Expired VM',
            'partner_id': self.partner.id,
            'hypervisor_server_id': self.hypervisor_server.id,
            'hypervisor_vm_ref': '101',
            'hypervisor_node_name': 'test-node-01',
            'state': 'active',
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',  # Истекший срок
            'cores': 1,
            'memory': 1024,
            'disk': 10,
        })
        
        # Мокаем сервис
        with patch.object(vm, '_get_hypervisor_service') as mock_service:
            mock_service.return_value.suspend_vm.return_value = True
            
            # Запускаем cron
            self.env['vm_rental.machine']._cron_check_expiry()
            
            # Проверяем, что ВМ приостановлена
            self.assertEqual(vm.state, 'suspended')
            mock_service.return_value.suspend_vm.assert_called_once()
    
    def test_snapshot_operations(self):
        """Тест операций со снапшотами"""
        vm = self.env['vm_rental.machine'].create({
            'name': 'VM with Snapshots',
            'partner_id': self.partner.id,
            'hypervisor_server_id': self.hypervisor_server.id,
            'hypervisor_vm_ref': '102',
            'hypervisor_node_name': 'test-node-01',
            'state': 'active',
            'cores': 2,
            'memory': 2048,
            'disk': 50,
        })
        
        # Создаем снапшот
        snapshot = self.env['vm.snapshot'].create({
            'name': 'Test Snapshot',
            'description': 'Test description',
            'vm_instance_id': vm.id,
            'proxmox_name': 'snap_20240101120000',
        })
        
        self.assertEqual(len(vm.snapshot_ids), 1)
        self.assertEqual(vm.snapshot_ids[0].name, 'Test Snapshot')
    
    def test_partner_access_rules(self):
        """Тест правил доступа для партнеров"""
        # Создаем второго партнера
        partner2 = self.env['res.partner'].create({
            'name': 'Another Customer',
            'email': 'another@example.com',
        })
        
        # Создаем ВМ для первого партнера
        vm1 = self.env['vm_rental.machine'].create({
            'name': 'VM Partner 1',
            'partner_id': self.partner.id,
            'hypervisor_server_id': self.hypervisor_server.id,
            'cores': 1,
            'memory': 1024,
            'disk': 10,
        })
        
        # Создаем ВМ для второго партнера
        vm2 = self.env['vm_rental.machine'].create({
            'name': 'VM Partner 2',
            'partner_id': partner2.id,
            'hypervisor_server_id': self.hypervisor_server.id,
            'cores': 1,
            'memory': 1024,
            'disk': 10,
        })
        
        # Проверяем, что каждый партнер видит только свои ВМ
        # (это потребует создания тестовых пользователей с правами портала)


class TestHypervisorService(common.TransactionCase):
    
    def setUp(self):
        super().setUp()
        
        self.server = self.env['hypervisor.server'].create({
            'name': 'Test Server',
            'hypervisor_type': 'proxmox',
            'host': '192.168.1.100',
            'user': 'root@pam',
            'token_name': 'test',
            'token_value': 'test123',
        })
    
    @patch('vm_rental.services.proxmox_service.ProxmoxAPI')
    def test_proxmox_connection(self, mock_proxmox_api):
        """Тест подключения к Proxmox"""
        # Настраиваем мок
        mock_instance = MagicMock()
        mock_proxmox_api.return_value = mock_instance
        mock_instance.version.get.return_value = {'version': '7.4-1'}
        
        # Получаем сервис
        service = self.server._get_service_manager()
        
        # Проверяем версию
        version = service.get_version()
        self.assertEqual(version, '7.4-1')
        
        # Проверяем, что подключение было создано с правильными параметрами
        mock_proxmox_api.assert_called_once_with(
            '192.168.1.100',
            user='root@pam',
            token_name='test',
            token_value='test123',
            verify_ssl=True,
            port=8006
        )
    
    @patch('vm_rental.services.proxmox_service.ProxmoxAPI')
    def test_list_nodes(self, mock_proxmox_api):
        """Тест получения списка нод"""
        # Настраиваем мок
        mock_instance = MagicMock()
        mock_proxmox_api.return_value = mock_instance
        mock_instance.nodes.get.return_value = [
            {'node': 'pve01', 'status': 'online'},
            {'node': 'pve02', 'status': 'online'},
        ]
        
        service = self.server._get_service_manager()
        nodes = service.list_nodes()
        
        self.assertEqual(len(nodes), 2)
        self.assertEqual(nodes[0]['name'], 'pve01')
        self.assertEqual(nodes[1]['name'], 'pve02')


class TestVmLinking(common.TransactionCase):
    
    def setUp(self):
        super().setUp()
        
        self.partner = self.env['res.partner'].create({
            'name': 'Test Customer',
        })
        
        self.server = self.env['hypervisor.server'].create({
            'name': 'Test Server',
            'hypervisor_type': 'proxmox',
            'host': '192.168.1.100',
            'user': 'root@pam',
            'token_name': 'test',
            'token_value': 'test123',
        })
        
        self.node = self.env['hypervisor.node'].create({
            'name': 'pve01',
            'server_id': self.server.id,
        })
    
    @patch.object(type(self.server), '_get_service_manager')
    def test_fetch_and_link_vms(self, mock_get_service):
        """Тест получения и привязки существующих ВМ"""
        # Настраиваем мок сервиса
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_service.list_all_vms.return_value = [
            {'vmid': '100', 'name': 'existing-vm-1', 'status': 'running'},
            {'vmid': '101', 'name': 'existing-vm-2', 'status': 'stopped'},
        ]
        
        # Создаем задание на привязку
        linking_job = self.env['vm_rental.linking_job'].create({
            'hypervisor_server_id': self.server.id,
            'partner_id': self.partner.id,
        })
        
        # Получаем список ВМ
        linking_job.action_fetch_vms()
        
        # Проверяем, что ВМ были найдены
        self.assertEqual(len(linking_job.line_ids), 2)
        
        # Выбираем первую ВМ для привязки
        linking_job.line_ids[0].should_link = True
        
        # Выполняем привязку
        result = linking_job.action_link_vms()
        
        # Проверяем, что ВМ была создана
        linked_vms = self.env['vm_rental.machine'].search([
            ('hypervisor_vm_ref', '=', '100')
        ])
        self.assertEqual(len(linked_vms), 1)
        self.assertEqual(linked_vms.name, 'existing-vm-1')
        self.assertEqual(linked_vms.partner_id.id, self.partner.id)
        self.assertEqual(linked_vms.state, 'active')
        
