// vm_rental/static/src/js/portal_vm_control.js

odoo.define('vm_rental.portal_vm_control', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');
    var ajax = require('web.ajax');
    var core = require('web.core');

    // VM Control Widget для портала
    var VmPortalControl = publicWidget.Widget.extend({
        selector: '.vm-portal-control',
        events: {
            'click .vm-action-start': '_onStartVm',
            'click .vm-action-stop': '_onStopVm',
            'click .vm-action-restart': '_onRestartVm',
            'click .vm-action-console': '_onOpenConsole',
            'click .vm-action-snapshot': '_onCreateSnapshot',
            'click .vm-refresh-status': '_onRefreshStatus',
            'click .snapshot-restore': '_onRestoreSnapshot',
            'click .snapshot-delete': '_onDeleteSnapshot'
        },

        start: function () {
            this._super.apply(this, arguments);
            this._initializeVmControl();
            this._startStatusPolling();
        },

        _initializeVmControl: function () {
            // Инициализация интерфейса управления VM
            this._addTooltips();
            this._updateButtonStates();
        },

        _addTooltips: function () {
            // Добавляем tooltips к кнопкам управления
            this.$('.vm-action-start').attr('title', 'Start virtual machine');
            this.$('.vm-action-stop').attr('title', 'Stop virtual machine');
            this.$('.vm-action-restart').attr('title', 'Restart virtual machine');
            this.$('.vm-action-console').attr('title', 'Open VM console');
            this.$('.vm-action-snapshot').attr('title', 'Create snapshot');
            this.$('.vm-refresh-status').attr('title', 'Refresh VM status');
        },

        _updateButtonStates: function () {
            var vmState = this.$el.data('vm-state') || 'unknown';
            var $startBtn = this.$('.vm-action-start');
            var $stopBtn = this.$('.vm-action-stop');
            var $restartBtn = this.$('.vm-action-restart');
            var $consoleBtn = this.$('.vm-action-console');

            // Обновляем состояние кнопок в зависимости от статуса VM
            switch (vmState) {
                case 'active':
                case 'running':
                    $startBtn.prop('disabled', true).addClass('disabled');
                    $stopBtn.prop('disabled', false).removeClass('disabled');
                    $restartBtn.prop('disabled', false).removeClass('disabled');
                    $consoleBtn.prop('disabled', false).removeClass('disabled');
                    break;
                case 'stopped':
                case 'suspended':
                    $startBtn.prop('disabled', false).removeClass('disabled');
                    $stopBtn.prop('disabled', true).addClass('disabled');
                    $restartBtn.prop('disabled', true).addClass('disabled');
                    $consoleBtn.prop('disabled', true).addClass('disabled');
                    break;
                case 'pending':
                case 'provisioning':
                    $startBtn.prop('disabled', true).addClass('disabled');
                    $stopBtn.prop('disabled', true).addClass('disabled');
                    $restartBtn.prop('disabled', true).addClass('disabled');
                    $consoleBtn.prop('disabled', true).addClass('disabled');
                    break;
                default:
                    // Неизвестное состояние - отключаем все кнопки
                    this.$('.vm-action').prop('disabled', true).addClass('disabled');
            }
        },

        _onStartVm: function (ev) {
            ev.preventDefault();
            var vmId = this._getVmId();
            this._performVmAction(vmId, 'start', 'Starting VM...');
        },

        _onStopVm: function (ev) {
            ev.preventDefault();
            var vmId = this._getVmId();
            this._showConfirmDialog('Stop VM', 'Are you sure you want to stop this virtual machine?', function() {
                this._performVmAction(vmId, 'stop', 'Stopping VM...');
            }.bind(this));
        },

        _onRestartVm: function (ev) {
            ev.preventDefault();
            var vmId = this._getVmId();
            this._showConfirmDialog('Restart VM', 'Are you sure you want to restart this virtual machine?', function() {
                this._performVmAction(vmId, 'restart', 'Restarting VM...');
            }.bind(this));
        },

        _onOpenConsole: function (ev) {
            ev.preventDefault();
            var vmId = this._getVmId();

            // Открываем консоль в новом окне
            var consoleUrl = '/my/vm/' + vmId + '/console';
            var consoleWindow = window.open(
                consoleUrl,
                'vm_console_' + vmId,
                'width=1024,height=768,scrollbars=yes,resizable=yes'
            );

            if (!consoleWindow) {
                this._showNotification('error', 'Console Access', 'Unable to open console. Please check popup blockers.');
            }
        },

        _onCreateSnapshot: function (ev) {
            ev.preventDefault();
            var vmId = this._getVmId();
            var snapshotName = prompt('Enter snapshot name:', 'Snapshot_' + new Date().toISOString().split('T')[0]);

            if (snapshotName) {
                this._createSnapshot(vmId, snapshotName);
            }
        },

        _onRefreshStatus: function (ev) {
            ev.preventDefault();
            this._refreshVmStatus();
        },

        _onRestoreSnapshot: function (ev) {
            ev.preventDefault();
            var snapshotId = $(ev.currentTarget).data('snapshot-id');
            var snapshotName = $(ev.currentTarget).data('snapshot-name');

            this._showConfirmDialog(
                'Restore Snapshot',
                'Are you sure you want to restore snapshot "' + snapshotName + '"? This will revert the VM to this state.',
                function() {
                    this._restoreSnapshot(snapshotId);
                }.bind(this)
            );
        },

        _onDeleteSnapshot: function (ev) {
            ev.preventDefault();
            var snapshotId = $(ev.currentTarget).data('snapshot-id');
            var snapshotName = $(ev.currentTarget).data('snapshot-name');

            this._showConfirmDialog(
                'Delete Snapshot',
                'Are you sure you want to delete snapshot "' + snapshotName + '"? This action cannot be undone.',
                function() {
                    this._deleteSnapshot(snapshotId);
                }.bind(this)
            );
        },

        _getVmId: function () {
            return this.$el.data('vm-id') || this.$el.closest('[data-vm-id]').data('vm-id');
        },

        _performVmAction: function (vmId, action, loadingMessage) {
            var self = this;

            this._showLoading(loadingMessage);
            this._disableAllButtons(true);

            ajax.jsonRpc('/my/vm/' + vmId + '/action', 'call', {
                'action': action
            }).then(function (result) {
                if (result.success) {
                    self._showNotification('success', 'VM Action', result.message || 'Action completed successfully');
                    // Обновляем статус через короткое время
                    setTimeout(function() {
                        self._refreshVmStatus();
                    }, 2000);
                } else {
                    self._showNotification('error', 'VM Action Failed', result.error || 'Action failed');
                }
            }).guardedCatch(function (error) {
                self._showNotification('error', 'VM Action Error', 'Failed to perform action: ' + error.message);
            }).finally(function () {
                self._hideLoading();
                self._disableAllButtons(false);
            });
        },

        _createSnapshot: function (vmId, snapshotName) {
            var self = this;

            this._showLoading('Creating snapshot...');

            ajax.jsonRpc('/my/vm/' + vmId + '/snapshot', 'call', {
                'name': snapshotName
            }).then(function (result) {
                if (result.success) {
                    self._showNotification('success', 'Snapshot Created', 'Snapshot "' + snapshotName + '" created successfully');
                    self._refreshSnapshotList();
                } else {
                    self._showNotification('error', 'Snapshot Failed', result.error || 'Failed to create snapshot');
                }
            }).guardedCatch(function (error) {
                self._showNotification('error', 'Snapshot Error', 'Failed to create snapshot: ' + error.message);
            }).finally(function () {
                self._hideLoading();
            });
        },

        _restoreSnapshot: function (snapshotId) {
            var self = this;

            this._showLoading('Restoring snapshot...');

            ajax.jsonRpc('/my/vm/snapshot/' + snapshotId + '/restore', 'call', {}).then(function (result) {
                if (result.success) {
                    self._showNotification('success', 'Snapshot Restored', 'VM restored to snapshot successfully');
                    setTimeout(function() {
                        self._refreshVmStatus();
                    }, 3000);
                } else {
                    self._showNotification('error', 'Restore Failed', result.error || 'Failed to restore snapshot');
                }
            }).guardedCatch(function (error) {
                self._showNotification('error', 'Restore Error', 'Failed to restore snapshot: ' + error.message);
            }).finally(function () {
                self._hideLoading();
            });
        },

        _deleteSnapshot: function (snapshotId) {
            var self = this;

            this._showLoading('Deleting snapshot...');

            ajax.jsonRpc('/my/vm/snapshot/' + snapshotId + '/delete', 'call', {}).then(function (result) {
                if (result.success) {
                    self._showNotification('success', 'Snapshot Deleted', 'Snapshot deleted successfully');
                    self._refreshSnapshotList();
                } else {
                    self._showNotification('error', 'Delete Failed', result.error || 'Failed to delete snapshot');
                }
            }).guardedCatch(function (error) {
                self._showNotification('error', 'Delete Error', 'Failed to delete snapshot: ' + error.message);
            }).finally(function () {
                self._hideLoading();
            });
        },

        _refreshVmStatus: function () {
            var self = this;
            var vmId = this._getVmId();

            ajax.jsonRpc('/my/vm/' + vmId + '/status', 'call', {}).then(function (result) {
                if (result.success) {
                    self.$el.data('vm-state', result.state);
                    self._updateStatusDisplay(result);
                    self._updateButtonStates();
                }
            }).guardedCatch(function (error) {
                console.warn('Failed to refresh VM status:', error);
            });
        },

        _refreshSnapshotList: function () {
            // Перезагружаем список снапшотов
            var $snapshotContainer = this.$('.vm-snapshots-container');
            if ($snapshotContainer.length) {
                location.reload(); // Простое решение - перезагрузка страницы
            }
        },

        _updateStatusDisplay: function (statusData) {
            // Обновляем отображение статуса VM
            var $statusBadge = this.$('.vm-status-badge');
            var $statusText = this.$('.vm-status-text');

            if ($statusBadge.length) {
                $statusBadge.removeClass('badge-success badge-danger badge-warning badge-secondary');

                switch (statusData.state) {
                    case 'active':
                    case 'running':
                        $statusBadge.addClass('badge-success').text('Running');
                        break;
                    case 'stopped':
                        $statusBadge.addClass('badge-danger').text('Stopped');
                        break;
                    case 'suspended':
                        $statusBadge.addClass('badge-warning').text('Suspended');
                        break;
                    default:
                        $statusBadge.addClass('badge-secondary').text(statusData.state || 'Unknown');
                }
            }

            if ($statusText.length && statusData.uptime) {
                $statusText.text('Uptime: ' + statusData.uptime);
            }
        },

        _startStatusPolling: function () {
            var self = this;
            // Обновляем статус каждые 30 секунд
            this.statusInterval = setInterval(function () {
                self._refreshVmStatus();
            }, 30000);
        },

        _disableAllButtons: function (disabled) {
            this.$('.vm-action').prop('disabled', disabled);
            if (disabled) {
                this.$('.vm-action').addClass('disabled');
            } else {
                this.$('.vm-action').removeClass('disabled');
                this._updateButtonStates(); // Восстанавливаем правильное состояние
            }
        },

        _showLoading: function (message) {
            var $loadingEl = this.$('.vm-loading-indicator');
            if ($loadingEl.length === 0) {
                $loadingEl = $('<div class="vm-loading-indicator text-center mt-2">' +
                    '<i class="fa fa-spinner fa-spin mr-2"></i>' +
                    '<span class="loading-message">' + message + '</span>' +
                '</div>');
                this.$el.append($loadingEl);
            } else {
                $loadingEl.find('.loading-message').text(message);
                $loadingEl.show();
            }
        },

        _hideLoading: function () {
            this.$('.vm-loading-indicator').hide();
        },

        _showNotification: function (type, title, message) {
            // Создаем уведомление
            var alertClass = {
                'success': 'alert-success',
                'error': 'alert-danger',
                'warning': 'alert-warning',
                'info': 'alert-info'
            }[type] || 'alert-info';

            var icon = {
                'success': 'fa-check-circle',
                'error': 'fa-times-circle',
                'warning': 'fa-exclamation-triangle',
                'info': 'fa-info-circle'
            }[type] || 'fa-info-circle';

            var $notification = $(
                '<div class="alert ' + alertClass + ' alert-dismissible fade show vm-notification" ' +
                'style="position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px; max-width: 500px;">' +
                    '<div class="d-flex align-items-center">' +
                        '<i class="fa ' + icon + ' fa-lg mr-2"></i>' +
                        '<div>' +
                            '<strong>' + title + '</strong><br>' +
                            '<small>' + message + '</small>' +
                        '</div>' +
                    '</div>' +
                    '<button type="button" class="close" data-dismiss="alert">' +
                        '<span>&times;</span>' +
                    '</button>' +
                '</div>'
            );

            $('body').append($notification);

            // Автоматически скрываем через 5 секунд
            setTimeout(function () {
                $notification.alert('close');
            }, 5000);
        },

        _showConfirmDialog: function (title, message, callback) {
            if (confirm(title + '\n\n' + message)) {
                callback();
            }
        },

        destroy: function () {
            if (this.statusInterval) {
                clearInterval(this.statusInterval);
            }
            this._super.apply(this, arguments);
        }
    });

    // VM List Widget для страницы со списком VM
    var VmPortalList = publicWidget.Widget.extend({
        selector: '.vm-portal-list',
        events: {
            'click .vm-quick-action': '_onQuickAction',
            'change .vm-filter-status': '_onFilterChange',
            'click .vm-bulk-action': '_onBulkAction'
        },

        start: function () {
            this._super.apply(this, arguments);
            this._initializeFilters();
        },

        _initializeFilters: function () {
            // Инициализация фильтров списка VM
            this._updateVmCounts();
        },

        _onQuickAction: function (ev) {
            ev.preventDefault();
            var $btn = $(ev.currentTarget);
            var vmId = $btn.data('vm-id');
            var action = $btn.data('action');

            // Делегируем действие к соответствующему контролу VM
            var $vmControl = $btn.closest('.vm-portal-control');
            if ($vmControl.length) {
                var controlWidget = $vmControl.data('widget');
                if (controlWidget) {
                    controlWidget.trigger_up('vm_action', {
                        vm_id: vmId,
                        action: action
                    });
                }
            }
        },

        _onFilterChange: function (ev) {
            var selectedStatus = $(ev.currentTarget).val();
            this._filterVmsByStatus(selectedStatus);
        },

        _onBulkAction: function (ev) {
            ev.preventDefault();
            var action = $(ev.currentTarget).data('action');
            var selectedVms = this._getSelectedVms();

            if (selectedVms.length === 0) {
                alert('Please select at least one VM');
                return;
            }

            this._performBulkAction(action, selectedVms);
        },

        _filterVmsByStatus: function (status) {
            var $vmItems = this.$('.vm-list-item');

            if (status === 'all') {
                $vmItems.show();
            } else {
                $vmItems.each(function () {
                    var itemStatus = $(this).data('vm-status');
                    if (itemStatus === status) {
                        $(this).show();
                    } else {
                        $(this).hide();
                    }
                });
            }

            this._updateVmCounts();
        },

        _getSelectedVms: function () {
            var vmIds = [];
            this.$('.vm-select-checkbox:checked').each(function () {
                vmIds.push($(this).val());
            });
            return vmIds;
        },

        _performBulkAction: function (action, vmIds) {
            var self = this;
            var actionName = action.charAt(0).toUpperCase() + action.slice(1);

            if (!confirm('Are you sure you want to ' + action + ' ' + vmIds.length + ' VM(s)?')) {
                return;
            }

            ajax.jsonRpc('/my/vms/bulk_action', 'call', {
                'action': action,
                'vm_ids': vmIds
            }).then(function (result) {
                if (result.success) {
                    self._showNotification('success', 'Bulk Action', result.message);
                    location.reload(); // Перезагружаем страницу для обновления статусов
                } else {
                    self._showNotification('error', 'Bulk Action Failed', result.error);
                }
            }).guardedCatch(function (error) {
                self._showNotification('error', 'Bulk Action Error', 'Failed to perform bulk action: ' + error.message);
            });
        },

        _updateVmCounts: function () {
            var $visibleItems = this.$('.vm-list-item:visible');
            var totalCount = this.$('.vm-list-item').length;
            var visibleCount = $visibleItems.length;

            this.$('.vm-count-display').text(visibleCount + ' of ' + totalCount + ' VMs');
        },

        _showNotification: function (type, title, message) {
            // Используем тот же метод что и в VmPortalControl
            VmPortalControl.prototype._showNotification.call(this, type, title, message);
        }
    });

    // Регистрируем виджеты
    publicWidget.registry.VmPortalControl = VmPortalControl;
    publicWidget.registry.VmPortalList = VmPortalList;

    return {
        VmPortalControl: VmPortalControl,
        VmPortalList: VmPortalList
    };
});