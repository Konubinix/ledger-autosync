import json
import sys
import time
import subprocess
from subprocess import Popen, PIPE
from threading import Thread
from Queue import Queue, Empty
from ledgerautosync.formatter import clean_ofx_id
import logging

def clean_payee(payee):
    payee = payee.replace('/', '\\/')
    payee = payee.replace('%', '')
    return payee

def enqueue_output(out, queue):
    item = ""
    buff = ""
    while (buff != None):
        buff = out.read(1)
        if (buff != None):
            item += buff
        if item.endswith("] "): # prompt
            queue.put(item[0:-2])
            item = ""
    out.close()

def mk_ledger(ledger_file=None):
    if subprocess.call(["which", "ledger"]) == 0:
        return Ledger(ledger_file)
    elif subprocess.call(["which", "hledger"]) == 0:
        return HLedger(ledger_file)
    else:
        return None

class Ledger(object):
    def __init__(self, ledger_file=None):
        on_posix = 'posix' in sys.builtin_module_names
        args = ["ledger"]
        if ledger_file is not None:
            args += ["-f", ledger_file]
        self.p = Popen(args, bufsize=1, stdin=PIPE, stdout=PIPE,
                       close_fds=on_posix)
        self.q = Queue()
        self.t = Thread(target=enqueue_output, args=(self.p.stdout, self.q))
        self.t.daemon = True # thread dies with the program
        self.t.start()
        # read output until prompt
        self.q.get()

    def run(self, cmd):
        self.p.stdin.write("json %s\n"%(cmd))
        return json.loads(self.q.get())['ledger']

    def get_transaction(self, q):
        d = self.run("reg %s"%(q))
        if d['transactions'] == '':
            return None
        else:
            return d['transactions']

    def check_transaction_by_ofxid(self, ofxid):
        return (self.get_transaction("meta ofxid='%s'"%(clean_ofx_id(ofxid))) != None)
    
    def get_account_by_payee(self, payee):
        txn = self.get_transaction("payee '%s'"%(clean_payee(payee)))
        if txn is None: return None
        else: return txn['postings']['posting']['account']['name']

class HLedger(object):
    def __init__(self, ledger_file=None):
        self.args = ["hledger"]
        if ledger_file is not None:
            args += ["-f", ledger_file]
        
    def check_txn_by_ofxid(self, ofxid):
        return (subprocess.check_output(args + ["reg", "tag:ofxid=%s"%(ofxid)]) != '')
