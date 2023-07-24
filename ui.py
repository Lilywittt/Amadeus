# 本文件实现ui界面，主要利用pyqt库
# ui界面默认展示实时数据可视化界面，调用实时绘图线程

import sys
import time
import threading

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWebEngineWidgets import *
from PyQt5.QtWidgets import *

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from plot import *
from access_data import *

from datetime import datetime
from collections import deque


# 主窗口
class MainUIWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data Accessor App")
        self.setGeometry(600, 300, 400, 300)

        layout = QVBoxLayout()

        self.data_access_button = QPushButton("数据可视化采集")
        self.data_access_button.clicked.connect(self.open_data_access_window)
        layout.addWidget(self.data_access_button)

        self.static_plot_button = QPushButton("数据静态分析")
        self.static_plot_button.clicked.connect(self.open_data_select_window)
        layout.addWidget(self.static_plot_button)

        self.exit_app_button = QPushButton("退出程序")
        self.exit_app_button.clicked.connect(self.close)
        layout.addWidget(self.exit_app_button)

        self.setLayout(layout)

    # 打开数据实时可视化采集窗口
    def open_data_access_window(self):
        # 数据缓存队列、时间戳缓存队列的定义，并实例化一个线程同步条件
        data_buffer_queue_0 = deque(maxlen=500)
        data_buffer_queue_1 = deque(maxlen=500)
        data_buffer_queue_2 = deque(maxlen=500)
        data_buffer_queue_3 = deque(maxlen=500)
        time_buffer_queue = deque(maxlen=500)
        power_buffer_queue = deque(maxlen=500)
        data_plot_condition = threading.Condition()

        # 实例化数据采集卡
        acquisition_card = AcquisitionCard(data_queue_0=data_buffer_queue_0, data_queue_1=data_buffer_queue_1,
                                           data_queue_2=data_buffer_queue_2, data_queue_3=data_buffer_queue_3,
                                           time_queue=time_buffer_queue, power_queue=power_buffer_queue,
                                           condition=data_plot_condition)  # 数据采集卡实例化
        temp = acquisition_card.start()  # 采集数据开，一切正常则返回0，未成功连接至采集卡则返回1，其他错误信息待添加
        if temp == 1:
            QMessageBox.warning(self, "警告", "请先连接采集卡！")
            return

        self.data_access_window = DataAccessWindow(data_queue_0=data_buffer_queue_0, data_queue_1=data_buffer_queue_1,
                                                   data_queue_2=data_buffer_queue_2, data_queue_3=data_buffer_queue_3,
                                                   time_queue=time_buffer_queue, power_queue=power_buffer_queue,
                                                   condition=data_plot_condition, data_source=acquisition_card,
                                                   former_window=self)
        self.data_access_window.show()
        self.hide()

    # 打开数据选取窗口
    def open_data_select_window(self):
        self.data_select_window = DataSelectWindow(former_window=self)
        self.data_select_window.show()
        self.hide()

    def closeEvent(self, event):
        exit_dialog = ExitDialog()
        result = exit_dialog.exec()

        if result == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()


# 数据实时可视化采集窗口
class DataAccessWindow(QWidget):
    def __init__(self, data_queue_0, data_queue_1, data_queue_2, data_queue_3, time_queue, power_queue, condition, data_source, former_window):
        super().__init__()
        self.setWindowTitle("数据可视化采集")

        self.former_window = former_window

        self.data_queue_0 = data_queue_0
        self.data_queue_1 = data_queue_1
        self.data_queue_2 = data_queue_2
        self.data_queue_3 = data_queue_3
        self.time_queue = time_queue
        self.power_queue = power_queue
        self.condition = condition
        self.data_source = data_source

        self.display_plot_window()

    # 创建和布局ui界面，以及将绘图线程与ui界面相关联
    def display_plot_window(self):
        # 实例化绘图线程
        self.plot_thread = PlotThread(data_queue_0=self.data_queue_0, data_queue_1=self.data_queue_1, data_queue_2=self.data_queue_2, data_queue_3=self.data_queue_3, time_queue=self.time_queue, power_queue=self.power_queue, condition=self.condition)

        # 垂直布局器layout
        layout = QVBoxLayout()

        # figure_canvas显示绘图线程中的绘图图形，并添加到布局中
        figure_canvas = FigureCanvas(self.plot_thread.fig)
        layout.addWidget(figure_canvas)

        # 启动线程
        self.plot_thread.start()

        # 播放、暂停和退出按钮
        play_button = QPushButton("播放")
        play_button.clicked.connect(self.play_thread)
        layout.addWidget(play_button)

        pause_button = QPushButton("暂停")
        pause_button.clicked.connect(self.pause_thread)
        layout.addWidget(pause_button)

        exit_button = QPushButton("退出")
        exit_button.clicked.connect(self.close)
        layout.addWidget(exit_button)

        # 将布局应用到窗口上
        self.setLayout(layout)

    # 播放
    def play_thread(self):
        if self.plot_thread.running == False:
            self.plot_thread.running = True
            self.plot_thread.run()

    # 暂停
    def pause_thread(self):
        self.plot_thread.running = False

    # 重写关闭窗口的方法
    def closeEvent(self, event):
        exit_dialog = ExitDialog()
        result = exit_dialog.exec()

        if result == QMessageBox.Yes:
            # 先停止两个线程
            self.plot_thread.stop()
            self.data_source.stop()

            self.former_window.show()
            event.accept()

        else:
            event.ignore()


# 数据选取窗口，获取数据以用于静态绘图
class DataSelectWindow(QWidget):
    def __init__(self, former_window):
        super().__init__()
        self.setWindowTitle("数据来源选取")
        self.setGeometry(600, 300, 400, 300)

        self.former_window = former_window

        # csv模式
        self.file_selected_flag = False # 文件是否被选取
        self.csv_file_path = None

        # 数据库模式
        self.time_interval_selected_flag = False
        self.start_timestamp = None
        self.end_timestamp = None

        self.layout = QVBoxLayout()

        self.select_csv_button = QPushButton("从CSV文件读取")
        self.select_csv_button.clicked.connect(self.select_csv_file)
        self.layout.addWidget(self.select_csv_button)

        self.select_sql_button = QPushButton("从数据库中截取")
        self.select_sql_button.clicked.connect(self.select_from_sql)
        self.layout.addWidget(self.select_sql_button)

        self.exit_button = QPushButton("退出")
        self.exit_button.clicked.connect(self.close)
        self.layout.addWidget(self.exit_button)

        self.setLayout(self.layout)

    # 选定csv文件并读取数据
    def select_csv_file(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("CSV 文件 (*.csv)")
        if file_dialog.exec_():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                self.csv_file_path = selected_files[0]
                self.file_selected_flag = True
                self.close()

    # 从实时采集的数据库中截取一定时间的数据
    def select_from_sql(self):
        return

    # 打开静态绘图窗口,mode为获取数据的模式，0为从csv文件中获取，1为从数据库中获取
    def open_static_plot_window(self, mode):
        if mode == 0:
            # 上一个窗口依然为主界面
            self.static_plot_window = StaticPlotWindow(former_window=self.former_window, mode=mode,
                                                       csv_file_path=self.csv_file_path)
            self.static_plot_window.show()

        elif mode == 1:
            self.static_plot_window = StaticPlotWindow(former_window=self.former_window, mode=mode,
                                                       start_timestamp=self.start_timestamp, end_timestamp=self.end_timestamp)
            self.static_plot_window.show()


    # 重写关闭窗口的方法
    def closeEvent(self, event):
        # csv:已选取文件
        if self.file_selected_flag:
            # 打开静态绘图窗口并退出当前窗口
            self.open_static_plot_window(mode=0)
            event.accept()

        # 数据库:已选取时间间隔
        elif self.time_interval_selected_flag:
            self.open_static_plot_window(mode=1)
            event.accept()

        # 均未选取
        else:
            exit_dialog = ExitDialog()
            result = exit_dialog.exec()

            if result == QMessageBox.Yes:
                self.former_window.show()
                event.accept()

            else:
                event.ignore()


# 静态绘图窗口
class StaticPlotWindow(QWidget):
    def __init__(self, former_window, mode, csv_file_path = None, start_timestamp = None, end_timestamp = None):
        super().__init__()
        self.setWindowTitle("数据静态分析")

        self.former_window = former_window
        self.mode = mode    # mode为获取数据的模式，0为从csv文件中获取，1为从数据库中获取
        self.csv_file_path = csv_file_path

        self.setWindowTitle('Plotly Charts')
        self.setGeometry(5, 30, 1355, 730)

        self.fig0_file, self.fig1_file, self.fig2_file, self.fig3_file, self.fig_power_file = StaticPlot(csv_file_path=self.csv_file_path)

        # 创建控制按钮和返回主界面的按钮
        self.btn_exit = QPushButton('退出')
        self.btn_ai0 = QPushButton('Ai0')
        self.btn_ai1 = QPushButton('Ai1')
        self.btn_ai2 = QPushButton('Ai2')
        self.btn_ai3 = QPushButton('Ai3')

        # 将按钮放入一个组
        self.button_group = QGroupBox()
        layout_buttons = QVBoxLayout()
        layout_buttons.addWidget(self.btn_ai0)
        layout_buttons.addWidget(self.btn_ai1)
        layout_buttons.addWidget(self.btn_ai2)
        layout_buttons.addWidget(self.btn_ai3)
        layout_buttons.addWidget(self.btn_exit)
        self.button_group.setLayout(layout_buttons)

        # 创建浏览器小窗
        self.browser0 = QWebEngineView()
        self.browser1 = QWebEngineView()
        self.browser2 = QWebEngineView()
        self.browser3 = QWebEngineView()

        # 加载html文件
        self.browser0.load(QUrl.fromLocalFile(os.path.abspath(self.fig0_file)))
        self.browser1.load(QUrl.fromLocalFile(os.path.abspath(self.fig1_file)))
        self.browser2.load(QUrl.fromLocalFile(os.path.abspath(self.fig2_file)))
        self.browser3.load(QUrl.fromLocalFile(os.path.abspath(self.fig3_file)))

        # 连接按钮的点击信号和槽函数
        self.btn_exit.clicked.connect(self.close)
        self.btn_ai0.clicked.connect(self.show_ai0)
        self.btn_ai1.clicked.connect(self.show_ai1)
        self.btn_ai2.clicked.connect(self.show_ai2)
        self.btn_ai3.clicked.connect(self.show_ai3)

        # QStackedLayout便于窗口变换
        self.main_layout = QStackedLayout()
        self.init_layouts()

    # 初始化浏览器嵌入窗口
    def init_layouts(self):
        for i in range(4):
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.addWidget(getattr(self, f'browser{i}'))
            self.main_layout.addWidget(page)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.btn_ai0)
        buttons_layout.addWidget(self.btn_ai1)
        buttons_layout.addWidget(self.btn_ai2)
        buttons_layout.addWidget(self.btn_ai3)
        buttons_layout.addWidget(self.btn_exit)

        final_layout = QVBoxLayout()
        final_layout.addLayout(self.main_layout)
        final_layout.addLayout(buttons_layout)

        self.setLayout(final_layout)

    # ai0~ai3的显示切换
    def show_ai0(self):
        self.main_layout.setCurrentIndex(0)

    def show_ai1(self):
        self.main_layout.setCurrentIndex(1)

    def show_ai2(self):
        self.main_layout.setCurrentIndex(2)

    def show_ai3(self):
        self.main_layout.setCurrentIndex(3)

    # 重写关闭方法
    def closeEvent(self, event):
        exit_dialog = ExitDialog()
        result = exit_dialog.exec()
        if result == QMessageBox.Yes:
            self.former_window.show()
            event.accept()
        else:
            event.ignore()


# 退出确认弹窗
class ExitDialog(QMessageBox):
    def __init__(self):
        super().__init__()
        self.setIcon(QMessageBox.Question)
        self.setWindowTitle("退出确认")
        self.setText("是否确认退出当前界面？")
        self.setStandardButtons(QMessageBox.Yes | QMessageBox.No)