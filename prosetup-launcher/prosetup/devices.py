"""Список подключённых USB/Bluetooth-устройств игровой периферии (только чтение).

Используется SetupAPI Windows: названия моделей берутся из того, что сообщает
само устройство (Bus reported device description), а не из таблиц в коде.
Никаких команд устройствам не отправляется.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .winapi import IS_WINDOWS

log = logging.getLogger(__name__)

VENDORS = {
    "046D": "Logitech",
    "31E3": "Wooting",
    "1038": "SteelSeries",
    "1532": "Razer",
}

# Официальное ПО производителей, где настраивается Rapid Trigger
VENDOR_SOFTWARE = {
    "31E3": ("Wootility", "https://wooting.io/wootility"),
    "1038": ("SteelSeries GG", "https://steelseries.com/gg"),
    "1532": ("Razer Synapse", "https://www.razer.com/synapse-4"),
}

_USB_RE = re.compile(r"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})")
_BT_RE = re.compile(r"VID&0[12]([0-9A-F]{4})_PID&([0-9A-F]{4})")


@dataclass
class Device:
    vid: str
    pid: str
    name: str = ""
    classes: set[str] = field(default_factory=set)

    @property
    def vendor(self) -> str:
        return VENDORS.get(self.vid, self.vid)

    @property
    def key(self) -> str:
        return f"{self.vid}:{self.pid}"

    @property
    def is_receiver(self) -> bool:
        return "receiver" in self.name.lower()

    @property
    def is_mouse(self) -> bool:
        return "mouse" in self.classes

    @property
    def is_keyboard(self) -> bool:
        return "keyboard" in self.classes

    @property
    def display_name(self) -> str:
        name = self.name or f"Устройство {self.vid}:{self.pid}"
        return f"{self.vendor} {name}" if not name.lower().startswith(self.vendor.lower()) else name

    @property
    def kind_text(self) -> str:
        if self.is_receiver:
            return "приёмник — модель мыши/клавиатуры за ним Windows не сообщает"
        kinds = [k for k, flag in (("мышь", self.is_mouse), ("клавиатура", self.is_keyboard)) if flag]
        return ", ".join(kinds) or "другое устройство"


def parse_ids(instance_id: str) -> tuple[str, str] | None:
    upper = instance_id.upper()
    match = _USB_RE.search(upper) or _BT_RE.search(upper)
    return (match.group(1), match.group(2)) if match else None


def list_devices(vendors: tuple[str, ...] = tuple(VENDORS)) -> list[Device]:
    """Подключённые устройства указанных производителей, сгруппированные по VID:PID."""
    if not IS_WINDOWS:
        return []
    try:
        nodes = _enumerate_nodes()
    except OSError as exc:
        log.error("SetupAPI недоступен: %s", exc)
        return []
    return group_nodes(nodes, vendors)


def group_nodes(nodes, vendors) -> list[Device]:
    """nodes: (instance_id, класс, bus-reported описание, описание)."""
    devices: dict[tuple[str, str], Device] = {}
    for instance_id, cls, bus_desc, desc in nodes:
        ids = parse_ids(instance_id)
        if not ids or ids[0] not in vendors:
            continue
        dev = devices.setdefault(ids, Device(*ids))
        if cls:
            dev.classes.add(cls.lower())
        # Имя из USB-узла самое точное; общие имена Windows («HID-compliant mouse») хуже
        candidate = bus_desc or ""
        if candidate and (not dev.name or instance_id.upper().startswith("USB\\")):
            dev.name = candidate.strip()
        elif not dev.name and desc and "hid" not in desc.lower():
            dev.name = desc.strip()
    return sorted(devices.values(), key=lambda d: (d.vendor, d.name))


# ---------------------------------------------------------------------------
if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _setupapi = ctypes.WinDLL("setupapi", use_last_error=True)

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

    class SP_DEVINFO_DATA(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("ClassGuid", GUID),
                    ("DevInst", wintypes.DWORD), ("Reserved", ctypes.c_size_t)]

    class DEVPROPKEY(ctypes.Structure):
        _fields_ = [("fmtid", GUID), ("pid", wintypes.ULONG)]

    def _guid(text: str) -> GUID:
        import uuid
        u = uuid.UUID(text)
        g = GUID()
        g.Data1, g.Data2, g.Data3 = u.fields[0], u.fields[1], u.fields[2]
        for i, b in enumerate(u.bytes[8:]):
            g.Data4[i] = b
        return g

    DEVPKEY_BUS_REPORTED_DESC = DEVPROPKEY(_guid("540b947e-8b40-45bc-a8a2-6a0b894cbda2"), 4)
    DIGCF_PRESENT = 0x2
    DIGCF_ALLCLASSES = 0x4
    SPDRP_DEVICEDESC = 0x0
    SPDRP_CLASS = 0x7
    ERROR_NO_MORE_ITEMS = 259
    INVALID_HANDLE = ctypes.c_void_p(-1).value

    _setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
    _setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE
    _setupapi.SetupDiEnumDeviceInfo.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(SP_DEVINFO_DATA)]
    _setupapi.SetupDiEnumDeviceInfo.restype = wintypes.BOOL
    _setupapi.SetupDiGetDeviceInstanceIdW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(SP_DEVINFO_DATA), wintypes.LPWSTR, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD)]
    _setupapi.SetupDiGetDeviceInstanceIdW.restype = wintypes.BOOL
    _setupapi.SetupDiGetDeviceRegistryPropertyW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(SP_DEVINFO_DATA), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    _setupapi.SetupDiGetDeviceRegistryPropertyW.restype = wintypes.BOOL
    _setupapi.SetupDiGetDevicePropertyW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(SP_DEVINFO_DATA), ctypes.POINTER(DEVPROPKEY),
        ctypes.POINTER(wintypes.ULONG), ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        wintypes.DWORD]
    _setupapi.SetupDiGetDevicePropertyW.restype = wintypes.BOOL
    _setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
    _setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL


def _enumerate_nodes() -> list[tuple[str, str, str, str]]:
    handle = _setupapi.SetupDiGetClassDevsW(None, None, None, DIGCF_PRESENT | DIGCF_ALLCLASSES)
    if handle in (None, 0, INVALID_HANDLE):
        raise ctypes.WinError(ctypes.get_last_error())
    nodes: list[tuple[str, str, str, str]] = []
    buf = ctypes.create_unicode_buffer(1024)
    try:
        index = 0
        while True:
            data = SP_DEVINFO_DATA()
            data.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
            if not _setupapi.SetupDiEnumDeviceInfo(handle, index, ctypes.byref(data)):
                if ctypes.get_last_error() == ERROR_NO_MORE_ITEMS:
                    break
                index += 1
                continue
            index += 1
            if not _setupapi.SetupDiGetDeviceInstanceIdW(handle, ctypes.byref(data), buf, len(buf), None):
                continue
            instance_id = buf.value
            ids = parse_ids(instance_id)
            if not ids or ids[0] not in VENDORS:
                continue  # чужие устройства не опрашиваем
            nodes.append((
                instance_id,
                _registry_string(handle, data, SPDRP_CLASS),
                _bus_reported(handle, data),
                _registry_string(handle, data, SPDRP_DEVICEDESC),
            ))
    finally:
        _setupapi.SetupDiDestroyDeviceInfoList(handle)
    return nodes


def count_present_devices() -> int:
    """Число всех подключённых устройств — для самопроверки SetupAPI."""
    if not IS_WINDOWS:
        return 0
    handle = _setupapi.SetupDiGetClassDevsW(None, None, None, DIGCF_PRESENT | DIGCF_ALLCLASSES)
    if handle in (None, 0, INVALID_HANDLE):
        raise ctypes.WinError(ctypes.get_last_error())
    count = 0
    try:
        data = SP_DEVINFO_DATA()
        data.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
        while _setupapi.SetupDiEnumDeviceInfo(handle, count, ctypes.byref(data)):
            count += 1
    finally:
        _setupapi.SetupDiDestroyDeviceInfoList(handle)
    return count


def _registry_string(handle, data, prop: int) -> str:
    buf = ctypes.create_unicode_buffer(512)
    if _setupapi.SetupDiGetDeviceRegistryPropertyW(
            handle, ctypes.byref(data), prop, None, buf, ctypes.sizeof(buf), None):
        return buf.value
    return ""


def _bus_reported(handle, data) -> str:
    buf = ctypes.create_unicode_buffer(512)
    prop_type = wintypes.ULONG()
    if _setupapi.SetupDiGetDevicePropertyW(
            handle, ctypes.byref(data), ctypes.byref(DEVPKEY_BUS_REPORTED_DESC),
            ctypes.byref(prop_type), buf, ctypes.sizeof(buf), None, 0):
        return buf.value
    return ""
