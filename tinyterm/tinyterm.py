#!/usr/bin/env python3
""" Minimalistic serial terminal program. Like Minicom or Screen, except
without any kind of screen-drawing, scroll-trapping, etc. """

import sys
import argparse
import select
import os
import tty
import fcntl
import atexit
import termios
import signal

import serial


def register_cleanup(function, *args, **kwargs):
    """ Registers a function with atexit and the system exception handler.
    Function will be called once at exit, regardless of whether the exit was
    intentional or not. """

    # pylint: disable=missing-docstring

    def cleanup():
        if not cleanup.called:
            function(*args, **kwargs)
            cleanup.called = True

    cleanup.called = False
    atexit.register(cleanup)
    old_hook = sys.excepthook

    def new_hook(exception_type, value, traceback):
        cleanup()
        return old_hook(exception_type, value, traceback)

    sys.excepthook = new_hook


def register_handler(signum, function, *args, **kwargs):
    """ Registers a function with a signal handler. Calls the original signal
    handler (if possible) after running the user-supplied addition. """

    # pylint: disable=missing-docstring

    old_handler = signal.getsignal(signum)

    def handler(signum, frame):
        result = function(*args, **kwargs)

        if callable(old_handler):
            return old_handler(signum, frame)

        return result

    signal.signal(signum, handler)


def reopen_stdin():
    """ Reopens stdin as a non-blocking binary file, ready for select() or
    nonblocking read() calls. Modifies terminal settings to allow for raw
    access. Registers functions to restore the existing settings at program
    exit. """

    filedes = os.dup(sys.stdin.fileno())
    sys.stdin.close()

    sys.stdin = os.fdopen(filedes, 'rb', 0)
    stty = termios.tcgetattr(sys.stdin)
    register_cleanup(termios.tcsetattr, sys.stdin, termios.TCSANOW, stty)

    flags = fcntl.fcntl(sys.stdin.fileno(), fcntl.F_GETFL)
    fcntl.fcntl(sys.stdin.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK)
    tty.setcbreak(sys.stdin)


class SerialConsole():
    """ Simple serial console. Passes all characters through as transparently
    as possible. Exit with [CTRL+a, q]. """

    # pylint: disable=too-few-public-methods

    def __init__(self, device='/dev/ttyUSB0', baudrate=115200, parity='N'):
        self.port = serial.Serial(device, baudrate=baudrate, parity=parity,
                                  timeout=0)
        register_cleanup(self.port.close)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        register_handler(signal.SIGINT, self.port.write, b'\x03')

        self.port.reset_input_buffer()
        self.port.reset_output_buffer()
        self.ctrl_a = b'\x01'
        self.stop = False

        reopen_stdin()

    def __call__(self):
        """ Runs the terminal, passing data from stdin to the serial port
        and back. Traps and interpets CTRL+a. """

        targets = [sys.stdin, self.port]
        trap_next = False
        self.stop = False
        outbuf = []

        print("--- Press [CTRL+A] and then q to quit. ---")

        while True:
            ready = select.select(targets, [], targets)

            if self.port in ready[0]:
                data = self.port.read()
                sys.stdout.buffer.write(data)
                sys.stdout.flush()

            if sys.stdin in ready[0]:
                data = sys.stdin.read()
                data = [data[x:x + 1] for x in range(len(data))]

                for char in data:
                    if trap_next:
                        outbuf.append(self.interpret(char))
                        trap_next = False
                    elif char == self.ctrl_a:
                        trap_next = True
                    else:
                        outbuf.append(char)

                if self.stop:
                    break

                self.port.write(b''.join(outbuf))
                outbuf.clear()

        print("\n--- Goodbye. ---")

    def interpret(self, char):
        """ Interprets a trapped control character. Returns a bytes()
        instance that is sent to the attached port. """

        if char in [b'q', b'Q', b'k', b'K', b'\\']:
            self.stop = True
            return b''

        if char in [b'r', b'R']:
            commands = [
                "export TERM=%s" % os.getenv('TERM', 'vt100'),
                "resize",
                "reset"
            ]
            prefix = bytes("\x01\x0B\ntrue\n", 'utf-8')
            result = prefix + bytes(' && '.join(commands) + '\n', 'utf-8')
            return result

        if char in [b'?']:
            self.print_help()
            return b''

        return char

    @staticmethod
    def print_help():
        """ Prints TinyTerm's help menu to the screen. """

        print("Tiny-term commands:")
        print(r" [CTRL+a, (q, k, or \)]: Exit")
        print(r" [CTRL+a, r]:            Send shell commands terminal-config")
        print(r" [CTRL+a, CTRL+a]:       Send literal CTRL+a")
        print(r" [CTRL+a, ?]:            Show this menu")


def _create_parser():
    """ Creates an argparse parser for the command-line application. """

    parser = argparse.ArgumentParser(description="""Launch a minimal serial
                                     console. Exit with [CTRL+a, q].""")

    parser.add_argument('-d', '-D', '--device', dest='device',
                        default='/dev/ttyUSB0', help="Target serial port")

    parser.add_argument('-b', '--baud', dest='baud', default='115200',
                        help="Serial baud rate (default: 115200)")

    parser.add_argument('-p', '--parity', dest='parity', default='N',
                        help="Serial parity (default: None)")

    return parser


def main():
    """ Command-line application for this utility. """

    parser = _create_parser()
    args = parser.parse_args()
    args.parity = args.parity.strip().upper()[0]

    if args.parity not in ['E', 'O', 'N']:
        sys.stderr.write("Error: unknown parity setting [%s].\n" % args.parity)
        sys.exit(1)

    try:
        args.baud = int(args.baud)
    except ValueError:
        sys.stderr.write("Error: couldn't parse baud rate [%s].\n" % args.baud)
        sys.exit(1)

    if not os.path.exists(args.device):
        sys.stderr.write("Error: couldn't find device [%s].\n" % args.device)
        sys.exit(1)

    console = SerialConsole(args.device, args.baud, args.parity)
    console()


if __name__ == "__main__":
    main()
