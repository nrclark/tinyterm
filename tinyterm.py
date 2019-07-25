#!/usr/bin/env python3
""" Library and command-line utility for sending serial commands to
a remote Busybox prompt. """

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
        function(*args, **kwargs)
        if callable(old_handler):
            return old_handler(signum, frame)

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


class SerialConsole(object):
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

        reopen_stdin()

    def __call__(self):
        targets = [sys.stdin, self.port]
        trapped_control = False

        print("--- Press [CTRL+A] and then q to quit. ---")

        while True:
            ready = select.select(targets, [], targets)
            if self.port in ready[0]:
                outbound_data = self.port.read()
                sys.stdout.buffer.write(outbound_data)
                sys.stdout.flush()

            if sys.stdin in ready[0]:
                outbound_data = sys.stdin.read()
                if b'\x01q' in outbound_data:
                    print("\n--- Goodbye. ---")
                    break

                elif trapped_control and outbound_data[0:1] == b'q':
                    print("\n--- Goodbye. ---")
                    break

                elif outbound_data[-1:] == b'\x01':
                    trapped_control = True
                    self.port.write(outbound_data[:-1])
                else:
                    if trapped_control:
                        trapped_control = False
                        self.port.write(b'\x01')

                    self.port.write(outbound_data)


def _create_parser():
    """ Creates an argparse parser for the command-line application. """

    parser = argparse.ArgumentParser(description="""Launch a minimal serial
                                     console. Exit with [CTRL+a, q].""")

    parser.add_argument('-d', '--device', dest='device',
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
    args.baud = int(args.baud)
    console = SerialConsole(args.device, args.baud, args.parity)
    console()
    return 0


if __name__ == "__main__":
    main()
