from electrum.plugin import BasePlugin, hook
from electrum.gui.qt.util import (EnterButton, Buttons, CloseButton, OkButton, WindowModalDialog)
from PyQt5.QtWidgets import (QVBoxLayout, QLabel)
from functools import partial
from electrum.i18n import _

class Plugin(BasePlugin):

    def __init__(self, parent, config, name):
        BasePlugin.__init__(self, parent, config, name)

    def requires_settings(self):
        return True

    def settings_widget(self, window): 
        # Return a button that when pressed presents a settings dialog.
        return EnterButton(_('Settings'), partial(self.settings_dialog, window))

    def settings_dialog(self, window):
        # Return a settings dialog.
        d = WindowModalDialog(window, _("Bitpost settings"))
        vbox = QVBoxLayout(d)

        d.setMinimumSize(500, 200)
        vbox.addStretch()
        vbox.addLayout(Buttons(CloseButton(d), OkButton(d)))
        d.show()

    @hook
    def create_send_tab(self, grid):
        """ Called after sending a payment

            Args:
                grid: QGridLayout containing the Send tab UI

            """
        pass
