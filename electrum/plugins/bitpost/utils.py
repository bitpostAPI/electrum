from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,QLineEdit, QComboBox)
from electrum.gui.qt.util import (Buttons, CloseButton, OkButton, WindowModalDialog, get_parent_main_window)
from electrum.i18n import _
import re

def get_fee_units(main_window, default):
    fee_combo_values = ['sats', 'sats/byte']
    if main_window.fx and main_window.fx.is_enabled():
        fee_combo_values.append(main_window.fx.get_currency())
    if default in fee_combo_values:
        fee_combo_values.remove(default)
        fee_combo_values.insert(0, default)
    return fee_combo_values


class HelpTexts:

    max_fee = 'The maximum amount you are willing to pay for a bitcoin transaction. ' \
              'The actual fee you will pay will likely be lower than the amount you choose, especially' \
              'if you choose a high value. You can choose a maximum in fiat if you enabled a fiat currency' \
              'under Tools > Preferences > Fiat'

    subscriptions = 'You can subscribe to notifications about important events regarding your payments.' \
                    'Here is a explanation of the avaible events/subscriptions:\n' \
                    '- Overdue: the payment hasn\'t been confirmed before the chosen deadline.\n' \
                    '- Mined: the payment has been mined/confirmed.\n' \
                    '- Maximum fee reached: the transaction with the maximum fee has been broadcasted....\n' \
                    '- Block reorganization: a chainsplit has occured and your previously confirmed transaction may ' \
                    'have become unconfirmed again.\n' \
                    '- Child transaction orphaned: an old transaction in the parent payment was confirmed making it' \
                    'impossible for the child payment to be executed. This is an unlikely scenario that will better' \
                    'handled in a posterior release of the plugin.'

    num_txs = 'The number of transactions that will be broadcasted by default to bitpost.'
    delay = 'When you schedule a payment with a deadline far into the future, bitpost may choose to broadcast the' \
            'first transaction posteriorly. You may allow or disallow this practice.'


def create_settings_window(small_window):
    window = get_parent_main_window(small_window)

    d = WindowModalDialog(window, _("Bitpost settings"))
    vbox = QVBoxLayout(d)

    d.setMinimumSize(500, 200)

    hbox_maxfee = QHBoxLayout()
    hbox_maxfee.addWidget(QLabel("Default max fee to use"))
    max_fees_e = QLineEdit()
    max_fees_e.setText(str(window.config.get('bitpost_max_fee')))
    hbox_maxfee.addWidget(max_fees_e)

    fee_combo = QComboBox()
    fee_combo_values = get_fee_units(window, window.config.get('bitpost_max_fee_unit'))

    fee_combo.addItems(fee_combo_values)
    hbox_maxfee.addWidget(fee_combo)

    help_button__max_fee = QPushButton("?")
    help_button__max_fee.clicked.connect(lambda: d.show_message(HelpTexts.max_fee))
    hbox_maxfee.addWidget(help_button__max_fee)

    vbox.addLayout(hbox_maxfee)

    empty_line = QHBoxLayout()
    empty_line.addWidget(QLabel(""))
    vbox.addLayout(empty_line)

    advanced_settings_title = QHBoxLayout()
    advanced_settings_title.addStretch()
    advanced_settings_title.addWidget(QLabel("<b>Notifications</b>"))
    advanced_settings_title.addStretch()
    vbox.addLayout(advanced_settings_title)

    platform_address = QHBoxLayout()

    platform_address.addWidget(QLabel("Platform"))
    platform_combo = QComboBox()
    fee_combo_values = ['None', 'Email', 'Twitter']
    platform_combo.addItems(fee_combo_values)
    platform_combo.setCurrentText(window.config.get('bitpost_notification_platform'))
    platform_address.addWidget(platform_combo)

    platform_address.addWidget(QLabel("Address/handle"))
    vbox.addLayout(platform_address)
    address_input = QLineEdit()
    address_input.setText(window.config.get('bitpost_notification_address', ''))
    platform_address.addWidget(address_input)

    subscription_title = QHBoxLayout()
    subscription_title.addWidget(QLabel("Subscriptions"))
    subscriptions_help = QPushButton("?")
    subscriptions_help.clicked.connect(lambda: d.show_message(HelpTexts.subscriptions))
    subscription_title.addWidget(subscriptions_help)
    subscription_title.addStretch()
    vbox.addLayout(subscription_title)

    subscriptions = {subscription['name'] for subscription in
                     window.config.get('bitpost_notification_subscriptions')}
    subscriptions1 = QVBoxLayout()
    overdue_checkbox = QCheckBox("Overdue")
    if 'overdue' in subscriptions:
        overdue_checkbox.setChecked(True)
    subscriptions1.addWidget(overdue_checkbox)

    mined_checkbox = QCheckBox("Mined")
    if 'mine' in subscriptions:
        mined_checkbox.setChecked(True)
    subscriptions1.addWidget(mined_checkbox)
    max_fee_reached_checkbox = QCheckBox("Maximum fee reached")
    if 'reached' in subscriptions:
        max_fee_reached_checkbox.setChecked(True)
    subscriptions1.addWidget(max_fee_reached_checkbox)
    vbox.addLayout(subscriptions1)

    reorg_checkbox = QCheckBox("Block reorganization")
    if 'orphaned_block' in subscriptions:
        reorg_checkbox.setChecked(True)
    subscriptions1.addWidget(reorg_checkbox)
    orphaned_checkbox = QCheckBox("Child transaction orphaned")
    if '' in subscriptions:
        orphaned_checkbox.setChecked(True)
    subscriptions1.addWidget(orphaned_checkbox)

    advanced_settings_title = QHBoxLayout()
    advanced_settings_title.addStretch()
    advanced_settings_title.addWidget(QLabel("<b>Advanced Settings</b>"))
    advanced_settings_title.addStretch()
    vbox.addLayout(advanced_settings_title)

    hbox_ntx = QHBoxLayout()
    hbox_ntx.addWidget(QLabel("Default number of Txs"))
    num_txs_e = QLineEdit()
    num_txs_e.setText(str(window.config.get('bitpost_num_txs')))
    hbox_ntx.addWidget(num_txs_e)
    help_button__num_txs = QPushButton("?")
    help_button__num_txs.clicked.connect(lambda: d.show_message(HelpTexts.num_txs))
    hbox_ntx.addWidget(help_button__num_txs)
    vbox.addLayout(hbox_ntx)

    broadcast_policy = QHBoxLayout()
    broadcast_policy.addWidget(QLabel("First broadcast policy"))

    broadcast_policy_combo = QComboBox()
    # 'Broadcast lowest fee transaction immediatly'
    broadcast_policy_options = ['Don\'t delay first broadcast', 'Allow delay of first broadcast']
    if window.config.get('bitpost_delay') == 1:
        broadcast_policy_options.reverse()

    broadcast_policy_combo.addItems(broadcast_policy_options)
    broadcast_policy.addWidget(broadcast_policy_combo)

    help_button__broadcast_policy = QPushButton("?")
    help_button__broadcast_policy.clicked.connect(lambda: d.show_message(HelpTexts.delay))
    broadcast_policy.addWidget(help_button__broadcast_policy)
    vbox.addLayout(broadcast_policy)

    vbox.addStretch()
    vbox.addLayout(Buttons(CloseButton(d), OkButton(d)))

    if not d.exec_():
        return

    window.config.set_key('bitpost_max_fee_unit', fee_combo.currentText())
    delay = 1 if broadcast_policy_combo.currentText() == 'Allow delay of first broadcast' else 0
    window.config.set_key('bitpost_delay', delay)
    window.config.set_key('bitpost_notification_platform', platform_combo.currentText())

    subscriptions = []
    if overdue_checkbox.isChecked():
        subscriptions.append({'name': 'overdue'})
    if mined_checkbox.isChecked():
        subscriptions.append({'name': 'mine'})
    if max_fee_reached_checkbox.isChecked():
        subscriptions.append({'name': 'reached'})
    if reorg_checkbox.isChecked():
        subscriptions.append({'name': 'orphaned_block'})
    if orphaned_checkbox.isChecked():
        pass  # TODO
    window.config.set_key('bitpost_notification_subscriptions', subscriptions)

    try:
        window.config.set_key('bitpost_max_fee', float(max_fees_e.text()))
    except:
        d.show_error('Invalid maximum fee, must be a number.')
        create_settings_window(small_window)

    try:
        window.config.set_key('bitpost_num_txs', int(num_txs_e.text()))
    except:
        d.show_error('Invalid default number of transactions, must be an integer')
        create_settings_window(small_window)

    if not valid_address(platform_combo.currentText(), address_input.text()):
        d.show_error('Invalid handle/address for ' + platform_combo.currentText())
        create_settings_window(small_window)

    window.config.set_key('bitpost_notification_address', address_input.text())


def valid_address(platform, address):
    if platform.lower() == 'none':
        return True
    elif not 1 <= len(address) < 200:
        return False
    elif platform.lower() == 'email':
        return re.match('^[^@]+@[^@]+\.[^@]+$', address)
    elif platform.lower() == 'twitter':
        return re.match('^[a-zA-Z0-9_]{1,15}$', address)
    else:
        return True
