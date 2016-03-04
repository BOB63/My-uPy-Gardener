#*****************************************************************
# irrigatoreBT V07.py 
#*****************************************************************

#The MIT License (MIT)
#
#Copyright (c) 2016 Roberto Portesani
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in all
#copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.
 

#This sw use the upower.py module Copyright (c) Peter Hinch.
#https://github.com/peterhinch/micropython-micropower
#refer to upower.py documentation for more details.






# Programma di gestione per irrigatore a 2 zone con possibilita' di uso sonde umidita' terreno.

# Via xBEE viene inviata una struttura dati di typo dictionary
# con i dati di settaggio impostati tramite applicazione host scritta in processing2.
# I dati di settaggio sono memorizzati nella bkram del microcontroller.

# PIN utilizzati :
# x1 : triggher pin per uscire dallo stato di low power
# x2 : pin_sonda_b , input lettura adc
# x3 : pin_sonda_b , input lettura adc 
# x4 : valvola1   , output
# x5 : valvola2   , output


      
# just for memo.....
# L'RTC registra i dati all'interno di un vettore seguendo questo formato:
#
#   [0]year 
#   [1]month
#   [2]day
#   [3]weekday 1-7 for Monday through Sunday.
#   [4]hours
#   [5]minutes
#   [6]seconds
#   [7]subseconds
#
#   esempi di utilizzo:
#   rtc = pyb.RTC()
#   rtc.datetime((2015, 8, 9, 1, 13, 0, 0, 0))
#   print(rtc.datetime()) 
#
#


import stm
import sys
import pyb
import uctypes
import upower
import micropython

import pickle
from pyb import Pin
from pyb import RTC
from pyb import ExtInt
from pyb import ADC
from pyb import UART

micropython.alloc_emergency_exception_buf(100)

rtc = pyb.RTC()

print(rtc.datetime())

sonda1 = Pin('X11', Pin.IN)
sonda2 = Pin('X12', Pin.IN)
pin_FF_reset=Pin('X2', Pin.OUT_PP)
pin_relay_a=Pin('X3', Pin.OUT_PP)
pin_relay_b=Pin('X4', Pin.OUT_PP)

adc1 = ADC(Pin('X11'))
adc2 = ADC(Pin('X12'))

verde= pyb.LED(2)
blue=pyb.LED(4)
yellow=pyb.LED(3)
switch = pyb.Switch()
 
# see upower documentation.

bkram = upower.BkpRAM()
ba = bkram.get_bytearray()

reason=''
pkl={}

active_day_a=False
active_day_b=False
enable_sonda_a=False
enable_sonda_b=False
sonda_a=0
sonda_b=0

#definisco due allarmi  - alarm definition.
# see upower documentation.

allarm_a = upower.alarm('a')
allarm_b = upower.alarm('b')

#leggo sonda a - read sonda a
def leggi_sonda_a():
    sonda_s=0
    for x in range(1,20):
        sonda_r=adc1.read() # read value, 0-4095
        sonda_s=sonda_s+sonda_r
    sonda_a=sonda_s/20
    return sonda_a
#leggo sonda b - read sonda b
def leggi_sonda_b():
    sondb_s=0
    for x in range(1,20):
        sondb_r=adc2.read() # read value, 0-4095
        sondb_s=sondb_s+sondb_r
    sonda_b=sondb_s/20
    return sonda_b

def set_rtc():
    uart.write("Setting RTC : "+pkl['yyyy_h']+"/"+pkl['mm_h']+"/"+pkl['gg_h']+"-"+pkl['wd_h']+"-"+pkl['hr_h']+":"+pkl['min_h']+ '\n')
    rtc.datetime((int(pkl['yyyy_h']),int(pkl['mm_h']),int(pkl['gg_h']),int(pkl['wd_h']),int(pkl['hr_h']),int(pkl['min_h']),0,0))
    
# invio setting presente in memoria to host.
# send settings recovered from EEPROM to host 
def send_setting():
    uart.write('Invio dati da uPython to Host : '+'\r\n')
    uart.write(str(pkl)+'\n') # invia dati json a host   
    
def set_allarms():
    allarm_a.timeset(hour=int(pkl['hrs_a']),minute=int(pkl['mins_a']),second=0) 
    allarm_b.timeset(hour=int(pkl['hrs_b']),minute=int(pkl['mins_b']),second=3) 
    uart.write('Settaggio Allarmi :Done ' + '\n')


# carica setting salvato in MCU EEPROM.
# restore data saved in MCU EEPROM.
def restore_data(): 
                 
    global setting_a
    global setting_b
    global active_day_a
    global active_day_b
    global enable_sonda_a
    global enable_sonda_b
    global pkl
    print("Restore data from bkmem :")
    uart.write('Restore data from bkmem :'+'\n')
    try:       
        pkl = pickle.loads(bytes(ba[4:4+bkram[0]]).decode("utf-8"))


        # conversione in binario - binary conversion.
        setting_a='{0:08b}'.format(int(pkl['setting_a'])) 

        setting_b='{0:08b}'.format(int(pkl['setting_b'])) 

        # recupero RTC setting - read data from MCU RTC.
        ttx=rtc.datetime() 
        
        pkl['yy_rtc']=str(ttx[0])
        pkl['mm_rtc']=str(ttx[1])
        pkl['dd_rtc']=str(ttx[2])
        pkl['wkd_rtc']=str(ttx[3])
        pkl['hr_rtc']=str(ttx[4])
        pkl['min_rtc']=str(ttx[5])

        # week day da RTC  
        week_day=ttx[3]

        # decodifico "setting_a"  - "setting_a" decoding. 
        if setting_a[0]=='1' : 
           enable_sonda_a=True
        else:
           enable_sonda_a=False
        
        if   setting_a[1]=='1' and week_day==1: 
             active_day_a=True 
        elif setting_a[2]=='1' and week_day==2: 
             active_day_a=True  
        elif setting_a[3]=='1' and week_day==3: 
             active_day_a=True  
        elif setting_a[4]=='1' and week_day==4: 
             active_day_a=True  
        elif setting_a[5]=='1' and week_day==5: 
             active_day_a=True  
        elif setting_a[6]=='1' and week_day==6: 
             active_day_a=True  
        elif setting_a[7]=='1' and week_day==7: 
             active_day_a=True  
        else:
             active_day_a=False
        
        # decodifico "setting_b"  - "setting_b" decoding. 
        if setting_b[0]=='1' : 
           enable_sonda_b=True 
        else:
           enable_sonda_b=False
          
        if   setting_b[1]=='1' and week_day==1: 
             active_day_b=True 
        elif setting_b[2]=='1' and week_day==2: 
             active_day_b=True 
        elif setting_b[3]=='1' and week_day==3: 
             active_day_b=True 
        elif setting_b[4]=='1' and week_day==4: 
             active_day_b=True 
        elif setting_b[5]=='1' and week_day==5: 
             active_day_b=True 
        elif setting_b[6]=='1' and week_day==6: 
             active_day_b=True 
        elif setting_b[7]=='1' and week_day==7: 
             active_day_b=True 
        else:
             active_day_b=False

        
    
    except Exception as er:
       # se non vi sono dati salvati in memoria forzo il setting dei dati.
       # if MCU EEPROM is empty force setting.   
       uart.write("Errore durante restore dati da EEPROM : "+repr(er)+'\n')
       print("Non c'e dictionary in EEPROM")
       reset_dict={'header':'$$$',	'setting_a':'0',
                   'hrs_a':'0','mins_a':'0','hre_a':'0','mine_a':'0','in_sonda_a':'0',
                   'relay_a':'0','tr_sonda_a':'0','setting_b':'0',	'hrs_b':'0','mins_b':'0',
                   'hre_b':'0','mine_b':'0','in_sonda_b':'0','relay_b':'0','tr_sonda_b':'0','yyyy_h':'0',
                   'mm_h':'0','gg_h':'0','wd_h':'0','hr_h':'0','min_h':'0','yy_rtc':'0','mm_rtc':'0',
                   'dd_rtc':'0','wkd_rtc':'0','hr_rtc':'0','min_rtc':'0','footer':'###'}
       z = pickle.dumps(reset_dict).encode('utf8')
       bkram[0] = len(z)
       ba[4: 4+len(z)] = z
       restore_data()

    return pkl

def gestione_power_on():

    print("Power On")
    uart.write("Power On.")

 
#imposto setting seriale - set MCU serial port1  
uart = UART(1, 9600)                         
uart.init(9600, bits=8, parity=None, stop=1)
 
test=0

reason=upower.why()   # motivo dell'uscita da low power mode.
                      # see upower.py module documentation.

uart.write(str(reason) +'\n')

#reason='ALARM_B'     # solo per debug
try:
    if reason=='X1':
       verde.on()
       pyb.delay(3)
       verde.off()
       uart.write('ready'+'\n') # uscito da standby - standby exit.
       while test==0:
          inBuffer_rx=""
          if uart.any(): 
             inBuffer_rx=uart.readline()
             print(inBuffer_rx)
             inBuffer_chr=""

             if inBuffer_rx!='':
                inBuffer_chr=inBuffer_rx.decode()
             if inBuffer_chr=='connecting':
                print('connecting')
                uart.write('sono connesso!'+'\n') # uscito da standby - standby exit.
                restore_data()
                sa=leggi_sonda_a()
                pkl['in_sonda_a']=int(sa)
                sb=leggi_sonda_b()
                pkl['in_sonda_b']=int(sb)
                uart.write(str(pkl)+'\n') # invia dati a host - send data to host.  

             else:
                # host invia dati a pyBoard - host send deta to pyBoard.
                uart.write('Invio dato a pyBoard :'+'\n')
                uart.write(inBuffer_rx+'\n')
                bkram[0] = len(inBuffer_rx)
                ba[4: 4+len(inBuffer_rx)] = inBuffer_rx
              
                restore_data()
                uart.write('Settaggio RTC'+'\n')
               
                set_rtc() # sincronizzo RTC con orario host -sync MCU RTC with host time.

                set_allarms() # imposto allarmi secondo dati ricevuti da host -set alarms based on host input.
                reason=''
                upower.wkup.enable()
                pin_FF_reset.low()
                pyb.standby()  
     
    if reason=='ALARM_A':
       uart.write('Evento Alarm A'+'\n') 
       verde.on()
       pyb.delay(30)
       verde.off()
       print('Gestione Alarm A')
       restore_data()
       uart.write('Relay A :'+pkl['relay_a']+ '\n')
            
       if enable_sonda_a==True:
          uart.write('Soglia Lettura A :'+ '\n') 
          lettura_sonda_a=leggi_sonda_a()
          uart.write('Lettura Sonda  A :'+str(lettura_sonda_a)+ '\n')
          uart.write('Soglia Lettura A :'+pkl['tr_sonda_a']+ '\n')

       if active_day_a==True and pkl['relay_a']=='0' and enable_sonda_a==True and lettura_sonda_a<int(pkl['tr_sonda_a']):
                  uart.write("Alarm_A --> active_day_a=True,relay_a=0,enable_sonda_a=True,lettura sonda_a <soglia_a "+"\n")
                  

                  # imposto allarme A con ora spegnimento e setto flag relay_a=1.
                  # set alarm A at switch off time and set relay_a=1 
                  allarm_a.timeset(hour=int(pkl['hre_a']),minute=int(pkl['mine_a']),second=0)
                  uart.write("Set Stop Time A at : "+pkl['hre_a']+":"+pkl['mine_a']+"\n")

                  # aggiorno dati salvati in memoria per riflettere nuovo valore relay_a
                  # update data to reflect relay_a status. 
                  pkl['relay_a']="1"
                  z = pickle.dumps(pkl).encode('utf8')
                  bkram[0] = len(z)
                  ba[4: 4+len(z)] = z

                  # genero impulso per cambio stato FF.
                  # pulse to change state on FF
                  pin_relay_a.high()
                  pyb.delay(10)
                  pin_relay_a.low()
                  uart.write("Attiva Relay A - con sonda - "+"\n")
                  uart.write("relay_a_on"+"\n")
                  uart.write("Sleep A - con sonda -"+"\n")
                  reason=""
                  upower.wkup.enable()
                  pyb.standby()

       if active_day_a==True and pkl['relay_a']=='0' and enable_sonda_a==False:
              uart.write('Alarm A --> active_day_a=True, relay_a=0, enable_sonda_a=False. '+'\n') 
              uart.write("Set Stop Time A at : "+str(hre_a)+":"+str(mine_a)+"\n")

                # imposto allarme A con ora spegnimento e setto flag relay_a=1
                # set alarm A at switch off time and set relay_a=1              
              allarm_a.timeset(hour=int(pkl['hre_a']),minute=int(pkl['mine_a']),second=0) 

                # aggiorno dati salvati in memoria per riflettere nuovo valore relay_a
                # update data to reflect relay_a status.  
              pkl['relay_a']='1'
              z = pickle.dumps(pkl).encode('utf8')
              bkram[0] = len(z)
              ba[4: 4+len(z)] = z

              # genero impulso per attivare FF-D
              # pulse to change state on FF
              uart.write("Attiva Relay A - no sonda - "+"\n")
              uart.write("relay_a_on"+"\n")
              pin_relay_b.high()
              pyb.delay(10)
              pin_relay_b.low()

              uart.write("Sleep A - no sonda -"+"\n")
              reason=""
              upower.wkup.enable()   
              pyb.standby() 


              
                # se ultimo status relay_a era 1,imposto orario di attivazione prossimo allarme
                # if relay_a=1 set alarm to swich on time . 
       if active_day_a==True and pkl['relay_a']=='1':
              uart.write("Alarm A --> active_day_a=True,relay_a=1. "+"\n") 
              uart.write("Set Start Time A at : "+pkl['hrs_a']+":"+pkl['mins_a']+"\n")
                # imposto allarme A con ora spegnimento e setto flag relay_b=0
                # set alarm A at switch on time and set relay_a=0          
              allarm_a.timeset(hour=int(pkl['hrs_a']),minute=int(pkl['mins_a']),second=0)   
              
              pkl['relay_a']='0'
              z = pickle.dumps(pkl).encode('utf8')
              bkram[0] = len(z)
              ba[4: 4+len(z)] = z

                # genero impulso per attivare FF-D
                # pulse to change state on FF
              uart.write("Disattiva Relay A "+"\n")  
              pin_relay_a.high()
              pyb.delay(10)            
              pin_relay_a.low()
              
              uart.write("Sleep A dopo restart time."+"\n")
              uart.write("relay_a_off"+"\n")
              reason=""
              upower.wkup.enable()   
              pyb.standby() 
              
                # in caso non cia siano condizioni per cambiare stato relay a torno in sleep mode.
                # if are not satisfied the condition to change the relay state return to sleep mode.
       uart.write("Alarm A - no actions - torna in sleep mode."+"\n")
       reason=""
       upower.wkup.enable()   
       pyb.standby()    
              
           
    if reason=='ALARM_B':
       uart.write('Evento Alarm B'+'\n') 
       verde.on()
       pyb.delay(30)
       verde.off()
       print('Gestione Alarm B')
       restore_data()
       
       uart.write('Relay B :'+pkl['relay_b']+ '\n')
            
       if enable_sonda_b==True:
          uart.write('Soglia Lettura B :'+ '\n') 
          lettura_sonda_b=leggi_sonda_b()
          uart.write('Lettura Sonda  B :'+str(lettura_sonda_b)+ '\n')
          uart.write('Soglia Lettura B :'+pkl['tr_sonda_b']+ '\n')

       if active_day_b==True and pkl['relay_b']=='0' and enable_sonda_b==True and lettura_sonda_b<int(pkl['tr_sonda_b']):
                  uart.write("Alarm_B --> active_day_b=True,relay_b=0,enable_sonda_b=True,lettura sonda_b <soglia_b "+"\n")
                  uart.write("Set Stop Time B at : "+pkl['hre_b']+":"+pkl['mine_b']+"\n")

                  # imposto allarme B con ora spegnimento e setto flag relay_b=1
                  allarm_b.timeset(hour=int(pkl['hre_b']),minute=int(pkl['mine_b']),second=2)


                  # aggiorno dati salvati in memoria per riflettere nuovo valore relay_B

                  pkl['relay_b']="1"
                  z = pickle.dumps(pkl).encode('utf8')
                  bkram[0] = len(z)
                  ba[4: 4+len(z)] = z

                  # genero impulso per attivare FF-D

                  pin_relay_b.high()
                  pyb.delay(10)
                  pin_relay_b.low()
                  uart.write("Attiva Relay B - con sonda - "+"\n")
                  uart.write("relay_b_on"+"\n")
                  uart.write("Sleep B - con sonda -"+"\n")
                  reason=""
                  upower.wkup.enable()
                  pyb.standby()

       if active_day_b==True and pkl['relay_b']=='0' and enable_sonda_b==False:
              uart.write('Alarm_B --> active_day_b=True, relay_b=0, enable_sonda_b=False. '+'\n') 
              uart.write("Set Stop Time B at : "+str(hre_b)+":"+str(mine_b)+"\n")

                # imposto allarme B con ora spegnimento e setto flag relay_b=1
                             
              allarm_b.timeset(hour=int(pkl['hre_b']),minute=int(pkl['mine_b']),second=2) 

                # aggiorno dati salvati in memoria per riflettere nuovo valore relay_b

              pkl['relay_b']='1'
              z = pickle.dumps(pkl).encode('utf8')
              bkram[0] = len(z)
              ba[4: 4+len(z)] = z

              # genero impulso per attivare FF-D

              uart.write("Attiva Relay B - no sonda - "+"\n")
              uart.write("relay_b_on"+"\n")
              pin_relay_B.high()
              pyb.delay(10)
              pin_relay_B.low()

              uart.write("Sleep B - no sonda -"+"\n")
              reason=""
              upower.wkup.enable()   
              pyb.standby() 


              
                # se ultimo status relay_b era 1,imposto orario di attivazione prossimo allarme

       if active_day_b==True and pkl['relay_b']=='1':
              uart.write("Alarm B --> active_day_b=True,relay_b=1. "+"\n") 
              uart.write("Set Start Time B at : "+pkl['hrs_b']+":"+pkl['mins_b']+"\n")

              # imposto allarme B con ora spegnimento e setto flag relay_b=0

              allarm_b.timeset(hour=int(pkl['hrs_b']),minute=int(pkl['mins_b']),second=2)   
                           
              pkl['relay_b']='0'
              z = pickle.dumps(pkl).encode('utf8')
              bkram[0] = len(z)
              ba[4: 4+len(z)] = z
              
                # genero impulso per attivare FF-D
                
              uart.write("Disattiva Relay B "+"\n")  
              pin_relay_b.high()
              pyb.delay(10)            
              pin_relay_b.low()
              
              uart.write("Sleep B dopo restart time."+"\n")
              uart.write("relay_b_off"+"\n")
              reason=""
              upower.wkup.enable()   
              pyb.standby() 
              
       
       uart.write("Alarm B - no actions - torna in sleep mode."+"\n")
       reason=""
       upower.wkup.enable()   
       pyb.standby()    
              
    if reason=='POWERUP' :
       uart.write(reason+'\n') 
       pin_FF_reset.high()
       restore_data()
       set_allarms() # imposto allarmi secondo dati ricevuti da host
       reason=''
       upower.wkup.enable()
       pin_FF_reset.low()
       upower.wkup.enable()  
       pyb.standby()   
    upower.wkup.enable()   
    pyb.standby() 
except Exception as er:
       # just for debugging.
       uart.write("errore type :"+repr(er))
