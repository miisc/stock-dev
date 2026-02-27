#!/usr/bin/env python
"""
PyQt界面测试脚本
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
    from PyQt5.QtCore import Qt
    
    print("PyQt5导入成功")
    
    class TestWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("测试窗口")
            self.setGeometry(100, 100, 400, 300)
            
            # 创建中央部件
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            
            # 创建布局
            layout = QVBoxLayout(central_widget)
            
            # 添加标签
            label = QLabel("PyQt5界面测试成功！")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
    
    # 创建应用
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    
    print("PyQt5窗口已显示")
    
    # 运行应用
    sys.exit(app.exec_())
    
except ImportError as e:
    print(f"导入PyQt5失败: {e}")
    print("请确保已安装PyQt5: pip install PyQt5")
    
except Exception as e:
    print(f"运行PyQt5应用失败: {e}")
    import traceback
    traceback.print_exc()