#!/usr/bin/env python


from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Union

from PyQt5.QtWidgets import  QVBoxLayout, QLabel, QGridLayout, QPushButton, QLineEdit, QCalendarWidget, QComboBox,QHBoxLayout,QDateTimeEdit, QListWidget,QCheckBox,QSizePolicy
from PyQt5.QtCore import QDate,QDateTime

from electrum.i18n import _
from electrum.util import NotEnoughFunds, NoDynamicFeeEstimates
from electrum.plugin import run_hook
from electrum.transaction import Transaction, PartialTransaction
from electrum.simple_config import FEERATE_WARNING_HIGH_FEE, FEE_RATIO_HIGH_WARNING
from electrum.wallet import InternalAddressCorruption

from electrum.gui.qt.util import (WindowModalDialog, ColorScheme, HelpLabel, Buttons, CancelButton,
                   BlockingWaitingDialog, PasswordLineEdit)

from electrum.gui.qt.fee_slider import FeeSlider, FeeComboBox

import requests
from .interface import BitpostInterface
from datetime import datetime
import time

if TYPE_CHECKING:
    from electrum.gui.qt.main_window import ElectrumWindow

class PreviewTxsDialog(WindowModalDialog):
    def __init__(self, *, window:'ElectrumWindow',txs):
        WindowModalDialog.__init__(self,window,_('BitPost Transactions Preview'))
        self.main_window=window
        self.txs=txs
        vbox=QVBoxLayout()
        self.setLayout(vbox)
        lbox=QListWidget()
        
      
class ConfirmTxDialog(WindowModalDialog):
    # set fee and return password (after pw check)

    def __init__(self, *, window: 'ElectrumWindow', make_tx, bump_fee, output_value: Union[int, str], is_sweep: bool):
        WindowModalDialog.__init__(self, window, _("BitPost Confirm Transaction"))
        self.main_window = window
        self.make_tx = make_tx
        self.bump_fee=bump_fee
        self.output_value = output_value

        self.delay = None
        self.target = None
        self.txs = []
        self.config = window.config
        self.wallet = window.wallet
        self.not_enough_funds = False
        self.no_dynfee_estimates = False
        self.needs_update = False
        self.password_required = self.wallet.has_keystore_encryption() and not is_sweep

        self.num_txs = int(window.config.get('bitpost_num_txs'))

       
        vbox = QVBoxLayout()
        self.setLayout(vbox)
        grid = QGridLayout()
        vbox.addLayout(grid)
        self.amount_label = QLabel('')
        
        # grid.addWidget(QLabel(_("Amount to be sent") + ": "), 0, 0)
        # grid.addWidget(self.amount_label, 0, 1)

        # grid.addWidget(QLabel(_("NUMBER TXS")),1,0)
        # self.num_txs = QLineEdit(str(window.config.get('bitpost_num_txs')))
        # self.num_txs.textChanged.connect(self.change_num_txs)
        # grid.addWidget(self.num_txs,1,1)
        grid.addWidget(QLabel(_("TARGET")),0,0)
        self.qtarget=QDateTimeEdit(QDateTime.currentDateTime().addSecs(int(window.config.get('bitpost_target_interval'))*60))
        grid.addWidget(self.qtarget,0,1) 

        self.asap_check=QCheckBox("ASAP")
        self.asap_check.clicked.connect(self.toggle_target)
        
        grid.addWidget(self.asap_check,0,2)
        
           
        grid.addWidget(QLabel(_("MAX FEE")),2,0)
        self.max_fees = QLineEdit(str(window.config.get('bitpost_max_fees')))
        self.max_fees.textChanged.connect(self.change_max_fees)
        grid.addWidget(self.max_fees,2,1)                
        fee_combo=QComboBox()
        fee_combo_values=['sats','sats/byte']


        print(dir(self.main_window.fx))
        print(self.main_window.fx.get_currency())
        if self.main_window.fx and self.main_window.fx.is_enabled():
            fee_combo_values.append(self.main_window.fx.get_currency())
            
        fee_combo.addItems(fee_combo_values)
        
        
        grid.addWidget(fee_combo,2,2)
        
       
        
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
        vbox.addLayout(Buttons(CancelButton(self), self.send_button))

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
            print("checked")
            self.qdelay.setVisible(True)

        else:
            print("unckecked")
            self.qdelay.setVisible(False)
    def change_max_fees(self):
        """
        TODO
        check user input data
        """
        pass
        
    def default_message(self):
        return _('Enter your password to proceed') if self.password_required else _('Click Send to proceed')

    def on_preview(self):
        self.accept()

    def run(self):
        cancelled = not self.exec_()
        password = self.pw.text() or None
        return cancelled, self.is_send, password, self.txs, self.target, self.delay

    def on_send(self):
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
        #target_d = self.qtarget.selectedDate().toPyDate()
        #delay_d = self.qdelay.selectedDate().toPyDate()
        #self.target=datetime(target_d.year,target_d.month,target_d.day,self.qtargeth,self.qtargetm)
        #self.target=datetime(delay_d.year,delay_d.month,delay_d.day,self.qdelayh,self.qdelaym)
        if self.asap_check.isChecked():
            self.target=0
        self.target=self.qtarget.dateTime().toPyDateTime()
        if self.schedule_check.isChecked():
            self.delay=self.qdelay.dateTime().toPyDateTime()  
        else:
            self.delay=0
        self.is_send = True
        BlockingWaitingDialog(self.main_window, _("Preparing transaction..."), self.prepare_txs)
        if self.is_send:
            self.accept()
        else:
            print("ERROR: is_send is false")

    def get_feerates(self):
        if self.config.get('testnet'):
            testnet = True
        else:
            testnet = False
        bitpost_interface = BitpostInterface(testnet=testnet)
        return bitpost_interface.get_feerates(float(self.max_fees.text()), size=self.num_txs)

    def prepare_txs(self):
        try:
            feerates = self.get_feerates()
        except:
            self.main_window.show_error(_("Fee Rates Service Not Available"), parent=self)
            self.is_send = False
            return

        try:
            base_tx = self.make_tx(1)
            est_size = base_tx.estimated_size()
            print("tx total size estimated:",base_tx.estimated_total_size())
            print("tx size estimated:",base_tx.estimated_size())
            base_tx.set_rbf(True)
            base_tx.serialize_to_network()
            for fee in feerates:
                tx=self.bump_fee(base_tx,fee)
                tx.set_rbf(True)
                self.txs.append(tx)
                
            self.not_enough_funds = False
            self.no_dynfee_estimates = False
        except NotEnoughFunds:
            self.not_enough_funds = True
            self.txs = None
            if fallback_to_zero_fee:
                try:
                    self.txs = [self.make_tx(0)]
                except BaseException:
                    return
            else:
                return
        except NoDynamicFeeEstimates:
            self.no_dynfee_estimates = True
            self.txs = None
            try:
                self.txs = [self.make_tx(0)]
            except BaseException:
                return
        except InternalAddressCorruption as e:
            self.txs = None
            self.main_window.show_error(str(e))
            raise