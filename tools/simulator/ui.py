"""Tk desktop window for the development-only simulator."""

from queue import Empty
from tkinter import BOTH, BOTTOM, LEFT, RIGHT, TOP, Button, Frame, Label, Tk

from PIL import Image, ImageTk

from tools.simulator.adapters import image_from_payload, SimulatorButtonPins


KEY_MAP = {
    "Up": SimulatorButtonPins.KEY_UP,
    "Down": SimulatorButtonPins.KEY_DOWN,
    "Left": SimulatorButtonPins.KEY_LEFT,
    "Right": SimulatorButtonPins.KEY_RIGHT,
    "Return": SimulatorButtonPins.KEY_PRESS,
    "KP_Enter": SimulatorButtonPins.KEY_PRESS,
    "1": SimulatorButtonPins.KEY1,
    "KP_1": SimulatorButtonPins.KEY1,
    "2": SimulatorButtonPins.KEY2,
    "KP_2": SimulatorButtonPins.KEY2,
    "3": SimulatorButtonPins.KEY3,
    "KP_3": SimulatorButtonPins.KEY3,
}


class SimulatorWindow:
    def __init__(
        self,
        frame_queue,
        input_queue,
        error_queue,
        app_process,
        *,
        scale: int = 2,
    ):
        self.frame_queue = frame_queue
        self.input_queue = input_queue
        self.error_queue = error_queue
        self.app_process = app_process
        self.scale = max(1, int(scale))
        self._pressed: set[int] = set()
        self._tk_image = None
        self._frames = 0

        self.root = Tk()
        self.root.title("BitPolito SeedSigner 0.8.7 Simulator")
        self.root.configure(bg="#F3F5FF")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<KeyPress>", self._key_press)
        self.root.bind("<KeyRelease>", self._key_release)

        self.display_label = Label(self.root, bg="black")
        self.display_label.pack(side=TOP, padx=12, pady=(12, 6))

        self.status = Label(
            self.root,
            text="Starting real SeedSigner application…",
            bg="#F3F5FF",
            fg="#001CE0",
        )
        self.status.pack(side=TOP, pady=(0, 6))

        controls = Frame(self.root, bg="#F3F5FF")
        controls.pack(side=BOTTOM, fill=BOTH, padx=12, pady=(0, 12))

        dpad = Frame(controls, bg="#F3F5FF")
        dpad.pack(side=LEFT, padx=(0, 18))
        self._button(dpad, "↑", SimulatorButtonPins.KEY_UP, 0, 1)
        self._button(dpad, "←", SimulatorButtonPins.KEY_LEFT, 1, 0)
        self._button(dpad, "●", SimulatorButtonPins.KEY_PRESS, 1, 1)
        self._button(dpad, "→", SimulatorButtonPins.KEY_RIGHT, 1, 2)
        self._button(dpad, "↓", SimulatorButtonPins.KEY_DOWN, 2, 1)

        side = Frame(controls, bg="#F3F5FF")
        side.pack(side=RIGHT)
        for row, (label, pin) in enumerate(
            (
                ("1", SimulatorButtonPins.KEY1),
                ("2", SimulatorButtonPins.KEY2),
                ("3", SimulatorButtonPins.KEY3),
            )
        ):
            self._button(side, label, pin, row, 0, width=6)

        self.root.after(15, self._poll)

    def _button(self, parent, label, pin, row, column, width=4):
        button = Button(parent, text=label, width=width, takefocus=False)
        button.grid(row=row, column=column, padx=2, pady=2)
        button.bind("<ButtonPress-1>", lambda event, value=pin: self.press(value))
        button.bind("<ButtonRelease-1>", lambda event, value=pin: self.release(value))
        return button

    def press(self, pin: int):
        if pin in self._pressed:
            return
        self._pressed.add(pin)
        self.input_queue.put((pin, 0))

    def release(self, pin: int):
        if pin not in self._pressed:
            return
        self._pressed.remove(pin)
        self.input_queue.put((pin, 1))

    def _key_press(self, event):
        pin = KEY_MAP.get(event.keysym)
        if pin is not None:
            self.press(pin)

    def _key_release(self, event):
        pin = KEY_MAP.get(event.keysym)
        if pin is not None:
            self.release(pin)

    def _poll(self):
        latest = None
        while True:
            try:
                latest = self.frame_queue.get_nowait()
            except Empty:
                break

        if latest is not None:
            frame = image_from_payload(latest)
            scaled = frame.resize(
                (frame.width * self.scale, frame.height * self.scale),
                Image.Resampling.NEAREST,
            )
            self._tk_image = ImageTk.PhotoImage(scaled, master=self.root)
            self.display_label.configure(image=self._tk_image)
            self._frames += 1
            self.status.configure(
                text=f"Live · {frame.width}×{frame.height} · frame {self._frames}"
            )

        try:
            error = self.error_queue.get_nowait()
        except Empty:
            error = None
        if error:
            self.status.configure(text="Application error — see terminal", fg="#B42318")
            print(error)

        if not self.app_process.is_alive() and not error:
            self.status.configure(text="Application stopped", fg="#B42318")

        self.root.after(15, self._poll)

    def close(self):
        for pin in tuple(self._pressed):
            self.release(pin)
        self.root.destroy()

    def run(self):
        self.root.mainloop()
