import binascii

class ConstraintException(Exception):
    """this is exception is thrown when attempting to change a setting to an
    invalid value.  not all setting types validate input, only those with a
    dictionary for the 'fmt' key (see BLHeliHex.LAYOUT)"""
    def __init__(self, name, supplied_val, constraint_dict):
        msg = '%s is not a valid value for "%s"' % (supplied_val, name,)
        msg += '\nplease use one of the following:\n'
        for k,v in constraint_dict.iteritems():
            msg += '%s (%s)\n' % (k,v,)
        self.msg = msg
        super(ConstraintException, self).__init__(self, msg)

    def __str__(self):
        return self.msg

class BLHeliHex(object):
    """The main class for reading BLHeli hex files"""
    def __init__(self, atmel):

        #self.LAYOUT maps each setting to its various dependents
        #'pos' is the byte position in th eeprom
        #'fmt' is how to translate the value to a human readable format
        #'val' (added after reading) is the integer value read from the hex
        #'input_fn' is only for settings where BLHeli transforms the raw data
        #   ex: ppm-min-throttle where the byte value is transformed to
        #   the actual ppm value by x*4+1000.  The input function is the
        #   inverse, so you can say hex['ppm-min-throttle'] = 1138 and the code
        #   will put the correct byte value (1138-1000)/4 into the hex
        #'read-only' is present and set to true for read only fields such as
        #   the signature, firmware revision, etc

        self.LAYOUT = {
            #firmware revision
            'fw-rev': {'pos': 0, 'fmt' : int, 'read-only' : True },
            #firmware subrevision
            'fw-subrev': {'pos': 1, 'fmt': int, 'read-only' : True},
            #eeprom layout revision
            'fw-eeprom-layout-rev': {'pos': 2, 'fmt': int, 'read-only' : True},
            #eeprom signature high byte
            'signature-hi' : {'pos':13, 'fmt': hex,
                'read-only' : True}, #should be 0x55
            #eeprom signature low byte
            'signature-lo' : {'pos':14, 'fmt': hex,
                'read-only' : True}, #should be 0xaa
            #temperature protection
            'temp-protection' : {'pos': 35,
                'fmt': {1: 'Enabled', 2: 'Disabled'}},
            #motor direction
            'motor-direction': {'pos': 11,
                'fmt' : {1: 'Normal', 2: 'Reversed', 3: 'Bidirectional'}},
            #demag compensation
            'demag-comp': {'pos': 31,
                'fmt': {1: 'Disabled', 2: 'Low', 3: 'High'}},
            #pwm frequency
            'pwm-freq': {'pos': 10,
                'fmt': {1: 'High', 2: 'Low', 3: 'DampedLight' }},
            #motor timing
            'motor-timing': {'pos': 21,
                'fmt': {1: 'Low', 2: 'MediumLow', 3: 'Medium',
                4: 'MediumHigh', 5: 'High'}},
            #input polarity
            'input-polarity': {'pos': 12,
                'fmt': {1: 'Positive', 2: 'Negative'}},
            #beep strength
            'beep-strength': {'pos': 27, 'fmt': int},
            #beacon strength
            'beacon-strength': {'pos': 28, 'fmt': int},
            #beacon delay
            'beacon-delay': {'pos': 29,
                'fmt': {1:'1 minute', 2: '2 minutes', 3: '5 minutes',
                4: '10 minutes', 5: 'infinite'}},
            #ppm min for throttle
            'ppm-min-throttle': {'pos': 25,
                'fmt': lambda x: x*4+1000, 'input_fn': lambda x: (x-1000)/4 },
            #ppm max for throttle
            'ppm-max-throttle': {'pos': 26,
                'fmt': lambda x: x*4+1000, 'input_fn': lambda x: (x-1000)/4 },
            #low voltage limiter
            'low-volt-limiter': {'pos': 6, 'fmt': {1: 'Off', 2: '3.0V/c',
                3: '3.1V/c', 4: '3.2V/c', 5: '3.3V/c', 6: '3.4V/c'}},
            #closed loop ('governor') mode
            'closed-loop': {'pos': 5,
                'fmt': {1: 'HiRange', 2: 'MidRange', 3: 'LoRange', 4: 'Off'}},
            #motor gain
            'motor-gain': {'pos': 7,
                'fmt' : {1:0.75, 2: 0.88, 3: 1.00, 4:1.12, 5: 1.25}}
            }

        #remember if this is an atmel hex, not currently supported
        self.atmel = atmel
        if self.atmel is True:
            raise Exception('ATMEL support not available (yet!)')

        #upon reading the settings, this is set to the index of the first line
        #in the hex which describes the settings
        self.settings_first_line_idx = -1
        #and the last line
        self.settings_last_line_idx = -1
        #the actual byte buffer of the settings
        self.settings_buf = None

        #upon reading, this is set to the hex file data as a list of lines
        self.data = None

    def printable(self, setting_name):
        """returns the current value for a given setting
        in human readable format"""
        v = self.LAYOUT[setting_name]
        fmt = v['fmt']
        if type(fmt) is dict:
            return fmt[v['val']]
        elif type(fmt) is type(int):
            return v['val']
        elif callable(fmt):
            return fmt(v['val'])
        else:
            raise Exception('Unknown format type for %s (%s)' %
                            (setting_name, type(fmt),))


    def constraints(self, setting_name):
        """if the given setting name has a dictionary list of possible values,
        return the dictionary (k,v maps blheli value => human readable value)
        otherwise return None"""
        v = self.LAYOUT[setting_name]
        fmt = v['fmt']
        if type(fmt) is dict:
            return dict(fmt)
        else:
            return None

    def read(self, filename):
        """read the settings from a hex file"""
        with open(filename, 'r') as f:
            self.data = f.read().split('\n')

        hex_buf = ''
        in_settings = False  #set to True when we hit the settings block
        num_lines = 0
        if self.atmel:
            line_start = ':100000'
        else:
            line_start = ':101A00'
        #find all the settings lines and concatenate them into one hex buffer
        for idx, line in enumerate(self.data):
            #check to see if we're in the settings
            #if so, keep reading until we hit the end which is demarcated by
            #a line with <16 bytes
            if in_settings is True:
                #we count lines strictly as a sanity check, if this gets
                #above 10 (arbitrarily) we've done something wrong
                num_lines += 1
                if num_lines > 10:
                    raise Exception('Somethings fucky.  Should not have \
                                    ten lines of settings')
                #append this line
                hex_buf += line[9:-2]
                #check the length to see if we're done
                line_len = int(line[1:3],16)
                if line_len < 16:
                    #this is the last line
                    self.settings_last_line_idx = idx
                    break
            #settings for SiLabs start at 1A00, so we look for ':101A00'
            #determine if we've found the settings block
            if line.find(line_start) == 0:
                in_settings = True
                hex_buf = line[9:-2]
                self.settings_first_line_idx = idx
                num_lines = 1

        #decode the hex into a byte string
        self.settings_buf = bytearray(hex_buf.decode('hex'))
        #read the actual settings
        for v in self.LAYOUT.values():
            idx = v['pos']
            v['val'] = self.settings_buf[idx]

    def _checksum(self, bytearr):
        """intel HEX file - line checksum function"""
        chk = 0
        for b in bytearr:
            chk += b
        return self._twos_comp(chk & 0xFF)

    def _twos_comp(self, val):
        """returns the two's complement of an 8 bit
        number, used for checksums"""
        return (~val & 0xFF)+1

    def print_settings(self):
        """prints all the settings and their values
        in a two column format for easy viewing"""
        keys = self.LAYOUT.keys()
        #display settings in two columns
        s1 = ''
        s2 = ''
        for i in range(0, len(keys), 2):
            s1 = '%s => %s' % (keys[i], self.printable(keys[i]),)
            if i+1 < len(keys):
                s2 = '%s => %s' % (keys[i+1], self.printable(keys[i+1]), )
            else:
                s2 = ''
            print '%-32s %s' % (s1, s2)

    def write(self, filename):
        """writes the updated hex data to 'filename'"""
        if self.settings_first_line_idx == -1 or self.data is None:
            raise Exception('Must read a hex file first')

        #start address
        if self.atmel:
            base_addr = 0x0000
        else:
            base_addr = 0x1A00
        #length of settings buf
        s_len = len(self.settings_buf)
        i = 0

        lines = []
        #write it into intel hex format lines
        while i < s_len:
            #line length
            l_len = 16
            #make sure we don't overrun
            if s_len - i < 16:
                l_len = s_len - i

            #format is  :llaaaarr[nn..]cc
            #ll = line length (# of bytes, length of n)
            #aaaa = address
            #rr = record type (0x00 = data)
            #nn.. = data
            #cc = checksum, twos complement of (sum(nn..) & 0xFF)

            addr = base_addr + i

            line = bytearray()
            #line length + address
            line += bytearray([l_len, (addr & 0xFF00) >> 8, addr & 0xFF])
            #record type
            line.append(0x00)
            #data
            line += self.settings_buf[i:i+l_len]
            chksum = self._checksum(line)
            #checksum
            line.append(chksum)

            lines.append(':'+binascii.hexlify(line).upper())

            i += 16

        #chop out the old settings and insert the new
        file_data = self.data[0:self.settings_first_line_idx] +\
            lines + self.data[self.settings_last_line_idx+1:]

        with open(filename,'w') as f:
            f.write('\n'.join(file_data))


    def __getitem__(self, name):
        """allows one to do blheliobj['setting-name'] to retrieve a value"""
        if name in self.LAYOUT:
            return self.LAYOUT[name]['val']
        else:
            raise Exception('unrecognized setting "%s"' % name)

    def __setitem__(self, name, value):
        """allows one to do blheliobj['setting-name'] = val to set a value"""
        #make sure we're updating a valid setting
        if hasattr(self, 'LAYOUT') and name in self.LAYOUT:
            v = self.LAYOUT[name]

            #make sure its not read only
            if v.get('read-only') is True:
                raise Exception('cannot change read only setting "%s"' % name)

            #make sure value is valid by checking against the dictionary
            #only useful in settings where 'fmt' key maps to a dict
            #see BLHeliHex.LAYOUT for more information
            fmt = v['fmt']
            if type(fmt) is dict:
                constraints = fmt.keys()
                if value not in constraints:
                    raise ConstraintException(name, value, fmt)

            #check to see if we need to reformat user input
            #this is done specifically for PPM values where
            #a value such as 1044 has to be transformed to BLHeli's
            #interpretationg by (1044-1000)/4
            #that transformation is the 'input_fn' function
            if 'input_fn' in v:
                v['val'] = v['input_fn'](value)
            else:
                v['val'] = value
            #update the setting in the actual byte buffer as well
            idx = v['pos']
            self.settings_buf[idx] = v['val']
        else:
            super(BLHeliHex, self).__setattr__(name, value)

    #keys, values, and items, iteritems represent dict like functions for
    #traversing settings
    def keys(self):
        return self.LAYOUT.keys()

    def values(self):
        for k in self.LAYOUT.keys():
            yield self.LAYOUT[k]['val']

    def iteritems(self):
        for k in self.LAYOUT.keys():
            yield (k, self.LAYOUT[k]['val'])

    def items(self):
        return list(self.iteritems())
