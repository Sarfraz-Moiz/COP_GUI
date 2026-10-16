
from __future__ import annotations
import json, socket
from PySide6.QtCore import QObject, Signal, QThread

class TelemetryReceiver(QObject):
    packet_received=Signal(object)
    status_changed=Signal(str)
    def __init__(self,host="0.0.0.0",port=5010,parent=None):
        super().__init__(parent); self.host=host; self.port=port; self.sock=None; self.running=False
        self.thread=QThread(); self.moveToThread(self.thread); self.thread.started.connect(self._run)

    def start(self):
        if self.running:return
        self.running=True; self.thread.start()

    def _run(self):
        try:
            self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            self.sock.bind((self.host,self.port)); self.sock.settimeout(0.5)
            self.status_changed.emit(f"TELEMETRY UDP :{self.port}")
        except Exception as e:
            self.status_changed.emit(f"TELEMETRY ERROR: {e}"); return
        while self.running:
            try:
                data,_=self.sock.recvfrom(65535)
                packet=json.loads(data.decode("utf-8"))
                self.packet_received.emit(packet)
            except socket.timeout: continue
            except Exception as e: self.status_changed.emit(f"PACKET ERROR: {e}")
        try:self.sock.close()
        except:pass

    def stop(self):
        self.running=False
        if self.sock:
            try:self.sock.close()
            except:pass
        if self.thread.isRunning(): self.thread.quit(); self.thread.wait(1000)
