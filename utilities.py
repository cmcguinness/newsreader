#    ┌──────────────────────────────────────────────────────────┐
#    │                                                          │
#    │                        Utilities                         │
#    │                                                          │
#    │        It's a singleton to allow easy sharing of         │
#    │           information across the application.            │
#    │                                                          │
#    └──────────────────────────────────────────────────────────┘
import os


class Utilities:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if "callback" not in self.__dict__:
            self.callback = self.default_status_callback

    @staticmethod
    def default_status_callback(state, message):
        print(f"State: {state}, Message: {message}", flush=True)

    def set_callback(self, callback):
        self.callback = callback

    def update_status(self, state, message):
        self.callback(state, message)

    @staticmethod
    def stop_process():
        os.kill(os.getpid(), 15)