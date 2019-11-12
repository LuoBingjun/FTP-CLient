import sys
import os
import re
import socket
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from PyQt5.QtNetwork import QTcpSocket, QTcpServer


class FTPError(Exception):
    def __init__(self, code, detail):
        self.code = code
        self.detail = detail

    def __str__(self):
        return '%d: %s' % (self.code, self.detail)


def exception_catcher(func):
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except socket.error as msg:
            self.ctrl_socket.close()
            self.error.emit(-1, str(msg))
        except FTPError as e:
            if e.code == 0 or e.code == 421:
                self.ctrl_socket.close()
            self.error.emit(e.code, e.detail)
        except Exception as e:
            self.ctrl_socket.close()
            self.error.emit(-1, 'unexpected: {0}'.format(e))
    return wrapper


class CtrlConnection(QObject):
    stop = False
    remote_dir = '/'
    server_info = {}

    ctrl_socket = None
    data_thread = None

    init_datasock = None
    
    error = pyqtSignal(int, str)
    info = pyqtSignal(str)
    debug = pyqtSignal(str)
    remotedirChanged = pyqtSignal(str)
    remotelistChanged = pyqtSignal(list)
    getFinished = pyqtSignal()
    transferUpdated = pyqtSignal(float)

    @exception_catcher
    def init(self, server_info, trans_method):
        self.server_info = server_info
        if trans_method:
            self.init_datasock = self.init_PORT
        else:
            self.init_datasock = self.init_PASV

        self.ctrl_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ctrl_socket.settimeout(10)
        if self.login() == 0:
            _, detail = self.com_SYST()

            _, detail = self.com_TYPE()

            self.setRemotedir('/')

    def login(self):
        self.ctrl_socket.connect(
            (self.server_info['hostname'], self.server_info['port']))

        recv_data = self.ctrl_socket.recv(8192)
        _, _ = self.unwrap(recv_data, [220])

        self.ctrl_socket.sendall('USER {0}\r\n'.format(self.server_info['username']).encode('utf-8'))

        recv_data = self.ctrl_socket.recv(8192)
        _, _ = self.unwrap(recv_data, [331])

        self.ctrl_socket.sendall('PASS {0}\r\n'.format(self.server_info['password']).encode('utf-8'))

        recv_data = self.ctrl_socket.recv(8192)
        _, _ = self.unwrap(recv_data, [230])

        return 0

    def com_LIST(self):
        self.ctrl_socket.sendall(('LIST\r\n').encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        return self.unwrap(recv_data, [125, 150])

    def com_REST(self, offset):
        self.ctrl_socket.sendall(('REST {0}\r\n').format(offset).encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        return self.unwrap(recv_data, [350])

    def com_APPE(self, filename):
        self.ctrl_socket.sendall(('APPE {0}\r\n').format(filename).encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        return self.unwrap(recv_data, [125, 150])

    def com_RETR(self, filename):
        self.ctrl_socket.sendall(('RETR {0}\r\n').format(filename).encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        return self.unwrap(recv_data, [125, 150])

    def com_STOR(self, filename):
        self.ctrl_socket.sendall(('STOR {0}\r\n').format(filename).encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        return self.unwrap(recv_data, [125, 150])

    def com_SYST(self):
        self.ctrl_socket.sendall('SYST\r\n'.encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        return self.unwrap(recv_data, [215])

    def com_TYPE(self):
        self.ctrl_socket.sendall('TYPE I\r\n'.encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        return self.unwrap(recv_data, [200])

    def com_DELE(self, path):
        self.ctrl_socket.sendall('DELE {0}\r\n'.format(path).encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        return self.unwrap(recv_data, [250])

    def com_CWD(self, path):
        self.ctrl_socket.sendall('CWD {0}\r\n'.format(path).encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        return self.unwrap(recv_data, [250])

    def com_PWD(self):
        self.ctrl_socket.sendall('PWD\r\n'.encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        return self.unwrap(recv_data, [257])

    def com_MKD(self, path):
        self.ctrl_socket.sendall('MKD {0}\r\n'.format(path).encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        return self.unwrap(recv_data, [257])

    def com_RMD(self, path):
        self.ctrl_socket.sendall('RMD {0}\r\n'.format(path).encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        return self.unwrap(recv_data, [250])

    def com_RNFR(self, path):
        self.ctrl_socket.sendall('RNFR {0}\r\n'.format(path).encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        return self.unwrap(recv_data, [350])

    def com_RNTO(self, path):
        self.ctrl_socket.sendall('RNTO {0}\r\n'.format(path).encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        return self.unwrap(recv_data, [250])

    @exception_catcher
    def close_sock(self):
        try:
            self.ctrl_socket.sendall('QUIT\r\n'.encode('utf-8'))
            self.ctrl_socket.close()
        except Exception:
            pass
        finally:
            self.info.emit('Disconnected from server.')

    def init_PORT(self, command, *args):
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen_socket.bind(('', 0))
        listen_socket.listen(1)
        addr, _ = self.ctrl_socket.getsockname()
        _, port = listen_socket.getsockname()
        h = [int(i) for i in addr.split('.')]
        p1 = port // 256
        p2 = port % 256
        self.ctrl_socket.sendall('PORT {0},{1},{2},{3},{4},{5}\r\n'.format(h[0], h[1], h[2], h[3], p1, p2).encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        _, _ = self.unwrap(recv_data, [200])
        command(*args)
        data_socket, _ = listen_socket.accept()
        listen_socket.close()
        return data_socket

    def init_PASV(self, command, *args):
        self.ctrl_socket.sendall('PASV\r\n'.encode('utf-8'))
        recv_data = self.ctrl_socket.recv(8192)
        _, addr_str = self.unwrap(recv_data, [227])
        res = re.search(r'(\d*),(\d*),(\d*),(\d*),(\d*),(\d*)', addr_str)
        addr = [int(res.group(i)) for i in range(1, 7)]
        data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_socket.connect(('{0}.{1}.{2}.{3}'.format(addr[0], addr[1], addr[2], addr[3]), addr[4]*256+addr[5]))
        command(*args)
        return data_socket

    def list_dir(self):
        data_socket = self.init_datasock(self.com_LIST)
        list_data = bytes(0)
        recv_data = 1
        while recv_data:
            recv_data = data_socket.recv(8192)
            list_data += recv_data
        data_socket.close()
        list_str = bytes.decode(list_data)
        recv_data = self.ctrl_socket.recv(8192)
        _, _ = self.unwrap(recv_data, [226])
        lines = list_str.split('\r\n')
        del lines[-1]
        return lines

    @exception_catcher
    def del_file(self, remote_path):
        code, detail = self.com_DELE(remote_path)
        self.info.emit('{0} {1}'.format(code, detail))
        list_data = self.list_dir()
        self.remotelistChanged.emit(list_data)

    @exception_catcher
    def rm_dir(self, remote_path):
        code, detail = self.com_RMD(remote_path)
        self.info.emit('{0} {1}'.format(code, detail))
        list_data = self.list_dir()
        self.remotelistChanged.emit(list_data)

    @exception_catcher
    def mk_dir(self, remote_path):
        code, detail = self.com_MKD(remote_path)
        self.info.emit('{0} {1}'.format(code, detail))
        list_data = self.list_dir()
        self.remotelistChanged.emit(list_data)

    @exception_catcher
    def rename(self, old_name, new_name):
        _, _ = self.com_RNFR(old_name)
        code, detail = self.com_RNTO(new_name)
        self.info.emit('{0} {1}'.format(code, detail))
        list_data = self.list_dir()
        self.remotelistChanged.emit(list_data)

    @exception_catcher
    def get_file(self, local_path, remote_path, size):
        data_socket = self.init_datasock(self.com_RETR, remote_path)
        try:
            f = open(local_path, 'wb+')
            recv_data = 1
            progress = 0
            self.transferUpdated.emit(progress / size)
            while recv_data:
                if self.stop:
                    self.stop = False
                    break
                recv_data = data_socket.recv(8192)
                progress += len(recv_data)
                self.transferUpdated.emit(progress / size)
                f.write(recv_data)
            print('ok')
            f.close()
            data_socket.close()
            recv_data = self.ctrl_socket.recv(8192)
            code, detail = self.unwrap(recv_data, [226])
            self.info.emit('{0} {1}'.format(code, detail))
        except IOError as e:
            raise FTPError(0, str(e))
        finally:
            self.transferUpdated.emit(1)
            self.getFinished.emit()

    @exception_catcher
    def rest_file(self, local_path, remote_path, size, offset):
        _, _ = self.com_REST(offset)
        data_socket = self.init_datasock(self.com_RETR, remote_path)
        try:
            f = open(local_path, 'ab+')
            recv_data = 1
            progress = offset
            self.transferUpdated.emit(progress / size)
            while recv_data:
                if self.stop:
                    self.stop = False
                    break
                recv_data = data_socket.recv(8192)
                progress += len(recv_data)
                self.transferUpdated.emit(progress / size)
                f.write(recv_data)
            print('ok')
            f.close()
            data_socket.close()
            recv_data = self.ctrl_socket.recv(8192)
            code, detail = self.unwrap(recv_data, [226])
            self.info.emit('{0} {1}'.format(code, detail))
        except IOError as e:
            raise FTPError(0, str(e))
        finally:
            self.transferUpdated.emit(1)
            self.getFinished.emit()

    @exception_catcher
    def put_file(self, local_path, remote_path, size):
        data_socket = self.init_datasock(self.com_STOR, remote_path)
        try:
            f = open(local_path, 'rb')
            read_data = 1
            progress = 0
            self.transferUpdated.emit(progress / size)
            while read_data:
                if self.stop:
                    self.stop = False
                    break
                read_data = f.read(8192)
                data_socket.sendall(read_data)
                progress += len(read_data)
                self.transferUpdated.emit(progress / size)
            f.close()
            data_socket.close()
            recv_data = self.ctrl_socket.recv(8192)
            code, detail = self.unwrap(recv_data, [226])
            self.info.emit('{0} {1}'.format(code, detail))
        except IOError as e:
            raise FTPError(0, str(e))
        finally:
            self.transferUpdated.emit(1)
            list_data = self.list_dir()
            self.remotelistChanged.emit(list_data)

    @exception_catcher
    def appe_file(self, local_path, remote_path, size, offset):
        data_socket = self.init_datasock(self.com_APPE, remote_path)
        try:
            f = open(local_path, 'rb')
            f.seek(offset)
            read_data = 1
            progress = offset
            self.transferUpdated.emit(progress / size)
            while read_data:
                if self.stop:
                    self.stop = False
                    break
                read_data = f.read(8192)
                data_socket.sendall(read_data)
                progress += len(read_data)
                self.transferUpdated.emit(progress / size)
            f.close()
            data_socket.close()
            recv_data = self.ctrl_socket.recv(8192)
            code, detail = self.unwrap(recv_data, [226])
            self.info.emit('{0} {1}'.format(code, detail))
        except IOError as e:
            raise FTPError(0, str(e))
        finally:
            self.transferUpdated.emit(1)
            list_data = self.list_dir()
            self.remotelistChanged.emit(list_data)

    @exception_catcher
    def setRemotedir(self, dir_path):
        try:
            code, detail = self.com_CWD(dir_path)
            self.info.emit('{0} {1}'.format(code, detail))
        except FTPError:
            raise
        finally:
            _, detail = self.com_PWD()
            res = re.match(r'"(.*)"', detail)
            self.remote_dir = res.group(1)
            self.remotedirChanged.emit(self.remote_dir)
            list_data = self.list_dir()
            self.remotelistChanged.emit(list_data)
            

    def unwrap(self, recv_data, expect_code=None):
        code = -1
        detail = ''
        try:
            response = bytes.decode(recv_data)
            responses = response.split('\r\n')
            for line in responses:
                res = re.match(r'^(\d{3})($| (.*)$)', line)
                if res:
                    code = int(res.group(1))
                    detail = res.group(3)
                    break
        except:
            pass

        if expect_code and (code not in expect_code):
            raise FTPError(code, detail)
        self.debug.emit('{0} {1}'.format(code, detail))
        return code, detail


class CtrlThread(QThread):
    def __init__(self, parent, trans_method, server_info):
        self.server_info = server_info
        self.trans_method = trans_method
        super(CtrlThread, self).__init__(parent=parent)

    def run(self):
        client = CtrlConnection()
        parent = self.parent()

        self.finished.connect(self.finish)

        parent.remotedirChanged.connect(client.setRemotedir)
        parent.getFile.connect(client.get_file)
        parent.restFile.connect(client.rest_file)
        parent.putFile.connect(client.put_file)
        parent.appeFile.connect(client.appe_file)
        parent.delFile.connect(client.del_file)
        parent.rmDir.connect(client.rm_dir)
        parent.mkDir.connect(client.mk_dir)
        parent.rename.connect(client.rename)

        client.error.connect(parent.errorSlot)
        client.info.connect(parent.infoSlot)
        client.debug.connect(parent.debugSlot)
        client.remotedirChanged.connect(parent.setRemotedir)
        client.remotelistChanged.connect(parent.updateRemotelist)
        client.getFinished.connect(parent.updateLocalList)
        client.transferUpdated.connect(parent.transferUpdate)

        self.client = client

        client.init(self.server_info, self.trans_method)
        self.exec_()

    def finish(self):
        try:
            client = self.client
            parent = self.parent()
            client.close_sock()
            parent.disconnect()
            client.disconnect()
            parent.resetRemote()
        except Exception: 
            pass
