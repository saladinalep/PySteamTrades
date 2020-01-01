#!/usr/bin/env python3

import sys, smtplib, ssl, keyring, os, logging, time, re, subprocess
from enum import Enum
from bs4 import BeautifulSoup
from PyQt5.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon, QMenu, QAction, QDialog, QFileDialog, \
QStyledItemDelegate, QProgressBar, QMessageBox
from PyQt5.QtGui import QImage, QPixmap, QIcon, QColor, QTextCursor, QIntValidator
from PyQt5.QtCore import Qt, QUrl, QTimer, QSettings, QObject, QRunnable, QThreadPool, QMutex, QMutexLocker, \
QAbstractItemModel, QSortFilterProxyModel, QModelIndex, QSize, pyqtSignal
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt5.QtWebEngineWidgets import QWebEnginePage
from PySteamTrades.Ui_MainWindow import *
from PySteamTrades.Ui_PrefsDialog import *
from PySteamTrades.Ui_TestDialog import *

baseDir = None
readIcon = None
unreadIcon = None

defaultInterval = 5
defaultLevel = 2
defaultLogfile = 'PySteamTrades.log'
logFormat = '%(asctime)s - %(thread)d - %(levelname)s: %(message)s'
stUrl = QUrl('https://www.steamtrades.com/')
messagesUrl = QUrl('https://www.steamtrades.com/messages')

logLevels = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]
orgName = 'PySteamTrades'
appName = 'PySteamTrades'
sysName = "{}-{}".format(orgName, appName)

messageTemplate = """\
Subject: New message on SteamTrades
From: {sender}
To: {recipient}

You have {count} new message(s)

New message from {author}:
{message}
"""

testTemplate = """\
Subject: PySteamTrades test message
From: {sender}
To: {recipient}

PySteamTrades test message
"""

pattern = re.compile("https://www\.steamtrades\.com/trade/.{5}/")
def baseUrl(url):
    m = pattern.match(url)
    if m:
        return m[0]

class NodeType(Enum):
    INVALID = -1
    TRADE_PAGE = 1
    H_GAME = 2
    W_GAME = 3

class Emitter(QObject):
    error = pyqtSignal(str, str)
    loadError = pyqtSignal(int)
    newNode = pyqtSignal(int, str, NodeType)
    updateName = pyqtSignal(int, str)
    updateIconUrl = pyqtSignal(int, str)
    finished = pyqtSignal(int)

class MailSender(QRunnable):
    def __init__(self, sender, recipient, smtpServer, smtpPort, encryption,\
    username, password, message, permalink = '', debug = False):
        super().__init__()
        self.sender = sender
        self.recipient = recipient
        self.smtpServer = smtpServer
        self.smtpPort = smtpPort
        self.encryption = encryption
        self.username = username
        self.password = password
        self.message = message
        self.permalink = permalink
        self.debug = debug
        self.emitter = Emitter()
    def run(self):
        server = None
        try:
            context = ssl.create_default_context()
            if self.encryption == 'SSL':
                server = smtplib.SMTP_SSL(self.smtpServer, self.smtpPort, timeout=30, context=context)
            else:
                server = smtplib.SMTP(self.smtpServer, self.smtpPort, timeout=30)
            if self.debug:
                server.set_debuglevel(1)
            if self.encryption == 'TLS':
                server.starttls(context=context)
            if self.username != '':
                server.login(self.username, self.password)
            server.sendmail(self.sender, self.recipient, self.message.encode("utf8"))
        except Exception as e:
            logging.error('Error sending email: ' + str(e))
            self.emitter.error.emit('Error sending email: ' + str(e), self.permalink)
        try:
            if server:
                server.quit()
        except:
            pass

class TestDialog(QDialog):
    newMessage = pyqtSignal(str)
    def __init__(self, parent, mailSender):
        super().__init__(parent)
        self.ui = Ui_TestDialog()
        self.ui.setupUi(self)
        self.mailSender = mailSender
        self.newMessage.connect(self.logMessage)
        self.mailSender.emitter.error.connect(self.logMessage)
    def showEvent(self, event):
        super().showEvent(event)
        # redirect stderr to self.write, to capture debug output of sendmail
        self.stderr = sys.stderr
        sys.stderr = self
        QThreadPool.globalInstance().start(self.mailSender)
    def closeEvent(self, event):
        sys.stderr = self.stderr
        event.accept()
    def write(self, message):
        # update logTextEdit from the GUI thread
        self.newMessage.emit(message)
    def logMessage(self, message):
        self.ui.logTextEdit.moveCursor(QTextCursor.End)
        self.ui.logTextEdit.insertPlainText(message)

class PrefsDialog(QDialog):
    intervalChanged = pyqtSignal(int)
    loglevelChanged = pyqtSignal(int)
    logfileChanged = pyqtSignal()
    autoSearchChanged = pyqtSignal()
    def __init__(self, parent):
        super().__init__(parent)
        self.ui = Ui_PrefsDialog()
        self.ui.setupUi(self)

        self.ui.okButton.clicked.connect(self.accept)
        self.ui.testButton.clicked.connect(self.testSettings)
        self.ui.logfileButton.clicked.connect(self.selectFile)

        validator = QIntValidator(1, 65535, self)
        self.ui.portLineEdit.setValidator(validator)

        s = QSettings(orgName, appName)

        self.ui.intervalSpinBox.setValue(s.value('misc/interval', defaultInterval, type = int))
        self.ui.loglevelComboBox.setCurrentIndex(s.value('misc/loglevel', defaultLevel, type = int))
        self.ui.logGroupBox.setChecked(True if s.value('logfile/enable', False, type=bool) else False)
        self.ui.logfileLineEdit.setText(s.value('logfile/filename', defaultLogfile))

        self.ui.emailGroupBox.setChecked(True if s.value('email/notify', False, type=bool) else False)
        self.ui.encryptionGroupBox.setChecked(True if s.value('email/encrypt', False, type=bool) else False)
        self.ui.loginGroupBox.setChecked(True if s.value('email/login', False, type=bool) else False)

        self.ui.senderLineEdit.setText(s.value('email/sender'))
        self.ui.recipientLineEdit.setText(s.value('email/recipient'))
        self.ui.hostLineEdit.setText(s.value('email/host'))
        self.ui.portLineEdit.setText(s.value('email/port'))

        self.ui.encryptionComboBox.setCurrentText(s.value('email/encryption_type'))

        self.ui.usernameLineEdit.setText(s.value('email/username'))
        try:
            self.ui.passwordLineEdit.setText(keyring.get_password(sysName,  "email/password"))
        except Exception as e:
            logging.warning('Cannot read password from keyring: ' + str(e))

        self.ui.autoSearchGroupBox.setChecked(True if s.value('autosearch/enable', False, type=bool) else False)
        self.ui.haveTextEdit.setPlainText(s.value('autosearch/have_list', ''))
        self.ui.wantTextEdit.setPlainText(s.value('autosearch/want_list', ''))
    def selectFile(self):
        filename, _ = QFileDialog.getSaveFileName(self, 'Log file name', self.ui.logfileLineEdit.text(), "Log file (*.log);;All files(*.*)")
        if filename:
            self.ui.logfileLineEdit.setText(filename)
    def testSettings(self):
        mailSender = MailSender(self.ui.senderLineEdit.text(), self.ui.recipientLineEdit.text(),\
        self.ui.hostLineEdit.text(), self.ui.portLineEdit.text(),\
        self.ui.encryptionComboBox.currentText() if self.ui.encryptionGroupBox.isChecked() else '',\
        self.ui.usernameLineEdit.text() if self.ui.loginGroupBox.isChecked() else '',\
        self.ui.passwordLineEdit.text() if self.ui.loginGroupBox.isChecked() else '',\
        testTemplate.format(sender = self.ui.senderLineEdit.text(),  recipient = self.ui.recipientLineEdit.text()), '', True)
        testDialog = TestDialog(self,  mailSender)
        testDialog.exec_()
    def accept(self):
        s = QSettings(orgName, appName)

        newInterval = self.ui.intervalSpinBox.value()
        if s.value('misc/interval', type = int) != newInterval:
            s.setValue('misc/interval', newInterval)
            self.intervalChanged.emit(newInterval)

        newLevel = self.ui.loglevelComboBox.currentIndex()
        if s.value('misc/loglevel', defaultLevel, type = int) != newLevel:
            s.setValue('misc/loglevel', newLevel)
            self.loglevelChanged.emit(newLevel)

        if s.value('logfile/enable', False, type = bool) != self.ui.logGroupBox.isChecked()\
        or s.value('logfile/filename') != self.ui.logfileLineEdit.text():
            s.setValue('logfile/enable', self.ui.logGroupBox.isChecked())
            s.setValue('logfile/filename', self.ui.logfileLineEdit.text())
            self.logfileChanged.emit()

        s.setValue('email/notify', self.ui.emailGroupBox.isChecked())
        s.setValue('email/encrypt', self.ui.encryptionGroupBox.isChecked())
        s.setValue('email/login', self.ui.loginGroupBox.isChecked())

        s.setValue('email/sender',  self.ui.senderLineEdit.text())
        s.setValue('email/recipient',  self.ui.recipientLineEdit.text())
        s.setValue('email/host',  self.ui.hostLineEdit.text())
        s.setValue('email/port',  self.ui.portLineEdit.text())

        s.setValue('email/encryption_type',  self.ui.encryptionComboBox.currentText())

        s.setValue('email/username',  self.ui.usernameLineEdit.text())
        try:
            keyring.set_password(sysName,  "email/password", self.ui.passwordLineEdit.text())
        except Exception as e:
            logging.error('Cannot save password to keyring: ' + str(e))

        if s.value('autosearch/enable', False, type = bool) != self.ui.autoSearchGroupBox.isChecked()\
        or s.value('autosearch/have_list', '') != self.ui.haveTextEdit.toPlainText()\
        or s.value('autosearch/want_list',  '') != self.ui.wantTextEdit.toPlainText():
            s.setValue('autosearch/enable', self.ui.autoSearchGroupBox.isChecked())
            s.setValue('autosearch/have_list', self.ui.haveTextEdit.toPlainText())
            s.setValue('autosearch/want_list', self.ui.wantTextEdit.toPlainText())
            self.autoSearchChanged.emit()
        super().accept()

class Handler(QObject, logging.Handler):
    newMessage = pyqtSignal(str)
    def emit(self, record):
        msg = self.format(record)
        self.newMessage.emit(msg)
    def write(self, msg):
        pass

class Node:
    def __init__(self, parent = None, name = '', type_ = NodeType.INVALID, url = ''):
        self.parent = parent
        self.name = name
        self.type_ = type_
        self.url = url
        self.iconUrl = ''
        self.icon = None
        self.children = []
        self.counter = 0
    def childCount(self):
        return len(self.children)
    def getChild(self, row):
        if row >= 0 and row < self.childCount():
            return self.children[row]
    def getParent(self):
        return self.parent
    def childRow(self, id_):
        for i, child in enumerate(self.children):
            if child.id_ == id_:
                return i
        return -1
    def getRow(self):
        if self.parent:
            return self.parent.childRow(self.id_)
    def addChild(self, name, type_, url):
        if url:
            row = 0
        else:
            row = len(self.children)
        node = Node(self, name, type_, url)
        node.id_ = self.counter
        self.counter += 1
        self.children.insert(row, node)
        return node
    def removeChild(self, row):
        self.children.pop(row)
    def ids(self):
        return [child.id_ for child in self.children]

class Model(QAbstractItemModel):
    statusMessage = pyqtSignal(str)
    progress = pyqtSignal(int)
    cancelAll = pyqtSignal()
    def __init__(self, haveList = [], wantList = []):
        super().__init__()
        self.root = Node()
        self.nam = QNetworkAccessManager()
        self.haveList = haveList
        self.wantList = wantList
        self.queued = 0
        self.processed = 0
        self.timestamps = {}
        self.urls = {}
        self.ids = {}
    def rowCount(self, index):
        if index.isValid():
            return index.internalPointer().childCount()
        return self.root.childCount()
    def columnCount(self, index):
        return 2
    def index(self, row, column, parentIndex = None):
        if not self.hasIndex(row, column, parentIndex):
            return QModelIndex()
        if not parentIndex or not parentIndex.isValid():
            parent = self.root
        else:
            parent = parentIndex.internalPointer()
        child = parent.getChild(row)
        if child:
            return self.createIndex(row, column, child)
        else:
            return QModelIndex()
    def parent(self, index):
        if index.isValid():
            p = index.internalPointer().getParent()
            if p != self.root:
                return self.createIndex(p.getRow(), 0, p)
        return QModelIndex()
    def data(self, index, role):
        if not index.isValid():
            return None
        node = index.internalPointer()
        if role == Qt.DisplayRole:
            if index.column() == 0:
                return node.name
            else:
                return node.url
        if role == Qt.DecorationRole:
            if index.column() == 0:
                return node.icon
        if role == Qt.BackgroundRole:
            if node.type_ == NodeType.H_GAME:
                return QColor(0xFF, 0xCC, 0xCB)
            elif node.type_ == NodeType.W_GAME:
                return QColor(0xAD, 0xD8, 0xE6)
    def addChild(self, parent, name, type_, url = '', iconUrl = ''):
        if parent == self.root:
            parentIndex = QModelIndex()
            if url in self.urls.keys():
                node = self.urls[url]
                self.beginRemoveRows(parentIndex, node.getRow(), node.getRow())
                self.root.removeChild(node.getRow())
                self.urls.pop(url)
                self.ids.pop(node.id_)
                self.endRemoveRows()
            self.beginInsertRows(parentIndex, 0, 0)
        else:
            parentIndex = self.createIndex(parent.getRow(), 0, parent)
            self.beginInsertRows(parentIndex, parent.childCount(), parent.childCount())
        node = parent.addChild(name, type_, url)
        if parent == self.root:
            self.urls[url] = node
            self.ids[node.id_] = node
        self.endInsertRows()
        if iconUrl:
            self.onUpdateIconUrl(node.id_, iconUrl)
        return node
    def onUpdateName(self, id_, newName):
        if id_ not in self.ids.keys():
            return
        node = self.ids[id_]
        if node.name != newName:
            node.name = newName
            index = self.createIndex(node.getRow(), 0, node)
            self.dataChanged.emit(index, index)
    def onUpdateIconUrl(self, id_, newUrl):
        if id_ not in self.ids.keys() or not newUrl:
            return
        node = self.ids[id_]
        if node.iconUrl != newUrl:
            node.iconUrl = newUrl
            request = QNetworkRequest(QUrl(newUrl))
            reply = self.nam.get(request)
            reply.finished.connect(lambda self=self, id_=id_: self.onUpdateIcon(id_, self.sender()))
    def onUpdateIcon(self, id_, reply):
        if id_ not in self.ids.keys():
            return
        if reply.error() != QNetworkReply.NoError:
            logging.warning("Error downloading icon {}: {}".format(\
            reply.request().url().toString(), reply.errorString()))
            return
        try:
            node = self.ids[id_]
            img = QImage()
            img.loadFromData(reply.readAll())
            icon = QIcon(QPixmap.fromImage(img))
            node.icon = icon
            index = self.createIndex(node.getRow(), 0, node)
            self.dataChanged.emit(index, index)
        except Exception as e:
            logging.error('Error setting icon: ' + str(e))
    def onNewNode(self, parentId, name, type_):
        if parentId not in self.ids.keys():
            return
        parent = self.ids[parentId]
        self.addChild(parent, name, type_)
    def parseSearchResults(self, html):
        try:
            soup = BeautifulSoup(html, 'html.parser')

            trades = soup.find_all('div', attrs={'class': 'row_inner_wrap'})
            counter = 0
            for trade in reversed(trades):
                if trade.find('i', attrs={'class': 'red fa fa-lock'}):
                    # Closed trade page
                    continue
                url = 'https://www.steamtrades.com' + trade.find('h3').find('a')['href']
                if self.queueUrl(url, False):
                    counter += 1
            if counter > 0:
                self.statusMessage.emit('Queued {} pages'.format(counter))
        except Exception as e:
            logging.error('Error parsing search results: ' + str(e))
    def queueUrl(self, url, force, title = '', iconUrl = ''):
        url = baseUrl(url)
        if not force and url in self.timestamps.keys() and time.time() < self.timestamps[url] + 3600:
            return False
        if not title:
            title = url
        node = self.addChild(self.root, title, NodeType.TRADE_PAGE, url, iconUrl)
        w = Worker(url, self.haveList, self.wantList, node.id_)
        node.worker = w
        w.emitter.newNode.connect(self.onNewNode)
        w.emitter.updateName.connect(self.onUpdateName)
        w.emitter.updateIconUrl.connect(self.onUpdateIconUrl)
        w.emitter.loadError.connect(self.workerError)
        w.emitter.finished.connect(self.workerFinished)
        self.cancelAll.connect(w.cancel)
        self.timestamps[url] = time.time()
        self.queued += 1
        logging.debug('Queued URL: ' + url)
        return True
    def workerFinished(self, id_):
        if id_ not in self.ids.keys():
            logging.error("workerFinished() called for invalid id {}".format(id_))
            return
        node = self.ids[id_]
        if not node.worker:
            logging.error("workerFinished() called more than once for {}".format(node.url))
            return
        node.worker = None
        self.processed += 1
        if self.processed == self.queued:
            self.queued = 0
            self.processed = 0
            self.progress.emit(100)
        elif self.queued == 0:
            logging.error("invalid value of queued workers")
        else:
            self.progress.emit(int(self.processed * 100 / self.queued))
    def workerError(self, id_):
        if id_ not in self.ids.keys():
            return
        self.onUpdateName(id_, "Error loading page")
        node = self.ids[id_]
        self.timestamps[node.url] = 0
    def checkNow(self, url):
        self.queueUrl(url, True)
    def invalidateAll(self):
        # clear timestamps to invalidate the current search results
        self.timestamps.clear()
    def updateLists(self, haveList, wantList):
        self.haveList = haveList
        self.wantList = wantList
        self.invalidateAll()

class WorkerState(Enum):
    PENDING = 1
    RUNNING = 2
    FINISHED = 3

class Worker(QRunnable):
    def __init__(self, url, haveList = [], wantList = [], id_ = -1):
        super().__init__()
        self.url = url
        self.haveList = haveList
        self.wantList = wantList
        self.id_ = id_
        self.state = WorkerState.PENDING
        self.mutex = QMutex()
        self.emitter = Emitter()
        self.page = QWebEnginePage()
        self.html = ''
        self.page.loadFinished.connect(self.loadFinished)
        self.page.setUrl(QUrl(self.url))
        # Set timeout to 3 minutes
        QTimer.singleShot(3 * 60 * 1000, self.cancel)
    def changeState(self, new, old = None):
        mutexLocker = QMutexLocker(self.mutex)
        if not old or old == self.state:
            self.state = new
            return True
    def run(self):
        if not self.changeState(WorkerState.RUNNING, WorkerState.PENDING):
            return
        try:
            soup = BeautifulSoup(self.html, 'html.parser')
            closedTag = soup.find('div', attrs={'class': 'notification yellow'})
            if closedTag and closedTag.text.startswith('Closed'):
                title = 'Closed'
            else:
                title = soup.find('div', attrs={'class': 'page_heading'}).find('h1').text
            style = soup.find('div', attrs={'class': 'comment_inner'}).find('a', attrs={'class': 'author_avatar'})['style']
            res = re.findall('url\((.*)\);', style)
            if len(res) == 1:
                iconUrl = res[0]
            else:
                iconUrl = ''
            self.emitter.updateName.emit(self.id_, title)
            self.emitter.updateIconUrl.emit(self.id_, iconUrl)

            h = soup.find('div', attrs={'class': 'have markdown'})
            if h:
                hls = h.text.split('\n')
                for g in self.wantList:
                    for hl in hls:
                        if g in hl.lower():
                            self.emitter.newNode.emit(self.id_, '[H] ' + hl, NodeType.H_GAME)
            h = soup.find('div', attrs={'class': 'want markdown'})
            if h:
                hls = h.text.split('\n')
                for g in self.haveList:
                    for hl in hls:
                        if g in hl.lower():
                            self.emitter.newNode.emit(self.id_, '[W] ' + hl, NodeType.W_GAME)
        except Exception as e:
            logging.error('Error parsing trade page: ' + str(e))
        self.changeState(WorkerState.FINISHED)
        self.emitter.finished.emit(self.id_)
    def loadFinished(self, ok):
        if not ok:
            logging.warning('Failed to load page: ' + self.url)
            self.changeState(WorkerState.FINISHED)
            self.emitter.loadError.emit(self.id_)
            self.emitter.finished.emit(self.id_)
            return
        self.page.toHtml(self.processPage)
    def processPage(self, html):
        self.html = html
        QThreadPool.globalInstance().start(self)
    def cancel(self):
        if not self.changeState(WorkerState.FINISHED, WorkerState.PENDING):
            return
        self.page.triggerAction(QWebEnginePage.Stop)
        logging.warning('Canceling ' + self.url)
        self.emitter.loadError.emit(self.id_)
        self.emitter.finished.emit(self.id_)

class BookmarksModel(QSortFilterProxyModel):
    def __init__(self, urls):
        super().__init__()
        self.bookmarkedUrls = urls
    def filterAcceptsRow(self, sourceRow, sourceParent):
        urlIndex = self.sourceModel().index(sourceRow, 1, sourceParent)
        url = self.sourceModel().data(urlIndex, role = Qt.DisplayRole)
        # Only trade pages have URLs. Game nodes are always shown
        if not url or url in self.bookmarkedUrls:
            return True
        return False

class ItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        if index.isValid():
            urlIndex = index.siblingAtColumn(1)
            if urlIndex and urlIndex.isValid() and urlIndex.data(Qt.DisplayRole):
                return size * 1.2
        return size

class MainWindow(QMainWindow):
    error = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowIcon(readIcon)
        # permalinks of comments we already notified the user of
        self.permalinks = []
        self.quitting = False
        self.error.connect(self.showError)
        # Logger
        self.fileHandler = None
        self.handler = Handler()
        self.handler.newMessage.connect(self.logMessage)
        s = QSettings(orgName, appName)
        level = s.value('misc/loglevel', defaultLevel, type = int)
        self.handler.setLevel(logLevels[level])
        self.handler.setFormatter(logging.Formatter(logFormat))
        logging.getLogger().addHandler(self.handler)
        self.updateLogger()
        # Auto search
        self.model = Model()
        self.model.statusMessage.connect(self.showStatusMessage)
        self.model.progress.connect(self.showProgress)
        self.updateAutoSearch()
        self.autoSearchPage = QWebEnginePage()
        self.autoSearchPage.loadFinished.connect(self.searchPageLoaded)
        self.progressBar = QProgressBar()
        self.progressBar.setTextVisible(False)
        self.progressBar.setMaximumWidth(100)
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(99)
        self.statusBar().addPermanentWidget(self.progressBar)
        self.progressBar.hide()
        self.delegate = ItemDelegate()
        self.fontSize = 14
        self.ui.treeView.setHeaderHidden(True)
        self.ui.treeView.setIconSize(QSize(40, 40))
        self.ui.treeView.setStyleSheet("QTreeView {{font-size: {}pt;}}".format(self.fontSize))
        self.ui.treeView.setModel(self.model)
        self.ui.treeView.setItemDelegate(self.delegate)
        self.ui.treeView.hideColumn(1)
        self.ui.treeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.treeView.customContextMenuRequested.connect(self.onCustomMenu)

        bookmarks = s.value('bookmarks/bookmarks_list', '')
        self.bookmarksList = [baseUrl(line) for line in bookmarks.split('\n') if baseUrl(line)]
        self.bookmarksList = list(dict.fromkeys(self.bookmarksList))
        self.bookmarksModel = BookmarksModel(self.bookmarksList)
        self.bookmarksModel.setSourceModel(self.model)
        self.ui.bookmarksTreeView.setHeaderHidden(True)
        self.ui.bookmarksTreeView.setIconSize(QSize(40, 40))
        self.ui.bookmarksTreeView.setStyleSheet("QTreeView {{font-size: {}pt;}}".format(self.fontSize))
        self.ui.bookmarksTreeView.setModel(self.bookmarksModel)
        self.ui.bookmarksTreeView.setItemDelegate(self.delegate)
        self.ui.bookmarksTreeView.hideColumn(1)
        self.ui.bookmarksTreeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.bookmarksTreeView.customContextMenuRequested.connect(self.onCustomMenu)
        # Tray icon
        self.ui.prefsAction.triggered.connect(self.showPrefs)
        self.ui.refreshAction.triggered.connect(self.refresh)
        self.ui.quitAction.triggered.connect(self.quit)
        self.ui.zoomInAction.triggered.connect(self.zoomIn)
        self.ui.zoomOutAction.triggered.connect(self.zoomOut)
        minimizeAction = QAction("Mi&nimize",  self)
        minimizeAction.triggered.connect(self.hide)
        restoreAction = QAction("&Restore",  self)
        restoreAction.triggered.connect(self.show)
        trayMenu = QMenu(self)
        trayMenu.addAction(minimizeAction)
        trayMenu.addAction(restoreAction)
        trayMenu.addAction(self.ui.prefsAction)
        trayMenu.addAction(self.ui.refreshAction)
        trayMenu.addAction(self.ui.quitAction)
        self.trayIcon = QSystemTrayIcon()
        self.trayIcon.setContextMenu(trayMenu)
        self.trayIcon.activated.connect(self.iconActivated)
        self.trayIcon.setIcon(readIcon)
        self.trayIcon.setVisible(True)
        self.ui.webView.loadStarted.connect(lambda self=self: self.ui.urlLineEdit.setText(self.ui.webView.url().toString()))
        self.ui.webView.loadFinished.connect(self.loadFinished)
        self.ui.urlLineEdit.returnPressed.connect(lambda self=self: self.ui.webView.setUrl(QUrl(self.ui.urlLineEdit.text())))
        self.ui.webView.setUrl(stUrl)
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.updateInterval(s.value('misc/interval', defaultInterval, type = int))
        self.timer.start()
        self.messagesPage = QWebEnginePage()
        self.messagesPage.loadFinished.connect(self.messagesPageLoaded)
        self.refresh()
    def zoomIn(self):
        currentIndex = self.ui.tabWidget.currentIndex()
        if currentIndex == 0:
            self.ui.webView.setZoomFactor(self.ui.webView.zoomFactor() + 0.25)
        elif currentIndex == 1 or currentIndex == 2:
            if self.fontSize >= 20:
                return
            self.fontSize += 1
            self.ui.treeView.setStyleSheet("QTreeView {{font-size: {}pt;}}".format(self.fontSize))
            self.ui.bookmarksTreeView.setStyleSheet("QTreeView {{font-size: {}pt;}}".format(self.fontSize))
        elif currentIndex == 3:
            self.ui.logTextEdit.zoomIn()
    def zoomOut(self):
        currentIndex = self.ui.tabWidget.currentIndex()
        if currentIndex == 0:
            self.ui.webView.setZoomFactor(self.ui.webView.zoomFactor() - 0.25)
        elif currentIndex == 1 or currentIndex == 2:
            if self.fontSize <= 8:
                return
            self.fontSize -= 1
            self.ui.treeView.setStyleSheet("QTreeView {{font-size: {}pt;}}".format(self.fontSize))
            self.ui.bookmarksTreeView.setStyleSheet("QTreeView {{font-size: {}pt;}}".format(self.fontSize))
        elif currentIndex == 3:
            self.ui.logTextEdit.zoomOut()
    def onCustomMenu(self, point):
        sender = self.sender()
        index = sender.indexAt(point)
        urlIndex = index.siblingAtColumn(1)
        url = str(sender.model().data(urlIndex, role = Qt.DisplayRole))
        url = baseUrl(url)
        if not url:
            return
        self.contextMenu = QMenu()
        action = QAction("Copy url", self.contextMenu)
        action.triggered.connect(lambda checked, arg=url: QApplication.clipboard().setText(arg))
        self.contextMenu.addAction(action)
        action = QAction("Open in browser", self.contextMenu)
        action.triggered.connect(lambda checked, self=self, url=url: self.toBrowser(url))
        self.contextMenu.addAction(action)
        action = QAction("Open in default browser", self.contextMenu)
        action.triggered.connect(lambda checked, arg=url: subprocess.call([sys.executable, '-m', 'webbrowser', '-t', arg]))
        self.contextMenu.addAction(action)
        if url not in self.bookmarksList:
            enabled = True
            action = QAction("Add to bookmarks", self.contextMenu)
        else:
            enabled = False
            action = QAction("Remove from bookmarks", self.contextMenu)
        action.triggered.connect(lambda checked, self=self, url=url, enabled=enabled: self.setBookmarked(url, enabled))
        self.contextMenu.addAction(action)
        action = QAction("Check now", self.contextMenu)
        action.triggered.connect(lambda checked, self=self, url=url: self.model.checkNow(url))
        self.contextMenu.addAction(action)
        self.contextMenu.exec(sender.viewport().mapToGlobal(point))
    def setBookmarked(self, url, enabled):
        bookmarked =  url in self.bookmarksList
        s = QSettings(orgName, appName)
        if bookmarked and not enabled:
            self.bookmarksList.remove(url)
        elif enabled and not bookmarked:
            self.bookmarksList.append(url)
        self.bookmarksModel.invalidate()
        s.setValue('bookmarks/bookmarks_list', '\n'.join(self.bookmarksList))
    def toBrowser(self, url):
        self.ui.webView.setUrl(QUrl(url))
        self.ui.tabWidget.setCurrentIndex(0)
    def logMessage(self, msg):
        self.ui.logTextEdit.appendPlainText(msg)
    def updateLogLevel(self, newLevel):
        logging.debug('setting log level ' + str(newLevel))
        logging.getLogger().setLevel(logLevels[newLevel])
        for h in logging.getLogger().handlers:
            h.setLevel(logLevels[newLevel])
    def updateLogger(self):
        logging.debug("updating logger handlers")
        s = QSettings(orgName, appName)
        if self.fileHandler:
            logging.getLogger().removeHandler(self.fileHandler)
            self.fileHandler = None
        if s.value('logfile/enable', False, type = bool):
            f = s.value('logfile/filename', defaultLogfile)
            if not os.path.isabs(f):
                f = os.path.join(baseDir, f)
            logging.debug('new file handler for ' + f)
            fileHandler = logging.FileHandler(f)
            level = s.value('misc/loglevel', defaultLevel, type = int)
            fileHandler.setLevel(logLevels[level])
            fileHandler.setFormatter(logging.Formatter(logFormat))
            self.fileHandler = fileHandler
            logging.getLogger().addHandler(self.fileHandler)
    def updateAutoSearch(self):
        s = QSettings(orgName, appName)
        self.autoSearchEnabled = s.value('autosearch/enable', False, type = bool)
        haveListStr = s.value('autosearch/have_list', '')
        haveList = [line.strip().lower() for line in haveListStr.split('\n') if line.strip()]
        wantListStr = s.value('autosearch/want_list', '')
        wantList = [line.strip().lower() for line in wantListStr.split('\n') if line.strip()]
        self.model.updateLists(haveList, wantList)
    def searchPageLoaded(self, ok):
        if not ok:
            logging.warning('Failed to load URL: ' + stUrl.toString())
            return
        self.autoSearchPage.toHtml(self.model.parseSearchResults)
    def refresh(self):
        self.messagesPage.setUrl(messagesUrl)
        if not self.autoSearchEnabled:
            return
        self.autoSearchPage.setUrl(stUrl)
        for url in self.bookmarksList:
            self.model.queueUrl(url, False)
    def updateInterval(self, newInterval):
        logging.info('setting refresh interval: {} minutes'.format(newInterval))
        self.timer.setInterval(newInterval * 1000 * 60)
    def quit(self):
        self.trayIcon.setVisible(False)
        self.quitting = True
        self.model.cancelAll.emit()
        self.statusBar().showMessage('Waiting for worker threads...')
        QThreadPool.globalInstance().waitForDone()
        QApplication.setQuitOnLastWindowClosed(True)
        self.close()
    def loadFinished(self, ok):
        if not ok:
            logging.warning('failed to load URL: ' + self.ui.webView.url().toString())
            return
        self.ui.urlLineEdit.setText(self.ui.webView.url().toString())
        self.ui.urlLineEdit.setCursorPosition(0)

        if not self.autoSearchEnabled:
            return
        url = self.ui.webView.url().toString()
        if url == stUrl.toString() or url.startswith('https://www.steamtrades.com/trades/search'):
            self.ui.webView.page().toHtml(self.model.parseSearchResults)
        elif url.startswith('https://www.steamtrades.com/trade/'):
            self.model.queueUrl(url, False)

    def messagesPageLoaded(self, ok):
        if not ok:
            logging.warning('failed to load URL: ' + self.messagesPage.url().toString())
            return
        self.messagesPage.toHtml(self.checkMessages)
    def closeEvent(self,  event):
        if not self.quitting:
            self.hide()
            event.ignore()
        else:
            event.accept()
    def iconActivated(self,  reason):
        if reason == QSystemTrayIcon.Context or reason == QSystemTrayIcon.Trigger:
            return
        if self.isVisible():
            self.hide()
        else:
            self.show()
    def showPrefs(self):
        d = PrefsDialog(self)
        d.intervalChanged.connect(self.updateInterval)
        d.loglevelChanged.connect(self.updateLogLevel)
        d.logfileChanged.connect(self.updateLogger)
        d.autoSearchChanged.connect(self.updateAutoSearch)
        d.exec_()
    def showError(self, message):
        self.trayIcon.showMessage('', message, QSystemTrayIcon.Warning)
    def showStatusMessage(self, message):
        self.statusBar().showMessage(message, 5000)
    def showProgress(self, percent):
        if percent >= 0 and percent <= 99:
            self.progressBar.setValue(percent)
            if self.progressBar.isHidden():
                self.progressBar.show()
        else:
            self.progressBar.hide()
    def onMailError(self, msg, permalink):
        self.showError(msg)
        if permalink in self.permalinks:
            self.permalinks.remove(permalink)
    def checkMessages(self,  page):
        url = self.messagesPage.url()
        logging.info('loaded page ' + url.toString())
        soup = BeautifulSoup(page, 'html.parser')
        if url.host() == 'www.steamtrades.com' or url.host() == 'steamtrades.com':
            if '<span>Messages' not in page:
                logging.warning('log in to SteamTrades to receive message notifications')
                return
        if url != messagesUrl:
            return
        messageCount = soup.find('span', attrs={'class': 'message_count'})
        if not messageCount:
            self.trayIcon.setIcon(readIcon)
            self.setWindowIcon(readIcon)
            return

        logging.debug('message count:' + messageCount.text)

        self.trayIcon.setIcon(unreadIcon)
        self.setWindowIcon(unreadIcon)
        try:
            parsed = 0
            for comment in soup.find_all('div', attrs={'class': 'comment_inner'}):
                if parsed >= int(messageCount.text):
                    break
                if comment.find('div', attrs={'class': 'comment_unread'}) == None:
                    continue
                parsed += 1
                author = comment.find('a', attrs={'class': 'author_name'}).text.strip()
                message = comment.find('div', attrs={'class': 'comment_body_default markdown'}).text.strip()
                permalink = comment.find_all('a')[-1]['href']
                if permalink not in self.permalinks:
                    logging.debug('unread comment: \n' + str(comment))
                    logging.debug('author: ' + author)
                    logging.debug('message: \n' + message)
                    logging.debug('permalink:' + permalink)
                    self.trayIcon.showMessage("New message from " + author,  message)
                    s = QSettings(orgName, appName)
                    if s.value('email/notify', False, type=bool):
                        sender = s.value('email/sender')
                        recipient =s.value('email/recipient')
                        smtpServer = s.value('email/host')
                        smtpPort = s.value('email/port')
                        encryption = s.value('email/encryption_type') if s.value('email/encrypt', False, type=bool) else ''
                        username = s.value('email/username') if s.value('email/login', False, type=bool) else ''
                        password = ''
                        try:
                            if s.value('email/login', False, type=bool):
                                password = keyring.get_password(sysName,  "email/password")
                        except Exception as e:
                            logging.warning('Cannot read password from keyring: ' + str(e))
                        mailSender = MailSender(sender, recipient, smtpServer, smtpPort, encryption, username, password,\
                        messageTemplate.format(sender = sender,  recipient = recipient, count = messageCount.text, author = author, message = message), permalink)
                        logging.info('sending email...')
                        mailSender.emitter.error.connect(self.onMailError)
                        QThreadPool.globalInstance().start(mailSender)
                    self.permalinks.append(permalink)
        except Exception as e:
            logging.error(str(e))
            self.error.emit(str(e))

if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        baseDir = sys._MEIPASS
    else:
        baseDir = os.path.dirname(os.path.realpath(__file__))
    app = QApplication(sys.argv)

    try:
        from tendo import singleton
        me = singleton.SingleInstance()
    except singleton.SingleInstanceException:
        QMessageBox.warning(None, "Error", "Already running")
        sys.exit(1)

    s = QSettings(orgName, appName)
    level = s.value('misc/loglevel', defaultLevel, type = int)
    logging.basicConfig(format=logFormat, level=logLevels[level])
    if sys.stderr == None:
        logging.getLogger().handlers.clear()
    QApplication.setQuitOnLastWindowClosed(False)
    readIcon = QIcon(baseDir + '/read.ico')
    unreadIcon = QIcon(baseDir + '/unread.ico')
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
