# VSLS-specific function calls.

import axserver, sqlite3, smbus, math, jsonrpclib, datetime
from evdev import InputDevice

status_db = '/tmp/status.db'

power_items = {
    'dc_voltage': '/sys/class/hwmon/hwmon1/in1_input',
    'dc_current': '/sys/class/hwmon/hwmon1/curr1_input',
    'dc_power': '/sys/class/hwmon/hwmon1/power1_input',
    'solar_voltage': '/sys/class/hwmon/hwmon2/in1_input',
    'solar_current': '/sys/class/hwmon/hwmon2/curr1_input',
    'solar_power': '/sys/class/hwmon/hwmon2/power1_input',
    'battery_voltage': '/sys/class/hwmon/hwmon3/in1_input',
    'battery_current': '/sys/class/hwmon/hwmon3/curr1_input',
    'battery_power': '/sys/class/hwmon/hwmon3/power1_input',
}

class vsls(axserver.AXServerPlugin):

    def __init__(self, *args, **kwargs):
        super(vsls, self).__init__(*args, **kwargs)    
        
        self.enabled = True
        self.sign_id = 1
        self.xbee = jsonrpclib.Server('http://127.0.0.1:41999')

        # Add some check functions.
        self.server.plugins.alarm.check_functions['displayDriverFailure'] = \
            lambda p: [1 if i is True else 0 for i in \
                p.server.plugins.vsls.get_display_fault().values()]
        self.server.plugins.alarm.check_functions['displaySingleLEDFailure'] = \
            lambda p: p.server.plugins.vsls.get_total_errors().values()
        self.server.plugins.alarm.check_functions['displayMultiLEDFailure'] = \
            lambda p: [sum(p.server.plugins.vsls.get_total_errors().values())]
        self.server.plugins.alarm.check_functions['annulusLEDFailure'] = \
            lambda p: [p.server.plugins.vsls.get_total_errors()['annulus']]

        self.server.plugins.alarm.check_functions['masterCommsTimeout'] = \
            lambda p: [p.server.plugins.vsls.get_last_comms()]

        self.server.plugins.alarm.check_functions['batteryLow'] = \
            lambda p: [p.server.plugins.vsls.get_variable('battery_voltage')]
        self.server.plugins.alarm.check_functions['batteryCritical'] = \
            lambda p: [p.server.plugins.vsls.get_variable('battery_voltage')]           
        self.server.plugins.alarm.check_functions['mainsFailed'] = \
            lambda p: [1 if p.server.plugins.vsls.get_mains() \
                       == 'failed' else 0]
        self.server.plugins.alarm.check_functions['solarSystem'] = \
            lambda p: [1 if p.server.plugins.vsls.get_solar() \
                       == 'failed' else 0]
        self.server.plugins.alarm.check_functions['signTilt'] = \
            lambda p: [int(p.server.plugins.vsls.get_tilt())]

        with self.server.get_config_db() as db:
            result = db.execute('select value from system where \
                                 parameter="signEnabled" ').fetchone()[0]
            if str(result) == 'yes':
                self.enabled = True
            else:
                self.enabled = False
                
            self.sign_id = int(db.execute('select value from system where \
                                       parameter="signID" ').fetchone()[0])
    
    def get_sign_id(self):
        return self.sign_id

    def get_variable(self, item=None):
        if item:
            if status_items.has_key(item):
                with open(status_items[item], 'r') as itemfile:
                    if str(item).find('power') == -1:
                        item_value = int(itemfile.read()) / 1000.0
                    else:
                        item_value = int(itemfile.read()) / 1000000.0
                
                return item_value
        else:
            item_values = {}
            for key, value in status_items.iteritems():
                with open(value, 'r') as itemfile:
                    if str(key).find('power') == -1:
                        item_values[key] = int(itemfile.read()) / 1000.0
                    else:
                        item_values[key] = int(itemfile.read()) / 1000000.0    
            
            return item_values

    def get_mains(self):
        with open('/sys/class/gpio/gpio247/value', 'r') as mainsfile:
            if int(mainsfile.read()) == 1:
                return 'ok'
            else:
                return 'failed'

    def get_solar(self):
        return 'ok'

    def get_speeds(self):
        speed_list = []
        with self.server.get_config_db() as db:
            db.row_factory = sqlite3.Row
            result = db.execute('select * from speeds').fetchall()
            if result is not None:
                for speed in result:
                    speed_list.append(dict(speed))
                
        return speed_list
        
    def set_speeds(self, data):
        for speed in data:        
            with self.server.get_config_db() as db:
                db.execute("update speeds set allowed=? where frame_id=?",
                    (str(speed['allowed']), int(speed['frame_id'])))
            
            if speed['allowed'] == 'no':
                with self.server.get_config_db() as db:
                    result = db.execute(
                        'select scheduleID from schedule where document=?',
                        (int(speed['frame_id']),)).fetchall()
                    if result is not None:
                        for schedule_id in result:
                            self.server.plugins.schedule.remove(schedule_id[0])
                    result = db.execute(
                        'select scheduleID from schedule where document=?' \
                        (int(speed['frame_id'])+1,)).fetchall()
                    if result is not None:
                        for schedule_id in result:
                            self.server.plugins.schedule.remove(schedule_id[0])

    def get_tilt(self):
        dev = InputDevice('/dev/input/event0')
        cap = dev.capabilities()
        axis_x = cap[3][0][1][0]
        axis_y = cap[3][1][1][0]
        axis_z = cap[3][2][1][0]

        if abs(16384-math.sqrt(axis_x**2 + axis_y**2 + axis_z**2)) > 800:
            raise Exception('Too much acceleration for accurate tilt reading')

        return math.degrees(
            math.atan2(math.sqrt(axis_y**2 + axis_z**2), abs(axis_x)))

    def get_total_errors(self):
        result = {}
    
        matrix_files = [
            '/sys/bus/platform/devices/4aa80000.axent_ledmon/open_errors',
            '/sys/bus/platform/devices/4aa80000.axent_ledmon/short_errors'
        ]
        
        annulus_files = [
            '/sys/bus/platform/devices/4aab0000.axent_ledmon/open_errors',
            #'/sys/bus/platform/devices/4aab0000.axent_ledmon/short_errors'
        ]
        
        total = 0
        for i in matrix_files:
            with open(i, 'r') as fault_file:
                total += int(fault_file.read())
        result['matrix'] = max(total-120, 0)
        
        total = 0
        for i in annulus_files:
            with open(i, 'r') as fault_file:
                total += int(fault_file.read())
        result['annulus'] = max(total-72, 0)
        
        return result
    
    def get_visible_errors(self):
        result = {}
        
        total = 0
        with open(
        '/sys/bus/platform/devices/4aa80000.axent_ledmon/visible_errors',
        'r') as fault_file:
            total += int(fault_file.read())
        result['matrix'] = max(total-120, 0)
        
        total = 0
        with open(
        '/sys/bus/platform/devices/4aab0000.axent_ledmon/visible_errors',
        'r') as fault_file:
            total += int(fault_file.read())
        result['annulus'] = max(total-72, 0)
        
        return result
    
    def get_display_fault(self):
        result = {}
        
        matrix_files = [
            '/sys/bus/platform/devices/4aa80000.axent_ledmon/clk_err',
            '/sys/bus/platform/devices/4aa80000.axent_ledmon/lat_err',
            '/sys/bus/platform/devices/4aa80000.axent_ledmon/oe_err'
        ]
        
        annulus_files = [
            '/sys/bus/platform/devices/4aab0000.axent_ledmon/clk_err',
            '/sys/bus/platform/devices/4aab0000.axent_ledmon/lat_err',
            '/sys/bus/platform/devices/4aab0000.axent_ledmon/oe_err'
        ]
        
        fault = False
        for i in matrix_files:
            with open(i, 'r') as fault_file:
                if int(fault_file.read()) == 1:
                    fault = True
                    break
        result['matrix'] = fault
        
        fault = False
        for i in annulus_files:
            with open(i, 'r') as fault_file:
                if int(fault_file.read()) == 1:
                    fault = True
                    break
        result['annulus'] = fault
        
        return result

    def enable(self):
        self.server.plugins.schedule.enable_scheduler()
        #self.server.plugins.player.start()
        self.enabled = True
        with self.server.get_config_db() as db:
            db.execute('update system set value="yes" where \
                        parameter="signEnabled"')
        with sqlite3.connect(status_db) as db:
            db.execute('update status set enabled="yes" where \
                        sign_id=?', (int(self.sign_id),)) 

    def disable(self):
        self.server.plugins.schedule.disable_scheduler()
        self.server.plugins.player.load(0)
        self.server.plugins.player.stop()
        self.enabled = False
        with self.server.get_config_db() as db:
            db.execute('update system set value="no" where \
                        parameter="signEnabled"')
        with sqlite3.connect(status_db) as db:
            db.execute('update status set enabled="no" where \
                        sign_id=?', (int(self.sign_id),)) 


    def display_frame(self, frame_id):
        if self.enabled is True:
            self.server.plugins.schedule.disable_scheduler()
            self.server.plugins.player.load(int(frame_id))
            self.server.plugins.player.start()
        else:
            self.server.plugins.player.load(int(frame_id))
            self.server.plugins.player.load(0)

    def allow_speed(self, speed, allowed):
        allowed_states = ['yes', 'no']
        if allowed not in allowed_states:
            raise Exception('State not allowed')
        
        with self.server.get_config_db() as db:
            db.execute('update speeds set allowed=? where frame_id=?',
                (allowed, int(speed)))
        
        if self.sign_id == 1:
            if allowed == 'yes':
                self.server.plugins.signs.rta_event_log('frameAdded', 
                                                         int(speed))
            else:
                self.server.plugins.signs.rta_event_log('frameDeleted', 
                                                         int(speed))

    def get_last_comms(self):
        if self.sign_id == 1:
            return 0
        else:
            with sqlite3.connect(status_db) as db:
                db.row_factory = sqlite3.Row
                result = db.execute('select date from comms where sign_id=?',
                                     (self.sign_id,)).fetchone()[0]
            
            last_comms = datetime.datetime.strptime(str(result),
                                                    '%Y-%m-%d %H:%M:%S.%f')
            
            return int((datetime.datetime.now()-last_comms).total_seconds())
 
    def check_valid_frames(self, frame):
        with self.server.get_config_db() as db:
            if (int(frame) % 5) == 1:
                frame = int(frame) -1
            result = db.execute('select allowed from speeds where frame_id=?',
                (int(frame),)).fetchone()
            if result is not None:
                if str(result[0]) == 'yes':
                    return True
        return False
 
