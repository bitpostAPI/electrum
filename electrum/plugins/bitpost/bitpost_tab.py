#!/usr/bin/env python

from typing import Optional, List, Dict, Sequence, Set
from enum import IntEnum
import copy
import re

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QFont,QStandardItem
from PyQt5.QtWidgets import QAbstractItemView, QMenu, QLabel, QHBoxLayout

from electrum.i18n import _
from electrum.transaction import PartialTxInput

from electrum.gui.qt.util import MyTreeView, ColorScheme, MONOSPACE_FONT, EnterButton,webopen

class BitPostList(MyTreeView):
    invoice_items=[]
    class Columns(IntEnum):
        DATE = 0
        ID = 1
        DELAY = 2
        TARGET = 3
        MAX_FEES = 4

    headers = {
        Columns.DATE: _('Date'),
        Columns.ID: _('ID'),
        Columns.DELAY: _('Delay'),
        Columns.TARGET: _('Target'),
        Columns.MAX_FEES: _('Max Fees'),
    }
    filter_columns = [Columns.DATE, Columns.ID, Columns.MAX_FEES]
    stretch_column = Columns.TARGET
    def __init__(self, parent):
        super().__init__(parent, self.create_menu,
                         stretch_column=self.stretch_column,
                         editable_columns=[])
                         
        self.setModel(QStandardItemModel(self))
        #self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSortingEnabled(True)
        self.update()
    def get_url(self,txid):
        if self.config.get('testnet'):
          testnet="testnet-"
        else:
          testnet=""
        return "https://{}api.bitpost.co/explorer?query={}".format(testnet,txid)
    def update(self):
        bitposts=self.parent.config.get("bitpost_ids",[])
        self.model().clear()
        self.update_headers(self.__class__.headers)
        invoices=self.parent.wallet.get_invoices()
        for idx,invoice in enumerate(invoices):
            mex=invoice.message
            self.insert_invoice(idx,invoice)
        self.filter()
    def insert_invoice(self,idx,invoice):
        try:
            invoice_date=invoice.time
            message_split=re.split("https\:\/\/(?:testnet\-)?api\.bitpost\.co/explorer\?query\=(.{11})\,(\d*)\,(\d*)",invoice.message)
            invoice_id=message_split[1]
            invoice_delay=message_split[2]
            invoice_target=message_split[3]
            labels = ['%d'%invoice_date, invoice_id, invoice_delay, invoice_target,'hello']
            invoice_item =[]
            for x in labels:
              invoice_item.append(QStandardItem(x))
            invoice_item[self.Columns.DATE].setData(invoice_date)
            invoice_item[self.Columns.ID].setData(invoice_id)
            invoice_item[self.Columns.DELAY].setData(invoice_delay)
            invoice_item[self.Columns.TARGET].setData(invoice_target)
            invoice_item[self.Columns.MAX_FEES].setData("")
            self.model().appendRow(invoice_item)
            self.invoice_items.append(labels)
        except:
          pass
        
    def create_menu(self,position):
        
        org_idx: QModelIndex = self.indexAt(position)
        
        selected=self.invoice_items[org_idx.row()]
        menu=QMenu()
        menu.addAction(("Open in BitPost explorer"),lambda: webopen(self.get_url(selected[1])))
        menu.exec_(self.viewport().mapToGlobal(position))

      
