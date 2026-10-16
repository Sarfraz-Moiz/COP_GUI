from __future__ import annotations
import json, socket, sys, time
from pathlib import Path
import yaml
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication,QComboBox,QFormLayout,QGridLayout,QGroupBox,QHBoxLayout,QLabel,QLineEdit,QMainWindow,QPlainTextEdit,QPushButton,QSpinBox,QDoubleSpinBox,QCheckBox,QVBoxLayout,QWidget)

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from app.protocol import TelemetryPacket,ALARM_CATEGORIES

class SimulatorGUI(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle("CCM Telemetry Simulator");self.resize(980,900);self.setStyleSheet("QMainWindow,QWidget{background:#0b1118;color:#dbe7f3;font-family:'Segoe UI';} QGroupBox{border:1px solid #2b3a4c;border-radius:7px;margin-top:10px;padding:10px;font-weight:700;} QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 4px;} QLineEdit,QComboBox,QDoubleSpinBox,QSpinBox,QPlainTextEdit{background:#0d151f;border:1px solid #304052;border-radius:5px;padding:6px;color:#e5edf5;} QPushButton{background:#1a2634;border:1px solid #344356;border-radius:5px;padding:8px 12px;} QPushButton#send{background:#1478e8;color:white;font-weight:700;} QLabel#status{font-weight:700;color:#35d07f;}" )
        self.seq=0;self.timer=QTimer(self);self.timer.timeout.connect(self.send_packet)
        self.cfg=yaml.safe_load((ROOT/'config'/'scenario.yaml').read_text(encoding='utf-8'))
        root=QWidget();self.setCentralWidget(root);layout=QVBoxLayout(root)
        grid=QGridLayout();layout.addLayout(grid)
        self.camera_id=QComboBox();self.camera_id.addItems([c['id'] for c in self.cfg['cameras']]);self.camera_id.currentTextChanged.connect(self.load_camera)
        self.host=QLineEdit('127.0.0.1');self.port=QSpinBox();self.port.setRange(1,65535);self.port.setValue(5010);self.rate=QDoubleSpinBox();self.rate.setRange(0.1,50);self.rate.setValue(10);self.rate.setSuffix(' Hz')
        net=QGroupBox('Transport');nf=QFormLayout(net);nf.addRow('Camera ID',self.camera_id);nf.addRow('Destination',self.host);nf.addRow('UDP Port',self.port);nf.addRow('Rate',self.rate);grid.addWidget(net,0,0)

        cam=QGroupBox('Camera / GPS');cf=QFormLayout(cam)
        self.lat=self.ds(28.315);self.lon=self.ds(67.445);self.alt=self.ds(95);self.heading=self.ds(35);self.azimuth=self.ds(35);self.elevation=self.ds(-20);self.fov=self.ds(55);self.gps_fix=QSpinBox();self.gps_fix.setRange(0,6);self.gps_fix.setValue(3);self.hdop=self.ds(0.8);cf.addRow('Latitude °',self.lat);cf.addRow('Longitude °',self.lon);cf.addRow('Altitude m',self.alt);cf.addRow('GPS fix',self.gps_fix);cf.addRow('HDOP',self.hdop);cf.addRow('Compass heading °',self.heading);cf.addRow('Camera azimuth °',self.azimuth);cf.addRow('Camera elevation °',self.elevation);cf.addRow('FOV °',self.fov);grid.addWidget(cam,0,1)

        target=QGroupBox('Target / Classification');tf=QFormLayout(target)
        self.target_enabled=QCheckBox();self.target_enabled.setChecked(True);self.tid=QLineEdit('TGT-01');self.tlat=self.ds(28.300);self.tlon=self.ds(67.455);self.talt=self.ds(20);self.category=QComboBox();self.category.addItems(ALARM_CATEGORIES);self.conf=self.ds(0.0);self.conf.setRange(0,1);self.conf.setSingleStep(.01);self.message=QLineEdit('')
        tf.addRow('Target enabled',self.target_enabled);tf.addRow('Target ID',self.tid);tf.addRow('Target latitude °',self.tlat);tf.addRow('Target longitude °',self.tlon);tf.addRow('Target altitude m',self.talt);tf.addRow('Category',self.category);tf.addRow('Confidence',self.conf);tf.addRow('Alarm message',self.message);grid.addWidget(target,1,0)

        sysg=QGroupBox('Rangefinder / System / Video');sf=QFormLayout(sysg)
        self.range_m=self.ds(0);self.range_valid=QCheckBox();self.armed=QCheckBox();self.alarm_active=QCheckBox();self.alarm_active.setChecked(False);self.battery=self.ds(24.1);self.link=QDoubleSpinBox();self.link.setRange(0,100);self.link.setValue(100);self.video_source=QComboBox();self.video_source.addItems(['FILE','RTSP','USB','BUILTIN']);self.video_name=QLineEdit('videos/CAM-01.mp4')
        sf.addRow('Range m',self.range_m);sf.addRow('Range valid',self.range_valid);sf.addRow('Alarm active',self.alarm_active);sf.addRow('Armed',self.armed);sf.addRow('Battery V',self.battery);sf.addRow('Link quality %',self.link);sf.addRow('Video source',self.video_source);sf.addRow('Video name/URL',self.video_name);grid.addWidget(sysg,1,1)

        buttons=QHBoxLayout();load=QPushButton('Load Selected Camera');load.clicked.connect(lambda:self.load_camera(self.camera_id.currentText()));buttons.addWidget(load);self.send=QPushButton('Send One Packet');self.send.setObjectName('send');self.send.clicked.connect(self.send_packet);buttons.addWidget(self.send);self.start=QPushButton('Start Continuous');self.start.clicked.connect(self.toggle);buttons.addWidget(self.start);layout.addLayout(buttons)
        self.status=QLabel('Ready');self.status.setObjectName('status');layout.addWidget(self.status)
        self.preview=QPlainTextEdit();self.preview.setReadOnly(True);layout.addWidget(self.preview,1)
        self.load_camera(self.camera_id.currentText())

    def ds(self,v):
        x=QDoubleSpinBox();x.setRange(-1000000,1000000);x.setDecimals(7);x.setSingleStep(.0001);x.setValue(v);return x
    def load_camera(self,cid):
        c=next((x for x in self.cfg['cameras'] if x['id']==cid),None)
        if not c:return
        self.lat.setValue(c['lat']);self.lon.setValue(c['lon']);self.alt.setValue(c['altitude_m']);self.heading.setValue(c['heading_deg']);self.fov.setValue(c['fov_deg']);self.tid.setText(c.get('target_id','TGT-01'));self.video_name.setText(f"videos/{cid}.mp4")
        t=next((x for x in self.cfg['targets'] if x['id']==self.tid.text()),None)
        if t:self.tlat.setValue(t['lat']);self.tlon.setValue(t['lon']);self.talt.setValue(t['altitude_m'])
        cat=c.get('target_category','NONE');self.category.setCurrentText(cat);self.conf.setValue(float(c.get('target_confidence',0.0)));self.alarm_active.setChecked(cat=='SUSPICIOUS');self.message.setText(c.get('alarm_message',''))
    def packet(self):
        self.seq+=1;cid=self.camera_id.currentText();cat=self.category.currentText();conf=self.conf.value()
        target=None
        if self.target_enabled.isChecked():target={'id':self.tid.text().strip() or 'TGT-01','latitude_deg':self.tlat.value(),'longitude_deg':self.tlon.value(),'altitude_m':self.talt.value(),'category':cat,'confidence':conf}
        alarm={'active':self.alarm_active.isChecked() or cat=='SUSPICIOUS','category':cat,'confidence':conf,'message':self.message.text().strip()}
        return TelemetryPacket(camera_id=cid,sequence=self.seq,timestamp_unix_ms=int(time.time()*1000),gps={'latitude_deg':self.lat.value(),'longitude_deg':self.lon.value(),'altitude_m':self.alt.value(),'fix':self.gps_fix.value(),'hdop':self.hdop.value()},compass={'heading_deg':self.heading.value(),'source':'SIMULATOR_GUI'},camera={'azimuth_deg':self.azimuth.value(),'elevation_deg':self.elevation.value(),'fov_deg':self.fov.value()},target=target,rangefinder={'distance_m':self.range_m.value() if self.range_valid.isChecked() else None,'valid':self.range_valid.isChecked(),'type':'SIMULATED'},system={'armed':self.armed.isChecked(),'battery_v':self.battery.value(),'link_quality_pct':self.link.value()},video={'source':self.video_source.currentText(),'name':self.video_name.text()},alarm=alarm)
    def send_packet(self):
        try:
            p=self.packet();TelemetryPacket.validate(p.to_dict());sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.sendto(p.encode(),(self.host.text().strip(),self.port.value()));sock.close();d=p.to_dict();self.preview.setPlainText(json.dumps(d,indent=2));self.status.setText(f"Sent {d['camera_id']} seq={d['sequence']} category={d['alarm']['category']} -> {self.host.text().strip()}:{self.port.value()}")
        except Exception as e:self.status.setText(f"ERROR: {e}")
    def toggle(self):
        if self.timer.isActive():self.timer.stop();self.start.setText('Start Continuous');self.status.setText('Continuous injection stopped')
        else:self.timer.start(max(20,int(1000/self.rate.value())));self.start.setText('Stop Continuous');self.send_packet()

if __name__=='__main__':
    app=QApplication(sys.argv);app.setStyle('Fusion');w=SimulatorGUI();w.show();sys.exit(app.exec())
