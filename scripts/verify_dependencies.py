"""Fail the build if a feature dependency cannot be imported or initialized."""
import importlib
import tkinter

for name in ('PIL.ImageTk', 'PIL.ImageGrab', 'pystray._win32',
             'i18n.loaders.json_loader', 'psycopg2.extras', 'pymysql',
             'pytesseract', 'cryptography.hazmat.primitives.asymmetric.rsa',
             'sqlite3', 'ssl', 'ctypes'):
    importlib.import_module(name)
root = tkinter.Tk()
root.withdraw()
root.update()
root.destroy()
print('Python libraries and Tcl/Tk verified.')
