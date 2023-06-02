import pytest
from krita_image_search.krita_image_docker import *
from PyQt5.QtWidgets import *
from PyQt5.QtTest import QTest

@pytest.fixture
def docker():
    Krita.instance().returnValue = QApplication()
    return Krita.instance().findChild(QDockWidget, "krita_image_search")

def test_searchImage(docker):
    searchBar = docker.widget().findChild(QLineEdit)
    searchBar.return_value = QLineEdit()
    QTest.keyClicks(searchBar, "banana")
    # assert searchBar.text == "banana"
    assert docker.query == "banana"
    #QTest.keyClick(searchBar, Qt.Key_Enter)
    



