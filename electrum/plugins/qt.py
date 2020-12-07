from electrum.plugin import BasePlugin, hook
from electrum.gui.qt.util import (EnterButton, Buttons, CloseButton, OkButton, WindowModalDialog, get_parent_main_window)
from electrum.gui.qt.main_window import ElectrumWindow
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QInputDialog, QPushButton, QCheckBox,QLineEdit)
from functools import partial
from electrum.i18n import _
from .confirm_tx_dialog import ConfirmTxDialog

from typing import Optional, TYPE_CHECKING, Sequence, List, Union

from electrum.invoices import PR_TYPE_ONCHAIN, PR_TYPE_LN, PR_DEFAULT_EXPIRATION_WHEN_CREATING, Invoice
from electrum.invoices import PR_PAID, PR_FAILED, pr_expiration_values, LNInvoice, OnchainInvoice
from electrum.transaction import (Transaction, PartialTxInput,
                                  PartialTransaction, PartialTxOutput)
                                  
                                  
from .interface import BitpostInterface
import datetime as dt

                                  
                                  
class Plugin(BasePlugin):
    def __init__(self, parent, config, name):
        BasePlugin.__init__(self, parent, config, name)
        self.wallets=set()

    def requires_settings(self):
        return True

    def settings_widget(self, window): 
        # Return a button that when pressed presents a settings dialog.
        return EnterButton(_("Settings"), partial(self.settings_dialog, window))

    def settings_dialog(self, window):
        # Return a settings dialog.
        d = WindowModalDialog(window, _("Bitpost settings"))
        vbox = QVBoxLayout(d)
        
        d.setMinimumSize(500, 200)
        hbox_ntx=QHBoxLayout()
        hbox_ntx.addWidget(QLabel("Default number of Txs"))
        hbox_ntx.addWidget(QLineEdit())
        vbox.addLayout(hbox_ntx)
        hbox_maxfee=QHBoxLayout()
        hbox_maxfee.addWidget(QLabel("Default max fee to use"))
        hbox_maxfee.addWidget(QLineEdit())        
        #vbox.addWidget(QCheckBox(_("Use Bitpost feerate")))
        vbox.addLayout(hbox_maxfee)
        vbox.addStretch()
        
        vbox.addLayout(Buttons(CloseButton(d), OkButton(d)))
        d.show()


        
    def display_bitpost(self,dialog):
        window = get_parent_main_window(dialog)
        
        external_keypairs=None
        raw_signed_txs=[]
        """
        while True:
            if isinstance(window, ElectrumWindow):
                break
            window=window.parent()
            if not window:
                break
        """
                 
        invoice = window.read_invoice()       
        if not invoice:
            print("BitPostPlugin: Invoice is Null")
            return

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
        bump_fee= lambda base_tx,new_fee: window.wallet._bump_fee_through_coinchooser(
            tx=base_tx,
            new_fee_rate= new_fee,
            coins=inputs)
        output_values = [x.value for x in outputs]
        if output_values.count('!') > 1:
            window.show_error(_("More than one output set to spend max"))
            return

        output_value = '!' if '!' in output_values else sum(output_values)
        d = ConfirmTxDialog(window=window, make_tx=make_tx, bump_fee=bump_fee, output_value=output_value, is_sweep=is_sweep)
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
            print(target.timestamp())
            print(delay.timestamp())
            bitpost_interface = BitpostInterface(testnet=True)
            request = bitpost_interface.create_bitpost_request(raw_signed_txs, int(target.timestamp()), delay=int(delay.timestamp()))

            print(request.send_request().json())

        else:
            window.preview_tx_dialog(make_tx=make_tx,
                                external_keypairs=external_keypairs)    

                                    

        
    @hook
    def load_wallet(self, wallet, main_window):
        self.wallet=wallet
    
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



    @hook
    def abort_send(self, window):
        """ Called after sending a payment

        Args:
            grid: QGridLayout containing the Send tab UI

        """
        button = EnterButton(_("BitPost"),lambda: ConfirmTxDialog(grid))

        #button.clicked.connect(lambda: self.display_bitpost(grid))
        #grid.addWidget(button,6,5)
        
        dir(window.layout())
        #window.layout().addWidget(button)
        
        button.show()
