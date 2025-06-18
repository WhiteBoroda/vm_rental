odoo.define('vm_rental.vm_snapshot_actions', function (require) {
    'use strict';

    var publicWidget = require('web.public.widget');
    var ajax = require('web.ajax');
    var core = require('web.core');
    var _t = core._t;
    var csrf_token = core.csrf_token;

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
            const vmId = this.$el.data('vm-id');
            const name = $form.find('#snapshot_name').val();
            const description = $form.find('#snapshot_desc').val();
            
            this._rpc({
                route: `/vm/${vmId}/snapshot/create`,
                params: { name: name, description: description },
            }).then(res => {
                if (res.success) {
                    // Простой и надежный способ обновить страницу
                    window.location.reload(); 
                } else {
                    alert(_t('Error: ') + res.error);
                }
            });
        },

        _onRollbackSnapshot: function (ev) {
            if (!confirm(_t("Are you sure you want to rollback? This will revert the VM to the state of this snapshot and CANNOT be undone."))) {
                return;
            }

            const $button = $(ev.currentTarget);
            const $item = $button.closest('.list-group-item');
            const vmId = this.$el.data('vm-id');
            const proxmoxName = $item.data('proxmox-name');

            this._rpc({
                route: `/vm/${vmId}/snapshot/${proxmoxName}/rollback`,
                params: {},
            }).then(res => {
                if(res.success) {
                    alert(_t('Rollback started successfully! The VM will now restart.'));
                } else {
                    alert(_t('Rollback failed: ') + res.error);
                }
            });
        },

        _onDeleteSnapshot: function (ev) {
            if (!confirm(_t("Are you sure you want to delete this snapshot? This CANNOT be undone."))) {
                return;
            }
            
            const $button = $(ev.currentTarget);
            const $item = $button.closest('.list-group-item');
            const vmId = this.$el.data('vm-id');
            const proxmoxName = $item.data('proxmox-name');

            this._rpc({
                route: `/vm/${vmId}/snapshot/${proxmoxName}/delete`,
                params: {},
            }).then(res => {
                if (res.success) {
                    $item.remove(); // Удаляем элемент из списка
                } else {
                    alert(_t('Error deleting snapshot: ') + res.error);
                }
            });
        },
        
        // РЕФАКТОРИНГ: обертка для ajax.jsonRpc для удобства и обработки ошибок
        _rpc: function(routeOptions) {
            const $buttons = this.$('button, a');
            $buttons.addClass('disabled');
            
            return ajax.jsonRpc(routeOptions.route, 'call', routeOptions.params || {})
                .guardedCatch((err) => {
                    const errorMsg = err.data.message || _t('An RPC error occurred.');
                    alert(errorMsg);
                })
                .finally(() => {
                    $buttons.removeClass('disabled');
                });
        }
    });

    return publicWidget.registry.VmSnapshotManager;
});
