# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'atrial_ventricular.ui'
##
## Created by: Qt User Interface Compiler version 6.6.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QLabel, QMainWindow, QMenuBar,
    QSizePolicy, QStatusBar, QWidget)

from plotwidget import PlotWidget

class Ui_AtrialVentricular(object):
    def setupUi(self, AtrialVentricular):
        if not AtrialVentricular.objectName():
            AtrialVentricular.setObjectName(u"AtrialVentricular")
        AtrialVentricular.resize(1068, 541)
        self.centralwidget = QWidget(AtrialVentricular)
        self.centralwidget.setObjectName(u"centralwidget")
        self.atrial_plots = PlotWidget(self.centralwidget)
        self.atrial_plots.setObjectName(u"atrial_plots")
        self.atrial_plots.setGeometry(QRect(220, 0, 641, 241))
        self.vent_plots = PlotWidget(self.centralwidget)
        self.vent_plots.setObjectName(u"vent_plots")
        self.vent_plots.setGeometry(QRect(220, 250, 641, 241))
        self.label = QLabel(self.centralwidget)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(40, 150, 58, 16))
        self.label_2 = QLabel(self.centralwidget)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setGeometry(QRect(40, 310, 71, 16))
        AtrialVentricular.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(AtrialVentricular)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 1068, 22))
        AtrialVentricular.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(AtrialVentricular)
        self.statusbar.setObjectName(u"statusbar")
        AtrialVentricular.setStatusBar(self.statusbar)

        self.retranslateUi(AtrialVentricular)

        QMetaObject.connectSlotsByName(AtrialVentricular)
    # setupUi

    def retranslateUi(self, AtrialVentricular):
        AtrialVentricular.setWindowTitle(QCoreApplication.translate("AtrialVentricular", u"MainWindow", None))
        self.label.setText(QCoreApplication.translate("AtrialVentricular", u"Atrial", None))
        self.label_2.setText(QCoreApplication.translate("AtrialVentricular", u"Ventricular", None))
    # retranslateUi

