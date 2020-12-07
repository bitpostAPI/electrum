#!/usr/bin/env python
from electrum.plugin import BasePlugin, hook
from electrum.gui.qt.util import (EnterButton, Buttons, CloseButton, OkButton, WindowModalDialog, get_parent_main_window)
from electrum.gui.qt.main_window import ElectrumWindow
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QInputDialog, QPushButton, QCheckBox,QLineEdit, QComboBox)
from functools import partial
from electrum.i18n import _
from .confirm_tx_dialog import ConfirmTxDialog

from typing import Optional, TYPE_CHECKING, Sequence, List, Union

from electrum.invoices import PR_TYPE_ONCHAIN, PR_TYPE_LN, PR_DEFAULT_EXPIRATION_WHEN_CREATING, Invoice
from electrum.invoices import PR_PAID, PR_FAILED, pr_expiration_values, LNInvoice, OnchainInvoice
from electrum.transaction import (Transaction, PartialTxInput,
                                  PartialTransaction, PartialTxOutput)
                                  
                                  
from .interface import BitpostInterface
from datetime import datetime

                                  
                                  
class Plugin(BasePlugin):

    default_max_fee = 1000
    default_num_txs = 50
    default_target_mins = 20

    def __init__(self, parent, config, name):
        BasePlugin.__init__(self, parent, config, name)
        self.wallets=set()
        self.max_fees=self.config.get('bitpost_max_fees', self.default_max_fee)
        self.num_txs=self.config.get('bitpost_num_txs', self.default_num_txs)
        self.target_interval=self.config.get('bitpost_target_interval', self.default_target_mins)

        
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
        max_fees_e.setText(str(self.max_fees))
        hbox_maxfee.addWidget(max_fees_e)

        fee_combo = QComboBox()
        fee_combo_values = ['sats', 'sats/byte']
        if main_window.fx and main_window.fx.is_enabled():
            fee_combo_values.append(main_window.fx.get_currency())
        fee_combo.addItems(fee_combo_values)
        hbox_maxfee.addWidget(fee_combo)

        help_button__max_fee = QPushButton("?")
        hbox_maxfee.addWidget(help_button__max_fee)

        vbox.addLayout(hbox_maxfee)

        advanced_settings_title = QHBoxLayout()
        advanced_settings_title.addWidget(QLabel("<b>Advanced Settings</b>"))
        vbox.addLayout(advanced_settings_title)

        hbox_ntx=QHBoxLayout()
        hbox_ntx.addWidget(QLabel("Default number of Txs"))
        num_txs_e=QLineEdit()
        num_txs_e.setText(str(self.num_txs))
        hbox_ntx.addWidget(num_txs_e)
        help_button__num_txs = QPushButton("?")
        hbox_ntx.addWidget(help_button__num_txs)
        vbox.addLayout(hbox_ntx)
        

        
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
            
        max_fees = str(max_fees_e.text())
        self.config.set_key('bitpost_max_fees', max_fees)
        self.max_fees = max_fees

        num_txs = str(num_txs_e.text())
        self.config.set_key('bitpost_num_txs', num_txs)
        self.num_txs = num_txs

        # target_interval = str(target_interval_e.text())
        # self.config.set_key('bitpost_target_interval', target_interval)
        # self.target_interval = target_interval

    
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

        
        
    def send_txs(self,txs):
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

        # shortcut to advanced preview (after "enough funds" check!)
        if self.config.get('advanced_preview'):
            self.preview_tx_dialog(make_tx=make_tx,
                external_keypairs=external_keypairs)
            return

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
                delay=delay.timestamp()
            except:
                delay=0
                
            now=datetime.now().timestamp()
            if target < delay:
                raise Exception("Target should be greter than delay")
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
            
            response=request.send_request().json()
            if response['status'] == 'success':
                if len(invoice.message)>0:
                    invoice.message += "\n"
                invoice.message += response['data']['url']
            
                window.wallet.save_invoice(invoice)

                window.invoice_list.update()
                window.do_clear()
                   
        else:
            d = ConfirmTxDialog(window=window,txs=txs)
                

        
    @hook
    def load_wallet(self, wallet, main_window):
        self.wallet=wallet

        self.config.set_key('bitpost_max_fees', self.default_max_fee)
        self.config.set_key('bitpost_num_txs', self.default_num_txs)
        self.config.set_key('bitpost_target_interval', self.default_target_mins)
    
    @hook
    def close_wallet(self, wallet):
        self.wallet=None
    
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
