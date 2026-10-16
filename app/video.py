
from __future__ import annotations
from pathlib import Path
import cv2, numpy as np
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtGui import QImage

class VideoSource(QObject):
    """Unified video adapter: local file, RTSP, USB camera, or built-in camera."""
    frame_ready = Signal(object)
    status_changed = Signal(str)
    error = Signal(str)

    def __init__(self, videos_dir: str|Path, camera_id="CAM-01", fps=25):
        super().__init__()
        self.videos_dir=Path(videos_dir)
        self.camera_id=camera_id
        self.fps=fps
        self.source_type="FILE"
        self.source_value=""
        self.capture=None
        self.timer=QTimer(self)
        self.timer.setInterval(max(1,int(1000/fps)))
        self.timer.timeout.connect(self._read)
        self.timer.start()

    def configure(self, source_type, value=""):
        self.source_type=source_type.upper()
        self.source_value=str(value)
        self._open()

    def set_camera(self,camera_id):
        self.camera_id=camera_id
        if self.source_type=="FILE" or not self.source_value:
            self.source_type="FILE"
            self.source_value=str(self.videos_dir/f"{camera_id}.mp4")
        self._open()

    def _open(self):
        if self.capture is not None:
            self.capture.release()
            self.capture=None
        try:
            if self.source_type=="FILE":
                path=Path(self.source_value or (self.videos_dir/f"{self.camera_id}.mp4"))
                self.capture=cv2.VideoCapture(str(path))
            elif self.source_type=="RTSP":
                # OpenCV FFmpeg backend is used when available. Real deployments can
                # replace this adapter with a GStreamer pipeline without changing the UI.
                self.capture=cv2.VideoCapture(self.source_value, cv2.CAP_FFMPEG)
                self.capture.set(cv2.CAP_PROP_BUFFERSIZE,1)
            elif self.source_type in ("USB","BUILTIN"):
                idx=int(self.source_value or 0)
                self.capture=cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                self.capture.set(cv2.CAP_PROP_BUFFERSIZE,1)
            else:
                self.capture=None
            if self.capture is not None and self.capture.isOpened():
                self.status_changed.emit("VIDEO ONLINE")
            else:
                if self.capture is not None: self.capture.release()
                self.capture=None
                self.status_changed.emit("VIDEO OFFLINE")
        except Exception as e:
            self.capture=None
            self.status_changed.emit("VIDEO ERROR")
            self.error.emit(str(e))

    def _read(self):
        if self.capture is None:
            self.frame_ready.emit(self._fallback("NO VIDEO SOURCE"))
            return
        ok,frame=self.capture.read()
        if not ok:
            if self.source_type=="FILE":
                self.capture.set(cv2.CAP_PROP_POS_FRAMES,0)
                ok,frame=self.capture.read()
            if not ok:
                self.frame_ready.emit(self._fallback("STREAM LOST"))
                return
        frame=cv2.resize(frame,(960,540),interpolation=cv2.INTER_AREA)
        cv2.putText(frame,f"{self.camera_id} | {self.source_type}",(18,32),cv2.FONT_HERSHEY_SIMPLEX,.65,(230,240,250),2)
        rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB); h,w=rgb.shape[:2]
        self.frame_ready.emit(QImage(rgb.data,w,h,rgb.strides[0],QImage.Format_RGB888).copy())

    def _fallback(self,msg):
        img=np.zeros((540,960,3),np.uint8); img[:]=(10,17,25)
        cv2.putText(img,self.camera_id,(30,60),cv2.FONT_HERSHEY_SIMPLEX,1.1,(90,180,255),2)
        cv2.putText(img,msg,(30,110),cv2.FONT_HERSHEY_SIMPLEX,.8,(230,170,80),2)
        rgb=cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
        return QImage(rgb.data,960,540,rgb.strides[0],QImage.Format_RGB888).copy()

    def close(self):
        self.timer.stop()
        if self.capture is not None: self.capture.release()
