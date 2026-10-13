#include <Wire.h>
#include <Adafruit_OPT4048.h>
#include <Adafruit_NeoPixel.h>
#include <math.h>
Adafruit_OPT4048 sensor;
Adafruit_NeoPixel pixel(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);
constexpr uint16_t MAX_SAMPLES=2400;
struct Sample {uint32_t us, raw; uint8_t counter, exponent; double x,y,lux;};
Sample samples[MAX_SAMPLES];
String command;
uint8_t address=0x44;
bool readBytes(uint8_t reg,uint8_t *buf,uint8_t n){
 Wire.beginTransmission(address);Wire.write(reg);
 if(Wire.endTransmission(false)!=0)return false;
 if(Wire.requestFrom(address,n)!=n)return false;
 for(uint8_t i=0;i<n;i++)buf[i]=Wire.read();return true;
}
bool decode(uint8_t *b,uint32_t &raw,uint8_t &counter,uint8_t &exponent){
 exponent=b[0]>>4;counter=b[3]>>4;
 uint32_t m=((uint32_t)(b[0]&15)<<16)|((uint32_t)b[1]<<8)|b[2];
 uint8_t c0=0,c1=0,c2=0,c3=0;
 for(int i=0;i<4;i++)c0^=((exponent>>i)^(counter>>i))&1;
 for(int i=0;i<20;i++)c0^=(m>>i)&1;
 c1=((counter>>1)^(counter>>3)^(exponent>>1)^(exponent>>3))&1;
 for(int i=1;i<20;i+=2)c1^=(m>>i)&1;
 c2=((counter>>3)^(exponent>>3))&1;
 for(int i=3;i<20;i+=4)c2^=(m>>i)&1;
 for(int i=3;i<20;i+=8)c3^=(m>>i)&1;
 if(((c3<<3)|(c2<<2)|(c1<<1)|c0)!=(b[3]&15)||exponent>6)return false;
 raw=m<<exponent;return true;
}
void capture(String mode,String id){
 bool fast=mode=="fast";
 sensor.setMode(OPT4048_MODE_POWERDOWN);
 sensor.setConversionTime(fast?OPT4048_CONVERSION_TIME_600US:OPT4048_CONVERSION_TIME_25MS);
 sensor.setMode(OPT4048_MODE_CONTINUOUS);
 delay(fast?30:500);
 uint8_t last=255;uint16_t n=0;uint32_t errors=0,duplicates=0,skips=0;
 uint32_t start=micros();
 while(n<MAX_SAMPLES && micros()-start<(fast?5000000UL:10000000UL)){
  uint8_t buf[16];Sample s={};uint32_t tick=micros();
  if(!readBytes(fast?0x02:0x00,buf,fast?4:16)){errors++;continue;}
  if(fast){if(!decode(buf,s.raw,s.counter,s.exponent)){errors++;continue;}}
  else {
   uint32_t raw[4];uint8_t counters[4],exp[4];bool valid=true;
   for(int ch=0;ch<4;ch++)valid &= decode(buf+ch*4,raw[ch],counters[ch],exp[ch]);
   if(!valid || counters[0]!=counters[1] || counters[1]!=counters[2] || counters[2]!=counters[3]){errors++;delayMicroseconds(300);continue;}
   s.raw=raw[1];s.counter=counters[1];s.exponent=exp[1];
   double X=raw[0]*2.34892992e-4+raw[1]*4.07467441e-5+raw[2]*9.28619404e-5;
   double Y=raw[0]*-1.89652390e-5+raw[1]*1.98958202e-4+raw[2]*-1.69739553e-5;
   double Z=raw[0]*1.20811684e-5+raw[1]*-1.58848115e-5+raw[2]*6.74021520e-4;
   if(X+Y+Z>0){s.x=X/(X+Y+Z);s.y=Y/(X+Y+Z);}else{s.x=NAN;s.y=NAN;}
  }
  if(s.counter==last){duplicates++;delayMicroseconds(fast?100:500);continue;}
  if(last!=255)skips+=(s.counter-last+16)%16-1;
  last=s.counter;s.us=tick-start;s.lux=s.raw*0.00215;samples[n++]=s;
  if(!fast && n==30)break;
 }
 uint32_t duration=micros()-start;
 Serial.printf("{\"type\":\"begin\",\"firmware\":\"usb-fast-v1\",\"request_id\":\"%s\",\"mode\":\"%s\",\"conversion_us_per_channel\":%u,\"samples\":%u,\"duration_us\":%lu,\"crc_or_read_errors\":%lu,\"duplicate_polls\":%lu,\"counter_skips\":%lu}\n",id.c_str(),mode.c_str(),fast?600:25000,n,(unsigned long)duration,(unsigned long)errors,(unsigned long)duplicates,(unsigned long)skips);
 double sum=0,lo=1e30,hi=0,sx=0,sy=0,sc=0;int colors=0;
 for(uint16_t i=0;i<n;i++){
  Sample &s=samples[i];sum+=s.lux;lo=fmin(lo,s.lux);hi=fmax(hi,s.lux);
  double cct=NAN;
  if(!fast && isfinite(s.x) && isfinite(s.y)) {cct=sensor.calculateColorTemperature(s.x,s.y);sx+=s.x;sy+=s.y;sc+=cct;colors++;}
  Serial.printf("S,%lu,%lu,%u,%u,%.8f,",(unsigned long)s.us,(unsigned long)s.raw,s.counter,s.exponent,s.lux);
  if(!fast && isfinite(s.x))Serial.printf("%.8f,%.8f,%.4f\n",s.x,s.y,cct);else Serial.println(",,");
 }
 Serial.printf("{\"type\":\"end\",\"request_id\":\"%s\",\"samples\":%u,\"lux\":%.8f,\"lux_min\":%.8f,\"lux_max\":%.8f,\"foot_candles\":%.8f",id.c_str(),n,n?sum/n:0,n?lo:0,hi,n?sum/n/10.76391:0);
 if(colors)Serial.printf(",\"x\":%.8f,\"y\":%.8f,\"cct\":%.4f",sx/colors,sy/colors,sc/colors);
 Serial.println("}");
}
void setup(){
 Serial.begin(115200);delay(500);
 pinMode(NEOPIXEL_I2C_POWER,OUTPUT);digitalWrite(NEOPIXEL_I2C_POWER,HIGH);
 pixel.begin();pixel.clear();pixel.show();pinMode(LED_BUILTIN,OUTPUT);digitalWrite(LED_BUILTIN,LOW);
 Wire.begin();Wire.setClock(400000);
 if(!sensor.begin(address)){Serial.println("{\"error\":\"sensor_missing\"}");return;}
 sensor.setRange(OPT4048_RANGE_AUTO);sensor.setMode(OPT4048_MODE_POWERDOWN);
 Serial.println("{\"ready\":true,\"firmware\":\"usb-fast-v1\"}");
}
void loop(){
 while(Serial.available()){
  char ch=Serial.read();if(ch=='\n'){
   int space=command.indexOf(' ');String mode=command.substring(0,space),id=command.substring(space+1);
   if((mode=="fast"||mode=="color") && id.length() && id.length()<80)capture(mode,id);
   else Serial.println("{\"error\":\"invalid_command\"}");command="";
  }else if(command.length()<100)command+=ch;
 }
 delay(1);
}
