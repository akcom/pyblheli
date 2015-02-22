#!/usr/bin/python
import blhelihex
import curses
import curses.wrapper
import os.path
import sys

def show_help(scr, command=None):
    scr.addstr('Help! How do I use this?\n')
    if command is None:
        text = """List of commands:
        help                 display this message
        help <command>       display additional help for a command
        oh <filename>        open hex file for editing
        sh <filename>        save edited hex to new filename
        ls                   list settings & their current values
        es <setting>         edit setting value
        vs <setting>         view setting value
        quit                 exit this program
        """
        scr.addstr(text)
    elif command == 'help':
        scr.addstr('You think you\'re funny, doncha?')
    elif command == 'oh':
        text = """oh <filename>
        open a hex file for reading.
        note that for atmel ESC's, you should open the '.EEP' file
        but for SiLab ESC's you should open the '.HEX' file"""
        scr.addstr(text)
    elif command == 'sh':
        text = """sh <filename>
        save edited hex to a new file.  pyblheli will not overwrite
        files by default.  To overwrite a file, prepend the filename
        with a bang.

        Example: sh !BS12A_MULTI.EEP"""
        scr.addstr(text)
    elif command == 'ls':
        text ="""ls
        list settings and their current values."""
        scr.addstr(text)
    elif command == 'es':
        text = """es <setting>
        edit setting value.  if this setting is constrained to
        predefined values you will be shown a list of possible
        values.  You will then be prompted to enter the new value.
        For convenience, you can enter just the beginning of a
        setting name as long as it is unambiguous.

        Example: es pwm"""
        scr.addstr(text)
    elif command == 'vs':
        text = """vs <setting>
        view setting value.  displays the current value for an
        individual setting along with all possible values for
        that setting.  For convenience, you can enter just the
        beginning of a setting name as long as it is unambiguous.

        Example: vs beacon-s"""
        scr.addstr(text)
    elif command == 'quit':
        scr.addstr('quit\n\tquit without saving changes')

def input_line(scr):
    maxy, maxx = scr.getmaxyx()
    y = maxy-1
    x = 0
    scr.addch(y,x, ":")
    return scr.getstr(y,x+1)

def show_title(scr):
    y,x = scr.getmaxyx()
    x /=2
    x -= 20
    y = 1
    scr.addstr(y, x, 'PyBLHeli - because real men use the terminal')
    scr.addstr(y+1, x, '   by akcom')
    scr.move(y+3, 0)

def print_err(scr, text):
    scr.addstr('ERROR: %s' % text)

def find_setting(lst, prefix):
    #given a prefix (ex: pwm) find a matching setting from the lst
    #if there is more than one match, return none
    result = None
    prefix = prefix.lower()
    for x in lst:
        if x.startswith(prefix):
            #more than one match
            if result is not None:
                return None
            result = x
    return result

def main(scr):
    curses.start_color()
    curses.echo()

    #set to True after the first run
    init = False
    blh = blhelihex.BLHeliHex()
    scr.scrollok(True)

    #set to true once we've opened a file and the other commands are available
    file_opened = False

    while True:
        #initialize, if not done already
        if init is False:
            #write the title
            show_title(scr)
            #show the help message
            show_help(scr)
            init = True

        #show the screen
        scr.refresh()

        #get the input and parse
        line = input_line(scr)
        line = line.split(' ')
        cmd = line[0]
        args = line[1:]

        #clear the screen
        scr.erase()
        #write the title
        show_title(scr)

        valid_commands = ['help', 'quit', 'oh', 'sh', 'ls', 'es', 'vs']
        if cmd not in valid_commands:
            print_err(scr, 'Unrecognized command')
            continue


        if cmd == 'help':
            #help
            if len(args) == 1:
                show_help(scr, args[0])
            else:
                show_help(scr)
        elif cmd == 'quit':
            #quit
            break
        elif cmd == 'oh':
            #open hex file
            if len(args) == 1:
                extension = args[0].split('.')[-1].upper()
                #validate the extension, EEP = Atmel, HEX = SiLabs
                try:
                    if extension == 'EEP' or extension == 'HEX':
                        is_atmel = extension == 'EEP' or args[-2] == 'EEP'
                        blh.read(args[0], atmel=is_atmel)
                        scr.addstr('File read successfully')
                        file_opened = True
                    else:
                        print_err(scr,
                            'Unknown file type (only HEX and EEP accepted)')
                except Exception as e:
                    print_err(scr, 'Unable to read file: %s' % e)

            else:
                show_help(scr, 'oh')
        elif not file_opened:
            #the rest of the commands can only be used once a file is opened
            print_err(scr, 'Must open a file first')
        elif cmd == 'sh':
            #save hex file
            if len(args) == 1:
                if os.path.isfile(args[0]):
                    print_err(scr,
                              'File exists, prepend with bang to overwrite')
                    continue
                if args[0][0] == '!':
                    args[0] = args[0][1:]
                try:
                    blh.write(args[0])
                    scr.addstr('File written')
                except Exception as e:
                    print_err(scr, 'Unable to write file: %s' % e)

            else:
                show_help(scr, 'sh')
        elif cmd == 'ls':
            #list settings
            items = blh.keys()

            #list in two columns, code is ugly sorry
            for i in range(0, len(items), 2):
                k = items[i]
                #first column text
                s1 = ''
                s2 = ''
                try:
                    s1 = '%s => %s' % (k, blh.printable(k))

                    #second column text
                    if i+1 < len(items):
                        k = items[i+1]
                        s2 = '%s => %s' % (k, blh.printable(k))
                    else:
                        s2 = ''
                except Exception as e:
                    scr.addstr('Error reading value @ %s - %s' % (k,e))

                #concatenate the columns
                line = '%-32s %s\n' % (s1, s2)
                scr.addstr(line)
                scr.refresh()
        elif cmd == 'es' or cmd == 'vs':
            #code is essentially the same except ES has a prompt at the end
            if len(args) != 1:
                show_help(scr, cmd)
                continue

            #look up the setting in case the user passed us a partial
            setting = find_setting(blh.keys(), args[0])
            if setting is None:
                print_err(scr, 'Ambiguous or unknown setting "%s"' % args[0])
                continue

            #print the current value
            scr.addstr('%s => %s\n\n' % (setting, blh.printable(setting)))

            #check to make sure its not read only

            #see if we can print constraints
            constraints = blh.constraints(setting)
            if constraints is not None:
                scr.addstr('Possible values:\n')
                for kk,vv in constraints.items():
                    scr.addstr('\t%-4s (%s)\n' % (kk,vv))

            if cmd == 'es':
                scr.addstr('\nSelect a new value\n')
                y,x = scr.getyx()
                val = input_line(scr)
                scr.move(y,x)
                try:
                    int_val = int(val)
                    blh[setting] = int_val
                    scr.addstr('%s updated' % setting)
                except Exception as e:
                    print_err(scr, 'Unable to set %s to %s: %s' %\
                              (setting, val, e))



def wrap():
    curses.wrapper(main)

if __name__ == '__main__':
    wrap()
