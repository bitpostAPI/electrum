#!/usr/bin/env python
from typing import TYPE_CHECKING, Optional, Union
from PyQt5.QtWidgets import  QVBoxLayout, QLabel, QGridLayout, QPushButton, QLineEdit, QCalendarWidget, QComboBox,QHBoxLayout,QDateTimeEdit, QListWidget,QCheckBox,QSizePolicy
from PyQt5.QtCore import QDate,QDateTime
from electrum.i18n import _
from electrum.util import NotEnoughFunds, NoDynamicFeeEstimates
from electrum.wallet import InternalAddressCorruption, CannotBumpFee
from electrum.gui.qt.util import (WindowModalDialog, Buttons, CancelButton, BlockingWaitingDialog, PasswordLineEdit)
from .interface import BitpostInterface, BitpostDownException
from .utils import get_fee_units
from .preview_tx_dialog import PreviewTxsDialog
from datetime import datetime
if TYPE_CHECKING:
    from electrum.gui.qt.main_window import ElectrumWindow


class ConfirmTxDialog(WindowModalDialog):
    # set fee and return password (after pw check)

    def __init__(self, *, window: 'ElectrumWindow', inputs, outputs, output_value: Union[int, str], is_sweep: bool):
        WindowModalDialog.__init__(self, window, _("BitPost Confirm Transaction"))
        self.main_window = window
        self.inputs = inputs
        self.outputs = outputs
        self.output_value = output_value
        self.delay = None
        self.target = None
        self.txs = []
        self.config = window.config
        self.wallet = window.wallet
        self.not_enough_funds = False
        self.no_dynfee_estimates = False
        self.needs_update = False
        self.is_sweep=is_sweep
        self.password_required = self.wallet.has_keystore_encryption() and not is_sweep
        self.num_txs = int(window.config.get('bitpost_num_txs'))
        
        self.imax_fees = 0
        self.imax_size = 0

        self.build_gui()

    def build_gui(self):
        vbox = QVBoxLayout()
        self.setLayout(vbox)
        grid = QGridLayout()
        vbox.addLayout(grid)
        self.amount_label = QLabel('')

        grid.addWidget(QLabel(_("Target for confirmation")),0,0)
        self.qtarget=QDateTimeEdit(QDateTime.currentDateTime().addSecs(int(self.main_window.config.get('bitpost_target_interval'))*60))
        grid.addWidget(self.qtarget,0,1) 

        self.asap_check=QCheckBox("ASAP")
        self.asap_check.clicked.connect(self.toggle_target)
        grid.addWidget(self.asap_check,0,2)
           
        grid.addWidget(QLabel(_("Maximum Fee")),2,0)
        self.max_fees = QLineEdit(str(self.main_window.config.get('bitpost_max_fee')))
        self.max_fees.textChanged.connect(self.change_max_fees)
        grid.addWidget(self.max_fees,2,1)                
        self.fee_combo=QComboBox()
        fee_combo_values = get_fee_units(self.main_window, self.main_window.config.get('bitpost_max_fee_unit'))
        self.fee_combo.addItems(fee_combo_values)
        grid.addWidget(self.fee_combo,2,2)

        self.schedule_check=QCheckBox(_("Schedule transaction"))
        self.schedule_check.clicked.connect(self.toggle_delay)
        grid.addWidget(self.schedule_check, 3, 0,1,-1)
        self.qdelay=QDateTimeEdit(QDateTime.currentDateTime())
        grid.addWidget(self.qdelay,4,0)
        sp_retain = QSizePolicy(self.qdelay.sizePolicy())
        sp_retain.setRetainSizeWhenHidden(True)
        self.qdelay.setSizePolicy(sp_retain)
        self.qdelay.setVisible(False)
                
        self.message_label = QLabel(self.default_message())
        grid.addWidget(self.message_label, 9, 0, 1, -1)
        self.pw_label = QLabel(_('Password'))
        self.pw_label.setVisible(self.password_required)
        self.pw = PasswordLineEdit()
        self.pw.setVisible(self.password_required)
        grid.addWidget(self.pw_label, 11, 0)
        grid.addWidget(self.pw, 11, 1, 1, -1)

        self.send_button = QPushButton(_('Send'))
        self.send_button.clicked.connect(self.on_send)
        self.send_button.setDefault(True)
        
        self.preview_button = QPushButton(_('Preview'))
        self.preview_button.clicked.connect(self.on_preview)
        self.preview_button.setDefault(True)

        vbox.addLayout(Buttons(CancelButton(self), self.preview_button,self.send_button))

        # set default to ASAP checked
        self.asap_check.setChecked(True)
        self.toggle_target()

        self.update()
        self.is_send = False
        
    def toggle_target(self):
        if self.asap_check.isChecked():
            self.qtarget.setEnabled(False)
            self.qdelay.setEnabled(False)
            self.schedule_check.setEnabled(False)
        else:
            self.qtarget.setEnabled(True)
            self.qdelay.setEnabled(True)
            self.schedule_check.setEnabled(True)
            
    def toggle_delay(self):
        if self.schedule_check.isChecked():
            self.qdelay.setVisible(True)

        else:
            self.qdelay.setVisible(False)

    def change_max_fees(self):
        pass
        
    def default_message(self):
        return _('Enter your password to proceed') if self.password_required else _('Click Send to proceed')

    def on_preview(self):
        password = self.pw.text() or None
        BlockingWaitingDialog(self.main_window, _("Preparing transaction..."), self.prepare_txs)
        if len(self.txs) <= 0:
            return
        d = PreviewTxsDialog(window=self.main_window,txs=self.txs,password=password,is_sweep=self.is_sweep)
        cancelled, is_send, password = d.run()
        if cancelled:
            return
        if is_send:
            self.pw.setText(password)
            self.send()
    
    def run(self):
        cancelled = not self.exec_()
        password = self.pw.text() or None
        return cancelled, self.is_send, password, self.txs, self.target, self.delay, self.imax_fees, self.imax_size

    def send(self):
        password = self.pw.text() or None
        if self.password_required:
            if password is None:
                self.main_window.show_error(_("Password required"), parent=self)
                return
            try:
                self.wallet.check_password(password)
            except Exception as e:
                self.main_window.show_error(str(e), parent=self)
                return
        self.is_send=True
        self.target=self.qtarget.dateTime().toPyDateTime().timestamp()
        if self.asap_check.isChecked():
            self.target = round(datetime.now().timestamp() + 20*60)
        
        if self.schedule_check.isChecked():
            self.delay=self.qdelay.dateTime().toPyDateTime()  
        else:
            self.delay = self.main_window.config.get('bitpost_delay', 0)
            
        if self.target<self.delay:
            self.main_window.show_error(_("Target should be greater than delay"))
            return
        self.is_send = True
        if self.is_send:
            self.accept()
        else:
            print("ERROR: is_send is false")

    def on_send(self):
        BlockingWaitingDialog(self.main_window, _("Preparing transaction..."), self.prepare_txs)
        if len(self.txs) <= 0:
            return
        self.send()
    
    def get_feerates(self, estimated_size):
        if self.config.get('testnet'):
            testnet = True
        else:
            testnet = False
        bitpost_interface = BitpostInterface(testnet=testnet)
        max_feerate = self.calculate_max_feerate(estimated_size, self.fee_combo.currentText())
        return bitpost_interface.get_feerates(max_feerate, size=self.num_txs)

    def calculate_max_feerate(self, estimated_size, fee_unit):
        raw_max_fee = float(self.max_fees.text())
        if fee_unit == 'sats/byte':
            return raw_max_fee
        elif fee_unit == 'sats':
            return raw_max_fee/estimated_size
        else:
            max_sats = 100_000_000*raw_max_fee/float(self.main_window.fx.exchange_rate())
            return max_sats/estimated_size

    def prepare_txs(self):
        try:
            self.prepare_txs_by_bumping_fee()
        except CannotBumpFee as ex:
            self.prepare_txs_manually()

    def prepare_txs_manually(self):
        max_fee = int(200*self.calculate_max_feerate(200, self.fee_combo.currentText()))
        highest_fee_tx = self.make_tx(max_fee)

        self.max_size = est_size = highest_fee_tx.estimated_size()
        self.max_fees = max_fee = int(est_size * self.calculate_max_feerate(est_size, self.fee_combo.currentText()))
        highest_fee_tx = self.make_tx(max_fee)

        can_be_change = lambda o: self.main_window.wallet.is_change(o.address) and self.main_window.wallet.is_mine(o.address)
        change_index = max([i for i in range(len(highest_fee_tx.outputs())) if can_be_change(highest_fee_tx.outputs()[i])])
        max_feerate = (highest_fee_tx.input_value() - highest_fee_tx.output_value())/highest_fee_tx.estimated_size()
        feerates = self.get_feerates(max_feerate)

        highest_fee_tx.set_rbf(True)
        self.txs = []
        for fee in feerates:
            tx = self.main_window.wallet.make_unsigned_transaction(coins=highest_fee_tx.inputs(), outputs=highest_fee_tx.outputs())
            new_change = highest_fee_tx.outputs()[change_index].value + int(abs(max_feerate-fee)*highest_fee_tx.estimated_size())
            tx.outputs()[change_index].value = new_change
            self.txs.append(tx)

        self.not_enough_funds = False
        self.no_dynfee_estimates = False

    def prepare_txs_by_bumping_fee(self):
        try:
            base_tx = self.make_tx(1)
            est_size = base_tx.estimated_size()
            feerates = self.get_feerates(est_size)

            base_tx.set_rbf(True)
            base_tx.serialize_to_network()
            for fee in feerates:
                tx=self.bump_fee(base_tx,fee)
                tx.set_rbf(True)
                self.txs.append(tx)
                self.imax_fees=max(self.imax_fees, tx.get_fee())
                self.imax_size=max(self.imax_size, tx.estimated_size())
            self.not_enough_funds = False
            self.no_dynfee_estimates = False
        except NotEnoughFunds:
            self.not_enough_funds = True
            self.txs = [] 
            return
        except NoDynamicFeeEstimates:
            self.no_dynfee_estimates = True
            self.txs = []
            try:            
                self.txs = [self.make_tx(0)]
            except BaseException:
                return
        except InternalAddressCorruption as e:
            self.txs = []
            self.main_window.show_error(str(e))
            return
        except BitpostDownException:
            self.main_window.show_error(_("Fee Rates Service Not Available"), parent=self)
            self.is_send = False
            return
        except Exception as e:
            self.txs = []
            print("Exception",e)
            self.main_window.show_error(_("Exception: "+str(e)), parent=self.main_window)
            return
    def bump_fee(self, tx, new_fee):
        
        inputs=tx.inputs()
        coco=[]
        for c in self.inputs:
            if c not in inputs:
                
                coco.append(c)
        try:
            self.main_window.logger.debug(str(new_fee) + "bump fee method 1")
            tx_out= self.main_window.wallet._bump_fee_through_coinchooser(
                tx=tx,
                new_fee_rate= new_fee,
                coins=coco)

        except Exception as ex:
            if all(self.main_window.wallet.is_mine(o.address) for o in list(tx.outputs())):
                raise ex
            self.window.show_error(_("Not enought funds, please add more inputs or reduce max fee"))
            raise NotEnoughFunds
        return tx_out
        
    def make_tx(self, fee_est):

        return self.main_window.wallet.make_unsigned_transaction(
            coins=self.inputs,
            outputs=self.outputs,
            fee=fee_est,
            is_sweep=self.is_sweep)
