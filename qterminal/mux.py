import threading
import select
import time


class Multiplexer(object):

    def __init__(self):
        self.backend_index = {}
        self.read_index = {}
        self.stop_flag = False

        self.thread = threading.Thread(target=self.listen)
        self.thread.start()

    def add_backend(self, backend):
        self.backend_index[backend.id] = backend
        self.read_index[backend.get_read_wait()] = backend

        if self.stop_flag:
            self.stop_flag = False
            self.thread = threading.Thread(target=self.listen)
            self.thread.start()

    def remove_and_close(self, backend):
        if backend.id in self.backend_index:
            self.read_index.pop(self.backend_index.pop(backend.id).get_read_wait())

        if len(self.backend_index) <= 0:
            self.stop()

    def stop(self):
        self.stop_flag = True

    def listen(self):
        while not self.stop_flag:
            read_wait_list = [a.get_read_wait() for a in self.backend_index.values()]
            if read_wait_list:
                try:
                    read_ready_list, write_ready_list, error_ready_list = select.select(read_wait_list, [], [])
                except:
                    read_ready_list = []

                for read_item in read_ready_list:
                    backend = self.read_index.get(read_item)
                    if backend:
                        backend.read()
            else:
                time.sleep(1)


mux = Multiplexer()
