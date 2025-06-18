#  tests/test_vm_rental.py

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
