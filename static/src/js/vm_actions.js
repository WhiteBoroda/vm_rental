odoo.define('vm_rental.vm_actions', function (require) {
  'use strict';

  var publicWidget = require('web.public.widget');
  var ajax = require('web.ajax');
  var core = require('web.core');
  var _t = core._t;
  var csrf_token = core.csrf_token;

  publicWidget.registry.VmButtons = publicWidget.Widget.extend({
      selector: '.vm-list', // Теперь этот селектор найдет наш контейнер
      events: {
          'click .start-vm': '_onVmAction',
          'click .stop-vm': '_onVmAction',
          'click .reboot-vm': '_onVmAction',
      },

      // Словарь для сопоставления статусов и CSS-классов
      STATUS_CLASSES: {
          'active': 'badge badge-success',
          'stopped': 'badge badge-secondary',
          'suspended': 'badge badge-warning',
      },

      /**
       * Общий обработчик для всех действий с ВМ
       * @param {MouseEvent} ev
       * @private
       */
      _onVmAction: function (ev) {
          ev.preventDefault();
          const $button = $(ev.currentTarget);
          const vmId = $button.data('vmid');
          
          // Определяем URL в зависимости от класса кнопки
          let rpc_url = '';
          if ($button.hasClass('start-vm')) rpc_url = `/vm/start/${vmId}`;
          if ($button.hasClass('stop-vm')) rpc_url = `/vm/stop/${vmId}`;
          if ($button.hasClass('reboot-vm')) rpc_url = `/vm/reboot/${vmId}`;
          if (!rpc_url) return;

          const $row = $button.closest('tr');
          const $actionsCell = $row.find('.vm-actions-cell');
          const $spinner = $actionsCell.find('.fa-spinner');
          const $statusCell = $row.find('.vm-status-cell');
          const $buttons = $actionsCell.find('.btn');

          // Блокируем интерфейс на время запроса
          $buttons.addClass('disabled');
          $spinner.removeClass('d-none');

          ajax.jsonRpc(rpc_url, 'call', {'csrf_token': csrf_token}).then(result => {
              if (result.success) {
                  // Обновляем значок статуса
                  const statusClass = this.STATUS_CLASSES[result.new_state] || 'badge badge-light';
                  $statusCell.html(`<span class="${statusClass}">${result.state_text}</span>`);
                  
                  // Обновляем видимость кнопок
                  this._updateButtonsVisibility($actionsCell, result.new_state);

              } else {
                  // Показываем ошибку, если что-то пошло не так
                  this.displayNotification({
                      type: 'danger',
                      title: _t('Error'),
                      message: result.error || _t('An unknown error occurred.'),
                  });
              }
          }).guardedCatch(err => {
               this.displayNotification({
                  type: 'danger',
                  title: _t('Error'),
                  message: _t('Could not contact the server.'),
              });
          }).finally(() => {
              // Возвращаем интерфейс в исходное состояние
              $buttons.removeClass('disabled');
              $spinner.addClass('d-none');
          });
      },

      /**
       * Обновляет видимость кнопок в зависимости от нового статуса ВМ
       * @param {JQuery} $actionsCell
       * @param {string} newState
       * @private
       */
      _updateButtonsVisibility: function ($actionsCell, newState) {
          $actionsCell.find('.start-vm').toggleClass('d-none', newState === 'active');
          $actionsCell.find('.stop-vm').toggleClass('d-none', newState !== 'active');
          $actionsCell.find('.reboot-vm').toggleClass('d-none', newState !== 'active');
      },
  });

  return publicWidget.registry.VmButtons;
});
