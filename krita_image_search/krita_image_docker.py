from PyQt5.QtWidgets import QLabel, QLineEdit, QWidget, QScrollArea, QVBoxLayout, QSizePolicy, QLayout
from PyQt5.QtCore import Qt, QObject, QThread, QByteArray, pyqtSignal, QRect, QSize, QMargins, QPoint
from PyQt5.QtGui import QMovie, QPixmap
from krita import *
from krita_image_search.vendor import aiohttp
import asyncio
from .resources import *
import socket
import os
import re

class Krita_Image_Docker(DockWidget):
    def __init__(self):
        super().__init__()
        self.query = ""
        self.clientId = ""
        hostname = socket.gethostname()
        self.ip_address = socket.gethostbyname(hostname)
        lat, lon, _ = re.split(",|\n", os.popen('curl ipinfo.io/loc').read())
        self.lat = lat
        self.lon = lon

        self.setWindowTitle("Krita Image Search")
        mainWidget = QWidget(self)
        self.setWidget(mainWidget)
        mainWidget.setLayout(QVBoxLayout())

        loadingGif = QMovie(":loading.gif")
        loadingGif.setScaledSize(QSize(100, 100))
        self.loadingIcon = QLabel(mainWidget)
        self.loadingIcon.setMovie(loadingGif)
        self.loadingIcon.setAlignment(Qt.AlignHCenter)      
        loadingGif.start()
        self.loadingIcon.hide()

        self.searchBar = QLineEdit(mainWidget)
        self.searchBar.textChanged.connect(self.updateQuery)
        self.searchBar.returnPressed.connect(self.createNewImageArea)
        self.searchBar.returnPressed.connect(self.searchImage)
        self.searchBar.returnPressed.connect(self.loadingIcon.show)

        self.imageArea = QScrollArea(mainWidget)

        mainWidget.layout().addWidget(self.searchBar)
        mainWidget.layout().addWidget(self.loadingIcon)
        mainWidget.layout().addWidget(self.imageArea)

    def canvasChanged(self, canvas):
        pass

    def createNewImageArea(self):
        self.widget().layout().removeWidget(self.imageArea)
        self.imageArea = QScrollArea(self.widget())
        self.imageArea.setWidgetResizable(True)
        
        imageGrid = QWidget(self.widget())
        imageGrid.setLayout(FlowLayout(imageGrid))

        self.imageArea.setWidget(imageGrid)
        self.widget().layout().addWidget(self.imageArea)

    def searchImage(self):
        self.searchApiThread = QThread()
        self.searchApiWorker = SearchAPIWorker(self.query, self.lat, self.lon, self.ip_address, self.clientId)
        self.searchApiWorker.moveToThread(self.searchApiThread)
        
        self.searchApiThread.started.connect(self.searchApiWorker.run)
        self.searchApiWorker.finished.connect(self.searchApiThread.quit)
        self.searchApiWorker.finished.connect(self.searchApiWorker.deleteLater)
        self.searchApiWorker.finished.connect(self.updateClientId)
        self.searchApiThread.finished.connect(self.searchApiThread.deleteLater)
        

        self.searchApiThread.start()

        self.searchBar.setEnabled(False)
        self.searchApiThread.finished.connect(lambda: self.searchBar.setEnabled(True))
        self.searchApiThread.finished.connect(self.loadingIcon.hide)
        self.searchApiWorker.imLoaded.connect(self.createImageTile)

    def createImageTile(self, data):
        # TODO: add features to image tile: right click to copy link
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        image = QLabel()
        image.setPixmap(pixmap.scaledToWidth(100))
        self.imageArea.widget().layout().addWidget(image)

    def updateQuery(self, text):
        self.query = text

    def updateClientId(self, newId):
        self.clientId = newId


class SearchAPIWorker(QObject):
    finished = pyqtSignal(str)
    imLoaded = pyqtSignal(QByteArray)
    url = "https://api.bing.microsoft.com/v7.0/images/search"

    def __init__(self, query, lat, lon, ip, clientId):
        super().__init__()
        self.q = query
        self.lat = lat
        self.lon = lon
        self.ip = ip
        self.clientId = clientId

    def hasClientId(self):
        return self.clientId != ""

    async def getSearchJson(self, session):
        params = {
            "q": self.q,
            # "count": 12 # TODO: set this to a variable in settings
        }
        headers = {
            "Ocp-Apim-Subscription-Key": "f5fa3af6ede24acd9d0392e618fbd9fe",
            "User-Agent": "Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; Touch; rv:11.0) like Gecko",
            "X-MSEdge-ClientIP": self.ip,
            "X-Search-Location": f"lat:{self.lat},long:{self.lon},re:22"
        }
        if (self.hasClientId()):
            headers["X-MSEdge-ClientID"] = self.clientId
        
        async with session.get(self.url, params=params, headers=headers) as resp:
            if (not self.hasClientId()):
                self.clientId = resp.headers["X-MSEdge-ClientID"]
            return await resp.json()

    async def imSearch(self):
        async with aiohttp.ClientSession() as session:
            r_json = await self.getSearchJson(session)
            # create a pixmap from each queried image
            thumbnailParams = {
                "h": 100,
                "w": 100,
                "c": 7
            }
            for im_result in r_json["value"]:
                imUrl = im_result["thumbnailUrl"]
                async with session.get(imUrl, params=thumbnailParams) as resp:
                    data = await resp.read()
                    self.imLoaded.emit(data)
            
            self.finished.emit(self.clientId)

    def run(self):
        asyncio.run(self.imSearch())


class FlowLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)

        if parent is not None:
            self.setContentsMargins(QMargins(0, 0, 0, 0))

        self._item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]

        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)

        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self._do_layout(QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()

        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())

        size += QSize(2 * self.contentsMargins().top(), 2 * self.contentsMargins().top())
        return size

    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._item_list:
            style = item.widget().style()
            layout_spacing_x = style.layoutSpacing(
                QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal
            )
            layout_spacing_y = style.layoutSpacing(
                QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical
            )
            space_x = spacing + layout_spacing_x
            space_y = spacing + layout_spacing_y
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()

        
Krita.instance().addDockWidgetFactory(DockWidgetFactory("krita_image_docker", DockWidgetFactoryBase.DockRight, Krita_Image_Docker))