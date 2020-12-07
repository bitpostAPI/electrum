#!/usr/bin/env python
#
# Electrum - lightweight Bitcoin client
# Copyright (2019) The Electrum Developers
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Union

from PyQt5.QtWidgets import  QVBoxLayout, QLabel, QGridLayout, QPushButton, QLineEdit, QCalendarWidget, QComboBox,QHBoxLayout,QDateTimeEdit
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
from datetime import datetime
import time

if TYPE_CHECKING:
    from .main_window import ElectrumWindow



class DateTimeCalendar(QVBoxLayout):
    def __init__(self,current_date=None):
        if not current_date:
            current_date=datetime.now()
            
        QVBoxLayout.__init__(self)
        self.date=QCalendarWidget()
        self.date.setSelectedDate(QDate(current_date.year,current_date.month,current_date.day))

        self.addWidget(self.date)
        hbox=QHBoxLayout()
        self.hour = QComboBox()
        self.minute = QComboBox()
        self.hour.addItems([ str(i) for i in range(0,24)])
        self.minute.addItems([ str(i) for i in range(0,60)])
        self.hour.setCurrentIndex(current_date.hour)
        self.minute.setCurrentIndex(current_date.minute)
        hbox.addWidget(QLabel(_("H:")))
        hbox.addWidget(self.hour)
        hbox.addWidget(QLabel(_("M:")))
        hbox.addWidget(self.minute)
        self.addLayout(hbox)
        
    
     
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

       
        vbox = QVBoxLayout()
        self.setLayout(vbox)
        grid = QGridLayout()
        vbox.addLayout(grid)
        self.amount_label = QLabel('')
        
        grid.addWidget(QLabel(_("Amount to be sent") + ": "), 0, 0)
        grid.addWidget(self.amount_label, 0, 1)

        grid.addWidget(QLabel(_("NUMBER TXS")),1,0)
        self.num_txs = QLineEdit("3")
        self.num_txs.textChanged.connect(self.change_num_txs)
        grid.addWidget(self.num_txs,1,1)
       
        grid.addWidget(QLabel(_("MAX FEE")),2,0)
        self.max_fees = QLineEdit("10000")
        self.max_fees.textChanged.connect(self.change_max_fees)
        grid.addWidget(self.max_fees,2,1)                
        
        grid.addWidget(QLabel(_("DELAY")),3,0)
        grid.addWidget(QLabel(_("TARGET")),3,1)
        """
        self.qdelay = QCalendarWidget()
        self.qtarget = QCalendarWidget()
        self.qdelayh = QComboBox()
        self.qdelaym = QComboBox()
        self.qdelayh.addItems([ str(i) for i in range(0,24)])
        self.qdelaym.addItems([ str(i) for i in range(0,60)])
        self.qtargeth = QComboBox()
        self.qtargetm = QComboBox()
        self.qtargeth.addItems([ str(i) for i in range(0,24)])
        self.qtargetm.addItems([ str(i) for i in range(0,60)])
        hLDelay=QHBoxLayout()
        hLDelay.addWidget(self.qdelayh)
        hLDelay.addWidget(self.qdelaym)
        hLTarget=QHBoxLayout()
        hLTarget.addWidget(self.qtargeth)
        hLTarget.addWidget(self.qtargetm)
        grid.addWidget(self.qdelay,5,0)
        grid.addWidget(self.qtarget,5,1)
        grid.addLayout(hLDelay,6,0)
        grid.addLayout(hLTarget,6,1)
        """
        self.qdelay=QDateTimeEdit(QDateTime.currentDateTime())

        self.qtarget=QDateTimeEdit(QDateTime.currentDateTime())
        grid.addWidget(self.qdelay,4,0)
        grid.addWidget(self.qtarget,4,1)
        
        
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
        #BlockingWaitingDialog(window, _("Preparing transaction..."), self.prepare_txs)
        self.update()
        self.is_send = False
        
    def change_max_fees(self):
        """
        TODO
        check user input data
        """
        pass
    def change_num_txs(self):
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

        self.target=self.qtarget.dateTime().toPyDateTime()
        self.delay=self.qdelay.dateTime().toPyDateTime()  
        self.is_send = True
        self.prepare_txs()
        if self.is_send:
            self.accept()
        else:
            print("ERROR: is_send is false")

    def prepare_txs(self):
        try:
            bp_feerate = requests.get("https://api.bitpost.co/feerateset?maxfeerate=" + 
                    str(self.max_fees.text())+"&size="+str(self.num_txs.text())).json()
                    
            feerates=[]
            if bp_feerate['status'] == 'success':
                feerates = bp_feerate['data']['feerates']
                print("feerates",feerates)
            else:
                self.main_window.show_error(_("Fee Rates Service Not Available"), parent=self)
                self.is_send = False
                return
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

