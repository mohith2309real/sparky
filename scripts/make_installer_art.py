"""Render installer artwork with the same native mascot, fonts and tokens."""
import os
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor,QFont,QImage,QPainter,QPen
from PyQt6.QtWidgets import QApplication
from sparky.ide.design import DAYLIGHT
from sparky.ide.theme import load_fonts
from make_logo import draw_logo
app=QApplication([]); load_fonts(ROOT/'assets')
def label(p,x,y,w,h,text,size,heading=False):
    f=QFont('Bricolage Grotesque' if heading else 'Figtree');f.setPixelSize(size)
    if heading:f.setWeight(QFont.Weight.Bold)
    p.setFont(f);p.setPen(QColor(DAYLIGHT['text']))
    p.drawText(QRectF(x,y,w,h),Qt.AlignmentFlag.AlignCenter,text)
image=QImage(640,420,QImage.Format.Format_RGB32);image.fill(QColor(DAYLIGHT['bg']))
p=QPainter(image);p.setRenderHint(QPainter.RenderHint.Antialiasing)
label(p,30,24,580,55,'A little spark. A new beginning.',30,True)
label(p,30,78,580,40,'Drag Sparky to Applications to start creating.',17)
p.setPen(QPen(QColor(DAYLIGHT['accent']),3));p.drawLine(275,232,355,232);p.drawLine(343,221,355,232);p.drawLine(343,243,355,232)
label(p,30,350,580,35,'Make drawings, stories, games and music.',15)
p.end();image.save(str(ROOT/'assets/dmg-background.png'))
image=QImage(164,314,QImage.Format.Format_RGB32);image.fill(QColor(DAYLIGHT['bg']))
p=QPainter(image);p.drawImage(QRectF(18,34,128,128),draw_logo(256));label(p,5,170,154,46,'Sparky',30,True);label(p,10,220,144,55,'Little ideas.\nReal code.',17);p.end();image.save(str(ROOT/'assets/installer-sidebar.bmp'))
print('Rendered Mac and Windows installer artwork.')
