odoo.define('vm_rental.vm_actions', function (require) {
  'use strict';

  var publicWidget = require('web.public.widget');
  var ajax = require('web.ajax');
  var core = require('web.core');
  var _t = core._t;

  publicWidget.registry.VmActions = publicWidget.Widget.extend({
      selector: '.vm-list',
      events: {
          'click .start-vm, .stop-vm, .reboot-vm': '_onVmAction',
      },

      _onVmAction: function (ev) {
          ev.preventDefault();
          const $button = $(ev.currentTarget);
          const vmId = $button.data('vmid');

          let rpc_url = '';
          if ($button.hasClass('start-vm')) rpc_url = `/vm/start/${vmId}`;
          if ($button.hasClass('stop-vm')) rpc_url = `/vm/stop/${vmId}`;
          if ($button.hasClass('reboot-vm')) rpc_url = `/vm/reboot/${vmId}`;
          if (!rpc_url) return;

          const $card = $button.closest('.vm-card');
          const $actionsCell = $card.find('.vm-actions-cell');
          const $icon = $button.find('i');
          const originalIconClass = $icon.attr('class');

          // ИЗМЕНЕНИЕ: Заменяем иконку на спиннер внутри кнопки
          $button.prop('disabled', true);
          $icon.attr('class', 'fa fa-spinner fa-spin mr-1');

          ajax.jsonRpc(rpc_url, 'call', {}).then(result => {
              if (result.success) {
                  this._updateStatusBadge($card, result.new_state);
                  this._updateButtonsVisibility($actionsCell, result.new_state);
                  this._showNotification(
                      'success', _t('Success'), _t('Operation completed successfully.'));
              } else {
                  this._showNotification('danger', _t('Error'), result.error || _t('An unknown error occurred.'));
              }
          }).guardedCatch(err => {
               this._showNotification('danger', _t('Error'), _t('Could not contact the server.'));
          }).finally(() => {
              // Возвращаем исходную иконку и активность кнопки
              $button.prop('disabled', false);
              $icon.attr('class', originalIconClass);
          });
      },

      _showNotification: function(type, title, message) {
            // Простой способ для фронтенда - используем alert или создаем Bootstrap toast
            if (type === 'danger') {
                alert(title + ': ' + message);
            } else {
                // Можно создать Bootstrap toast для успешных операций
                const toast = $(`
                    <div class="toast" role="alert" style="position: fixed; top: 20px; right: 20px; z-index: 9999;">
                        <div class="toast-body bg-success text-white">
                            <strong>${title}:</strong> ${message}
                        </div>
                    </div>
                `);
                $('body').append(toast);
                toast.toast({delay: 3000}).toast('show');
                setTimeout(() => toast.remove(), 3500);
            }
        },

      _updateStatusBadge: function ($card, newState) {
          const $badge = $card.find('.card-header .badge');
          if (!$badge.length) return;

          $badge.removeClass('badge-success badge-secondary badge-warning badge-info badge-danger badge-dark');
          let newClass = 'badge-light';
          let newText = newState.charAt(0).toUpperCase() + newState.slice(1);

          if (newState === 'active') newClass = 'badge-success';
          else if (newState === 'stopped') newClass = 'badge-secondary';
          else if (newState === 'suspended') newClass = 'badge-warning';

          $badge.addClass(newClass).text(newText);
      },

      _updateButtonsVisibility: function ($actionsCell, newState) {
          const isActive = newState === 'active';
          $actionsCell.find('.start-vm').toggleClass('d-none', isActive);
          $actionsCell.find('.stop-vm').toggleClass('d-none', !isActive);
          $actionsCell.find('.reboot-vm').toggleClass('d-none', !isActive);

          // Обновляем ширину кнопки снапшотов
          const $snapButton = $actionsCell.find('a[href*="snapshots"]');
          $snapButton.toggleClass('w-50', isActive).toggleClass('w-100', !isActive);
      },
  });

  return publicWidget.registry.VmActions;
});