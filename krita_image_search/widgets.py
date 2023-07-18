from PyQt5.QtWidgets import QLayout, QSizePolicy, QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QSlider, QFormLayout, QFrame, QSpinBox, QRadioButton
from PyQt5.QtCore import Qt, QRect, QSize, QMargins, QPoint, QUrl, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QPalette, QCursor, QIcon, QDesktopServices, QFontMetrics
from krita_image_search.resources import *
from krita import *

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

class PaginationWidget(QWidget):
    __currentPage = 1
    __pageOffset = 0
    __totalPages = 0
    __query = ""
    
    def __init__(self, onClickCallback, parent=None):
        super().__init__(parent)
        self.__callback = onClickCallback

        btnLayout = QHBoxLayout()
        btnLayout.setSpacing(0)
        self.setLayout(btnLayout)
        self.pageBtns = []

        self.firstBtn = QPushButton(QIcon(QPixmap(":public/double-back.png")), "")
        self.firstBtn.setFixedWidth(40)
        self.firstBtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.firstBtn.setDisabled(True)

        self.prevBtn = QPushButton(QIcon(QPixmap(":public/back.png")), "")
        self.prevBtn.setFixedWidth(40)
        self.prevBtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.prevBtn.setDisabled(True)

        self.nextBtn = QPushButton(QIcon(QPixmap(":public/next.png")), "")
        self.nextBtn.setFixedWidth(40)
        self.nextBtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.nextBtn.setDisabled(True)

        self.lastBtn = QPushButton(QIcon(QPixmap(":public/double-next.png")), "")
        self.lastBtn.setFixedWidth(40)
        self.lastBtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.lastBtn.setDisabled(True)

    def setQuery(self, query):
        self.__query = query

    def update(self, currentPage, pageOffset, totalPages):
        self.__currentPage = currentPage
        if (self.__pageOffset != pageOffset):
            self.__pageOffset = pageOffset
            self.setFixedWidth((4 + 2 * self.__pageOffset + 1) * 40)
        if (self.__totalPages != totalPages):
            self.__totalPages = totalPages
            self.__initButtons()
            
        self.__buildPaginationWidget()

    def enableButtons(self):
        if self.__currentPage > 1:
            self.firstBtn.setDisabled(False)
            self.prevBtn.setDisabled(False)

        if self.__currentPage < self.__totalPages:
            self.nextBtn.setDisabled(False)
            self.lastBtn.setDisabled(False)

        lowerBound = max(self.__currentPage - self.__pageOffset, 1) - 1
        upperBound = min(self.__currentPage + self.__pageOffset, self.__totalPages)
        for i in range(lowerBound, upperBound):
            if i + 1 != self.__currentPage:
                self.pageBtns[i].setDisabled(False)

    def __initButtons(self):
        # Init page buttons
        self.pageBtns = []
        for i in range(self.__totalPages):
            pageBtn = QPushButton(str(i + 1))
            pageBtn.setFixedWidth(40)
            pageBtn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            # Since clicked signal returns 1 argument of type bool,
            # add an argument in lambda to capture it so we can use default argument i
            pageBtn.clicked.connect(lambda _, i=i: self.__callback(self.__query, i + 1))
            pageBtn.clicked.connect(self.disableButtons)
            pageBtn.setDisabled(True)
            self.pageBtns.append(pageBtn)

        # Init other buttons
        self.firstBtn.clicked.connect(lambda: self.__callback(self.__query, 1))
        self.firstBtn.clicked.connect(self.disableButtons)
        self.prevBtn.clicked.connect(lambda: self.__callback(self.__query, self.__currentPage - 1))
        self.prevBtn.clicked.connect(self.disableButtons)
        self.nextBtn.clicked.connect(lambda: self.__callback(self.__query, self.__currentPage + 1))
        self.nextBtn.clicked.connect(self.disableButtons)
        self.lastBtn.clicked.connect(lambda: self.__callback(self.__query, self.__totalPages))
        self.lastBtn.clicked.connect(self.disableButtons)

    def __buildPaginationWidget(self):
        # Remove all buttons from layout
        for i in reversed(range(self.layout().count())):
            child = self.layout().takeAt(i)
            if child.widget():
                child.widget().setParent(None)

        # Add button to go to first page and previous page
        self.layout().addWidget(self.firstBtn)
        self.layout().addWidget(self.prevBtn)

        # Add pagination buttons
        lowerBound = max(self.__currentPage - self.__pageOffset, 1) - 1
        upperBound = min(self.__currentPage + self.__pageOffset, self.__totalPages)
        for i in range(lowerBound, upperBound):
            self.layout().addWidget(self.pageBtns[i])

        # Add button to go to next page and last page
        self.layout().addWidget(self.nextBtn)
        self.layout().addWidget(self.lastBtn)

    def disableButtons(self):
        for i in range(self.__totalPages):
            self.pageBtns[i].setDisabled(True)
            
        self.firstBtn.setDisabled(True)
        self.prevBtn.setDisabled(True)
        self.nextBtn.setDisabled(True)
        self.lastBtn.setDisabled(True)

class PropertiesWindow(QFrame):
    def __init__(self, parent, background_color, initIconSize, initPerPage, initQuality, propBtn):
        super().__init__(parent)
        self.setLayout(QFormLayout())
        self.padding = 10
        self.iconSize = initIconSize
        self.perPage = initPerPage
        self.quality = initQuality
        self.propBtn = propBtn
        
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Popup)

        # Set background color
        palette = QPalette()
        palette.setColor(QPalette.Window, background_color)
        self.setAutoFillBackground(True)
        self.setPalette(palette)

        # (Images) perPage spinbox
        self.perPageSpinbox = QSpinBox(self)
        self.perPageSpinbox.setMinimum(5)
        self.perPageSpinbox.setMaximum(30)
        self.perPageSpinbox.setValue(self.perPage)
        self.perPageSpinbox.valueChanged.connect(self.updatePerPage)

        # Quality spinbox
        self.qualitySpinbox = QSpinBox(self)
        self.qualitySpinbox.setMaximum(100)
        self.qualitySpinbox.setMinimum(0)
        self.qualitySpinbox.setValue(self.quality)
        self.qualitySpinbox.valueChanged.connect(self.updateQuality)

        # Icon Size slider
        self.iconSizeSlider = QSlider(Qt.Horizontal, self)
        self.iconSizeSlider.setMinimum(80)
        self.iconSizeSlider.setMaximum(500)
        self.iconSizeSlider.setValue(self.iconSize)
        self.iconSizeSlider.valueChanged.connect(self.updateIconSize)
        self.iconSizeSlider.sliderReleased.connect(lambda: self.saveProperties("IconSize", self.iconSize))

        self.layout().addRow("&Images Per Page:", self.perPageSpinbox)
        self.layout().addRow("&Quality:", self.qualitySpinbox)
        self.layout().addRow("&Icon Size:", self.iconSizeSlider)
        self.setLayout(QHBoxLayout())
        self.hide()
        self.propBtn.clicked.connect(self.toggleHidden)

    def alignWindow(self):
        newPos = self.parent().mapToGlobal(self.propBtn.geometry().bottomRight())
        self.move(newPos.x() - self.width(), newPos.y())

    def updateIconSize(self, value):
        self.iconSize = value

    def updatePerPage(self, value):
        self.perPage = value
        self.saveProperties("ImagesPerPage", self.perPage)

    def updateQuality(self, value):
        self.quality = value
        self.saveProperties("Quality", self.quality)

    def toggleHidden(self):
        if self.isHidden():
            self.show()
            self.alignWindow()
        else:
            self.hide()

    def saveProperties(self, name, value):
        Krita.instance().writeSetting("KritaImageSearch", name, str(value))

class ImageTile(QWidget):
    hovered = pyqtSignal(bool)

    def __init__(self, image_data, onClickCallback, iconSize, json, parent=None):
        super().__init__(parent)
        self.setLayout(QHBoxLayout())

        pixmap = QPixmap()
        pixmap.loadFromData(image_data)
        image = QIcon(pixmap)
        self.imageBtn = QPushButton(image, "", self)
        self.imageBtn.setFlat(True)
        self.imageBtn.setCursor(QCursor(Qt.PointingHandCursor))
        self.imageBtn.clicked.connect(onClickCallback)
        self.imageBtn.setLayout(QVBoxLayout())
        self.imageBtn.layout().setContentsMargins(0, 0, 0, 0)
        self.imageBtn.layout().setSpacing(0)
        self.imageBtn.setObjectName("imageBtn")
        self.imageBtn.setIconSize(QSize(iconSize, iconSize))
        self.imageBtn.setStyleSheet("QPushButton#imageBtn { border:none; padding: 0 -2px 0 -2px }")

        # Detail Mode - also add additional info from json
        self.detailSection = QWidget(self)
        self.detailSection.setLayout(QHBoxLayout())
        redirectUrl = f"{json['user']['links']['html']}?utm_source=krita_image_search&utm_medium=referral"
        userLink = ImageLink(redirectUrl, text=json['user']['name'], alignment="left", parent=self.detailSection)
        userLink.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed))

        linkIcon = Krita.instance().icon("link")
        fullImageLink = ImageLink(json['links']['html'], icon=linkIcon, parent=self.detailSection)

        self.detailSection.layout().addWidget(userLink)
        self.detailSection.layout().addWidget(fullImageLink)
        self.detailSection.layout().setAlignment(Qt.AlignLeft)
        self.detailSection.setStyleSheet("background-color: rgba(0, 0, 0, 0.5)")
        self.detailSection.layout().setContentsMargins(5, 5, 5, 5)
        self.detailSection.raise_()
        self.detailSection.hide()
        self.hovered.connect(self.displayDetails)

        self.layout().addWidget(self.imageBtn)
        self.imageBtn.layout().addStretch()
        self.imageBtn.layout().addWidget(self.detailSection)

    def updateIconSize(self, value):
        self.imageBtn.setIconSize(QSize(value, value))

    def enterEvent(self, event):
        self.hovered.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered.emit(False)
        super().leaveEvent(event)

    def displayDetails(self, isHovered):
        if isHovered:
            self.detailSection.show()
        else:
            self.detailSection.hide()

class ImageLink(QPushButton):
    def __init__(self, link, text="", alignment="center", icon=None, parent=None):
        if icon is None:
            self.isOnlyText = True
            super().__init__(text, parent)
        else:
            self.isOnlyText = False
            super().__init__(icon, text, parent)
        
        self.style = f"font-weight: bold; cursor: pointer; text-overflow: ellipsis; text-align: {alignment};"
        self.setFlat(True)
        self.fullText = text
        self.setStyleSheet(self.style)
        self.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(link, QUrl.TolerantMode)))

    def enterEvent(self, event):
        self.setStyleSheet(self.style + "text-decoration: underline")
        if not self.isOnlyText:
            self.setFlat(False)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self.style + "text-decoration: none")
        if not self.isOnlyText:
            self.setFlat(True)
        super().leaveEvent(event)

    def resizeEvent(self, event):
        metrics = QFontMetrics(self.font())
        elidedText = metrics.elidedText(self.fullText, Qt.ElideRight, self.width())
        self.setText(elidedText)
        super().resizeEvent(event)