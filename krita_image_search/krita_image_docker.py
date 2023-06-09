from PyQt5.QtWidgets import QLabel, QLineEdit, QWidget, QScrollArea, QVBoxLayout
from PyQt5.QtCore import Qt, QObject, QThread, QByteArray, pyqtSignal, QSize
from PyQt5.QtGui import QMovie, QPixmap
from krita import *
from krita_image_search.vendor import aiohttp
from krita_image_search.widgets import *
from krita_image_search.resources import *
import asyncio
import logging
from pathlib import Path

BASE_PATH = Path(__file__).parent
LOG_PATH = (BASE_PATH / "krita_image_search.log").resolve()

logging.basicConfig(
    filename=LOG_PATH, 
    filemode="w", 
    format='%(asctime)s %(name)s - %(levelname)s - %(message)s'
)

class Krita_Image_Docker(DockWidget):
    def __init__(self):
        super().__init__()
        self.query = ""
        self.pageOffset = 2
        self.perPage = 30

        # Init logging
        self.logger: logging.Logger = logging.getLogger(__name__)

        # Init Qt DockWidget
        self.initWidget()

    def initWidget(self):
        self.setWindowTitle("Krita Image Search")
        mainWidget = QWidget(self)
        self.setWidget(mainWidget)
        mainWidget.setLayout(QVBoxLayout())

        # Init loading icon
        loadingGif = QMovie(":public/loading.gif")
        loadingGif.setScaledSize(QSize(100, 100))
        self.loadingIcon = QLabel(mainWidget)
        self.loadingIcon.setMovie(loadingGif)
        self.loadingIcon.setAlignment(Qt.AlignCenter)      
        loadingGif.start()
        self.loadingIcon.hide()

        # Init image area
        self.imageArea = QScrollArea(mainWidget)

        # Init error label
        self.errorLabel = QLabel()

        # Init pagination
        self.pagination = PaginationWidget(self.searchImage)

        # Init searchbar
        self.searchBar = QLineEdit(mainWidget)
        self.searchBar.textChanged.connect(self.updateQuery)
        self.searchBar.returnPressed.connect(lambda: self.searchImage(self.query, 1))
        self.searchBar.returnPressed.connect(self.pagination.disableButtons)

        # Attach widgets to main docker widget
        mainWidget.layout().addWidget(self.searchBar)
        mainWidget.layout().addWidget(self.loadingIcon)
        mainWidget.layout().addWidget(self.imageArea)
        mainWidget.layout().addWidget(self.pagination)
        mainWidget.layout().setAlignment(self.pagination, Qt.AlignHCenter)
        mainWidget.layout().addWidget(self.errorLabel)
        

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

    def createPagination(self, pageNum, totalPages):
        self.pagination.update(pageNum, 2, totalPages)
            
    def searchImage(self, query, pageNum):
        # Clear error message
        self.errorLabel.setText("")

        # Clear image area
        self.createNewImageArea()

        # Show loading icon
        self.loadingIcon.show()

        # Set pagination button's query
        self.pagination.setQuery(query)

        # Create thread for search API worker
        self.searchApiThread = QThread()
        self.searchApiWorker = SearchAPIWorker(query, pageNum, self.perPage, self.logger)
        self.searchApiWorker.moveToThread(self.searchApiThread)
        
        self.searchApiThread.started.connect(self.searchApiWorker.run)
        self.searchApiWorker.finished.connect(self.searchApiThread.quit)
        self.searchApiWorker.finished.connect(self.searchApiWorker.deleteLater)
        self.searchApiThread.finished.connect(self.searchApiThread.deleteLater)
        
        self.searchApiThread.start()

        self.searchBar.setEnabled(False)
        self.searchApiThread.finished.connect(self.resetSearch)
        self.searchApiThread.finished.connect(self.loadingIcon.hide)
        self.searchApiThread.finished.connect(self.pagination.enableButtons)
        self.searchApiWorker.imLoaded.connect(self.createImageTile)
        self.searchApiWorker.onError.connect(self.handleSearchError)
        self.searchApiWorker.queried.connect(self.createPagination)

    def resetSearch(self):
        self.searchBar.setEnabled(True)
        self.searchBar.setText("")
        self.query = ""

    def createImageTile(self, data):
        # TODO: add features to image tile: right click to copy link
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        image = QLabel()
        image.setPixmap(pixmap.scaledToWidth(100))
        self.imageArea.widget().layout().addWidget(image)
        self.imageArea.widget().layout().setAlignment(image, Qt.AlignHCenter)

    def updateQuery(self, text):
        self.query = text

    def handleSearchError(self, msg):
        self.errorLabel.setText(msg)
        self.errorLabel.setAlignment(Qt.AlignCenter)
        self.errorLabel.setTextFormat(Qt.RichText)
        self.widget().layout().addWidget(self.errorLabel)


class SearchAPIWorker(QObject):
    finished = pyqtSignal()
    imLoaded = pyqtSignal(QByteArray)
    onError = pyqtSignal(str)
    queried = pyqtSignal(int, int)
    url = "https://joshapiproxy.herokuapp.com/api/unsplash"

    def __init__(self, query, pageNum, perPage, logger):
        super().__init__()
        self.q = query
        self.logger = logger
        self.pageNum = pageNum
        self.perPage = perPage
        self.count_images_failed = 0
        self.lock = asyncio.Lock()

    def errorMsgFormat(self, msg): 
        return f"<h3 style='color:#ce3531';margin:3px>Search Failed: {msg}</h3>"

    async def getSearchJson(self, session):
        params = {
            "query": self.q,
            "page": self.pageNum,
            "per_page": self.perPage
        }
        try:
            async with session.get(self.url, params=params) as resp:
                if resp.status == 429:
                    self.onError.emit(self.errorMsgFormat("Too many requests, please try again later"))
                elif resp.status == 200:
                    json = await resp.json()
                    self.queried.emit(self.pageNum, json["total_pages"])
                    return json
                elif resp.status >= 500:
                    self.onError.emit(self.errorMsgFormat("Server Error"))
                return None
        except Exception as e:
            self.logger.error(e)
            self.onError.emit(self.errorMsgFormat("Server Error"))    
            return None
        
    async def getImageTask(self, session, url, params):
        try:
            async with session.get(url, params=params) as resp:
                data = await resp.read()
                await self.lock.acquire()
                self.imLoaded.emit(data)
                self.lock.release()
        except Exception as e:
            await self.lock.acquire()
            self.logger.error(e)
            self.count_images_failed += 1
            self.lock.release()
            
        
    async def imSearch(self):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            r_json = await self.getSearchJson(session)
            if (r_json is not None):
                tasks = []
                thumbnailParams = {
                    "h": 200,
                    "w": 200,
                    "q": 80,
                    "fit": "crop",
                    "crop": "faces,focalpoint"
                }
                for im_result in r_json["results"]:
                    imUrl = im_result["urls"]["raw"]
                    tasks.append(asyncio.ensure_future(self.getImageTask(session, imUrl, thumbnailParams)))

                await asyncio.gather(*tasks)
                if self.count_images_failed > 0:
                    self.onError.emit(self.errorMsgFormat(f"Cannot load {self.count_images_failed} image(s)"))

            self.finished.emit()

    def run(self):
        asyncio.run(self.imSearch())

        
Krita.instance().addDockWidgetFactory(DockWidgetFactory("krita_image_docker", DockWidgetFactoryBase.DockRight, Krita_Image_Docker))