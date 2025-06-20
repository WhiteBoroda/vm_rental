from odoo import api, _
from odoo.exceptions import ValidationError


class VmResourceTrait:
    """
    Trait (примесь) для работы с ресурсами VM.
    Используется через композицию, не наследование.
    Полностью статический класс без зависимостей от Odoo моделей.
    """

    # Константы по умолчанию
    DEFAULT_CORES = 1
    DEFAULT_MEMORY = 1024  # MiB
    DEFAULT_DISK = 10  # GiB
    MIN_MEMORY = 128  # MiB

    @staticmethod
    def validate_resources(cores, memory, disk, env=None):
        """
        Статическая валидация ресурсов VM

        Args:
            cores (int): Количество CPU ядер
            memory (int): Объем памяти в MiB
            disk (int): Размер диска в GiB
            env (Environment): Odoo environment для получения лимитов (опционально)

        Raises:
            ValidationError: При некорректных значениях ресурсов
        """
        # Базовая валидация
        if cores <= 0:
            raise ValidationError(_("CPU cores must be greater than 0"))
        if memory < VmResourceTrait.MIN_MEMORY:
            raise ValidationError(_("Memory must be at least %d MiB") % VmResourceTrait.MIN_MEMORY)
        if disk <= 0:
            raise ValidationError(_("Disk size must be greater than 0 GiB"))

        # Проверка максимальных лимитов (если передан env)
        if env:
            max_cores = int(env['ir.config_parameter'].sudo().get_param('vm_rental.max_cores', 64))
            max_memory = int(env['ir.config_parameter'].sudo().get_param('vm_rental.max_memory', 131072))
            max_disk = int(env['ir.config_parameter'].sudo().get_param('vm_rental.max_disk', 10240))

            if cores > max_cores:
                raise ValidationError(_("CPU cores cannot exceed %d") % max_cores)
            if memory > max_memory:
                raise ValidationError(_("Memory cannot exceed %d MiB") % max_memory)
            if disk > max_disk:
                raise ValidationError(_("Disk size cannot exceed %d GiB") % max_disk)

    @staticmethod
    def get_resource_summary(cores, memory, disk, detailed=False):
        """
        Статическое создание сводки ресурсов

        Args:
            cores (int): Количество CPU ядер
            memory (int): Объем памяти в MiB
            disk (int): Размер диска в GiB
            detailed (bool): Детальное описание или краткое

        Returns:
            str: Текстовое описание ресурсов
        """
        if detailed:
            core_text = "core" if cores == 1 else "cores"
            return f"{cores} CPU {core_text}, {memory} MiB RAM, {disk} GiB storage"
        else:
            return f"{cores} CPU, {memory} MiB RAM, {disk} GiB Disk"

    @staticmethod
    def get_default_config():
        """Статическая конфигурация по умолчанию"""
        return {
            'cores': VmResourceTrait.DEFAULT_CORES,
            'memory': VmResourceTrait.DEFAULT_MEMORY,
            'disk': VmResourceTrait.DEFAULT_DISK
        }

    @staticmethod
    def get_predefined_configs():
        """Возвращает предустановленные конфигурации"""
        return {
            'nano': {'cores': 1, 'memory': 512, 'disk': 5},
            'micro': {'cores': 1, 'memory': 1024, 'disk': 10},
            'small': {'cores': 2, 'memory': 2048, 'disk': 20},
            'medium': {'cores': 4, 'memory': 4096, 'disk': 50},
            'large': {'cores': 8, 'memory': 8192, 'disk': 100},
            'xlarge': {'cores': 16, 'memory': 16384, 'disk': 200},
        }

    @staticmethod
    def calculate_price_multiplier(cores, memory, disk, base_cores=1, base_memory=1024, base_disk=10):
        """
        Вычисляет множитель цены на основе ресурсов

        Args:
            cores, memory, disk: Текущие ресурсы
            base_cores, base_memory, base_disk: Базовые ресурсы для расчета

        Returns:
            float: Множитель цены
        """
        cpu_multiplier = cores / base_cores
        memory_multiplier = memory / base_memory
        disk_multiplier = disk / base_disk

        # Взвешенное среднее (CPU важнее всего)
        return (cpu_multiplier * 0.5 + memory_multiplier * 0.3 + disk_multiplier * 0.2)

    @staticmethod
    def normalize_resources(cores, memory, disk):
        """
        Нормализует ресурсы к стандартным значениям

        Returns:
            dict: Нормализованные значения ресурсов
        """
        # Округляем до ближайших стандартных значений
        standard_cores = [1, 2, 4, 8, 16, 32, 64]
        standard_memory = [512, 1024, 2048, 4096, 8192, 16384, 32768, 65536]
        standard_disk = [5, 10, 20, 50, 100, 200, 500, 1000]

        normalized_cores = min(standard_cores, key=lambda x: abs(x - cores))
        normalized_memory = min(standard_memory, key=lambda x: abs(x - memory))
        normalized_disk = min(standard_disk, key=lambda x: abs(x - disk))

        return {
            'cores': normalized_cores,
            'memory': normalized_memory,
            'disk': normalized_disk
        }

    @staticmethod
    def get_resource_category(cores, memory, disk):
        """
        Определяет категорию ресурсов (nano, micro, small, etc.)

        Returns:
            str: Название категории
        """
        configs = VmResourceTrait.get_predefined_configs()

        # Находим ближайшую конфигурацию
        best_match = None
        best_score = float('inf')

        for name, config in configs.items():
            score = abs(cores - config['cores']) + abs(memory - config['memory']) / 1024 + abs(
                disk - config['disk']) / 10
            if score < best_score:
                best_score = score
                best_match = name

        return best_match or 'custom'


class VmOperationTrait:
    """
    Trait для операций с VM (расширение функциональности)
    """

    @staticmethod
    def get_recommended_specs_for_os(os_type):
        """Рекомендуемые характеристики для разных ОС"""
        recommendations = {
            'ubuntu': {'cores': 1, 'memory': 1024, 'disk': 20},
            'debian': {'cores': 1, 'memory': 1024, 'disk': 15},
            'centos': {'cores': 2, 'memory': 2048, 'disk': 25},
            'windows': {'cores': 2, 'memory': 4096, 'disk': 60},
            'docker': {'cores': 1, 'memory': 512, 'disk': 10},
        }
        return recommendations.get(os_type.lower(), VmResourceTrait.get_default_config())

    @staticmethod
    def estimate_boot_time(cores, memory, disk, os_type='linux'):
        """Оценивает время загрузки VM в секундах"""
        base_time = 30  # базовое время загрузки

        # Корректировки на основе ресурсов
        if memory < 1024:
            base_time += 15
        elif memory > 8192:
            base_time -= 10

        if cores == 1:
            base_time += 10
        elif cores >= 8:
            base_time -= 5

        if 'windows' in os_type.lower():
            base_time += 45

        return max(15, base_time)  # минимум 15 секунд
