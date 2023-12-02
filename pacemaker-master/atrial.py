from PySide6.QtWidgets import QWidget, QMainWindow
from pyqtgraph import PlotWidget

from ui_atrial_ventricular import Ui_AtrialVentricular


class AtrialVentricular(QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_AtrialVentricular()
        self.ui.setupUi(self)

