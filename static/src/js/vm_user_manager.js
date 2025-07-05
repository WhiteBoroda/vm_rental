// vm_rental/static/src/js/vm_user_manager.js

odoo.define('vm_rental.user_manager', function (require) {
'use strict';

var FormController = require('web.FormController');
var FormView = require('web.FormView');
var viewRegistry = require('web.view_registry');
var core = require('web.core');
var ajax = require('web.ajax');

var VmUserManagerFormController = FormController.extend({
    custom_events: _.extend({}, FormController.prototype.custom_events, {
        'validate_user_assignments': '_onValidateUserAssignments',
        'bulk_assign_users': '_onBulkAssignUsers',
    }),

    /**
     * @override
     */
    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self._updateStatistics();
            self._initializeValidation();
        });
    },

    /**
     * Обновляет статистику в реальном времени
     */
    _updateStatistics: function () {
        var self = this;
        var record = this.model.get(this.handle);

        if (record) {
            // Получаем текущие значения полей
            var adminUsers = record.data.admin_users ? record.data.admin_users.data : [];
            var managerUsers = record.data.manager_users ? record.data.manager_users.data : [];

            // Обновляем счетчики
            this._updateCounters(adminUsers.length, managerUsers.length);

            // Проверяем пересечения
            this._checkUserOverlap(adminUsers, managerUsers);
        }
    },

    /**
     * Обновляет счетчики пользователей
     */
    _updateCounters: function (adminCount, managerCount) {
        // Обновляем значения в карточках статистики
        this.$('.card.bg-primary h3').text(this._getTotalInternalUsers());
        // Можно добавить больше логики обновления UI
    },

    /**
     * Проверяет пересечения пользователей между ролями
     */
    _checkUserOverlap: function (adminUsers, managerUsers) {
        var adminIds = adminUsers.map(function(user) { return user.res_id; });
        var managerIds = managerUsers.map(function(user) { return user.res_id; });

        var intersection = adminIds.filter(function(id) {
            return managerIds.includes(id);
        });

        if (intersection.length > 0) {
            this._showOverlapWarning(intersection.length);
        } else {
            this._hideOverlapWarning();
        }
    },

    /**
     * Показывает предупреждение о пересечении ролей
     */
    _showOverlapWarning: function (overlapCount) {
        var $existingWarning = this.$('.user-overlap-warning');
        if ($existingWarning.length === 0) {
            var $warning = $(`
                <div class="alert alert-warning user-overlap-warning mt-2" role="alert">
                    <i class="fa fa-exclamation-triangle mr-2"></i>
                    <strong>Role Overlap:</strong> ${overlapCount} user(s) assigned to both Admin and Manager roles. 
                    Admin role will take precedence.
                </div>
            `);
            this.$('.o_form_sheet').prepend($warning);
        } else {
            $existingWarning.find('strong').next().text(
                ` ${overlapCount} user(s) assigned to both Admin and Manager roles. Admin role will take precedence.`
            );
        }
    },

    /**
     * Скрывает предупреждение о пересечении ролей
     */
    _hideOverlapWarning: function () {
        this.$('.user-overlap-warning').remove();
    },

    /**
     * Инициализирует валидацию в реальном времени
     */
    _initializeValidation: function () {
        var self = this;

        // Отслеживаем изменения в полях пользователей
        this.$('div[name="admin_users"], div[name="manager_users"]').on('DOMSubtreeModified', function() {
            self._updateStatistics();
        });

        // Добавляем tooltips
        this._addTooltips();
    },

    /**
     * Добавляет tooltips к элементам интерфейса
     */
    _addTooltips: function () {
        this.$('button[name="action_bulk_assign_managers"]').attr('title',
            'Assign VM Manager role to all internal users who don\'t have admin access');
        this.$('button[name="action_clear_all_access"]').attr('title',
            'Remove VM access from all users - use with caution');
        this.$('button[name="action_apply_changes"]').attr('title',
            'Save all user role changes to the system');
    },

    /**
     * Валидация назначений пользователей
     */
    _onValidateUserAssignments: function (event) {
        var record = this.model.get(this.handle);
        var adminUsers = record.data.admin_users ? record.data.admin_users.data : [];
        var managerUsers = record.data.manager_users ? record.data.manager_users.data : [];

        // Проверяем минимальные требования
        if (adminUsers.length === 0 && managerUsers.length === 0) {
            this.displayNotification({
                title: 'Validation Warning',
                message: 'At least one user should have VM access. Consider assigning some users before applying changes.',
                type: 'warning'
            });
            return;
        }

        // Рекомендации по безопасности
        if (adminUsers.length === 0) {
            this.displayNotification({
                title: 'Security Recommendation',
                message: 'No VM Administrators assigned. Consider assigning at least one admin for system management.',
                type: 'warning'
            });
        }

        if (adminUsers.length > 5) {
            this.displayNotification({
                title: 'Security Warning',
                message: 'Many users have admin access. Consider limiting admin privileges for better security.',
                type: 'warning'
            });
        }
    },

    /**
     * Массовое назначение пользователей
     */
    _onBulkAssignUsers: function (event) {
        var self = this;
        var assignmentType = event.data.type; // 'managers' или 'clear'

        if (assignmentType === 'managers') {
            // Получаем всех внутренних пользователей
            ajax.jsonRpc('/web/dataset/call_kw', 'call', {
                model: 'res.users',
                method: 'search',
                args: [[['share', '=', false], ['active', '=', true], ['id', '!=', 1]]], // Исключаем OdooBot
                kwargs: {}
            }).then(function(userIds) {
                // Обновляем поле manager_users
                self._updateManyToManyField('manager_users', userIds);
                self.displayNotification({
                    title: 'Bulk Assignment',
                    message: `Assigned VM Manager role to ${userIds.length} users. Click "Apply Changes" to save.`,
                    type: 'info'
                });
            });
        } else if (assignmentType === 'clear') {
            // Очищаем все назначения
            self._updateManyToManyField('admin_users', []);
            self._updateManyToManyField('manager_users', []);
            self.displayNotification({
                title: 'Access Cleared',
                message: 'VM access removed from all users. Click "Apply Changes" to save.',
                type: 'warning'
            });
        }
    },

    /**
     * Обновляет Many2many поле
     */
    _updateManyToManyField: function (fieldName, userIds) {
        var changes = {};
        changes[fieldName] = {
            operation: 'REPLACE_WITH',
            ids: userIds
        };
        this.model.notifyChanges(this.handle, changes);
    },

    /**
     * Получает общее количество внутренних пользователей
     */
    _getTotalInternalUsers: function () {
        // Это значение должно быть загружено или вычислено
        return this.$('.card.bg-primary h3').text() || '0';
    }
});

var VmUserManagerFormView = FormView.extend({
    config: _.extend({}, FormView.prototype.config, {
        Controller: VmUserManagerFormController,
    }),
});

// Регистрируем представление
viewRegistry.add('vm_user_manager_form', VmUserManagerFormView);

return {
    VmUserManagerFormController: VmUserManagerFormController,
    VmUserManagerFormView: VmUserManagerFormView,
};

});