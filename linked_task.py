"""Per-user Windows scheduled check; no service or audit-policy changes."""
from pathlib import Path
from datetime import datetime, timedelta
import csv
import io
import subprocess
import tempfile
import xml.etree.ElementTree as ET

NS='http://schemas.microsoft.com/windows/2004/02/mit/task'
TASK_PREFIX='Stintory Linked - '


def task_xml(root, pythonw, sid, start):
    ET.register_namespace('', NS)
    def add(parent, name, value=None, **attrs):
        el=ET.SubElement(parent, f'{{{NS}}}{name}', attrs)
        if value is not None: el.text=str(value)
        return el
    task=ET.Element(f'{{{NS}}}Task',version='1.3')
    info=add(task,'RegistrationInfo'); add(info,'Description','Start Stintory only while Resolve is running; check at most once per minute.')
    triggers=add(task,'Triggers'); timer=add(triggers,'TimeTrigger')
    rep=add(timer,'Repetition'); add(rep,'Interval','PT1M'); add(rep,'StopAtDurationEnd','false')
    add(timer,'StartBoundary',start.isoformat(timespec='seconds')); add(timer,'Enabled','true')
    logon=add(triggers,'LogonTrigger'); add(logon,'Enabled','true'); add(logon,'UserId',sid)
    principals=add(task,'Principals'); principal=add(principals,'Principal',id='Author')
    add(principal,'UserId',sid); add(principal,'LogonType','InteractiveToken'); add(principal,'RunLevel','LeastPrivilege')
    settings=add(task,'Settings')
    for name,val in [('MultipleInstancesPolicy','IgnoreNew'),('DisallowStartIfOnBatteries','false'),('StopIfGoingOnBatteries','false'),('StartWhenAvailable','true'),('AllowStartOnDemand','true'),('Enabled','true'),('WakeToRun','false'),('ExecutionTimeLimit','PT0S')]: add(settings,name,val)
    actions=add(task,'Actions',Context='Author'); execute=add(actions,'Exec')
    add(execute,'Command',str(pythonw))
    add(execute,'Arguments',subprocess.list2cmdline(['-E',str(root/'run_tracker.pyw'),'--scheduled','--with-resolve']))
    add(execute,'WorkingDirectory',str(root))
    return ET.tostring(task,encoding='utf-16',xml_declaration=True)


def user_sid(windows):
    output=subprocess.check_output([str(windows/'System32'/'whoami.exe'),'/user','/fo','csv','/nh'])
    for row in csv.reader(io.StringIO(output.decode('ascii',errors='replace'))):
        for field in row:
            if field.startswith('S-1-') and all(x.isdigit() for x in field[2:].split('-')): return field
    raise RuntimeError('Cannot identify current Windows user SID')


def install(root, windows, pythonw, run):
    sid=user_sid(windows)
    with tempfile.TemporaryDirectory() as directory:
        xml=Path(directory)/'task.xml'
        xml.write_bytes(task_xml(root,pythonw,sid,datetime.now()+timedelta(seconds=5)))
        run('Register per-user Resolve check', [str(windows/'System32'/'schtasks.exe'),'/Create','/TN',TASK_PREFIX+sid,'/XML',str(xml),'/F'])
