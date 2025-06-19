odoo.define('vm_rental.vm_snapshot_actions', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');
    var ajax = require('web.ajax');
    var core = require('web.core');
    var _t = core._t;

    publicWidget.registry.VmSnapshotManager = publicWidget.Widget.extend({
        selector: '#vm_snapshots_manager',
        events: {
            'submit #create_snapshot_form': '_onCreateSnapshot',
            'click .rollback-snapshot': '_onRollbackSnapshot',
            'click .delete-snapshot': '_onDeleteSnapshot',
        },

        _onCreateSnapshot: function (ev) {
            ev.preventDefault();
            const $form = $(ev.currentTarget);
            const $button = $form.find('button[type="submit"]');
            const $spinner = $button.find('i.fa-spinner');

            const vmId = this.$el.data('vm-id');
            const name = $form.find('#snapshot_name').val();
            const description = $form.find('#snapshot_desc').val();

            $button.prop('disabled', true);
            $spinner.removeClass('d-none');

            this._rpc({
                route: `/vm/${vmId}/snapshot/create`,
                params: {
                    name: name,
                    description: description,
                },
            }).then(res => {
                if (res.success) {
                    window.location.reload();
                } else {
                    alert(_t('Error: ') + res.error);
                    $button.prop('disabled', false);
                    $spinner.addClass('d-none');
                }
            });
        },

        _onRollbackSnapshot: function (ev) {
            if (!confirm(_t("Are you sure you want to rollback? This will revert the VM to the state of this snapshot and CANNOT be undone."))) {
                return;
            }

            const $button = $(ev.currentTarget);
            const $icon = $button.find('i');
            const originalIconClass = $icon.attr('class');
            const vmId = this.$el.data('vm-id');
            const proxmoxName = $button.closest('.list-group-item').data('proxmox-name');

            $button.prop('disabled', true);
            $icon.attr('class', 'fa fa-spinner fa-spin mr-1'); // Показываем спиннер

            this._rpc({
                route: `/vm/${vmId}/snapshot/${proxmoxName}/rollback`,
                params: {},
            }).then(res => {
                if(res.success) {
                    alert(_t('Rollback started successfully! The VM will now restart.'));
                } else {
                    alert(_t('Rollback failed: ') + res.error);
                }
            }).finally(() => {
                $button.prop('disabled', false);
                $icon.attr('class', originalIconClass); // Возвращаем иконку
            });
        },

        _onDeleteSnapshot: function (ev) {
            if (!confirm(_t("Are you sure you want to delete this snapshot? This CANNOT be undone."))) {
                return;
            }

            const $button = $(ev.currentTarget);
            const $item = $button.closest('.list-group-item');
            const $icon = $button.find('i');
            const originalIconClass = $icon.attr('class');
            const vmId = this.$el.data('vm-id');
            const proxmoxName = $item.data('proxmox-name');

            $button.prop('disabled', true);
            $icon.attr('class', 'fa fa-spinner fa-spin mr-1'); // Показываем спиннер

            this._rpc({
                route: `/vm/${vmId}/snapshot/${proxmoxName}/delete`,
                params: {},
            }).then(res => {
                if (res.success) {
                    $item.remove();
                } else {
                    alert(_t('Error deleting snapshot: ') + res.error);
                    $button.prop('disabled', false); // Разблокируем в случае ошибки
                    $icon.attr('class', originalIconClass); // Возвращаем иконку
                }
            });
        },

        _rpc: function(routeOptions) {
            return ajax.jsonRpc(routeOptions.route, 'call', routeOptions.params || {})
                .guardedCatch((err) => {
                    const errorMsg = err.data.message || _t('An RPC error occurred.');
                    alert(errorMsg);
                });
        }
    });

    return publicWidget.registry.VmSnapshotManager;
});