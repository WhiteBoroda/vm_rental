odoo.define('vm_rental.settings_enhanced', function (require) {
'use strict';

var publicWidget = require('web.public.widget');
var ajax = require('web.ajax');
var core = require('web.core');
var csrf_token = core.csrf_token;

publicWidget.registry.VmRentalSettings = publicWidget.Widget.extend({
    selector: '.app_settings_block[name="vm_rental_settings"]',
    events: {
        'click .js_test_connection': '_onTestConnectionClick',
        'change input[name="vm_rental_auto_backup"]': '_onAutoBackupChange',
        'input input[name="vm_rental_max_cores"]': '_onResourceLimitChange',
        'input input[name="vm_rental_max_memory"]': '_onResourceLimitChange',
        'input input[name="vm_rental_max_disk"]': '_onResourceLimitChange',
        'click .btn-outline-primary, .btn-outline-success, .btn-outline-warning, .btn-outline-info': '_onQuickActionClick',
    },

    start: function () {
        this._super.apply(this, arguments);
        this._initializeTooltips();
        this._validateResourceLimits();
        this._animateCards();
    },

    _initializeTooltips: function () {
        // Добавляем tooltips для полей
        this.$('[data-toggle="tooltip"]').tooltip();

        // Добавляем информационные tooltips
        this.$('input[name="vm_rental_default_trial_days"]').attr('title', 'Recommended: 3-14 days for trial periods');
        this.$('input[name="vm_rental_max_cores"]').attr('title', 'Typical range: 1-64 cores per VM');
        this.$('input[name="vm_rental_max_memory"]').attr('title', 'Memory in Mebibytes (1024 MiB = 1 GiB)');
        this.$('input[name="vm_rental_max_disk"]').attr('title', 'Disk space in Gibibytes');
    },

    _animateCards: function () {
        // Анимация появления карточек
        this.$('.card').each(function(index) {
            $(this).css({
                'opacity': '0',
                'transform': 'translateY(20px)'
            }).delay(index * 100).animate({
                'opacity': '1',
                'transform': 'translateY(0px)'
            }, 300);
        });
    },

    _onAutoBackupChange: function (ev) {
        var $checkbox = $(ev.currentTarget);
        var $retentionGroup = this.$('[name="vm_rental_backup_retention_days"]').closest('.content-group');

        if ($checkbox.is(':checked')) {
            $retentionGroup.slideDown(300);
            this._showNotification('success', 'Auto Backup Enabled', 'Configuration backups will be created automatically');
        } else {
            $retentionGroup.slideUp(300);
            this._showNotification('info', 'Auto Backup Disabled', 'Manual backup creation is still available');
        }
    },

    _onResourceLimitChange: function (ev) {
        this._validateResourceLimits();
    },

    _validateResourceLimits: function () {
        var cores = parseInt(this.$('input[name="vm_rental_max_cores"]').val()) || 0;
        var memory = parseInt(this.$('input[name="vm_rental_max_memory"]').val()) || 0;
        var disk = parseInt(this.$('input[name="vm_rental_max_disk"]').val()) || 0;

        // Валидация и предупреждения
        this._validateField('vm_rental_max_cores', cores, 1, 128, 'cores');
        this._validateField('vm_rental_max_memory', memory, 512, 1048576, 'MiB'); // 512 MiB - 1 TiB
        this._validateField('vm_rental_max_disk', disk, 1, 10240, 'GiB'); // 1 GiB - 10 TiB

        // Показываем рекомендации
        this._showResourceRecommendations(cores, memory, disk);
    },

    _validateField: function (fieldName, value, min, max, unit) {
        var $field = this.$(`input[name="${fieldName}"]`);
        var $feedback = $field.closest('.o_setting_box').find('.validation-feedback');

        // Удаляем предыдущий feedback
        $feedback.remove();

        var isValid = value >= min && value <= max;
        var feedbackClass = isValid ? 'text-success' : 'text-danger';
        var feedbackIcon = isValid ? 'fa-check-circle' : 'fa-exclamation-triangle';
        var feedbackText = '';

        if (!isValid) {
            if (value < min) {
                feedbackText = `Minimum recommended: ${min} ${unit}`;
            } else if (value > max) {
                feedbackText = `Maximum allowed: ${max} ${unit}`;
            }
        } else {
            feedbackText = `Valid range: ${min}-${max} ${unit}`;
        }

        var $feedbackElement = $(`
            <small class="validation-feedback ${feedbackClass} d-block mt-1">
                <i class="fa ${feedbackIcon} mr-1"></i>${feedbackText}
            </small>
        `);

        $field.closest('.input-group').after($feedbackElement);

        // Изменяем стиль поля
        $field.removeClass('is-valid is-invalid').addClass(isValid ? 'is-valid' : 'is-invalid');
    },

    _showResourceRecommendations: function (cores, memory, disk) {
        // Определяем категорию ресурсов
        var category = this._determineResourceCategory(cores, memory, disk);
        var $recommendationAlert = this.$('.resource-recommendation-alert');

        if ($recommendationAlert.length === 0) {
            $recommendationAlert = $(`
                <div class="alert alert-info resource-recommendation-alert mt-3">
                    <h6><i class="fa fa-lightbulb-o mr-1"></i>Resource Recommendation</h6>
                    <div class="recommendation-content"></div>
                </div>
            `);
            this.$('.card-body').first().append($recommendationAlert);
        }

        var recommendations = {
            'nano': { text: 'Suitable for testing and light development', icon: 'fa-flask' },
            'micro': { text: 'Good for small applications and services', icon: 'fa-rocket' },
            'small': { text: 'Recommended for web servers and databases', icon: 'fa-server' },
            'medium': { text: 'Ideal for production workloads', icon: 'fa-industry' },
            'large': { text: 'High-performance computing applications', icon: 'fa-tachometer' },
            'enterprise': { text: 'Enterprise-grade resource allocation', icon: 'fa-building' }
        };

        var rec = recommendations[category] || recommendations['medium'];
        $recommendationAlert.find('.recommendation-content').html(`
            <i class="fa ${rec.icon} mr-2 text-primary"></i>
            Current limits allow <strong>${category}</strong> VMs: ${rec.text}
        `);
    },

    _determineResourceCategory: function (cores, memory, disk) {
        if (cores <= 1 && memory <= 1024) return 'nano';
        if (cores <= 2 && memory <= 2048) return 'micro';
        if (cores <= 4 && memory <= 4096) return 'small';
        if (cores <= 8 && memory <= 8192) return 'medium';
        if (cores <= 16 && memory <= 16384) return 'large';
        return 'enterprise';
    },

    _onQuickActionClick: function (ev) {
        var $button = $(ev.currentTarget);

        // Добавляем анимацию клика
        $button.addClass('btn-clicked');
        setTimeout(function() {
            $button.removeClass('btn-clicked');
        }, 150);

        // Трекинг клика (можно использовать для аналитики)
        var action = $button.text().trim();
        console.log('Quick action clicked:', action);
    },

    _onTestConnectionClick: function (ev) {
        ev.preventDefault();
        var $button = $(ev.currentTarget);
        var $row = $button.closest('tr');
        var serverId = $row.data('server-id');

        if (!serverId) return;

        // Disable button and show spinner
        $button.prop('disabled', true);
        var originalIcon = $button.find('i').attr('class');
        var originalText = $button.text();

        $button.find('i').attr('class', 'fa fa-spinner fa-spin');
        $button.find('.btn-text').text(' Testing...');

        var $statusCell = $row.find('.server-status-cell');
        var $messageCell = $row.find('.server-message-cell');

        $statusCell.html('<span class="badge badge-warning"><i class="fa fa-spinner fa-spin mr-1"></i>Connecting...</span>');
        $messageCell.html('<small class="text-muted">Please wait...</small>');

        ajax.jsonRpc('/vm_rental/settings/test_server', 'call', {
            server_id: serverId,
            csrf_token: csrf_token
        })
        .then(result => {
            if (result.success) {
                $statusCell.html('<span class="badge badge-success"><i class="fa fa-check-circle mr-1"></i>Connected</span>');
                var message = result.message || 'Connection successful';
                $messageCell.html(`<small class="text-success">${message}</small>`);

                this._showNotification('success', 'Connection Successful', `Server ${serverId} is now connected`);

                // Анимация успеха
                $row.addClass('table-success');
                setTimeout(() => $row.removeClass('table-success'), 2000);

            } else {
                $statusCell.html('<span class="badge badge-danger"><i class="fa fa-times-circle mr-1"></i>Failed</span>');
                $messageCell.html(`<small class="text-danger">${result.message}</small>`);

                this._showNotification('danger', 'Connection Failed', result.message);

                // Анимация ошибки
                $row.addClass('table-danger');
                setTimeout(() => $row.removeClass('table-danger'), 3000);
            }
        })
        .guardedCatch(error => {
            $statusCell.html('<span class="badge badge-danger"><i class="fa fa-exclamation-triangle mr-1"></i>Error</span>');
            $messageCell.html('<small class="text-danger">Network error occurred</small>');

            this._showNotification('danger', 'Network Error', 'Could not contact the server');

            console.error('VM Settings API Error:', error);
        })
        .finally(() => {
            // Re-enable button and restore original state
            $button.prop('disabled', false);
            $button.find('i').attr('class', originalIcon);
            $button.find('.btn-text').text(originalText.replace(' Testing...', ''));
        });
    },

    _showNotification: function(type, title, message) {
        // Создаем красивое уведомление
        var alertClass = {
            'success': 'alert-success',
            'danger': 'alert-danger',
            'warning': 'alert-warning',
            'info': 'alert-info'
        }[type] || 'alert-info';

        var icon = {
            'success': 'fa-check-circle',
            'danger': 'fa-times-circle',
            'warning': 'fa-exclamation-triangle',
            'info': 'fa-info-circle'
        }[type] || 'fa-info-circle';

        var $notification = $(`
            <div class="alert ${alertClass} alert-dismissible fade show vm-notification" role="alert" style="position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px;">
                <div class="d-flex align-items-center">
                    <i class="fa ${icon} fa-lg mr-2"></i>
                    <div>
                        <strong>${title}</strong><br>
                        <small>${message}</small>
                    </div>
                </div>
                <button type="button" class="close" data-dismiss="alert">
                    <span aria-hidden="true">&times;</span>
                </button>
            </div>
        `);

        $('body').append($notification);

        // Автоматически скрываем через 5 секунд
        setTimeout(() => {
            $notification.alert('close');
        }, 5000);
    },

    // Метод для экспорта настроек
    exportSettings: function() {
        var settings = {
            trial_days: this.$('input[name="vm_rental_default_trial_days"]').val(),
            auto_suspend: this.$('input[name="vm_rental_auto_suspend"]').is(':checked'),
            max_cores: this.$('input[name="vm_rental_max_cores"]').val(),
            max_memory: this.$('input[name="vm_rental_max_memory"]').val(),
            max_disk: this.$('input[name="vm_rental_max_disk"]').val(),
            auto_backup: this.$('input[name="vm_rental_auto_backup"]').is(':checked'),
            backup_retention: this.$('input[name="vm_rental_backup_retention_days"]').val(),
            export_date: new Date().toISOString()
        };

        // Создаем и скачиваем JSON файл
        var dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(settings, null, 2));
        var downloadAnchorNode = document.createElement('a');
        downloadAnchorNode.setAttribute("href", dataStr);
        downloadAnchorNode.setAttribute("download", "vm_rental_settings_" + new Date().toISOString().split('T')[0] + ".json");
        document.body.appendChild(downloadAnchorNode);
        downloadAnchorNode.click();
        downloadAnchorNode.remove();

        this._showNotification('success', 'Settings Exported', 'Configuration has been saved to file');
    },

    // Метод для валидации всех настроек перед сохранением
    validateAllSettings: function() {
        var isValid = true;
        var errors = [];

        // Проверяем trial days
        var trialDays = parseInt(this.$('input[name="vm_rental_default_trial_days"]').val());
        if (trialDays < 1 || trialDays > 365) {
            errors.push('Trial period must be between 1 and 365 days');
            isValid = false;
        }

        // Проверяем resource limits
        var cores = parseInt(this.$('input[name="vm_rental_max_cores"]').val());
        var memory = parseInt(this.$('input[name="vm_rental_max_memory"]').val());
        var disk = parseInt(this.$('input[name="vm_rental_max_disk"]').val());

        if (cores < 1 || cores > 128) {
            errors.push('CPU cores must be between 1 and 128');
            isValid = false;
        }

        if (memory < 512 || memory > 1048576) {
            errors.push('Memory must be between 512 MiB and 1048576 MiB (1 TiB)');
            isValid = false;
        }

        if (disk < 1 || disk > 10240) {
            errors.push('Disk space must be between 1 GiB and 10240 GiB (10 TiB)');
            isValid = false;
        }

        // Проверяем backup retention
        if (this.$('input[name="vm_rental_auto_backup"]').is(':checked')) {
            var retention = parseInt(this.$('input[name="vm_rental_backup_retention_days"]').val());
            if (retention < 1 || retention > 365) {
                errors.push('Backup retention must be between 1 and 365 days');
                isValid = false;
            }
        }

        if (!isValid) {
            this._showNotification('danger', 'Validation Error', errors.join('<br>'));
        }

        return isValid;
    }
});

// Добавляем кастомные CSS стили для анимаций
var style = document.createElement('style');
style.innerHTML = `
    .btn-clicked {
        transform: scale(0.95);
        transition: transform 0.1s ease;
    }
    
    .vm-notification {
        animation: slideInRight 0.3s ease;
    }
    
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .table-success {
        background-color: rgba(40, 167, 69, 0.1) !important;
        transition: background-color 0.3s ease;
    }
    
    .table-danger {
        background-color: rgba(220, 53, 69, 0.1) !important;
        transition: background-color 0.3s ease;
    }
    
    .is-valid {
        border-color: #28a745;
    }
    
    .is-invalid {
        border-color: #dc3545;
    }
`;
document.head.appendChild(style);

return publicWidget.registry.VmRentalSettings;

});