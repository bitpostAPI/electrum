from PyQt5.QtWidgets import  QVBoxLayout, QLabel, QGridLayout, QPushButton, QLineEdit, QCalendarWidget, QComboBox,QHBoxLayout,QDateTimeEdit, QListWidget,QCheckBox,QSizePolicy
from electrum.i18n import _
from electrum.gui.qt.util import (WindowModalDialog, Buttons, CancelButton, BlockingWaitingDialog, PasswordLineEdit)


class Exchange():
    def __init__(self, fx):
        self.rate = float(fx.exchange_rate())
        self.currency = fx.get_currency()

    def str_exchange(self, value, r=2):
        return "({}{})".format(round(value * self.rate / 100000000, r), self.currency)


class PreviewTxsDialog(WindowModalDialog):
    def __init__(self, *, window: 'ElectrumWindow', txs, password, is_sweep):

        WindowModalDialog.__init__(self, window, _('BitPost Transactions Preview'))
        self.setMinimumSize(800, 600)
        self.main_window = window
        self.txs = txs
        self.password_required = self.main_window.wallet.has_keystore_encryption() and not is_sweep
        self.is_send = False
        vbox = QVBoxLayout()
        self.setLayout(vbox)
        lbox = QListWidget()

        items = []
        for tx in txs:
            inputs = tx.inputs()
            outputs = tx.outputs()
            fee = tx.get_fee()
            fiat = False

            text = "fee: {}".format(fee)
            if self.main_window.fx and self.main_window.fx.is_enabled():
                fiat = Exchange(self.main_window.fx)
                text += fiat.str_exchange(fee)

            text += "\t\tvbyte: {}\n".format(tx.estimated_size())

            tmp = "fee/vbyte: {}".format(round(fee / tx.estimated_size(), 2))
            if fiat:
                tmp += fiat.str_exchange(fee / tx.estimated_size())
            text += tmp
            if len(tmp) > 22:
                tab = "\t"
            else:
                tab = "\t\t"

            text += "{}total size: {}\n".format(tab,
                                                tx.estimated_total_size())

            text += "INPUTS:\n"
            for i in inputs:
                text += "{}:{} = {}".format(
                    i.prevout.txid.hex(),
                    i.prevout.out_idx,
                    i.value_sats())
                if fiat:
                    text += fiat.str_exchange(i.value_sats())
                text += "\n"
            text += "OUTPUTS:\n"
            for o in outputs:
                text += "{} = {}".format(o.address, o.value)
                if fiat:
                    text += fiat.str_exchange(o.value)
                text += "\n"

            items.append(text)

        lbox.addItems(items)
        vbox.addWidget(lbox)

        self.send_button = QPushButton(_('Send'))
        self.send_button.clicked.connect(self.on_send)
        self.send_button.setDefault(True)

        self.pw_label = QLabel(_('Password'))
        self.pw_label.setVisible(self.password_required)
        self.pw = PasswordLineEdit(password)
        self.pw.setVisible(self.password_required)

        vbox.addLayout(Buttons(CancelButton(self), self.pw_label, self.pw, self.send_button))

    def run(self):
        cancelled = not self.exec_()
        password = self.pw.text() or None
        return cancelled, self.is_send, password

    def on_send(self):
        """
        password = self.pw.text() or None
        if self.password_required:
            if password is None:
                self.main_window.show_error(_("Password required"), parent=self)
                return
            try:
                self.main_window.wallet.check_password(password)
            except Exception as e:
                self.main_window.show_error(str(e), parent=self)
                return
        """
        self.is_send = True
        self.accept()
