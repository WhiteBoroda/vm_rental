odoo.define('vm_rental.vm_actions', function (require) {
  var publicWidget = require('web.public.widget');
  var ajax = require('web.ajax');

  publicWidget.registry.VmButtons = publicWidget.Widget.extend({
    selector: '.vm-list',
    events: {
      'click .start-vm': '_onStartVm',
      'click .stop-vm': '_onStopVm',
      'click .reboot-vm': '_onRebootVm',
      'click .extend-vm': '_onExtendVm',
    },

    _onStartVm: function (ev) {
      const vmid = ev.currentTarget.dataset.vmid;
      ajax.jsonRpc(`/vm/start/${vmid}`, 'call', {}).then(() => location.reload());
    },

    _onStopVm: function (ev) {
      const vmid = ev.currentTarget.dataset.vmid;
      ajax.jsonRpc(`/vm/stop/${vmid}`, 'call', {}).then(() => location.reload());
    },

    _onRebootVm: function (ev) {
      const vmid = ev.currentTarget.dataset.vmid;
      ajax.jsonRpc(`/vm/reboot/${vmid}`, 'call', {}).then(() => location.reload());
    },

    _onExtendVm: function (ev) {
      const vmid = ev.currentTarget.dataset.vmid;
      ajax.jsonRpc(`/vm/extend/${vmid}`, 'call', {}).then(() => location.reload());
    },
  });

  return publicWidget.registry.VmButtons;
});
