# vm_rental/exceptions.py
class VmRentalException(Exception):
    """Базовое исключение для VM Rental"""
    pass

class VmProvisioningError(VmRentalException):
    """Ошибка при создании VM"""
    pass

class VmOperationError(VmRentalException):
    """Ошибка операции VM"""
    pass

class HypervisorConnectionError(VmRentalException):
    """Ошибка подключения к гипервизору"""
    pass