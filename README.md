# PyQTerminal
A terminal emulator written in pyqt。

# Requirement
* paramiko  --  SSH backend
* pyte      --  VT100 support

# Usage
```python
if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        win = QTerminal()
        win.show()
        sys.exit(app.exec_())
    except:
        traceback.print_exc()
```

# Screenshot
![1](./sp.png)
