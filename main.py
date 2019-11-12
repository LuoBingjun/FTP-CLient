import sys
import os
import time
if hasattr(sys, 'frozen'):
    os.environ['PATH'] = sys._MEIPASS + ";" + os.environ['PATH']

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import Ui_mainwindow
from client import CtrlThread

def exception_catcher(func):
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as e:
            self.errorSlot(0, str(e))
    return wrapper


class MainWindow(QMainWindow):
    remotedirChanged = pyqtSignal(str)
    getFile = pyqtSignal(str, str, int)
    restFile = pyqtSignal(str, str, int, int)
    putFile = pyqtSignal(str, str, int)
    appeFile = pyqtSignal(str, str, int, int)
    delFile = pyqtSignal(str)
    rmDir = pyqtSignal(str)
    mkDir = pyqtSignal(str)
    rename = pyqtSignal(str, str)
    clientThread = None
    local_dir = None
    remote_dir = None

    def init(self, ui):
        self.ui = ui

        self.progressBar = QProgressBar()
        self.progressBar.setGeometry(0, 0, 100, 15)
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.progressBar.hide()
        self.ui.statusbar.addPermanentWidget(self.progressBar)

        self.trans_method = QButtonGroup()
        self.trans_method.addButton(ui.portButton, 1)
        self.trans_method.addButton(ui.pasvButton, 0)

        # init localView
        self.localModel = QStandardItemModel(0, 4)
        self.localModel.setHorizontalHeaderLabels(
            ['Filename', 'Filesize', 'Filetype', 'Last modified'])
        ui.localView.setModel(self.localModel)
        ui.localView.setSelectionBehavior(QTreeView.SelectRows)
        ui.localView.setSelectionMode(QTreeView.SingleSelection)
        ui.localView.doubleClicked.connect(self.localviewClicked)
        ui.localView.setContextMenuPolicy(Qt.CustomContextMenu)
        ui.localView.customContextMenuRequested.connect(self.localMenu)

        # init remoteView
        self.remoteModel = QStandardItemModel(0, 6)
        self.remoteModel.setHorizontalHeaderLabels(
            ['Filename', 'Filesize', 'Filetype', 'Last modified', 'Permissions', 'Owner/Group'])
        ui.remoteView.setModel(self.remoteModel)
        ui.remoteView.setSelectionBehavior(QTreeView.SelectRows)
        ui.remoteView.setSelectionMode(QTreeView.SingleSelection)
        ui.remoteView.doubleClicked.connect(self.remoteviewClicked)
        ui.remoteView.setContextMenuPolicy(Qt.CustomContextMenu)
        ui.remoteView.customContextMenuRequested.connect(self.remoteMenu)

        ui.connectButton.clicked.connect(self.connect_to_server)
        ui.disconnectButton.clicked.connect(self.disconnect_from_server)

        # init localupButton
        ui.localupButton.clicked.connect(self.localupClicked)

        # init remoteupButton
        ui.remoteupButton.clicked.connect(self.remoteupClicked)

        # init localdirButton
        ui.localdirButton.clicked.connect(self.localdirClicked)

        # init remotedirButton
        ui.remotedirButton.clicked.connect(self.remotedirClicked)

        # init getButton
        ui.getButton.clicked.connect(self.getClicked)

        # init putButton
        ui.putButton.clicked.connect(self.putClicked)

        # init anymsBox
        ui.anymsBox.stateChanged.connect(self.anymsChanged)

        # init localdir
        self.setLocaldir(os.path.dirname(os.path.abspath(__file__)))

    @exception_catcher
    def localMenu(self, pos):
        menu = QMenu()
        index = self.ui.localView.indexAt(pos)
        row = index.row()
        if row >= 0:
            filename = self.localModel.item(row, 0).text()
            filetype = self.localModel.item(row, 2).text()
            def rename():
                newname, ok = QInputDialog.getText(self, "Rename", "Enter new filename:", text=filename)
                if ok:
                    try:
                        os.rename('{0}/{1}'.format(self.local_dir, filename), '{0}/{1}'.format(self.local_dir, newname))
                    except Exception as e:
                        self.errorSlot(0, str(e))
                    finally:
                        self.updateLocalList()
            menu.addAction('Rename', rename)
            
            if filetype == 'File Folder':
                def rmDir():
                    try:
                        os.rmdir(os.path.join(self.local_dir, filename))
                    except Exception as e:
                        self.errorSlot(0, str(e))
                    finally:
                        self.updateLocalList()
                menu.addAction('Remove directory', rmDir)
            else:
                def delFile():
                    try:
                        os.remove(os.path.join(self.local_dir, filename))
                    except Exception as e:
                        self.errorSlot(0, str(e))
                    finally:
                        self.updateLocalList()
                menu.addAction('Remove file', delFile)
            menu.addSeparator()

        def mkDir():
            filename, ok = QInputDialog.getText(self, "Create directory", "Enter the name of the directory to be created:")
            if ok:
                try:
                    os.mkdir(os.path.join(self.local_dir, filename))
                except Exception as e:
                    self.errorSlot(0, str(e))
                finally:
                    self.updateLocalList()
        menu.addAction('Create directory', mkDir)
        menu.exec(QCursor.pos())

    def remoteMenu(self, pos):
        menu = QMenu()
        index = self.ui.remoteView.indexAt(pos)
        row = index.row()
        if row >= 0:
            filename = self.remoteModel.item(row, 0).text()
            filetype = self.remoteModel.item(row, 2).text()
            def rename():
                newname, ok = QInputDialog.getText(self, "Rename", "Enter new filename:", text=filename)
                if ok:
                    self.rename.emit('{0}/{1}'.format(self.remote_dir, filename), '{0}/{1}'.format(self.remote_dir, newname))
            menu.addAction('Rename', rename)

            if filetype == 'File Folder':
                def rmDir():
                    self.rmDir.emit(
                        '{0}/{1}'.format(self.remote_dir, filename))
                menu.addAction('Remove directory', rmDir)
            else:
                def delFile():
                    self.delFile.emit(
                        '{0}/{1}'.format(self.remote_dir, filename))
                menu.addAction('Remove file', delFile)
            menu.addSeparator()

        def mkDir():
            filename, ok = QInputDialog.getText(self, "Create directory", "Enter the name of the directory to be created:")
            if ok:
                self.mkDir.emit('{0}/{1}'.format(self.remote_dir, filename))
        menu.addAction('Create directory', mkDir)
        menu.exec(QCursor.pos())

    @exception_catcher
    def localviewClicked(self, index):
        row = index.row()
        filename = self.localModel.item(row, 0).text()
        filetype = self.localModel.item(row, 2).text()
        filesize = int(self.localModel.item(row, 1).text())
        if filetype == 'File Folder':
            self.setLocaldir(os.path.join(self.local_dir, filename))
        else:
            self.put_file(filename, filesize)

    def remoteviewClicked(self, index):
        row = index.row()
        filename = self.remoteModel.item(row, 0).text()
        filetype = self.remoteModel.item(row, 2).text()
        filesize = int(self.remoteModel.item(row, 1).text())
        if filetype == 'File Folder':
            self.remotedirChanged.emit(filename)
        else:
            self.get_file(filename, filesize)

    def putClicked(self, _):
        index = self.ui.localView.selectedIndexes()
        if index:
            filename = index[0].data()
            filetype = index[2].data()
            filesize = int(index[1].data())
            if filetype == 'File Folder':
                pass
            else:
                self.put_file(filename, filesize)

    def getClicked(self, _):
        index = self.ui.remoteView.selectedIndexes()
        if index:
            filename = index[0].data()
            filetype = index[2].data()
            filesize = int(index[1].data())
            if filetype == 'File Folder':
                pass
            else:
                self.get_file(filename, filesize)

    @exception_catcher
    def localupClicked(self, _):
        self.setLocaldir(os.path.dirname(self.local_dir))

    def remoteupClicked(self, _):
        self.remotedirChanged.emit('..')

    @exception_catcher
    def localdirClicked(self, _):
        dir = QFileDialog.getExistingDirectory(self, 'Select local dir', self.local_dir)
        if dir:
            self.setLocaldir(dir)

    def remotedirClicked(self, _):
        remote_dir = self.ui.remotedirEdit.text()
        self.remotedirChanged.emit(remote_dir)

    def anymsChanged(self, data):
        if data:
            self.ui.usernameEdit.setText('anonymous')
            self.ui.usernameEdit.setReadOnly(True)
        else:
            self.ui.usernameEdit.setText('')
            self.ui.usernameEdit.setReadOnly(False)

    def get_file(self, filename, filesize):
        local_path = os.path.join(self.local_dir, filename)
        remote_path = '{0}/{1}'.format(self.remote_dir, filename)
        items = self.localModel.findItems(filename)

        self.ui.statusbar.showMessage('Downloading file: {0} (Size: {1} bytes)'.format(filename, filesize))
        
        if items and QMessageBox.question(self, "Local file exists", "Would you like to resume file transfer?", QMessageBox.Yes | QMessageBox.No):
            item = items[0]
            row = item.row()
            offset = int(self.localModel.item(row, 1).text())
            self.restFile.emit(local_path, remote_path, filesize, offset)
        else:
            self.getFile.emit(local_path, remote_path, filesize)

    def put_file(self, filename, filesize):
        local_path = os.path.join(self.local_dir, filename)
        remote_path = '{0}/{1}'.format(self.remote_dir, filename)
        items = self.remoteModel.findItems(filename)

        self.ui.statusbar.showMessage('Uploading file: {0} (Size: {1} bytes)'.format(filename, filesize))

        if items and QMessageBox.question(self, "Remote file exists", "Would you like to resume file transfer?", QMessageBox.Yes | QMessageBox.No):
            item = items[0]
            row = item.row()
            offset = int(self.remoteModel.item(row, 1).text())
            self.appeFile.emit(local_path, remote_path, filesize, offset)
        else:
            self.putFile.emit(local_path, remote_path, filesize)

    def resetRemote(self):
        self.remote_dir = None
        self.ui.remotedirEdit.setText('')
        self.remoteModel.removeRows(0, self.remoteModel.rowCount())

    def disconnect_from_server(self):
        if self.clientThread:
            self.ui.statusbar.showMessage('Disconnecting...')
            self.clientThread.client.stop = True
            self.clientThread.quit()
            self.resetRemote()
            self.transferUpdate(1)
            self.clientThread = None

    def connect_to_server(self):
        if self.clientThread:
            if QMessageBox.question(self, "Connection existed",  "Be sure to close current connection?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                self.disconnect_from_server()
            else:
                return

        self.clientThread = CtrlThread(parent=self, trans_method=self.trans_method.checkedId(), server_info={
            'hostname': self.ui.hostnameEdit.text(),
            'port': self.ui.portBox.value(),
            'username': self.ui.usernameEdit.text(),
            'password': self.ui.passwordEdit.text()
        })
        self.clientThread.start()
        self.ui.statusbar.showMessage('Connecting...')

    def setRemotedir(self, remote_dir):
        self.remote_dir = remote_dir
        ui.remotedirEdit.setText(remote_dir)

    def getExteninfo(self, extension):
        provider = QFileIconProvider()
        strTemplateName = QDir.tempPath() + QDir.separator() + QCoreApplication.applicationName() + "_XXXXXX." + extension
        tmpFile = QTemporaryFile(strTemplateName)
        tmpFile.setAutoRemove(False)
        tmpFile.open()
        tmpFile.close()
        icon = provider.icon(QFileInfo(tmpFile.fileName()))
        str_type = provider.type(QFileInfo(tmpFile.fileName()))
        return icon, str_type

    def updateRemotelist(self, detail):
        rows = []
        detail.sort(reverse=True)
        for line in detail:
            line = line.split(maxsplit=8)
            if len(line) != 9:
                self.errorSlot(0, 'LIST data read failed')
                return
            if line[0][0] == 'd':
                provider = QFileIconProvider()
                icon = provider.icon(QFileInfo('.'))
                str_type = provider.type(QFileInfo('.'))
            else:
                icon, str_type = self.getExteninfo(os.path.basename(line[8]))
            rows.append([(icon, line[8])] + [line[4], str_type, '{0} {1} {2}'.format(line[5], line[6], line[7]), line[0][1:], '{0}/{1}'.format(line[2], line[3])])
        self.remoteModel.removeRows(0, self.remoteModel.rowCount())
        for row in rows:
            self.remoteModel.appendRow([QStandardItem(*row[0])] + [QStandardItem(item) for item in row[1:]])

        self.ui.remoteView.sortByColumn(2, Qt.SortOrder.AscendingOrder)

    @exception_catcher
    def setLocaldir(self, dir):
        self.local_dir = dir
        self.ui.localdirEdit.setText(dir)
        self.updateLocalList()

    def getFileinfo(self, path):
        provider = QFileIconProvider()
        icon = provider.icon(QFileInfo(path))
        str_type = provider.type(QFileInfo(path))
        return icon, str_type

    @exception_catcher
    def updateLocalList(self):
        self.localModel.removeRows(0, self.localModel.rowCount())
        files = os.listdir(self.local_dir)
        files.sort(key=lambda x: not os.path.isdir(os.path.join(self.local_dir, x)))
        for filename in files:
            path = os.path.join(self.local_dir, filename)
            icon, str_type = self.getFileinfo(path)
            row = [QStandardItem(icon, filename)] + [QStandardItem(i) for i in [str(os.path.getsize(path)), str_type, time.strftime('%Y-%m-%d %H:%M', time.gmtime(os.path.getmtime(path)))]]
            self.localModel.appendRow(row)

    def transferUpdate(self, progress):
        if progress == 1:
            self.progressBar.setValue(100)
            self.progressBar.hide()
        else:
            self.progressBar.setValue(progress * 100)
            self.progressBar.show()

    def errorSlot(self, code, detail):
        if code in [-1, 421]:
            self.disconnect_from_server()
        self.ui.statusbar.showMessage('ERROR: %d %s' % (code, detail))

    def infoSlot(self, detail):
        self.ui.statusbar.showMessage(detail)

    def debugSlot(self, detail):
        print(detail)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    ui = Ui_mainwindow.Ui_MainWindow()
    ui.setupUi(mainWindow)
    mainWindow.init(ui)
    mainWindow.show()
    sys.exit(app.exec_())
