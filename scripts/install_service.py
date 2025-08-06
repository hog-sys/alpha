import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os

class CryptoScoutService(win32serviceutil.ServiceFramework):
    _svc_name_ = "CryptoScout"
    _svc_display_name_ = "Crypto Alpha Scout Service"
    _svc_description_ = "高性能加密货币机会扫描服务"
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        
    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        
    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.main()
        
    def main(self):
        # 启动主程序
        import subprocess
        import os
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        
        subprocess.Popen(
            [sys.executable, os.path.join(parent_dir, 'crypto_scout.py')],
            cwd=parent_dir
        )
        
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(CryptoScoutService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(CryptoScoutService)