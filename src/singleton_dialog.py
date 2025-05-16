from PySide6.QtWidgets import QDialog

class SingletonDialog(QDialog):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is not None and (cls._instance.isVisible() or cls._instance.isHidden()):
            cls._instance.raise_()
            cls._instance.activateWindow()
            return cls._instance
        instance = super().__new__(cls)
        cls._instance = instance
        return instance

    @classmethod
    def get_instance(cls, *args, **kwargs):
        if cls._instance is not None and (cls._instance.isVisible() or cls._instance.isHidden()):
            cls._instance.raise_()
            cls._instance.activateWindow()
            return cls._instance
        cls._instance = cls(*args, **kwargs)
        cls._instance.finished.connect(lambda: setattr(cls, "_instance", None))
        return cls._instance

    @classmethod
    def show_singleton(cls, *args, **kwargs):
        dlg = cls.get_instance(*args, **kwargs)
        dlg.setModal(False)
        if not dlg.isVisible():
            dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        return dlg

    def closeEvent(self, event):
        type(self)._instance = None
        super().closeEvent(event)
