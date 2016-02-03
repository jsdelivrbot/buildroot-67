# VSLS-specific player functions.

import cairo, sqlite3, jsonrpclib
import fcntl, struct, mmap, time, multiprocessing, datetime
import axserver

log_db = '/usr/share/db/log.db'

def create_log(sign_id, old, new):
    event = 'Display changed from %s to %s' % (str(old), str(new))

    with sqlite3.connect(log_db) as db:
        db.execute('insert into event_log (sign_id, type, event, date) \
                    values (?, ?, ?, ?)', (sign_id, 'operation', event,
                                    datetime.datetime.now().strftime(
                                            '%Y-%m-%d %H:%M:%S.%f')))

def render_annulus(lines):
    with open('/dev/fb1', 'r+') as fb:
        # This is an ioctl call to get the variable screen info from a
        # Linux framebuffer device.
        fb_var = fcntl.ioctl(fb, 0x4600, str(bytearray(160)))
        target_width, target_height = struct.unpack('<2L', fb_var[:8])
        
        if int(lines) > target_height:
            raise Exception('Too many lines for annulus')
        
        if int(lines) < 0:
            raise Exception('Number of lines cannot be negative')
        
        # mmap() the framebuffer device.
        mmap_size = target_width * target_height * 4
        pixel_map = mmap.mmap(fb.fileno(), mmap_size)
        pixel_map.seek(0)
        
        # Create a surface for the display.
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
            target_width, target_height)
        context = cairo.Context(surface)
        
        # Blank the surface.
        context.rectangle(0, 0, target_width, target_height)
        context.set_source_rgb(0, 0, 0)
        context.fill()
        
        # Draw required number of annulus lines.
        context.rectangle(0, target_height - int(lines), target_width, target_height)
        context.set_source_rgb(1, 1, 1)
        context.fill()
        
        # Blit the surface to the framebuffer.
        pixel_map.write(surface.get_data())

def render_matrix(speed):
    with open('/dev/fb0', 'r+') as fb:
        # This is an ioctl call to get the variable screen info from a
        # Linux framebuffer device.
        fb_var = fcntl.ioctl(fb, 0x4600, str(bytearray(160)))
        target_width, target_height = struct.unpack('<2L', fb_var[:8])
        
        # mmap() the framebuffer device.
        mmap_size = target_width * target_height * 4
        pixel_map = mmap.mmap(fb.fileno(), mmap_size)
        pixel_map.seek(0)
        
        # Create a surface for the display.
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
            target_width, target_height)
        context = cairo.Context(surface)
        
        # Blank the surface.
        context.rectangle(0, 0, target_width, target_height)
        context.set_source_rgb(0, 0, 0)
        context.fill()
        
        if speed is not None:
            # Load the image for the matrix.
            filename = '/usr/share/frames/%d.png' % int(speed)
            try:
                speed_surface = cairo.ImageSurface.create_from_png(filename)
            except:
                raise Exception('Unable to load specified frame: %d' \
                    % int(speed))
            context.set_source_surface(speed_surface)
            context.paint()
        
        # Blit the surface to the framebuffer.
        pixel_map.write(surface.get_data())

frame_map = {
    0: (False, 0),
    10: (False, 10),
    11: (True, 10),
    20: (False, 20),
    21: (True, 20),
    25: (False, 25),
    26: (True, 25),
    30: (False, 30),
    31: (True, 30),
    40: (False, 40),
    41: (True, 40),
    50: (False, 50),
    51: (True, 50),
    60: (False, 60),
    61: (True, 60),
    70: (False, 70),
    71: (True, 70),
    80: (False, 80),
    81: (True, 80),
    90: (False, 90),
    91: (True, 90),
    100: (False, 100),
    101: (True, 100),
    110: (False, 110),
    111: (True, 110),
    255: (False, 0)
}

class player(axserver.AXServerPlugin):
    def __init__(self, *args, **kwargs):
        super(player, self).__init__(*args, **kwargs)
        
        self.document = 0
        self.running = False
        self.old_document = 0

        class VSLSDisplay(multiprocessing.Process):
            def __init__(self, pipe):
                multiprocessing.Process.__init__(self)
                
                self.pipe = pipe
                self.frame = None
                self.period = 1.0
                self.enabled = False
                self.flashing = False
                self.daemon = True

            def tick(self):
                if self.flashing:
                    current = time.time()
                    # Calculate annulus lines.
                    if current % self.period > self.period/2.0:
                        render_annulus(3)
                    else:
                        render_annulus(1)
                else:
                    render_annulus(3)
                
                render_matrix(self.frame)

            def run(self):
                while True:
                    try:
                        if self.pipe.poll() is True:
                            new_data = self.pipe.recv()
                            if 'enable' in new_data:
                                self.enabled = True if new_data['enable'] \
                                    is True else False
                                if self.enabled is False:
                                    render_matrix(None)
                                    render_annulus(0)
                            if 'frame' in new_data:
                                # Choose frame and flash status based on frame id.
                                if new_data['frame'] == 0 or \
                                   new_data['frame'] == 255:
                                    render_matrix(None)
                                    render_annulus(0)

                                self.flashing, self.frame = \
                                    frame_map[int(new_data['frame'])]
                    except:
                        pass

                    if self.enabled and self.frame != 0:
                        self.tick()
                    time.sleep(0.01)

            def pause(self, pause):
                if pause is True:
                    self.paused = True
                elif pause is False:
                    self.start_tick = time.time()
                    self.paused = False
                    self.time_elapsed = 0
                else:
                    raise Exception('Must be True or False')

        conn1, self.pipe = multiprocessing.Pipe(False)
        self.display = VSLSDisplay(conn1)
        self.display.start()

    def status(self):
        return {
            'document': self.document,
            'running': self.running
        }
    
    def load(self, document):
        flashing, frame = frame_map[int(document)]
        with self.server.get_config_db() as db:
            result = db.execute('select allowed from speeds where frame_id=?',
                (int(frame),)).fetchone()
            if result is not None:
                if str(result[0]) != 'yes':
                    self.logger.warning('Document not allowed: %s' % str(frame))
                    raise Exception('Speed not allowed')
        
        self.old_document = self.document
        self.document = int(document)
        self.pipe.send({'frame': int(document)})
        if self.running is True:
            self.logger.info('Document loaded: %s' % str(self.document))
    
    def start(self):
        if self.running is False or self.document != self.old_document:
            log_change = True
        else:
            log_change = False
        self.running = True
        self.pipe.send({'enable': True})
        self.logger.info('Player started')
        if log_change is True:
            try:
                if self.server.plugins.vsls.sign_id == 1:
                    self.server.plugins.signs.operation(
                        1, self.old_document, self.document)
                else:
                    create_log(self.server.plugins.vsls.sign_id,
                        self.old_document, self.document)
                    self.server.plugins.vsls.xbee._notify.operation(
                        new_frame=int(self.document),
                        old_frame=int(self.old_document))
            except:
                print 'Unable to log operation'
                import traceback
                traceback.print_exc()
    
    def stop(self):
        self.pipe.send({'enable': False})
        
        self.logger.info('Player stopped')
        if self.running is True:
            self.running = False
            try:
                if self.server.plugins.vsls.sign_id == 1:
                    self.server.plugins.signs.operation(
                        1, self.document, 0)
                else:
                    create_log(self.server.plugins.vsls.sign_id,
                        self.old_document, self.document)
                    self.server.plugins.vsls.xbee._notify.operation(
                        new_frame=0,
                        old_frame=int(self.document))
            except:
                print 'Unable to log operation'
                import traceback
                traceback.print_exc()
