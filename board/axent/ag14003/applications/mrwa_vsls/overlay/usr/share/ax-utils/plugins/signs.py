# VSLS-specific function calls.

import axserver, datetime, sqlite3, os, jsonrpclib, time, socket, traceback, logging, struct
from multiprocessing import Process, Pipe

status_db = '/tmp/status.db'
log_db = '/usr/share/db/log.db'
rta_log_db = '/usr/share/db/rta_log.db'

error_code = {
    0x01: 'loadAverage',
    0x02: 'temperature',
    0x03: 'batteryLow',
    0x04: 'batteryCritical',
    0x05: 'mainsFailed',
    0x06: 'signCommsTimeout',
    0x07: 'masterCommsTimeout',
    0x08: 'signTilt',
    0x09: 'solarSystem',
    0x0A: 'displayDriverFailure',
    0x0B: 'displaySingleLEDFailure',
    0x0C: 'displayMultiLEDFailure',
    0x0D: 'annulusLEDFailure'
    }

error_code_map = {
    'mainsFailed': (0x01, True),
    'temperature': (0x12, False),
    'batteryLow': (0x0D, False),
    'batteryCritical': (0x01, True),
    'signCommsTimeout': (0x18, False),
    'signTilt': (0x1B, False),
    'solarSystem': (0x1A, False),
    'displayDriverFailure': (0x10, True),
    'displaySingleLEDFailure': (0x06, False),
    'displayMultiLEDFailure': (0x07, True),
    'annulusLEDFailure': (0x19, True)
    }

event_code_map = {
    'systemLogCleared': 0x01,
    'timeUpdated': 0x02,
    'passwordChanged': 0x03,
    'resetLogType': 0x04,
    'signAdded': 0x05,
    'signDeleted': 0x06,
    'frameAdded': 0x07,
    'frameDeleted': 0x08,
    'ucaStateChanged': 0x09,
    'ucaAddressChanged': 0x0A,
    'firmwareChanged': 0x0B,
    }

class signs(axserver.AXServerPlugin):
    def __init__(self, *args, **kwargs):
        super(signs, self).__init__(*args, **kwargs)    

        self.server.plugins.alarm.check_functions['signCommsTimeout'] = \
            lambda p: p.server.plugins.signs.get_last_comms()
                    
        self.xbee = jsonrpclib.Server('http://127.0.0.1:41999')

        class ucaProcess(Process):
            def __init__(self, conn):
                Process.__init__(self)
                                
                self.conn = conn
                self.logger = logging.getLogger('server.uca.process')
                self.daemon = True

                self.address = '192.168.0.1'
                self.port = 44000
                self.interval = 600
                self.enabled = True
                self.site = 1

                self.active = False
                self.last = datetime.datetime(2000, 1, 1)

            def log(self, data):
                try:
                    with sqlite3.connect(log_db) as db:
                        db.execute('insert into event_log \
                                    (sign_id, type, event, date) \
                                    values (?, ?, ?, ?)', (0, "uca", str(data),
                                     datetime.datetime.now().strftime(
                                        '%Y-%m-%d %H:%M:%S.%f')))

                except:
                    traceback.print_exc()
                    print >> sys.stderr, 'Exception in UCA database logging'

            def send_uca(self):
                self.active = True
                try:
                    uca = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    uca.sendto(chr(self.site), (self.address, self.port))
                except:
                    self.logger.info('Exception while trying to send UCA')
                finally:
                    self.logger.info('UCA sent to %s:%d' % (self.address,
                                                             self.port))
                    self.log('UCA sent to %s:%d' % (self.address, self.port))

                    self.last = datetime.datetime.now()

            def run(self):

                while 1:

                    if self.active and self.enabled:
                        delta = datetime.datetime.now()-self.last
                        if delta.total_seconds() >= self.interval:
                            self.send_uca()

                 # Check for data from parent thread.
                    new_data = self.conn.poll(1)
                    if new_data is True:
                        data = self.conn.recv()
                        if data.has_key('operation'):
                            if str(data['operation']) == 'send':
                                if self.active is False:
                                    self.send_uca()
                                    # TODO log to RTA db

                            if str(data['operation']) == 'cancel':
                                if self.active is True:
                                    pass # TODO log to RTA db

                                self.active = False
                                self.last = datetime.datetime(2000, 1, 1)

                        elif data.has_key('address'):
                            self.address = str(data['address'])
                            self.port = int(data['port'])
                            self.interval = int(data['interval'])
                            if str(data['enabled']) == 'yes':
                                self.enabled = True
                            else:
                                self.enabled = False
                            self.site = int(data['site'])
                            
        uca_conn_recv, self.uca_conn = Pipe(duplex=False)
        self.uca_process = ucaProcess(uca_conn_recv)
        self.uca_process.start()
        self.uca_settings()

    def uca_settings(self):
        settings = {}
        with self.server.get_config_db() as db:
            settings['address'] = str(db.execute('select value from system \
                            where parameter="ucaAddress"').fetchone()[0])
            settings['port'] = str(db.execute('select value from system \
                            where parameter="ucaPort"').fetchone()[0])
            settings['interval'] = str(db.execute('select value from system \
                            where parameter="ucaSendInterval"').fetchone()[0])
            settings['enabled'] = str(db.execute('select value from system \
                            where parameter="ucaEnabled"').fetchone()[0])
            settings['site'] = str(db.execute('select value from system \
                            where parameter="siteID"').fetchone()[0])

        self.uca_conn.send(settings)

    def send_uca(self):
        data = {'operation': 'send'}
        self.uca_conn.send(data)

    def get_disable_enable_uca(self):
        enable = 0
        with sqlite3.connect('/usr/share/db/config.db') as con:
            result = con.execute('select value from system where parameter="ucaEnabled"',) \
                .fetchone()
            if result is not None:
                enable = (1 if (result[0] == 'yes') else 0)
        return enable

    def disable_enable_uca(self, enable):
        with sqlite3.connect('/usr/share/db/config.db') as con:
            if enable == 1:
                con.execute('update system set value="yes" where parameter="ucaEnabled"',)
            else:
                con.execute('update system set value="no" where parameter="ucaEnabled"',)
        self.server.plugins.signs.rta_event_log('ucaStateChanged', enable)

    def get_uca_addr(self):
        with sqlite3.connect('/usr/share/db/config.db') as con:
            ip = con.execute('select value from system where parameter="ucaAddress"',) \
                .fetchone()
            port = con.execute('select value from system where parameter="ucaPort"',) \
                .fetchone()

            if ip is None or port is None:
                raise Exception('Get ucaAddress and port failed')

            addr = socket.ntohl(struct.unpack("I",socket.inet_aton(str(ip[0])))[0])
            return [addr, int(port[0])]

    def set_uca_addr(self, ip, port):
        with sqlite3.connect('/usr/share/db/config.db') as con:
            addr = socket.inet_ntoa(struct.pack('I',socket.htonl(ip)))
            con.execute('update system set value=? where parameter="ucaAddress"',
                        (str(addr),))
            con.execute('update system set value=? where parameter="ucaPort"',
                        (str(port),))
        self.server.plugins.signs.rta_event_log('ucaAddressChanged')

    def cancel_uca(self):
        data = {'operation': 'cancel'}
        self.uca_conn.send(data)

    def get_signs(self):
        sign_list = []
        with self.server.get_config_db() as db:
            result = db.execute('select * from signs').fetchall()
            if result is not None:
                for sign in result:
                    sign_list.append(dict(sign))
        return sign_list

    def add_sign(self, sign_id, sign_address):
        
        with self.server.get_config_db() as db:
            db.execute("insert or replace into signs \
                        (sign_id, address) values(?,?)",
                        (str(sign_id), str(sign_address)))     
        
        self.rta_event_log('signAdded', int(sign_id))

        self.heartbeat(sign_id)
        self.refresh_data(sign_id)
        self.sync_alarms(sign_id)

        # TODO: master address to assigned sign
    
    def remove_sign(self, sign_id):
        # TODO: Relaunch scripts?
        with self.server.get_config_db() as db:
            db.execute('delete from signs where sign_id=?', (int(sign_id),))
        with sqlite3.connect(status_db) as db:
            db.execute('delete from status where sign_id=?', (int(sign_id),))
            db.execute('delete from comms where sign_id=?', (int(sign_id),))
        with sqlite3.connect(log_db) as db:
            db.execute('delete from status_log \
                        where sign_id=?', (int(sign_id),))
        with sqlite3.connect(rta_log_db) as db:
            db.execute('delete from power_log \
                        where signID=?', (int(sign_id),))

        self.rta_event_log('signDeleted', int(sign_id))

    def search(self):
        pass
 
    def get_status(self, sign_id=None):
        status_list = []
        with sqlite3.connect(status_db) as db:
            db.row_factory = sqlite3.Row
            if sign_id is None:
                result = db.execute('select * from status').fetchall()
            else:
                result = db.execute('select * from status where \
                                     sign_id=?', (int(sign_id),)).fetchall()
            if result is not None:
                for sign in result:
                    status_list.append(dict(sign))
   
        return status_list
        
    def set_mode(self, sign_id, mode, master_address=None):
        allowed_modes = ['master', 'slave']
        if mode not in allowed_modes:
            raise Exception('Mode not allowed')
        if mode == 'master':
            sign_id = 1
            master_address = None
        else:
            if master_address is None:
                raise Exception('Master address is required')
            if (int(sign_id) < 2 or int(sign_id) > 254):
                raise Exception('Sign ID out of range')

        address = 'own address'
                
        with self.server.get_config_db() as db:
            db.execute('update system set value=? where \
                        parameter="signID"', (int(sign_id),))
            db.execute('update system set value=? where \
                        parameter="masterAddress"', (str(master_address),))
            db.execute('delete from signs')
            db.execute('insert or replace into signs (sign_id, address) \
                        values (?, ?)', (str(sign_id), str(address)))
            db.execute('update speeds set allowed="no"')
        
        # TODO: clear status and log databases
        self.server.plugins.schedule.clear()                

    def sync_schedules(self, sign_id=0):
        self.xbee._notify.resync_timeline(sign_id=int(sign_id))
  
    def heartbeat(self, sign_id=0):
        self.xbee._notify.heartbeat(sign_id=int(sign_id))
    
    def refresh_data(self, sign_id=0):
        self.xbee._notify.request_status(sign_id=int(sign_id))

    def sync_alarms(self, sign_id=0):
        self.xbee._notify.alarm_sync(sign_id=int(sign_id))

    def brightness(self, sign_id=0, brightness=0, auto=False):
        allowed_modes = [True, False]
        if auto not in allowed_modes:
            raise Exception('Auto mode incorrect')

        if int(sign_id) == 0 or int(sign_id) == 1:
            self.server.plugins.display.brightness(
                brightness=brightness, auto=auto)
        if int(sign_id) != 1:
            if auto is True:
                self.xbee._notify.brightness_auto(
                    sign_id=sign_id, enable=True)
            else:
                self.xbee._notify.brightness(
                    sign_id=sign_id, brightness=brightness)

        with self.server.get_config_db() as db:
            mode = 'auto' if auto is True else 'manual'
            if int(sign_id) == 0:
                db.execute('update signs set brightness=?, \
                                brightness_mode=?', (brightness, mode,))
            else:
                db.execute('update signs set brightness=?, brightness_mode=? \
                            where sign_id=?', (brightness, mode, sign_id))

    def test_mode(self, test_mode, sign_id=0):
        if int(sign_id) != 1:
            self.xbee._notify.test_mode(sign_id=sign_id, mode=test_mode)

        if int(sign_id) == 0 or int(sign_id) == 1:
            self.server.plugins.display.test_mode(mode=test_mode)

        with self.server.get_config_db() as db:
            if int(sign_id) == 0:
                db.execute('update signs set test_mode=?', (test_mode,))
            else:
                db.execute('update signs set test_mode=? \
                            where sign_id=?', (test_mode, sign_id))

    def get_last_comms(self):
        sign_times = []   
        with sqlite3.connect(status_db) as db:
            db.row_factory = sqlite3.Row
            result = db.execute('select sign_id, date from comms').fetchall()
            if result is not None:
                for sign in result:
                    last_comms = datetime.datetime.strptime(sign[1],
                                                    '%Y-%m-%d %H:%M:%S.%f')       
                    t = (datetime.datetime.now()-last_comms).total_seconds()
                    sign_times.append(int(t))
        
        return sign_times

    def alarm(self, sign_id, code, value):
        print "Alarm %d received from sign ID %d" % (code, sign_id)

        with sqlite3.connect(status_db) as db:
            db.execute('update alarms set active=? where \
                        (parameter=? and sign_id=?)',
                        (('yes' if value is True else 'no'), code, sign_id,))
        
        if error_code_map.has_key(error_code[code]):
            try:
                self.add_rta_log(sign_id, error_code[code], value)
            except:
                pass

            if value is True:
                if error_code_map[error_code[code]][1] is True:
                    self.send_uca()

        if int(sign_id) != 1:
            if value is True:
                event = 'Failed: '
            else:
                event = 'Cleared: '
                if self.server.plugins.schedule.check_enabled() is False:
                    player_data = self.server.plugins.player.status()
                    if player_data['running'] is True:
                        self.xbee._notify.display_frame(sign_id=int(sign_id),
                                          frame=int(player_data['document']))

            if error_code.has_key(code):
                event += str(error_code[code])
            else:
                event += 'Unknown error'      

            with sqlite3.connect(log_db) as db:
                db.execute('insert into event_log (sign_id, type, event, date) \
                            values (?, ?, ?, ?)', (sign_id, 'alarm', event,
                                            datetime.datetime.now().strftime(
                                                    '%Y-%m-%d %H:%M:%S.%f')))

    def operation(self, sign_id, old, new):
        if self.server.plugins.vsls.sign_id == 1:
            pass

        event = 'Display changed from %s to %s' % (str(old), str(new))

        with sqlite3.connect(log_db) as db:
            db.execute('insert into event_log (sign_id, type, event, date) \
                        values (?, ?, ?, ?)', (sign_id, 'operation', event,
                                        datetime.datetime.now().strftime(
                                                '%Y-%m-%d %H:%M:%S.%f')))

    def get_logs(self, log_type, limit=100, sign_id=None):
        log_list = []
        
        with sqlite3.connect(log_db) as db:
            db.row_factory = sqlite3.Row
            if sign_id is not None:
                result = db.execute('select * from ? where sign_id=?',
                    (str(log_type), int(sign_id)))
            else:
                result = db.execute('select * from ?', (str(log_type),))
        
        for log in result:
            log_list.append(dict(log))
            
        return log_list

    def get_version(self):
        version = 0
        with sqlite3.connect(status_db) as db:
            db.row_factory = sqlite3.Row
            result = db.execute(
                'select platform_version,application_version from status where sign_id=1').fetchone()
            if result is not None:
                av = str.split(str(result[1]), '.')
                version = (int(result[0]) << 16) | (int(av[0]) << 8) |(int(av[1]))

        return version


    def rta_event_log(self, event_name, parameter=None):
        # Look up error name and see if we need to create an rta_log entry.
        if event_code_map.has_key(event_name):
            event_code = event_code_map[event_name]
            date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        else:
            return

        try:
            with sqlite3.connect(rta_log_db) as db:
                db.row_factory = sqlite3.Row
                # Figure out which ID this entry should have.
                last_id = db.execute(
                    'select uniqueID from event_log \
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
            
                db.execute('insert into event_log values (?, ?, ?, ?)',
                            (new_id, date, event_code, int(parameter)))
        except:
            pass

    def add_rta_log(self, sign_id, error_name, reported):
        # Look up error name and see if we need to create an rta_log entry.
        if error_name in error_code_map:
            error_code = error_code_map[error_name][0]
            date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
            occurred = (1 if reported == True else 0)
        else:
            return
        
        with sqlite3.connect(rta_log_db) as db:
        # Figure out which ID this entry should have.
            last_id = db.execute(
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

            db.execute('insert into fault_log values (?, ?, ?, ?, ?)',
                       (new_id, int(sign_id), date, error_code, occurred))
