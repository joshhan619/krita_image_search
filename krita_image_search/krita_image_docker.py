from PyQt5.QtWidgets import QLabel, QLineEdit, QWidget, QScrollArea, QVBoxLayout, QPushButton
from PyQt5.QtCore import Qt, QThread, QSize
from PyQt5.QtGui import QMovie, QPixmap
from krita import *
from krita_image_search.widgets import *
from krita_image_search.resources import *
from krita_image_search.workers import *

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
        self.infoLabel = QLabel()
        self.infoLabel.setFixedHeight(50)
        self.infoLabel.setAlignment(Qt.AlignHCenter)

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
        mainWidget.layout().addWidget(self.infoLabel)
        

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
        self.infoLabel.setText("")

        # Clear image area
        self.createNewImageArea()

        # Show loading icon
        self.loadingIcon.show()

        # Set pagination button's query
        self.pagination.setQuery(query)

        # Create thread for search API worker
        self.searchApiThread = QThread()
        self.searchApiWorker = ImageSearchWorker(query, pageNum, self.perPage, self.logger)
        self.searchApiWorker.moveToThread(self.searchApiThread)
        
        #self.searchApiThread.started.connect(lambda: self.searchApiWorker.queryImages(query, pageNum, self.perPage))
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

    def getFullImage(self, fullUrl, download_location):
        self.searchApiThread = QThread()
        self.searchApiWorker = ImageDownloadWorker(fullUrl, download_location, self.logger)
        self.searchApiWorker.moveToThread(self.searchApiThread)

        self.searchApiThread.started.connect(self.searchApiWorker.run)
        self.searchApiWorker.finished.connect(self.searchApiThread.quit)
        self.searchApiWorker.finished.connect(self.searchApiWorker.deleteLater)
        self.searchApiThread.finished.connect(self.searchApiThread.deleteLater)

        self.searchApiThread.start()
        self.searchApiWorker.fullImageLoaded.connect(self.copyToClipboard)

    def resetSearch(self):
        self.searchBar.setEnabled(True)
        self.searchBar.setText("")
        self.query = ""

    def createImageTile(self, data, fullUrl, download_location):
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        image = QIcon(pixmap)
        imageBtn = QPushButton(image, "")
        imageBtn.setIconSize(pixmap.rect().size())
        imageBtn.clicked.connect(lambda: self.getFullImage(fullUrl, download_location))
        self.imageArea.widget().layout().addWidget(imageBtn)

    def updateQuery(self, text):
        self.query = text

    def handleSearchError(self, msg):
        self.infoLabel.setText(msg)
        self.infoLabel.setAlignment(Qt.AlignCenter)
        self.infoLabel.setTextFormat(Qt.RichText)
        self.widget().layout().addWidget(self.infoLabel)

    def copyToClipboard(self, data):
        clipboard = QtGui.QGuiApplication.clipboard()
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        clipboard.setPixmap(pixmap)
        self.infoLabel.setText("<h3 style='margin:3px'>Copied image to clipboard</h3>")
        
Krita.instance().addDockWidgetFactory(DockWidgetFactory("krita_image_docker", DockWidgetFactoryBase.DockRight, Krita_Image_Docker))