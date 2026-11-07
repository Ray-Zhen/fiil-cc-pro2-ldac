"""Activate, enable, and check LDAC on the legacy FIIL CC Pro2 over Windows Bluetooth."""

import argparse
import ctypes
import re
import select
import socket
import struct
import sys
import time
import uuid


SERVICE = uuid.UUID("d52b47bc-2dea-42c4-b26d-20252fceeeb3")
VENDOR = 0x0234
GET_ACTIVATION = 0x07AF
WRITE_ACTIVATION = 0x07B0
SET_SWITCH = 0x07B2
GET_SWITCH = 0x07B3
LOCAL_ACTIVATION = 0x88


def bluetooth_address(value):
    if not re.fullmatch(r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}|[0-9A-Fa-f]{12}", value):
        raise argparse.ArgumentTypeError("Expected a Bluetooth address such as AA:BB:CC:DD:EE:FF.")
    return int(value.replace(":", "").replace("-", ""), 16)


def connect_rfcomm(address, timeout, service=SERVICE):
    if sys.platform != "win32":
        raise OSError("This script uses the Windows Bluetooth socket API.")
    family = getattr(socket, "AF_BLUETOOTH", 32)
    protocol = getattr(socket, "BTPROTO_RFCOMM", 3)
    winsock = ctypes.WinDLL("Ws2_32.dll")
    connect = winsock.connect
    connect.argtypes = (ctypes.c_size_t, ctypes.c_void_p, ctypes.c_int)
    connect.restype = ctypes.c_int
    # Packed SOCKADDR_BTH. Port 0 resolves the custom service UUID by SDP.
    packed_endpoint = struct.pack("<HQ16sI", family, address, service.bytes_le, 0)
    endpoint = ctypes.create_string_buffer(packed_endpoint, len(packed_endpoint))
    stream = socket.socket(family, socket.SOCK_STREAM, protocol)
    try:
        stream.setblocking(False)
        if connect(stream.fileno(), endpoint, ctypes.sizeof(endpoint)):
            error = winsock.WSAGetLastError()
            if error not in (10035, 10036, 10037):
                raise OSError(f"RFCOMM connect failed (Winsock {error}).")
            _, writable, failed = select.select([], [stream], [stream], timeout)
            if not writable and not failed:
                raise TimeoutError("RFCOMM connect timed out.")
            error = stream.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if error:
                raise OSError(f"RFCOMM connect failed (Winsock {error}).")
        stream.settimeout(timeout)
        return stream
    except BaseException:
        stream.close()
        raise


def gaia_frame(command, payload=b""):
    return struct.pack(">BBBBHH", 0xFF, 1, 0, len(payload), VENDOR, command) + payload


class Gaia:
    def __init__(self, stream, timeout, verbose=False):
        self.stream = stream
        self.timeout = timeout
        self.verbose = verbose
        self.buffer = bytearray()

    def read_frame(self, deadline):
        while True:
            start = self.buffer.find(0xFF)
            if start < 0:
                self.buffer.clear()
            elif start:
                del self.buffer[:start]
            if len(self.buffer) >= 2 and self.buffer[1] not in (1, 0xF1):
                del self.buffer[:1]
                continue
            if len(self.buffer) >= 8:
                flags, size = self.buffer[2:4]
                end = 8 + size + (flags & 1)
                if len(self.buffer) >= end:
                    frame = bytes(self.buffer[:end])
                    del self.buffer[:end]
                    return frame
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("No matching GAIA reply.")
            self.stream.settimeout(remaining)
            packet = self.stream.recv(1024)
            if not packet:
                raise ConnectionError("The earphones closed the Bluetooth control connection.")
            self.buffer.extend(packet)

    def request(self, command, payload=b"", min_data=0):
        frame = gaia_frame(command, payload)
        if self.verbose:
            print("TX", frame.hex(" "))
        self.stream.settimeout(self.timeout)
        self.stream.sendall(frame)
        deadline = time.monotonic() + self.timeout
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"No matching GAIA reply to 0x{command:04x}.")
            try:
                reply = self.read_frame(deadline)
            except TimeoutError as exc:
                raise TimeoutError(f"No matching GAIA reply to 0x{command:04x}.") from exc
            if self.verbose:
                print("RX", reply.hex(" "))
            vendor, response_command = struct.unpack_from(">HH", reply, 4)
            if vendor != VENDOR or response_command != (command | 0x8000):
                continue
            data = reply[8:8 + reply[3]]
            if not data:
                raise ValueError(f"GAIA 0x{command:04x} reply has no status.")
            if data[0] != 0:
                raise ValueError(f"GAIA 0x{command:04x} returned status 0x{data[0]:02x}.")
            if len(data) < 1 + min_data:
                raise ValueError(f"GAIA 0x{command:04x} reply is missing data: {data.hex(' ')}")
            return data[1:]

    def activation(self):
        statuses = []
        for side in (1, 0):
            statuses.append(self.activation_state(side))
        return tuple(statuses)

    def activation_state(self, side):
        response = self.request(GET_ACTIVATION, bytes((side,)), min_data=2)
        state = response[1]
        print(f"activation[selector={side}]: {state}")
        return state

    def activate_local(self):
        """Use the firmware's local activation branch on the verified F039 build."""
        states = self.activation()
        if any(state not in (0, 1) for state in states):
            raise ValueError("Both earbuds must report state 0 or 1. Take both out of the case and reconnect")
        for side, state in zip((1, 0), states):
            if state == 1:
                continue
            reply = self.request(WRITE_ACTIVATION, bytes((side, LOCAL_ACTIVATION)), min_data=1)
            if reply[0] != side or self.activation_state(side) != 1:
                raise ValueError(f"Local activation did not verify for selector {side}")

    def switch_state(self):
        state = self.request(GET_SWITCH, min_data=1)[0]
        print(f"LDAC switch: {state}")
        return state


def enable_ldac(address, timeout, verbose):
    with connect_rfcomm(address, timeout) as stream:
        gaia = Gaia(stream, timeout, verbose)
        gaia.activate_local()
        if gaia.switch_state() == 1:
            return
        try:
            gaia.request(SET_SWITCH, b"\x01")
            if gaia.switch_state() == 1:
                return
        except OSError:
            # Switching codecs can restart the earbuds before they send a reply.
            pass

    print("Waiting for the earbuds to reconnect so the switch can be checked.")
    deadline = time.monotonic() + timeout
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            with connect_rfcomm(address, remaining) as stream:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                if Gaia(stream, remaining, verbose).switch_state() == 1:
                    return
        except OSError:
            pass
        time.sleep(max(0, min(1, deadline - time.monotonic())))
    raise TimeoutError("Both earbuds were activated, but the LDAC switch could not be verified")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("enable", "status", "on", "off", "activate-local"))
    parser.add_argument("address", type=bluetooth_address, help="Paired CC Pro2 Bluetooth address")
    parser.add_argument("--timeout", type=float, default=8)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if not 0 < args.timeout <= 120:
        parser.error("--timeout must be greater than 0 and at most 120 seconds")

    try:
        if args.action == "enable":
            enable_ldac(args.address, args.timeout, args.verbose)
            print("Both earbuds report LDAC activation and the switch is on.")
            return 0
        with connect_rfcomm(args.address, args.timeout) as stream:
            gaia = Gaia(stream, args.timeout, args.verbose)
            if args.action == "status":
                gaia.activation()
                gaia.switch_state()
            elif args.action == "activate-local":
                gaia.activate_local()
                print("Both earbuds report LDAC activation.")
            else:
                desired = int(args.action == "on")
                gaia.request(SET_SWITCH, bytes((desired,)))
                print("Switch command acknowledged. If the earphones reboot, reconnect and run status again.")
                if gaia.switch_state() != desired:
                    raise ValueError("The switch did not read back in the requested state.")
    except (OSError, ValueError) as exc:
        print(f"{str(exc).rstrip('.')}. Use status after reconnecting to check the current state.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
