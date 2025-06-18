odoo.define('vm_rental.settings', function (require) {
'use strict';

var publicWidget = require('web.public.widget');
var ajax = require('web.ajax');
var core = require('web.core');

publicWidget.registry.ProxmoxSettings = publicWidget.Widget.extend({
    selector: '.app_settings_block[name="vm_rental_settings"]',
    events: {
        'click .js_test_connection': '_onTestConnectionClick',
    },

    _onTestConnectionClick: function (ev) {
        ev.preventDefault();
        const $button = $(ev.currentTarget);
        const $row = $button.closest('tr');
        const serverId = $row.data('server-id');

        if (!serverId) return;

        // Disable button and show spinner
        $button.prop('disabled', true);
        const originalIcon = $button.find('i').attr('class');
        $button.find('i').attr('class', 'fa fa-spinner fa-spin');
        
        const $statusCell = $row.find('.server-status-cell');
        const $messageCell = $row.find('.server-message-cell');
        $statusCell.html('<span class="badge badge-warning">Connecting...</span>');
        $messageCell.html('');

        ajax.jsonRpc('/vm_rental/settings/test_server', 'call', { server_id: serverId })
            .then(result => {
                if (result.success) {
                    $statusCell.html('<span class="badge badge-success">Connected</span>');
                    const nodes = result.info.nodes.join(', ') || 'None';
                    $messageCell.html(`<small class="text-muted">Nodes: ${nodes}</small>`);
                } else {
                    $statusCell.html('<span class="badge badge-danger">Failed</span>');
                    $messageCell.html(`<small class="text-danger">${result.message}</small>`);
                }
            })
            .guardedCatch(() => {
                $statusCell.html('<span class="badge badge-danger">Failed</span>');
                $messageCell.html('<small class="text-danger">An RPC error occurred.</small>');
            })
            .finally(() => {
                // Re-enable button and restore icon
                $button.prop('disabled', false);
                $button.find('i').attr('class', originalIcon);
            });
    },
});

return publicWidget.registry.ProxmoxSettings;
});