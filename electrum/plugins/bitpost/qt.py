#!/usr/bin/env python
from functools import partial
from datetime import datetime
from electrum.plugin import BasePlugin, hook
from electrum.gui.qt.util import (EnterButton, get_parent_main_window)
from electrum.util import NotEnoughFunds
from electrum.i18n import _
from .confirm_tx_dialog import ConfirmTxDialog
from .interface import BitpostInterface
from .utils import create_settings_window
                                  
                                  
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
        
    def requires_settings(self):
        return True

    def settings_widget(self, window): 
        # Return a button that when pressed presents a settings dialog.
        return EnterButton(_("Settings"), partial(self.settings_dialog, window))

    def settings_dialog(self, window):
        create_settings_window(window)

    def valid_address(self, platform, address):
        return True  # TODO validation

    def bump_fee(self, tx, new_fee, coins):
        
        inputs=tx.inputs()
        coco=[]
        for c in coins:
            if c not in inputs:
                
                coco.append(c)
        try:
            print(str(new_fee) + "bump fee method 1")
            tx_out= self.window.wallet._bump_fee_through_coinchooser(
                tx=tx,
                new_fee_rate= new_fee,
                coins=coco)
            
        except:
            self.window.show_error(_("Not enought funds, please add more inputs or reduce max fee"))
            raise NotEnoughFunds
        return tx_out

    def send_txs(self,txs,password,target,delay):
            pass
        
    def display_bitpost(self,dialog):
        self.window = window = get_parent_main_window(dialog)

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
            # Check if we had enough funds excluding fees, if so, still provide opportunity to set lower fees.
            if not d.have_enough_funds_assuming_zero_fees():
                self.show_message(_('Not Enough Funds'))
                return

        self.send_bitpost_request(d, invoice)

    def send_bitpost_request(self, dialog, invoice):
        window = get_parent_main_window(dialog)

        cancelled, is_send, password, txs, target, delay = dialog.run()
        if cancelled or not is_send:
            return

        raw_signed_txs = []
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
            delay = delay.timestamp()
        except:
            delay = self.config.get('bitpost_delay')

        now=datetime.now().timestamp()
        if target < delay:
            window.show_error(_("Target should be greater than delay"))
            return
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

        if self.config.get('bitpost_notification_platform') != 'None':
            request.add_notification(self.config.get('bitpost_notification_platform'),
                                     self.config.get('bitpost_notification_address'),
                                     self.config.get('bitpost_notification_subscriptions'))

        response=request.send_request().json()
        if response['status'] == 'success':
            if len(invoice.message)>0:
                invoice.message += "\n"
            invoice.message += response['data']['url']

            window.wallet.save_invoice(invoice)

            window.invoice_list.update()
            window.do_clear()

    @hook
    def load_wallet(self, wallet, main_window):
        self.wallet=wallet
        self.window = main_window

        max_fee = self.config.get('bitpost_max_fee', self.default_max_fee)
        self.config.set_key('bitpost_max_fee', max_fee)

        max_fee_unit = self.config.get('bitpost_max_fee_unit', self.default_max_fee_unit)
        self.config.set_key('bitpost_max_fee_unit', max_fee_unit)

        num_txs = self.config.get('bitpost_num_txs', self.default_num_txs)
        self.config.set_key('bitpost_num_txs', num_txs)

        delay = self.config.get('bitpost_delay', self.default_delay)
        self.config.set_key('bitpost_delay', delay)

        target_interval = self.config.get('bitpost_target_interval', self.default_target_mins)
        self.config.set_key('bitpost_target_interval', target_interval)

        self.config.set_key('bitpost_notification_platform', self.config.get('bitpost_notification_platform',
                            self.default_notification_platform))
        self.config.set_key('bitpost_notification_address', self.config.get('bitpost_notification_address', ''))
        self.config.set_key('bitpost_notification_subscriptions', self.config.get('bitpost_notification_subscriptions', []))

    @hook
    def close_wallet(self, wallet):
        self.wallet=None

    @hook
    def close_settings_dialog(self):
        has_fx = self.window.fx and self.window.fx.is_enabled()

        has_different_fx = self.config.get('bitpost_max_fee_unit') != 'sats' and  \
            self.config.get('bitpost_max_fee_unit') != 'sats/byte' and \
            self.window.fx.get_currency() != self.config.get('bitpost_max_fee_unit')
            
        if has_fx and has_different_fx:
            self.config.set_key('bitpost_max_fee_unit', self.default_max_fee_unit)
            self.config.set_key('bitpost_max_fee', self.default_max_fee)

    @hook
    def create_send_tab(self, grid):
        button = EnterButton(_("Pay with Bitpost..."),lambda: self.display_bitpost(grid))
        grid.addWidget(button,6,5)
        button.show()
