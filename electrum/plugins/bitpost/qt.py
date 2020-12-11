#!/usr/bin/env python
from electrum.plugin import BasePlugin, hook
from electrum.gui.qt.util import (EnterButton, Buttons, CloseButton, OkButton, WindowModalDialog, get_parent_main_window)
from electrum.gui.qt.main_window import ElectrumWindow
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QInputDialog, QPushButton, QCheckBox,QLineEdit, QComboBox)
from functools import partial
from electrum.i18n import _
from .confirm_tx_dialog import ConfirmTxDialog,PreviewTxsDialog

from typing import Optional, TYPE_CHECKING, Sequence, List, Union

from electrum.invoices import PR_TYPE_ONCHAIN, PR_TYPE_LN, PR_DEFAULT_EXPIRATION_WHEN_CREATING, Invoice
from electrum.invoices import PR_PAID, PR_FAILED, pr_expiration_values, LNInvoice, OnchainInvoice
from electrum.transaction import (Transaction, PartialTxInput,
                                  PartialTransaction, PartialTxOutput)
                                  
                                  
from .interface import BitpostInterface
from datetime import datetime
from .utils import get_fee_units
                                  
                                  
class Plugin(BasePlugin):

    default_max_fee = 1000
    default_max_fee_unit = 'sats'

    default_num_txs = 50
    default_delay = 0
    default_target_mins = 20
    default_notification_platform = 'None'

    def __init__(self, parent, config, name):
        BasePlugin.__init__(self, parent, config, name)
        self.wallets=set()
        self.max_fee = self.config.get('bitpost_max_fee', self.default_max_fee)
        self.max_fee_unit = self.config.get('bitpost_max_fee_unit', self.default_max_fee_unit)
        self.num_txs = self.config.get('bitpost_num_txs', self.default_num_txs)
        self.delay = self.config.get('bitpost_delay', self.default_delay)
        self.target_interval = self.config.get('bitpost_target_interval', self.default_target_mins)

        
    def requires_settings(self):
        return True
        

    def settings_widget(self, window): 
        # Return a button that when pressed presents a settings dialog.
        return EnterButton(_("Settings"), partial(self.settings_dialog, window))


    def settings_dialog(self, window):
        # Return a settings dialog.
        main_window = get_parent_main_window(window)

        d = WindowModalDialog(window, _("Bitpost settings"))
        vbox = QVBoxLayout(d)
        
        d.setMinimumSize(500, 200)

        hbox_maxfee = QHBoxLayout()
        hbox_maxfee.addWidget(QLabel("Default max fee to use"))
        max_fees_e = QLineEdit()
        max_fees_e.setText(str(self.max_fee))
        hbox_maxfee.addWidget(max_fees_e)

        fee_combo = QComboBox()
        fee_combo_values = get_fee_units(main_window, self.max_fee_unit)

        fee_combo.addItems(fee_combo_values)
        hbox_maxfee.addWidget(fee_combo)

        help_button__max_fee = QPushButton("?")
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
        platform_address.addWidget(platform_combo)

        platform_address.addWidget(QLabel("Address/handle"))
        vbox.addLayout(platform_address)
        address_input = QLineEdit()
        platform_address.addWidget(address_input)

        subscription_title = QHBoxLayout()
        subscription_title.addWidget(QLabel("Subscriptions"))
        subscription_title.addWidget(QPushButton("?"))
        subscription_title.addStretch()
        vbox.addLayout(subscription_title)

        subscriptions1 = QVBoxLayout()
        overdue_checkbox = QCheckBox("Overdue")
        subscriptions1.addWidget(overdue_checkbox)
        mined_checkbox = QCheckBox("Mined")
        subscriptions1.addWidget(mined_checkbox)
        max_fee_reached_checkbox = QCheckBox("Maximum fee reached")
        subscriptions1.addWidget(max_fee_reached_checkbox)
        vbox.addLayout(subscriptions1)

        reorg_checkbox = QCheckBox("Block reorg")
        subscriptions1.addWidget(reorg_checkbox)
        orphaned_checkbox = QCheckBox("Child tx orphaned")
        subscriptions1.addWidget(orphaned_checkbox)

        advanced_settings_title = QHBoxLayout()
        advanced_settings_title.addStretch()
        advanced_settings_title.addWidget(QLabel("<b>Advanced Settings</b>"))
        advanced_settings_title.addStretch()
        vbox.addLayout(advanced_settings_title)

        hbox_ntx=QHBoxLayout()
        hbox_ntx.addWidget(QLabel("Default number of Txs"))
        num_txs_e=QLineEdit()
        num_txs_e.setText(str(self.num_txs))
        hbox_ntx.addWidget(num_txs_e)
        help_button__num_txs = QPushButton("?")
        hbox_ntx.addWidget(help_button__num_txs)
        vbox.addLayout(hbox_ntx)

        broadcast_policy = QHBoxLayout()
        broadcast_policy.addWidget(QLabel("First broadcast policy"))

        broadcast_policy_combo = QComboBox()
        # 'Broadcast lowest fee transaction immediatly'
        broadcast_policy_options = ['Don\'t delay first broadcast', 'Allow delay of first broadcast']
        if self.delay == 1:
            broadcast_policy_options.reverse()

        broadcast_policy_combo.addItems(broadcast_policy_options)
        broadcast_policy.addWidget(broadcast_policy_combo)

        help_button__broadcast_policy = QPushButton("?")
        broadcast_policy.addWidget(help_button__broadcast_policy)
        vbox.addLayout(broadcast_policy)

        # hbox_target_interval = QHBoxLayout()
        # hbox_target_interval.addWidget(QLabel("Target interval"))
        # target_interval_e=QLineEdit()
        # target_interval_e.setText(str(self.target_interval))
        # hbox_target_interval.addWidget(target_interval_e)
        # vbox.addLayout(hbox_target_interval)

        vbox.addStretch()
        vbox.addLayout(Buttons(CloseButton(d), OkButton(d)))

        if not d.exec_():
            return
            
        self.max_fee = str(max_fees_e.text())
        self.config.set_key('bitpost_max_fee', self.max_fee)

        self.config.set_key('bitpost_max_fee_unit', fee_combo.currentText())
        self.max_fee_unit = fee_combo.currentText()

        num_txs = str(num_txs_e.text())
        self.config.set_key('bitpost_num_txs', num_txs)
        self.num_txs = num_txs

        self.delay = 1 if broadcast_policy_combo.currentText() == 'Allow delay of first broadcast' else 0
        self.config.set_key('bitpost_delay', self.delay)

        if not self.valid_address(platform_combo.currentText(), address_input.text()):
            pass # TODO error window

        self.config.set_key('bitpost_notification_platform', platform_combo.currentText())
        self.config.set_key('bitpost_notification_address', address_input.text())

        subscriptions = []
        if overdue_checkbox.isChecked():
            subscriptions.append({'name': 'overdue'})
        if mined_checkbox.isChecked():
            subscriptions.append({'name': 'mined'})
        if max_fee_reached_checkbox.isChecked():
            subscriptions.append({'name': 'reached'})
        if reorg_checkbox.isChecked():
            subscriptions.append({'name': 'orphan_block'})
        if orphaned_checkbox.isChecked():
            pass # TODO

        self.config.set_key('bitpost_notification_subscriptions', subscriptions)

    def valid_address(self, platform, address):
        return True  # TODO validation

    def bump_fee(self, tx, new_fee, coins):
        print(tx.inputs())
        inputs=tx.inputs()
        coco=[]
        for c in coins:
            if c not in inputs:
                
                coco.append(c)
        try:
            print("bump fee method 1")
            tx_out= self.window.wallet._bump_fee_through_coinchooser(
                tx=tx,
                new_fee_rate= new_fee,
                coins=coco)
            
        except:
            print("bump fee method 2")
            tx_out = self.window.wallet._bump_fee_through_decreasing_outputs(
                tx=tx, new_fee_rate=new_fee)
        """        
        new_inputs=tx_out.inputs()
        my_dict = {i:new_inputs.count(i) for i in new_inputs}
        print(my_dict)
        for k in my_dict:
            if my_dict[k] > 1:
                print(f"DUPLICATED INPUT {k}:{v}")
                raise Exception(f"DUPLICATED INPUT {k}:{v}")
        """
        return tx_out

        
        
    def send_txs(self,txs,password,target,delay):
            pass
        
    def display_bitpost(self,dialog):
        self.window = window = get_parent_main_window(dialog)
        
        external_keypairs=None
        raw_signed_txs=[]

        invoice = window.read_invoice()       
        if not invoice:
            print("BitPostPlugin: Invoice is Null")
            return
        print(dir(invoice))
        print(invoice)
       
        window.wallet.save_invoice(invoice)

        window.invoice_list.update()
        window.do_clear()
        
        inputs = window.get_coins()
        outputs = invoice.outputs

        is_sweep = bool(None)
        make_tx = lambda fee_est: window.wallet.make_unsigned_transaction(
            coins=inputs,
            outputs=outputs,
            fee=fee_est,
            is_sweep=is_sweep)
        bump_fee= lambda base_tx,new_fee: self.bump_fee(
            tx=base_tx,
            new_fee= new_fee,
            coins=inputs)
    

        output_values = [x.value for x in outputs]
        if output_values.count('!') > 1:
            window.show_error(_("More than one output set to spend max"))
            return

        output_value = '!' if '!' in output_values else sum(output_values)
        d = ConfirmTxDialog(window=window, make_tx=make_tx, bump_fee=bump_fee, 
            output_value=output_value, is_sweep=is_sweep)

        if d.not_enough_funds:
            # Check if we had enough funds excluding fees,
            # if so, still provide opportunity to set lower fees.
            if not d.have_enough_funds_assuming_zero_fees():
                self.show_message(_('Not Enough Funds'))
                return
        """            
        # shortcut to advanced preview (after "enough funds" check!)
        if self.config.get('advanced_preview'):
            self.preview_tx_dialog(make_tx=make_tx,
                external_keypairs=external_keypairs)
            return
        """
        
        cancelled, is_send, password, txs, target, delay = d.run()
        if cancelled:
            return
        if is_send:
            print("TXS BATCH SIZE",len(txs))
            for tx in txs:
            
                print("----------------")      
                print("FEE",tx.get_fee())
                print("****************************")
                window.wallet.sign_transaction(tx,password)
                print("SERIALIZED", tx.serialize_to_network())
                raw_signed_txs.append(tx.serialize_to_network())
                print("****************************")
            

            print("transactions signed")
            try:
                target=target.timestamp()
            except:
                target=0
            try:
                delay = delay.timestamp()
            except:
                delay = self.delay
                
            now=datetime.now().timestamp()
            if target < delay:
                raise Exception("Target should be greater than delay")
            if now > target:
                target= now + 600
            if now > delay:
                delay = 0
                
            if self.config.get('testnet'):
                testnet = True
            else:
                testnet = False
            bitpost_interface = BitpostInterface(testnet=testnet)
            
            request = bitpost_interface.create_bitpost_request(raw_signed_txs, 
                                                int(target), delay=int(delay))

            if self.window.config.get('bitpost_notification_platform') != 'None':
                request.add_notification(self.window.config.get('bitpost_notification_platform'),
                                         self.window.config.get('bitpost_notification_address'),
                                         self.window.config.get('bitpost_notification_subscriptions'))

            response=request.send_request().json()
            if response['status'] == 'success':
                if len(invoice.message)>0:
                    invoice.message += "\n"
                invoice.message += response['data']['url']
            
                window.wallet.save_invoice(invoice)

                window.invoice_list.update()
                window.do_clear()
                   
        else:
            return
            
                

        
    @hook
    def load_wallet(self, wallet, main_window):
        self.wallet=wallet
        self.window = main_window

        self.config.set_key('bitpost_max_fee', self.max_fee)
        self.config.set_key('bitpost_max_fee_unit', self.max_fee_unit)

        self.config.set_key('bitpost_num_txs', self.num_txs)
        self.config.set_key('bitpost_delay', self.delay)

        self.config.set_key('bitpost_target_interval', self.target_interval)
        self.config.set_key('bitpost_notification_platform', self.config.get('bitpost_notification_platform'), self.default_notification_platform)

    @hook
    def close_wallet(self, wallet):
        self.wallet=None

    @hook
    def close_settings_dialog(self):
        has_fx = self.window.fx and self.window.fx.is_enabled()

        has_different_fx = self.max_fee_unit != 'sats' and  self.max_fee_unit != 'sats/byte' and self.window.fx.get_currency() != self.max_fee_unit
        if has_fx and has_different_fx:
            self.max_fee_unit = self.default_max_fee_unit
            self.config.set_key('bitpost_max_fee_unit', self.max_fee_unit)

            self.max_fee = self.default_max_fee
            self.config.set_key('bitpost_max_fee', self.max_fee)

    @hook
    def create_send_tab(self, grid):
        """ Called after sending a payment

        Args:
            grid: QGridLayout containing the Send tab UI

        """
        button = EnterButton(_("BitPost"),lambda: self.display_bitpost(grid))

        #button.clicked.connect(lambda: self.display_bitpost(grid))
        grid.addWidget(button,6,5)

        #window.layout().addWidget(button)
        button.show()
