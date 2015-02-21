#!/usr/bin/python
import blhelihex
import curses
import curses.wrapper

##EXAMPLE USAGE
def example():
    #initialize the blheli hex reader
    blh = blhelihex.BLHeliHex(atmel=False)
    #read a hex file
    blh.read('test2.hex')

    #once the hex has been, a BLHeliHex functions much like a dict object
    #it implements keys() - returns all setting names
    #it implements values() - returns all setting values
    #it implements items()/iteritems() - returns all
    #   key,value pairs as a list of tuples
    #there are also some additional functions as well

    #print the list of settings
    print('Old settings:')
    blh.print_settings()

    #to get a list of valid inputs for a given setting, use blh.constraints()
    constraints = blh.constraints('closed-loop')

    #constraints now bound to a dict that
    #maps bl heli value => human readable value
    print('\nValid values for "closed-loop" include:')
    for k,v in constraints.iteritems():
        print('%s => %s' % (k,v))

    #for the settings, you must provide the value as BLHeli expects it
    #check self.LAYOUT in BLHeliHex.__init__ for what these values mean

    blh['motor-gain'] = 1 #motor gain = x0.75
    blh['closed-loop'] = 2 #closed loop = MidRange
    blh['temp-protection'] = 2 #temp protection = Disabled

    #uncommenting the following line will raise an exception upon execution
    #you cannot change read-only settings
    #blh['fw-rev'] = 123

    #for the ppm settings, you can input the ppm value directly
    blh['ppm-min-throttle'] = 1140

    #blh.print_settings()

    blh.write('out2.hex')

def main():
    example()


if __name__ == '__main__':
    main()
