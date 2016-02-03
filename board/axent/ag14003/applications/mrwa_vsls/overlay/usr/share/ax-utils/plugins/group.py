# VSLS-specific function calls used by internal website and RTA comms daemon.

import axserver, sqlite3, datetime, os, itertools, socket, jsonrpclib, struct
from rtacomms import crc16
import datetime

class OverlapException(Exception):
    pass

class InvalidPlanException(Exception):
    pass

class ConspicuityException(Exception):
    pass

class SizeException(Exception):
    pass

class InvalidContentException(Exception):
    pass

class PlanActiveException(Exception):
    pass

# Function to set up a connection to the RTA database.

def open_rta_db():
    rta_db = sqlite3.connect('/usr/share/db/rta.db')
    rta_db.row_factory = sqlite3.Row
    
    return rta_db

# Function to set up a connection to the RTA log database.

def open_rta_log_db():
    rta_db = sqlite3.connect('/usr/share/db/rta_log.db')
    rta_db.row_factory = sqlite3.Row
    
    return rta_db

# Function to set up a connection to the status database.

def open_status_db():
    db = sqlite3.connect('/tmp/status.db')
    db.row_factory = sqlite3.Row
    
    return db

error_code_map = {
    'xupstdInputFailure': (0, 0x01),
    'upsLoadBreaker': (1, 0x01),
    'upsBatteryTest': (0, 0x04),
    'upsBatteryRemainCapacity': (0, 0x0e),
    'keySwitch': (0, 0x10),
    'temperature': (0, 0x09),
    'upsBatteryTemperatureHigh': (0, 0x14),
    'monitorLDRFailure': (1, 0x0c),
    'displayDriverFailure': (1, 0x11),
    'displayTemperatureFailure': (1, 0x14),
    'displaySingleLEDFailure': (1, 0x07),
    'displayMultiLEDFailure': (1, 0x08)
}

# Updates the rta_log database with any changes that have occurred in the
# alarm table of config.db.

def update_rta_log(error_name, reported):
    # Look up error name and see if we need to create an rta_log entry.
    if error_name in error_code_map:
        controller_id = error_code_map[error_name][0]
        error_code = error_code_map[error_name][1]
        date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        occurred = (1 if reported == True else 0)
    else:
        return
    
    con = open_rta_log_db()
    # Figure out which ID this entry should have.
    last_id = con.execute(
        'select uniqueID from fault_log \
         order by date desc, uniqueID desc limit 1').fetchone()
    
    if last_id is None:
        new_id = 0
    elif last_id[0] == 255:
        new_id = 0
    else:
        try:
            new_id = int(last_id[0]) + 1
        except:
            new_id = 0
    
    try:
        with con:
            con.execute('insert into fault_log values \
                (?, ?, ?, ?, ?)',
                (new_id, controller_id, date, error_code, occurred))
    except:
        pass


def valid_schedule_days(type, data, year, month):
    if type == 0:
        if data > 0x7F:
            return False

    elif type == 1:
        try:
            for i in range(4):  #only check from 29th~32nd day
                if ((data >> (28 + i)) & 0x01) == 0x01:    #only check this bit is set to 1
                    datetime.date(year, month, 29 + i)
        except:
            return False

    elif type == 2:
        try:
            daylist = data.decode('hex')
            for j in range(12):
                month = struct.unpack(">L", daylist[(j*4):(j*4) + 4])[0]
                for i in range(4):  #only check from 29th~32nd day
                    if ((month >> (28 + i)) & 0x01) == 0x01:
                        datetime.date(year, j+1, 29 + i)
        except:
            return False

    return True

class group(axserver.AXServerPlugin):
    def __init__(self, *args, **kwargs):
        super(group, self).__init__(*args, **kwargs)
        
        self.enabled = True
        self.application_error = 0
        
        self.xbee = jsonrpclib.Server('http://127.0.0.1:41999')

        self.led_error_onset = None
        
        # Store initial state of all alarms relevant to the RTA protocol.
        self.rta_alarm_status = dict(zip(error_code_map.keys(),
            [True if i in self.server.plugins.alarm.current_alarms else False \
             for i in error_code_map.keys()]))
    
    def enable(self, sign_id=0):
        if int(sign_id) == 0:
            with self.server.get_config_db() as db:
                db.execute('update signs set enabled="yes"')
            self.xbee._notify.enable(enable=True, sign_id=0)
            self.server.plugins.vsls.enable()
        elif int(sign_id) == 1:
            self.server.plugins.vsls.enable()
            with self.server.get_config_db() as db:
                db.execute('update signs set enabled="yes" where sign_id=1')            
        else:
            self.xbee._notify.enable(enable=True, sign_id=0)
            with self.server.get_config_db() as db:
                db.execute('update signs set enabled="yes" where sign_id=?', \
                            (int(sign_id),))
    
    def disable(self, sign_id=0):
        if int(sign_id) == 0:
            with self.server.get_config_db() as db:
                db.execute('update signs set enabled="no"')
            self.xbee._notify.enable(enable=False, sign_id=0)
            self.server.plugins.vsls.disable()
        elif int(sign_id) == 1:
            self.server.plugins.vsls.disable()
            with self.server.get_config_db() as db:
                db.execute('update signs set enabled="no" where sign_id=1')  
        else:
            self.xbee._notify.enable(enable=False, sign_id=0)
            with self.server.get_config_db() as db:
                db.execute('update signs set enabled="no" where sign_id=?', \
                            (int(sign_id),))
    
    def status(self):
        result = {
            'enabled': self.enabled,
            'applicationError': self.application_error
        }
        
        return result
    
    def display_frame(self, frame_id):
        self.xbee._notify.display_frame(sign_id=0, frame=int(frame_id))
        self.server.plugins.vsls.display_frame(int(frame_id))
        with self.server.get_config_db() as db:
            db.execute('update signs set test_mode=0')
        
    def enable_plan(self, plan_id):
        with open_rta_db() as con:
            # Enable the scheduler.
            self.server.plugins.schedule.enable_scheduler()

            # If plan_id is zero, disable *all* plan_entries.
            if plan_id == 0:
                if self.server.plugins.schedule.get_current() is None:
                    con.execute('update plan set enable=0')
                return
            
            # Ensure the selected plan exists.
            plan_entry = con.execute('select * from plan where uniqueID=?',
                (plan_id,)).fetchone()
            
            if plan_entry is None:
                raise InvalidContentException('No such plan exists')
            
            if plan_entry['enable'] == 1:
                return

            #check frame is allowed or not
            entries = con.execute('select frameID from plan_entry where planID=?',
                (plan_id,)).fetchall()

            if entries is None:
                raise InvalidContentException('No plan entry exists')

            for frame in entries:
                if self.server.plugins.vsls.check_valid_frames(frame[0]) == False :
                   raise InvalidContentException('Invalid Frame')

            #check whether it overlap with other plans
            try:
                self.server.plugins.schedule.get_timeline(overlap=plan_entry)
            except Exception as e:
                if 'Schedule Overlap' in e.message:
                    raise OverlapException('Schedule parameter overlap')
                else:
                    raise

            # Find all schedules associated with the plan and enable them.
            con.execute('update plan set enable=1 where uniqueID=?',(plan_id,))
            
            self.server.plugins.schedule.refresh()
    
    def disable_plan(self, plan_id):
        with open_rta_db() as con:
            # If plan_id is zero, disable *all* plan_entries.
            if plan_id == 0:
                if self.server.plugins.schedule.get_current() is None:
                    con.execute('update plan set enable=0')
                return

            # Ensure the selected plan exists.
            plan_entry = con.execute('select * from plan where uniqueID=?',
                (plan_id,)).fetchone()

            if plan_entry is None:
                raise InvalidContentException('No such plan exists')

            if plan_entry['enable'] == 0:
                return

            #check whether it is an active plan
            cur = self.server.plugins.schedule.get_current()
            if cur is not None:
                if cur[3] == plan_id:
                    raise PlanActiveException('Plan is active')

            # # Find all schedules associated with the plan and disable them.
            con.execute('update plan set enable=0 where uniqueID=?',(plan_id,))

            self.server.plugins.schedule.refresh()
    
    def set_plan(self, plan_id, rev, type, sch_data, plans):
        year = 0
        month = 0
        schdata = sch_data.decode('hex')
        
        if type == 0:
            data = ord(schdata)
            if(valid_schedule_days(type, data, 0, 0) == False):
                raise InvalidPlanException('Schedule parameter error')
            daylist = data
            
        elif type == 1:
            year = struct.unpack(">H", schdata[:2])[0]
            month = ord(schdata[2])
            data = struct.unpack(">L", schdata[3:])[0]
            if ((year < 1 or year > 9999) or
                (month  < 1 or month > 12) or
                (valid_schedule_days(type, data, year, month) == False)):
                raise InvalidPlanException('Schedule parameter error')
            daylist = data

        elif type == 2:
            year = struct.unpack(">H", schdata[:2])[0]
            data = str(schdata[2:])
            if  ((year < 1 or year > 9999) or
                (valid_schedule_days(type, data.encode('hex'), year, 0) == False)):
                raise InvalidPlanException('Schedule parameter error')
            daylist = data.encode('hex')
            
        #update database
        with open_rta_db() as con:
            # If the plan already exists, remove all data associated to it.
            existing_plan = con.execute('select * from plan where uniqueID=?',
                (plan_id,)).fetchone()
            
            if existing_plan is not None:
                con.execute('delete from plan_entry where planID=?', (plan_id,))
                if existing_plan['type'] == 0:
                    con.execute('delete from plan_weekly where planID=?', (plan_id,))
                elif existing_plan['type'] == 1:
                    con.execute('delete from plan_monthly where planID=?', (plan_id,))
                elif existing_plan['type'] == 2:
                    con.execute('delete from plan_yearly where planID=?', (plan_id,))            
            
            # Create plan entry in rta.db.
            con.execute('insert or replace into plan (uniqueID, revision, type) values \
                (?, ?, ?)', (plan_id, rev, type))
            
            #Create an entry in plan_weekly/plan_monthly/plan_yearly
            if type == 0:
                con.execute('insert or replace into plan_weekly values \
                (?, ?)', (plan_id, daylist))
            elif type == 1:
                con.execute('insert or replace into plan_monthly values \
                (?, ?, ?, ?)', (plan_id, year, month, daylist))
            elif type == 2:
                con.execute('insert or replace into plan_yearly values \
                (?, ?, ?)', (plan_id, year, daylist))

            # Create an entry in plan_entry for each message attached to this plan.
            for p in plans:
                # Create a new row in plan_entry.
                con.execute('insert or replace into plan_entry \
                    (planID, frameID, \
                     startH, startM, endH, endM) \
                    values (?, ?, ?, ?, ?, ?)',
                    (plan_id, p[1], p[2], p[3], p[4], p[5]))
            
            # Trigger a scheduler refresh.
            self.server.plugins.schedule.refresh()
    
    def get_frame_list(self):
        result = []
        with self.server.get_config_db() as db:
            result = db.execute(
                        'select frame_id from speeds where allowed="yes"' \
                        ).fetchall()
        return [i[0] for i in result]
    
    def get_plan(self, plan_id):
        results = []
        entries = []
        year = 0
        month = 0
        
        with open_rta_db() as con:
            plan = con.execute('select * from plan where uniqueID=?',
                (plan_id,)).fetchone()

            if plan is None:
                raise Exception('No such plan')

            # Now get plan_entries associated with this plan.
            plan_entries = con.execute('select * from plan_entry where planID=?',
                (plan_id,)).fetchall()

            if plan[2] == 0:
                plan_days = con.execute('select * from plan_weekly where planID=?',
                (plan_id,)).fetchone()
                value = plan_days[1]
            elif plan[2] == 1:
                plan_days = con.execute('select * from plan_monthly where planID=?',
                (plan_id,)).fetchone()
                value = plan_days[3]
                year = plan_days[1]
                month = plan_days[2]
            elif plan[2] == 2:
                plan_days = con.execute('select * from plan_yearly where planID=?',
                (plan_id,)).fetchone()
                value = plan_days[2]
                year = plan_days[1]

            results = {
                'revision': plan[1],
                'type': plan[2],
                'days': value,
                'year': year,
                'month': month,
                'entries': [dict(p) for p in plan_entries]
            }

        return results
    
    def get_enabled_plans(self):
        with open_rta_db() as con:
            # Find which plans are enabled.
            enabled_plans = con.execute(
                'select uniqueID from plan \
                 where enable=1').fetchall()

            enabled_plan_entries = []
            for e in enabled_plans:
                enabled_plan_entries.extend(i['planID'] for i in con.execute(
                    'select planID from plan_entry where planID=?',
                    (int(e[0]),)).fetchall())

            enabled_plans = list(set(enabled_plan_entries))
        
        return enabled_plans

    def get_enabled_plans_checksum(self):
        enabled_plans = []
        enabled_plans_checksum = []
        checksum = 0

        with open_rta_db() as con:
            # Find which plans are enabled.
            enabled_plans = con.execute(
                'select * from plan \
                 where enable=1').fetchall()

            for e in enabled_plans:
                # Now get entries associated with this plan.
                entries = con.execute('select * from plan_entry where planID=?',
                    (e[0],)).fetchall()

                if e[2] == 0:
                    plan_days = con.execute('select * from plan_weekly where planID=?',
                    (e[0],)).fetchone()
                    value = plan_days[1]
                elif e[2] == 1:
                    plan_days = con.execute('select * from plan_monthly where planID=?',
                    (e[0],)).fetchone()
                    value = plan_days[3]
                    year = plan_days[1]
                    month = plan_days[2]
                elif e[2] == 2:
                    plan_days = con.execute('select * from plan_yearly where planID=?',
                    (e[0],)).fetchone()
                    value = plan_days[2]
                    year = plan_days[1]

                # Assemble plan response.
                response_data = ''
                response_data += ('%x' % 0x21).zfill(2)
                response_data += ('%x' % e[0]).zfill(2)
                response_data += ('%x' % e[1]).zfill(2)
                response_data += ('%x' % e[2]).zfill(2)
                if int(e[2]) == 0:
                    response_data += ('%x' % int(value)).zfill(2)
                elif int(e[2]) == 1:
                    response_data += ('%x' % int(year)).zfill(4)
                    response_data += ('%x' % int(month)).zfill(2)
                    response_data += ('%x' % int(value)).zfill(8)
                elif int(e[2]) == 2:
                    response_data += ('%x' % int(year)).zfill(4)
                    response_data += str(value)

                for i in entries:
                    response_data += ('%x' % int(1)).zfill(2)
                    response_data += ('%x' % int(i['frameID'])).zfill(2)
                    response_data += ('%x' % int(i['startH'])).zfill(2)
                    response_data += ('%x' % int(i['startM'])).zfill(2)
                    response_data += ('%x' % int(i['endH'])).zfill(2)
                    response_data += ('%x' % int(i['endM'])).zfill(2)

                response_data = response_data.decode('hex')
                if len(entries) < 6:
                    response_data += '\x00'

                checksum = crc16.crc16(response_data)
                enabled_plans_checksum.append((e[0], checksum))
        return enabled_plans_checksum
    
    def list_frames(self):
        con = open_rta_db()
        all_frames = con.execute('select uniqueID from frame').fetchall()
        
        return [i[0] for i in all_frames]
    
    def list_plans(self):
        with open_rta_db() as con:
            all_plans = con.execute('select uniqueID from plan').fetchall()
        
        return [i[0] for i in all_plans]
    
    def get_current_fault(self, address):
        with self.server.get_config_db() as db:
            result = db.execute('select sign_id from signs').fetchall()
            sign_list = [r[0] for r in result]

        if address not in sign_list:
            raise Exception('Invalid address')
        
        with open_rta_log_db() as db:
            alarm = db.execute('select errorCode from open_fault_log \
                                 where signID=?', (address,)).fetchone()
        
        if alarm is not None:
            return alarm
        
        return 0
    
    def get_rta_log(self, max_entries, log_type=0):
        log_type = int(log_type)
        max_entries = int(max_entries)
        if log_type > 3:
            raise Exception('Invalid log type')

        if log_type == 0 or log_type == 1:
            self.server.plugins.signs.cancel_uca()
       
        if log_type == 0:
            table = 'fault_log'
        elif log_type == 1:
            table = 'open_fault_log'
        elif log_type == 2:
            table = 'operation_log'
        elif log_type == 3:
            table = 'event_log'

        with open_rta_log_db() as db:
            logs = db.execute(
                'select * from %s order by date desc limit %d' \
                % (table, max_entries)).fetchall()

        return [dict(l) for l in logs]

    def get_rta_power_log(self, day):
        if day == 0:
            offset_str = 'offset <= 24'
        elif day ==1:
            offset_str = 'offset >= 24'
        else:
            raise Exception("Invalid day reference")

        sign_logs = {}

        with self.server.get_config_db() as db:
            result = db.execute('select sign_id from signs').fetchall()
            sign_list = [r[0] for r in result]

        with open_rta_log_db() as db:
            for sign in sign_list:
                logs = db.execute(
                    'select * from power_log where (signID = %d and %s) \
                     order by offset' % (sign, offset_str)).fetchall()
                sign_logs[sign] = [dict(l) for l in logs]

                if len(sign_logs[sign]) < 25:
                    for i in range(25 - len(sign_logs[sign])):
                        sign_logs[sign].append({'solarCurrent': 0, 
                                                'batteryCurrent': 0, 
                                                'batteryVoltage': 0})

        return sign_logs
    
    def reset_rta_log(self, log_type=0):
        log_type = int(log_type)
        with open_rta_log_db() as db:
            if log_type == 0:
                db.execute('delete from fault_log')
            elif log_type == 1:
                db.execute('delete from open_fault_log')
            elif log_type == 2:
                db.execute('delete from operation_log')
            elif log_type == 3:
                db.execute('delete from event_log')
            elif log_type == 4:
                db.execute('delete from power_log')

        if int(log_type) == 2:
            self.server.plugins.signs.rta_event_log('systemLogCleared', 1)
        else:
            self.server.plugins.signs.rta_event_log('resetLogType', log_type)

    def reset_l0(self):        
        # Blank entirely.
        try:
            self.display_frame(0)
        except:
            pass
    
    def reset_l1(self, log=False):
        # L0 reset.
        self.reset_l0()
        
        # Disable all plans.
        with open_rta_db() as db:
            db.execute('update plan set enable=0')

        self.server.plugins.schedule.refresh()

        if log is True:
            self.server.plugins.signs.rta_event_log('systemLogCleared', 2)
    
    def reset_l2(self, log=False):
        # L1 reset.
        self.reset_l1()
        
        # Reset all faults and fault log.
        self.application_error = 0
        with open_rta_log_db() as db:
            db.execute('delete from fault_log')
            db.execute('delete from operation_log')
            db.execute('delete from event_log')
            db.execute('delete from power_log')

        self.server.plugins.signs.brightness(auto=True)
        self.enable()

        if log is True:
            self.server.plugins.signs.rta_event_log('systemLogCleared', 3)
    
    def reset_l3(self, log=False):
        # L2 reset.
        self.reset_l2()
        
        # Clear all frames, messages and plans.
        with open_rta_db() as db:
            db.execute('delete from plan')
        
        with self.server.get_config_db() as db:
            db.execute('update speeds set allowed="no"')
            db.execute('delete from schedule')
        
        self.server.plugins.schedule.refresh()
        
        if log is True:
            self.server.plugins.signs.rta_event_log('systemLogCleared', 4)

    def reset_l255(self):
        # L3 reset.
        self.reset_l3()
        
        parameter = {'rtaProtocolEnabled': 'yes',
                     'rtaPort': '43000',
                     'rtaPasswordOffset': 'a410',
                     'rtaPasswordSeedOffset': '2a',
                     'rtaSessionTimeout': '120',
                     'rtaDisplayTimeout': '0',
        }

        with self.server.get_config_db() as db:
            for key, value in parameters.iteritems():
                db.execute('update system set value=? \
                            where parameter=?', (key, value))

        # Restore the following to factory defaults:
        #     - seed offset
        #     - password offset
        #     - baud reset
        #     - parity
        #     - display timeout
        #     - default font

    def update_timeline_db(self, timeline, maxentries):
        with sqlite3.connect('/tmp/status.db') as con:
            cnt = 0
            con.execute('delete from timeline')
            if timeline is not None:
                for i in range(len(timeline)):
                    # Create a new row in timeline.
                    con.execute('insert or replace into timeline \
                        (start, end, frame) \
                        values (?, ?, ?)',
                        (timeline[i][0], timeline[i][1], timeline[i][2]))
                    cnt = i+1
                    if i == (maxentries -1):
                        break
                print 'updated timeline cnt:', cnt
                try:
                    self.xbee._notify.resync_timeline(sign_id=0)
                except:
                    print 'Unable to broadcast timeline resync'

    def get_timeline_db(self):
        timeline_list = []
        with sqlite3.connect('/tmp/status.db') as con:
            result = con.execute('select start,end,frame from timeline').fetchall()
            if result is not None:
                for timeline in result:
                    timeline_list.append(timeline)

        return timeline_list

    def clear_timeline_db(self):
        with sqlite3.connect('/tmp/status.db') as con:
            con.execute('delete from timeline')
