import pathlib,csv,sys
from reportlab.graphics.shapes import Drawing,String,Line,Rect
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.lib.colors import HexColor
from reportlab.graphics import renderSVG
R=pathlib.Path(sys.argv[1]);rows=list(csv.DictReader((R/'curve.csv').open()))
d=Drawing(1100,830);d.add(Rect(0,0,1100,830,fillColor=HexColor('#FFFFFF'),strokeColor=None));blue=HexColor('#2377AD');orange=HexColor('#D06726');gray=HexColor('#596574')
d.add(String(45,795,'Toilet SD — dimming, color and measured variation',fontName='Helvetica-Bold',fontSize=22,fillColor=HexColor('#172330')))
d.add(String(45,770,'Fixed sensor directly under fixture, about 3 ft above floor; additional light blocking',fontSize=12,fillColor=gray))
def plot(x,y,title,field,xmax=100,ymin=None,ymax=None,fast=False):
 d.add(String(x,y+285,title,fontName='Helvetica-Bold',fontSize=14,fillColor=gray))
 p=LinePlot();p.x=x+42;p.y=y+30;p.width=425;p.height=235
 data=[]
 for direction in ('ascending','descending'):
  points=[]
  for r in rows:
   pct=float(r['command_pct']);v=r.get(direction+'_'+field)
   if pct>xmax or not v:continue
   if fast and r.get(direction+'_fast_low_signal_quantization_screen')=='True':continue
   points.append((pct,float(v)))
  data.append(points)
 p.data=data;p.joinedLines=1
 p.xValueAxis.valueMin=0;p.xValueAxis.valueMax=xmax;p.xValueAxis.valueStep=20 if xmax==100 else 5
 if ymin is not None:p.yValueAxis.valueMin=ymin
 if ymax is not None:p.yValueAxis.valueMax=ymax
 p.xValueAxis.labels.fontSize=10;p.yValueAxis.labels.fontSize=10
 for i,color in enumerate((blue,orange)):p.lines[i].strokeColor=color;p.lines[i].strokeWidth=1.7
 d.add(p);d.add(String(x+165,y,'Commanded dimmer percent',fontSize=10,fillColor=gray))
plot(35,420,'Color estimate (K)','cct_planck_K_window_means_mean',ymin=1800,ymax=3300)
plot(580,420,'Illuminance at sensor (lux)','lux_window_means_mean',ymin=0)
plot(35,80,'Low-level illuminance (lux)','lux_window_means_mean',xmax=20,ymin=0)
plot(580,80,'Fast-mode min/max modulation (%)','fast_observed_modulation_pct',ymin=0,ymax=100,fast=True)
d.add(Line(45,42,75,42,strokeColor=blue,strokeWidth=2));d.add(String(82,38,'Ascending',fontSize=11,fillColor=gray));d.add(Line(190,42,220,42,strokeColor=orange,strokeWidth=2));d.add(String(228,38,'Descending',fontSize=11,fillColor=gray))
d.add(String(45,18,'Ascent: every 1%. Descent: every 1% to 20%, every 5% above. Fast plot omits low-signal captures.',fontSize=10,fillColor=gray))
d.add(String(45,4,'Variation includes noise; aliasing and phase coverage can limit measured modulation. Sensor CCT estimates are uncalibrated.',fontSize=9,fillColor=gray))
renderSVG.drawToFile(d,str(R/'curve-and-variation.svg'))
