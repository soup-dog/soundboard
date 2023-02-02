from __future__ import annotations

import pyaudio
import tkinter as tk
from tkinter import ttk
from tkinter import font
from tkinter import messagebox
import wave
import re
from typing import Mapping, List, Any
import pickle
from event import Event

import numpy as np
from pynput import keyboard


DeviceParameters = Mapping[str, str | int | float]


def bind(f, *args, **kwargs):
    def bound(*a, **kw):
        return f(*args, *a, **kwargs, **kw)

    return bound


def mix(a: bytes, b: bytes) -> bytes:
    return ((np.frombuffer(a, dtype=np.int16) + np.frombuffer(b, dtype=np.int16)) // 2).tobytes()


def get_device_by_name(name: str, devices: List[DeviceParameters]) -> DeviceParameters:
    return next((device for device in devices if device["name"] == name), devices[0])


class SoundSpec:
    def __init__(self):
        self.name: str = "Sound"
        self.path: str = ""
        self.volume: float = 1
        self.keys: set[keyboard.Key] = set()


class AppInfo:
    VERSION: float = 0.2

    def __init__(self):
        self.version: float = self.VERSION
        self.sounds: List[SoundSpec] = []
        self.echo: bool = True
        self.input_device_name = ""
        self.output_device_name = ""
        self.echo_device_name = ""

    def dumps(self) -> bytes:
        return pickle.dumps(self)

    @staticmethod
    def loads(serialised: bytes) -> AppInfo:
        return pickle.loads(serialised)


class SoundEditor(tk.Toplevel):
    _styles_initialised: bool = False
    ErrorStyleName = "Error.TLabel"

    def __init__(self, master: SoundboardApp, spec: SoundSpec, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        self.app = master
        self.spec = spec

        if not self._styles_initialised:
            self.init_styles()

        self.title("Shiteboard - " + spec.name)

        self.frame = ttk.Frame(self, padding=5)
        self.frame.grid()

        self.name_label = ttk.Label(self.frame, text="Sound Name")
        self.name_label.grid()
        self.name_var = tk.StringVar(value=self.spec.name)
        self.name_entry = ttk.Entry(self.frame, textvariable=self.name_var)
        self.name_entry.grid()

        self.path_label = ttk.Label(self.frame, text="Path")
        self.path_label.grid()
        self.path_var = tk.StringVar(value=self.spec.path)
        self.path_entry = ttk.Entry(self.frame, textvariable=self.path_var)
        self.path_entry.grid()

        self.volume_label = ttk.Label(self.frame, text="Volume")
        self.volume_label.grid()
        self.volume_var = tk.DoubleVar(value=self.spec.volume)
        self.volume_slider = ttk.Scale(self.frame, variable=self.volume_var)
        self.volume_slider.grid()

        self.key_frame = ttk.Frame(self.frame)
        self.key_frame.grid()

        self.key_button = ttk.Button(self.key_frame, text="Set Binding", command=lambda *_: self.set_binding())
        self.key_button.grid(row=0, column=0)

        self.key_label = ttk.Label(self.key_frame, text=self.stringify_keys())
        self.key_label.grid(row=0, column=1)

        self.buttons_frame = ttk.Frame(self.frame, padding=5)
        self.buttons_frame.grid()

        self.delete_button = ttk.Button(self.buttons_frame, text="🗑", command=lambda *_: self.app.remove_sound(self))
        self.delete_button.grid(row=0, column=0)

        self.apply_button = ttk.Button(self.buttons_frame, text="Apply", command=lambda *_: self.apply())
        self.apply_button.grid(row=0, column=1)

        self.test_button = ttk.Button(self.buttons_frame, text="Test", command=lambda *_: self.test())
        self.test_button.grid(row=0, column=2)

        self.error = ttk.Label(self.frame, text="", style=self.ErrorStyleName)
        self.error.grid()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def init_styles(self):
        s = ttk.Style()
        s.configure(self.ErrorStyleName, foreground="red")

    def stringify_keys(self):
        return " ".join(map(str, self.spec.keys))

    def on_close(self) -> None:
        self.app.editors.remove(self)
        self.destroy()

    def apply_to_spec(self, spec: SoundSpec) -> None:
        spec.name = self.name_var.get()
        spec.path = self.path_var.get()
        spec.volume = self.volume_var.get()

    def test(self) -> None:
        test_spec = SoundSpec()
        self.apply_to_spec(test_spec)
        try:
            self.app.play_sound(test_spec)
        except FileNotFoundError:
            self.error.config(text="File not found.")

    def apply(self) -> None:
        # self.spec.name = self.name_var.get()
        # self.spec.path = self.path_var.get()
        # self.spec.volume = self.volume_var.get()
        self.apply_to_spec(self.spec)

        self.app.thumbnails.get_thumbnail_by_spec(self.spec).spec_updated()
        self.app.save_appinfo()

        self.title("Shiteboard - " + self.spec.name)

    def set_binding(self):
        keys = set()

        def on_pressed(sender, key):
            if key not in keys:
                keys.add(key)

        def on_released(sender, key):
            self.app.pressed.remove(on_pressed)
            self.app.released.remove(on_released)

            self.spec.keys = keys

            self.key_label.configure(text=self.stringify_keys())

        self.app.pressed.add(on_pressed)
        self.app.released.add(on_released)


class SoundThumbnail(ttk.Frame):
    _styles_initialised = False
    StyleName = "ThumbnailStyle.TFrame"
    HoverStyleName = "ThumbnailHover.TFrame"
    LabelStyleName = "ThumbnailStyle.TLabel"
    LabelHoverStyleName = "ThumbnailHover.TLabel"

    def __init__(self, master, spec: SoundSpec, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        if not self._styles_initialised:
            self.init_styles()

        self.configure(borderwidth=1, relief="solid", padding=5, style=self.StyleName)

        self.clicked: Event[None] = Event()

        self.bind("<Button-1>", self.clicked.bind_invoke_empty(self, None))
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_exit)

        self.spec: SoundSpec = spec

        self.label = ttk.Label(self)
        self.label.bind("<Button-1>", self.clicked.bind_invoke_empty(self, None))
        self.label.configure(style=self.LabelStyleName)
        self.label.grid()

        self.spec_updated()

    def spec_updated(self):
        self.label.configure(text=self.spec.name)

    def init_styles(self):
        style = ttk.Style()
        style.configure(self.StyleName, background="white")
        style.configure(self.HoverStyleName, background="#e0eef9")
        style.configure(self.LabelStyleName, background="white")
        style.configure(self.LabelHoverStyleName, background="#e0eef9")

        self._styles_initialised = True

    def on_enter(self, value):
        self.configure(style=self.HoverStyleName)
        self.label.configure(style=self.LabelHoverStyleName)

    def on_exit(self, value):
        self.configure(style=self.StyleName)
        self.label.configure(style=self.LabelStyleName)


class Thumbnails(ttk.Frame):
    def __init__(self, master: SoundboardApp, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        self.app = master

        self.thumbnail_frame = ttk.Frame(self)
        self.thumbnail_frame.grid()
        # self.add_sound_frame = ttk.Frame(self.thumbnail_frame)
        # self.add_sound_frame.grid()
        self.buttons_frame = ttk.Frame(self)
        self.buttons_frame.grid()
        self.clear_sounds_button = ttk.Button(self.buttons_frame, text="🗑", command=self.clear_sounds)
        self.clear_sounds_button.grid(row=0, column=0)
        self.add_sound_button = ttk.Button(self.buttons_frame, text="+", command=self.add_sound)
        self.add_sound_button.grid(row=0, column=1)

        self.thumbnails_columns = 4
        for c in range(self.thumbnails_columns):
            self.thumbnail_frame.columnconfigure(c, pad=5)

        self.thumbnails: List[SoundThumbnail] = []
        self.create_sound_table()

    def clear_thumbnails(self):
        for thumbnail in self.thumbnails:
            thumbnail.destroy()

        self.thumbnails = []

    def remove_thumbnail(self, spec: SoundSpec):
        # inefficient but im lazy
        # to improve find index first and del
        thumbnail = self.get_thumbnail_by_spec(spec)
        thumbnail.destroy()
        self.thumbnails.remove(thumbnail)

    def get_thumbnail_by_spec(self, spec: SoundSpec) -> SoundThumbnail:
        return next(thumbnail for thumbnail in self.thumbnails if thumbnail.spec == spec)

    def create_sound_table(self) -> None:
        self.clear_thumbnails()

        for spec in self.app.appinfo.sounds:
            self.add_thumbnail(spec)

    def add_sound(self) -> None:
        spec = SoundSpec()
        self.app.appinfo.sounds.append(spec)
        self.app.save_appinfo()
        self.add_thumbnail(spec)

    def add_thumbnail(self, spec) -> None:
        thumbnail = SoundThumbnail(self.thumbnail_frame, spec)
        thumbnail.clicked.add(self.edit_sound)

        i = len(self.thumbnails)
        r = i // self.thumbnails_columns
        thumbnail.grid(row=r, column=i % self.thumbnails_columns)
        self.thumbnail_frame.rowconfigure(r, pad=5)
        self.thumbnails.append(thumbnail)

    def edit_sound(self, sender: SoundThumbnail, args) -> None:
        self.app.add_editor(sender.spec)

    def clear_sounds(self) -> None:
        ok = messagebox.askokcancel("Clear Sounds", "Are you sure you want to clear the soundboard?")
        if ok:
            self.clear_thumbnails()
            self.app.appinfo.sounds = []
            self.app.save_appinfo()


class Settings(ttk.Frame):
    def __init__(self, master: SoundboardApp, *args, **kwargs):
        super().__init__(master, *args, **kwargs)

        self.app = master

        self.output_device_label = ttk.Label(self, text="Input Device (Microphone)")
        self.output_device_label.grid()
        self.input_device_menu = ttk.OptionMenu(self, tk.StringVar(), self.app.input_device["name"],
                                                *map(lambda x: x["name"], self.app.input_devices),
                                                command=self.input_device_changed)
        self.input_device_menu.grid()

        self.output_device_label = ttk.Label(self, text="Output Device (Cable)")
        self.output_device_label.grid()
        self.output_device_menu = ttk.OptionMenu(self, tk.StringVar(), self.app.output_device["name"],
                                                 *map(lambda x: x["name"], self.app.output_devices),
                                                 command=self.output_device_changed)
        self.output_device_menu.grid()

        self.echo_var = tk.BooleanVar(value=self.app.appinfo.echo)
        self.echo_checkbox = ttk.Checkbutton(self, text="Echo Enabled", variable=self.echo_var,
                                             command=self.echo_enabled_changed)
        # self.echo_checkbox.state(["!alternate"])
        self.echo_checkbox.grid()
        self.echo_device_label = ttk.Label(self, text="Echo Device (Headphones)")
        self.echo_device_label.grid()
        self.echo_device_menu = ttk.OptionMenu(self, tk.StringVar(), self.app.echo_device["name"],
                                               *map(lambda x: x["name"], self.app.output_devices),
                                               command=self.echo_device_changed)
        self.echo_device_menu.grid()

    def input_device_changed(self, value: str) -> None:
        self.app.set_input_device(get_device_by_name(value, self.app.input_devices))
        self.app.input_stream.close()
        self.app.input_stream = self.app.get_stream(input=True, input_device_index=self.app.input_device["index"])
        self.app.save_appinfo()

    def output_device_changed(self, value: str) -> None:
        self.app.set_output_device(get_device_by_name(value, self.app.output_devices))
        self.app.output_stream.close()
        self.app.output_stream = self.app.get_stream(output=True, output_device_index=self.app.output_device["index"])
        self.app.save_appinfo()

    def echo_device_changed(self, value: str) -> None:
        self.app.set_echo_device(get_device_by_name(value, self.app.output_devices))
        self.app.echo_stream.close()
        self.app.echo_stream = self.app.get_stream(output=True, output_device_index=self.app.echo_device["index"])
        self.app.save_appinfo()

    def echo_enabled_changed(self) -> None:
        self.app.appinfo.echo = self.echo_var.get()
        self.app.save_appinfo()


class SoundboardApp(tk.Tk):
    RESOLUTION: int = 1
    AUDIO_FORMAT: int = pyaudio.paInt16
    CHANNELS: int = 2
    CHUNK: int = 512 * RESOLUTION
    RATE: int = 44100
    DELAY: int = 1 * RESOLUTION
    APPINFO_PATH: str = "appinfo.pickle"

    def __init__(self):
        super().__init__()

        self.title("Shiteboard")

        # default_font = font.nametofont("TkDefaultFont")
        # default_font.config(family="Terminal")
        # print(font.families())

        self.audio: pyaudio.PyAudio = pyaudio.PyAudio()

        self.pressed: Event[keyboard.Key] = Event()
        self.released: Event[keyboard.Key] = Event()

        self.pressed.add(self.on_pressed)
        self.released.add(self.on_released)

        self.listener = keyboard.Listener(on_press=self.pressed.bind_invoke_sender(self), on_release=self.released.bind_invoke_sender(self))
        self.listener.start()

        self.global_keys: set[keyboard.Key] = set()

        self.appinfo = self.load_appinfo()

        self.devices: List[DeviceParameters] = []
        self.input_devices: List[DeviceParameters] = []
        self.output_devices: List[DeviceParameters] = []
        self.fetch_devices()

        self._terminated: bool = False

        self.playback: Any = None

        self.input_device: DeviceParameters = get_device_by_name(self.appinfo.input_device_name, self.input_devices)
        self.set_input_device(self.input_device)
        self.output_device: DeviceParameters = next((device for device in self.output_devices if re.match("cable", device["name"], re.IGNORECASE)), get_device_by_name(self.appinfo.output_device_name, self.output_devices))
        self.set_output_device(self.output_device)
        self.echo_device: DeviceParameters = get_device_by_name(self.appinfo.echo_device_name, self.output_devices)
        self.set_echo_device(self.echo_device)

        self.input_stream: pyaudio.Stream = self.get_stream(input=True, input_device_index=self.input_device["index"])
        self.output_stream: pyaudio.Stream = self.get_stream(output=True, output_device_index=self.output_device["index"])
        self.echo_stream: pyaudio.Stream = self.get_stream(output=True, output_device_index=self.echo_device["index"])

        self.settings = Settings(self)
        self.settings.grid()

        self.thumbnails = Thumbnails(self)
        self.thumbnails.grid()

        self.editors: List[SoundEditor] = []

        self.save_appinfo()

        self.update_audio()

    def load_appinfo(self) -> AppInfo:
        try:
            with open(self.APPINFO_PATH, "rb") as f:
                appinfo = AppInfo.loads(f.read())
                if appinfo.version != AppInfo.VERSION:
                    appinfo = AppInfo()
        except FileNotFoundError:
            appinfo = AppInfo()
        return appinfo

    def save_appinfo(self) -> None:
        with open(self.APPINFO_PATH, "wb") as f:
            f.write(self.appinfo.dumps())

    def add_editor(self, spec: SoundSpec):
        self.editors.append(SoundEditor(self, spec))

    def remove_sound(self, editor: SoundEditor):
        spec = editor.spec
        self.appinfo.sounds.remove(spec)
        self.thumbnails.remove_thumbnail(spec)
        editor.destroy()
        self.editors.remove(editor)
        self.save_appinfo()

    # def get_input_device_by_name(self, name: str) -> DeviceParameters:
    #     return get_device_by_name(name, self.input_devices)
    #
    # def get_output_device_by_name(self, name: str) -> DeviceParameters:
    #     return get_device_by_name(name, self.output_devices)

    def keybind_met(self, keybind: set[keyboard.Key]):
        if len(keybind) == 0:
            return False
        return all((key in self.global_keys) for key in keybind)

    def on_pressed(self, sender, key):
        if key not in self.global_keys:
            self.global_keys.add(key)

        for sound in self.appinfo.sounds:
            if self.keybind_met(sound.keys):
                self.play_sound(sound)

    def on_released(self, sender, key):
        if key in self.global_keys:
            self.global_keys.remove(key)

    def set_input_device(self, device: DeviceParameters) -> None:
        self.input_device = device
        self.appinfo.input_device_name = device["name"]
        # self.save_appinfo()

    def set_output_device(self, device: DeviceParameters) -> None:
        self.output_device = device
        self.appinfo.output_device_name = device["name"]
        # self.save_appinfo()

    def set_echo_device(self, device: DeviceParameters) -> None:
        self.echo_device = device
        self.appinfo.echo_device_name = device["name"]
        # self.save_appinfo()

    def get_stream(self, *args, **kwargs) -> pyaudio.Stream:
        return self.audio.open(format=self.AUDIO_FORMAT,
                               channels=self.CHANNELS,
                               rate=self.RATE,
                               frames_per_buffer=self.CHUNK,
                               *args,
                               **kwargs)

    def fetch_devices(self) -> None:
        api_info = self.audio.get_host_api_info_by_index(0)
        self.devices = [self.audio.get_device_info_by_index(i) for i in range(api_info["deviceCount"])]
        # print("\n".join(map(str, self.devices)))
        self.input_devices = [device for device in self.devices if device["maxInputChannels"] > 0]
        self.output_devices = [device for device in self.devices if device["maxOutputChannels"] > 0]

    def play_sound(self, spec: SoundSpec):
        wf = wave.open(spec.path, "rb")
        self.set_playback(wf)

    def set_playback(self, playback):
        if self.playback is not None:
            self.playback.close()

        self.playback = playback

    def update_audio(self) -> None:
        input_bytes = self.input_stream.read(self.CHUNK, exception_on_overflow=False)
        if self.playback is not None:
            playback_bytes = self.playback.readframes(self.CHUNK)
            pb_frame_count = len(playback_bytes)
            if pb_frame_count == 0:
                self.playback.close()
                self.playback = None

            # print(type(input_bytes), type(playback_bytes))
            # self.output_stream.write(input_bytes)

            delta = len(input_bytes) - pb_frame_count

            if delta == 0:
                self.write_output(mix(input_bytes, playback_bytes))
            else:  # there are fewer playback frames than mic frames
                self.write_output(mix(input_bytes[:pb_frame_count], playback_bytes))  # mix as many frames as we can
                self.write_output(input_bytes[pb_frame_count:])  # play mic without mixing
        else:
            self.write_output(input_bytes)

        self.after(self.DELAY, self.update_audio)

    def write_output(self, frames: bytes) -> None:
        self.output_stream.write(frames)
        if self.appinfo.echo:
            self.echo_stream.write(frames)

    def terminate(self) -> None:
        self.input_stream.close()
        self.output_stream.close()
        self.echo_stream.close()

        self.audio.terminate()

        if self.playback is not None:
            self.playback.close()

        self._terminated = True

    def mainloop(self, n: int = -1) -> None:
        if self._terminated:
            raise "App is terminated."
        super().mainloop(n)


if __name__ == '__main__':
    app = SoundboardApp()

    # s = ttk.Style()
    # s.theme_use("alt")

    try:
        app.mainloop()
    finally:
        app.terminate()
