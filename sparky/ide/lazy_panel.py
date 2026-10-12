"""Sidebar shells keep optional widgets and tool discovery out of startup."""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget,QVBoxLayout

class LazyPanel(QWidget):
    message=pyqtSignal(str)
    QUIET={'switch_project','apply_palette','restore_board','refresh_installed','refresh','refresh_breakpoints','stop','save_chat'}
    def __init__(self,panel_type,main):
        super().__init__()
        self._panel_type,self._main=panel_type,main
        self._widget=None; self._pending={}; self._runs=[]
        self._layout=QVBoxLayout(self); self._layout.setContentsMargins(0,0,0,0)
    def ensure(self):
        if self._widget is None:
            widget=self._panel_type(self._main)
            self._widget=widget; self._layout.addWidget(widget)
            if hasattr(widget,'message'): widget.message.connect(self.message)
            for name,(args,kwargs) in self._pending.items(): getattr(widget,name)(*args,**kwargs)
            self._pending.clear()
            for run in self._runs: widget.add_run(run)
            self._runs.clear()
            if hasattr(widget,'refresh'): widget.refresh()
        return self._widget
    def showEvent(self,event):
        self.ensure(); super().showEvent(event)
    def __getattr__(self,name):
        if name.startswith('_'): raise AttributeError(name)
        widget=self.__dict__.get('_widget')
        if widget is not None: return getattr(widget,name)
        if name=='worker': return None
        if name=='workers': return []
        if name=='folder': return None
        if name=='busy': return lambda:False
        if name in self.QUIET: return lambda *args,**kwargs:None
        if name in ('watch','set_enabled'):
            def defer(*args,**kwargs): self._pending[name]=(args,kwargs)
            return defer
        if name=='add_run':
            def remember(run): self._runs.append(run); self._runs[:]=self._runs[-10:]
            return remember
        if callable(getattr(self._panel_type,name,None)):
            return lambda *args,**kwargs:getattr(self.ensure(),name)(*args,**kwargs)
        return getattr(self.ensure(),name)
