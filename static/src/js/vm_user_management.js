// vm_rental/static/src/js/vm_user_management.js

odoo.define('vm_rental.user_management', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');
    var ajax = require('web.ajax');
    var core = require('web.core');

    publicWidget.registry.VmUserManagement = publicWidget.Widget.extend({
        selector: '.app_settings_block[name="vm_rental_settings"]',
        events: {
            'click .js_refresh_user_stats': '_onRefreshUserStats',
            'click .js_open_user_manager': '_onOpenUserManager',
            'change input[name="auto_assign_vm_access"]': '_onAutoAssignChange',
            'change select[name="vm_user_type"]': '_onDefaultTypeChange'
        },

        start: function () {
            this._super.apply(this, arguments);
            this._loadUserStatistics();
            this._initializeTooltips();
        },

        _loadUserStatistics: function () {
            var self = this;

            // Загружаем статистику пользователей
            ajax.jsonRpc('/web/dataset/call_kw', 'call', {
                model: 'res.users',
                method: 'search_count',
                args: [[['share', '=', false], ['active', '=', true]]],
                kwargs: {}
            }).then(function(internalCount) {
                $('#internal_user_count').text(internalCount || 0);
            });

            ajax.jsonRpc('/web/dataset/call_kw', 'call', {
                model: 'res.users',
                method: 'search_count',
                args: [[['share', '=', true], ['active', '=', true]]],
                kwargs: {}
            }).then(function(portalCount) {
                $('#portal_user_count').text(portalCount || 0);
            });

            // Получаем количество пользователей в группах VM
            this._loadVmGroupStatistics();
        },

        _loadVmGroupStatistics: function () {
            var self = this;

            // Получаем информацию о группах через RPC
            ajax.jsonRpc('/vm_rental/user_stats', 'call', {}).then(function(result) {
                if (result) {
                    $('#vm_admin_count').text(result.vm_admins || 0);
                    $('#vm_manager_count').text(result.vm_managers || 0);

                    // Обновляем предупреждения
                    self._updateAccessWarnings(result);
                }
            }).guardedCatch(function() {
                // Fallback если эндпоинт недоступен
                $('#vm_admin_count').text('N/A');
                $('#vm_manager_count').text('N/A');
            });
        },

        _updateAccessWarnings: function (stats) {
            var accessCoverage = stats.total_internal > 0 ?
                ((stats.vm_admins + stats.vm_managers) / stats.total_internal * 100) : 0;

            // Создаем или обновляем алерт о покрытии доступа
            var $existingAlert = this.$('.access-coverage-alert');
            if ($existingAlert.length) {
                $existingAlert.remove();
            }

            var alertClass = 'alert-success';
            var alertIcon = 'fa-check-circle';
            var alertTitle = 'Good Access Coverage';
            var alertMessage = accessCoverage.toFixed(1) + '% of internal users have VM access';

            if (accessCoverage < 50) {
                alertClass = 'alert-warning';
                alertIcon = 'fa-exclamation-triangle';
                alertTitle = 'Low Access Coverage';
            } else if (accessCoverage < 25) {
                alertClass = 'alert-danger';
                alertIcon = 'fa-times-circle';
                alertTitle = 'Very Low Access Coverage';
            }

            var additionalMessage = accessCoverage < 50 ?
                '<br><small>Consider using the VM User Manager to assign access to more users.</small>' : '';

            var $alert = $(
                '<div class="alert ' + alertClass + ' access-coverage-alert mt-3" role="alert">' +
                    '<i class="fa ' + alertIcon + ' mr-2"></i>' +
                    '<strong>' + alertTitle + ':</strong> ' + alertMessage +
                    additionalMessage +
                '</div>'
            );

            this.$('.card-body').first().append($alert);
        },

        _onRefreshUserStats: function (ev) {
            ev.preventDefault();
            this._loadUserStatistics();
            this._showNotification('info', 'Statistics Refreshed', 'User statistics have been updated');
        },

        _onOpenUserManager: function (ev) {
            var self = this;
            ev.preventDefault();

            // Открываем VM User Manager через RPC
            ajax.jsonRpc('/web/dataset/call_kw', 'call', {
                model: 'vm.user.manager',
                method: 'create',
                args: [{}],
                kwargs: {}
            }).then(function(managerId) {
                // Открываем созданный визард
                var action = {
                    type: 'ir.actions.act_window',
                    name: 'VM User Manager',
                    res_model: 'vm.user.manager',
                    res_id: managerId,
                    view_mode: 'form',
                    target: 'new'
                };

                // Используем do_action если доступно
                if (self.do_action) {
                    self.do_action(action);
                } else {
                    // Fallback - открываем в новой вкладке
                    window.open('/web#action=' + JSON.stringify(action));
                }
            });
        },

        _onAutoAssignChange: function (ev) {
            var $checkbox = $(ev.currentTarget);
            var $defaultTypeField = this.$('select[name="user_type"]').closest('.o_setting_box');

            if ($checkbox.is(':checked')) {
                $defaultTypeField.slideDown(300);
                this._showNotification('info', 'Auto-Assignment Enabled',
                    'New internal users will automatically receive VM access');
            } else {
                $defaultTypeField.slideUp(300);
                this._showNotification('info', 'Auto-Assignment Disabled',
                    'New users will not automatically receive VM access');
            }
        },

        _onDefaultTypeChange: function (ev) {
            var selectedType = $(ev.currentTarget).val();
            var typeDescriptions = {
                'none': 'No automatic VM access will be granted',
                'user': 'Basic VM viewing access will be granted',
                'manager': 'VM management access will be granted',
                'admin': 'Full VM administrative access will be granted'
            };

            if (typeDescriptions[selectedType]) {
                this._showNotification('info', 'Default Access Updated', typeDescriptions[selectedType]);
            }
        },

        _initializeTooltips: function () {
            // Добавляем tooltips для элементов
            this.$('[data-toggle="tooltip"]').tooltip();

            // Добавляем информационные tooltips для кнопок и элементов
            this.$('.js_open_user_manager').attr('title', 'Open the dedicated VM User Access Manager');
            this.$('.js_refresh_user_stats').attr('title', 'Refresh user statistics and coverage information');

            // Добавляем tooltips для полей, которые действительно существуют
            this.$('field[name="vm_rental_user_access_summary"]').attr('title',
                'Summary of current VM user access assignments');
        },

        _showNotification: function(type, title, message) {
            // Создаем уведомление (совместимо с backend)
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

            var $notification = $(
                '<div class="alert ' + alertClass + ' alert-dismissible fade show vm-user-notification" ' +
                'role="alert" style="position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px;">' +
                    '<div class="d-flex align-items-center">' +
                        '<i class="fa ' + icon + ' fa-lg mr-2"></i>' +
                        '<div>' +
                            '<strong>' + title + '</strong><br>' +
                            '<small>' + message + '</small>' +
                        '</div>' +
                    '</div>' +
                    '<button type="button" class="close" data-dismiss="alert">' +
                        '<span aria-hidden="true">&times;</span>' +
                    '</button>' +
                '</div>'
            );

            $('body').append($notification);

            // Автоматически скрываем через 4 секунды
            setTimeout(function() {
                $notification.alert('close');
            }, 4000);
        }
    });

    // Возвращаем registry для возможности расширения
    return publicWidget.registry.VmUserManagement;

});