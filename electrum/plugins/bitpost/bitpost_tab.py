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

from electrum.util import format_time

class NotBitpostRowException(Exception):
    pass

           
class BitPostList(MyTreeView):
    invoice_items=[]
    invoices=[]
    class Columns(IntEnum):
        DATE = 0
        ID = 1
        DELAY = 2
        TARGET = 3
        MAX_FEES = 4
        MAX_SIZE = 5

    headers = {
        Columns.DATE: _('Date'),
        Columns.ID: _('ID'),
        Columns.DELAY: _('Delay'),
        Columns.TARGET: _('Target'),
        #Columns.CURR_FEES: _('Current Fees'),
        #Columns.CURR_SIZE: _('Current Size'),
        Columns.MAX_FEES: _('Max Fee'),
        Columns.MAX_SIZE: _('Max Size'),
    }

    filter_columns = [Columns.DATE, Columns.ID, Columns.MAX_FEES]
    stretch_column = Columns.ID

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
          testnet = "testnet-"
        else:
          testnet = ""
        return "https://{}api.bitpost.co/explorer?query={}".format(testnet,txid)
        
    def update(self):
        bitposts=self.parent.config.get("bitpost_ids",[])
        self.model().clear()
        self.update_headers(self.__class__.headers)
        
        invoices = self.parent.wallet.get_invoices()
        for invoice in invoices:
            self.insert_bitpost(invoice.time,invoice.message)
            
        history_values = self.parent.wallet.get_full_history().values()
        for h in history_values:
            self.insert_bitpost(h['timestamp'],h['label'])
            
        self.filter()
    
    def format_time(self,vtime):
        try:
            itime=int(vtime)
            if itime <= 0: 
                raise Exception()
            return format_time(itime)
        except Exception as e:
            return ""
    
    def insert_bitpost(self,invoice_date,message):
        try:
            message_split = self.split_row(message)
            invoice_id = message_split[1]
            if invoice_id in self.invoices:
                return
            self.invoices.append(invoice_id)
            
            invoice_date = self.format_time(invoice_date)
            
            invoice_delay = self.format_time(message_split[2])

            invoice_target = self.format_time(message_split[3])
            

            try: invoice_max_fees = message_split[4]
            except: invoice_max_fees = ""
            
            try: invoice_max_size = message_split[5]
            except: invoice_max_size = ""
            
            labels = [invoice_date, invoice_id, invoice_delay, invoice_target,invoice_max_fees,invoice_max_size]
            invoice_item =[]
            for x in labels:
              invoice_item.append(QStandardItem(x))
            try: invoice_item[self.Columns.DATE].setData(invoice_date)
            except: invoice_item[self.Columns.DATE].setData("")
            
            invoice_item[self.Columns.ID].setData(invoice_id)
            invoice_item[self.Columns.DELAY].setData(invoice_delay)
            invoice_item[self.Columns.TARGET].setData(invoice_target)
            invoice_item[self.Columns.MAX_FEES].setData(invoice_max_fees)
            invoice_item[self.Columns.MAX_SIZE].setData(invoice_max_size)
            
            self.model().appendRow(invoice_item)
            self.invoice_items.append(labels)
        except NotBitpostRowException:
            pass
        except Exception as e:
          print("error:", e)
          
    def split_row(self, message):
        message_split = re.split("https\:\/\/(?:testnet\-)?api\.bitpost\.co/explorer\?query\=(.{11})\,(\d*)\,(\d*),?(\d*)?,?(\d*)?",message)
        if len(message_split) < 2:
            raise NotBitpostRowException
        return message_split
        
    def create_menu(self,position):
        
        org_idx: QModelIndex = self.indexAt(position)
        
        selected=self.invoice_items[org_idx.row()]
        menu=QMenu()
        menu.addAction(_("Open in BitPost explorer"),lambda: webopen(self.get_url(selected[self.Columns.ID])))
        menu.addAction(_("Remove from local"),lambda: self.remove_bitpost(selected,org_idx.row()))
        
        menu.exec_(self.viewport().mapToGlobal(position))

    def remove_row_from_description(self,description,bitpost_id):
        rows=description.split("\n")
        new_message=""
        tobesaved = False
        for row in rows:
            try:
                i=self.split_row(row)
                if not i[1] == bitpost_id:
                    new_message+="\n" + row
                else:
                    tobesaved = True
            except NotBitpostRowException:
                pass
            except Exception as e:
                print(e)

        if new_message[:1] == "\n":
            new_message=new_message[1:]
                
        return new_message,tobesaved
        
    def get_item_key(self,tx_item):
        return tx_item.get('txid') or tx_item['payment_hash']
    
    def remove_bitpost(self,selected,position):
        self.remove_invoice(selected[self.Columns.ID])
        self.parent.invoice_list.update()
        self.remove_history(selected[self.Columns.ID])
        self.parent.history_list.update()
        self.model().removeRow(position)        
        
    def remove_invoice(self, bitpost_id):
        invoices = self.parent.wallet.get_invoices()
        for invoice in invoices:
            invoice.message,tobesaved=self.remove_row_from_description(invoice.message,bitpost_id)
            if tobesaved:
                self.parent.wallet.save_invoice(invoice)
                    
    def remove_history(self,bitpost_id):
        history=self.parent.wallet.get_full_history()
        values=history.values()
        for h in values:
            new_label,tobesaved=self.remove_row_from_description(h['label'],bitpost_id)
            if tobesaved:
                self.parent.wallet.set_label(self.get_item_key(h),new_label)
                
