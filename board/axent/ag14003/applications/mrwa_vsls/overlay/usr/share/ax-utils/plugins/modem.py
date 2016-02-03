# Modem-specific function calls.

import axserver, socket, subprocess, struct

validate_modem = {
    'interface': lambda p: type(p) is str or type(p) is unicode,
    'apn': lambda p: type(p) is str or type(p) is unicode,
    'auth_mode': lambda p: p in ('none', 'pap', 'chap'),
    'auth_user': lambda p: type(p) is str or type(p) is unicode,
    'auth_pass': lambda p: type(p) is str or type(p) is unicode,
    'watchdog_enabled': lambda p: p in ('yes', 'no'),
    'watchdog_ip': lambda p: len(socket.inet_aton(p)) == 4}

class modem(axserver.AXServerPlugin):
    # Set network interface settings.
    def set_settings(self,**kwargs):
        iface_parameters = {}
        
        # Validate network interface parameters.
        for p in kwargs.keys():
            try:
                valid = validate_modem[p](kwargs[p])
            except:
                valid = False
            
            if valid is not True:
                raise ValueError('Invalid value "%s" for parameter "%s"' \
                    % (kwargs[p], p))
            else:
                iface_parameters[p] = kwargs[p]
        
        with self.server.get_config_db() as db:
            # Make sure the specified interface exists in the specified
            # table.
            try:
                result = db.execute('select * from modem where interface=?',
                    (iface_parameters['interface'],)).fetchone()
            except KeyError:
                raise ValueError('No valid interface name given')
            else:
                if result is None:
                    raise ValueError('Specified interface does not exist')
            
            # Store the parameters in the database.
            for p in iface_parameters.keys():
                db.execute('update modem set ' + p + '=? where interface=?',
                    (iface_parameters[p], iface_parameters['interface']))
    
    # Get network interface settings.
    def get_settings(self):
        iface_list = {}
        
        # Iterate through the modem table to get all interfaces.
        with self.server.get_config_db() as db:
            results = db.execute('select * from modem').fetchall()
        
        for r in results:
            iface_list[r['interface']] = dict(r)
        
        return iface_list
    
    # Return information on network interfaces.
    # If iface_type not specified, look for iface_name in all tables.
    # If iface_name not specified, return info on all interfaces in the
    # selected table/s.
    def status(self):
        iface_list = []
        iface_data = {}
        
        # Iterate through the modem table to get all interfaces.
        with self.server.get_config_db() as db:
            results = db.execute('select interface from modem').fetchall()
        
        iface_list.extend((r[0] for r in results))
        
        # Now we have a list of the interfaces for which we should return
        # information.
        for i in iface_list:
            iface_info = {}
        
            try:
                addr_info = subprocess.check_output(
                    ['/sbin/ip', 'addr', 'show', i], stderr=-1)
            except subprocess.CalledProcessError:
                iface_info['present'] = False
            else:
                # Parse address info.
                if addr_info.find('can\'t find device') >= 0:
                    # Device not present.
                    iface_info['present'] = False
                else:
                    iface_info['present'] = True
                    l = addr_info.split('\n')
                    iface_info['flags'] = \
                        l[0][l[0].find('<')+1:l[0].find('>')].split(',')
                    
                    try:
                        iface_info['hw_address'] = l[1].strip().split(' ')[1]
                    except IndexError:
                        iface_info['hw_address'] = ''
                    
                    if len(l) > 2:
                        if 'inet' in l[2].strip().split():
                            try:
                                iface_info['address'] = \
                                    l[2].strip().split()[1].split('/')[0]
                            except IndexError:
                                iface_info['address'] = ''
                            
                            try:
                                iface_info['netmask'] = socket.inet_ntoa(
                                    struct.pack('<I', 2**int(
                                    l[2].strip().split()[1].split('/')[1])-1))
                            except IndexError:
                                iface_info['netmask'] = ''
                        else:
                            iface_info['address'] = ''
                            iface_info['netmask'] = ''
                        
                        if 'brd' in l[2].strip().split():
                            try:
                                iface_info['bc_address'] = \
                                    l[2].strip().split()[3]
                            except IndexError:
                                iface_info['bc_address'] = ''
                        else:
                            iface_info['bc_address'] = ''
                    else:
                        iface_info['address'] = ''
                        iface_info['netmask'] = ''
                        iface_info['bc_address'] = ''
            
            iface_data[i] = iface_info
        
        return iface_data
