# wxgui_component.py ---
#
# Filename: wxgui_component.py
# Description:
# Author: Elric Milon
# Maintainer:
# Created: Fri Mar  6 17:47:18 2015 (+0100)

# Commentary:
#
#
#
#

# Change Log:
#
#
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Emacs.  If not, see <http://www.gnu.org/licenses/>.
#
#

# Code:
import logging
import os
import sys

import wx
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.task import LoopingCall
from twisted.internet.threads import deferToThread

from Tribler.Main.Utility.GuiDBHandler import GUIDBProducer
from Tribler.Main.vwxGUI import forceAndReturnWxThread


from Tribler.Core.Utilities.twisted_thread import reactor
from Tribler.Core.session_component import AbstractSessionComponent
from Tribler.Main.vwxGUI import forceWxThread
from Tribler.Main.vwxGUI.abcapp import ABCApp

# used by the anon tunnel tests as there's no way to mess with the Session before running the test ATM.
FORCE_ENABLE_TUNNEL_COMMUNITY = False
ALLOW_MULTIPLE = os.environ.get("TRIBLER_ALLOW_MULTIPLE", "False").lower() == "true"

logger = logging.getLogger(__name__)


class WxGUIComponent(AbstractSessionComponent):

    def __init__(self, session, params, *argv, **kwargs):
        super(WxGUIComponent, self).__init__(session, *argv, **kwargs)
        self.params = params
        self.app = None
        self.abc = None

    def start(self):
        # If we get an error in the deferToThread deferred and the startup
        # sequence hasn't finished, fail its deferred as it means the startup
        # failed.
        def on_failed_startup(failure):
            if not self.startup_d.called:
                self.startup_d.callback(failure)
            return failure

        deferToThread(self._run).addErrback(on_failed_startup).addCallback(self.shutdown_d.callback)

        return self.startup_d

    def stop(self):
        @forceAndReturnWxThread
        def do_stop():
            dbp = GUIDBProducer.getInstance()
            GUIDBProducer.delInstance()
            dbp.cancel_all_pending_tasks()
            # since ABCApp is not a wx.App anymore, we need to call OnExit explicitly.
            self.abc.OnExit()
            self.app.ExitMainLoop()
            self.app.Exit()

        return deferToThread(do_stop)

    def _run(self):
        placeholder = wx.Frame(None)
        placeholder.Hide()

        if not self.app:
            self.app = wx.PySimpleApp(redirect=False)

        def do_abcapp():
            self._init_xthreads()

            self.abc = ABCApp(self.app, self.params, session=self.session)

            wx.CallAfter(self.onStarted)

        wx.CallAfter(do_abcapp)
        self._logger.critical("PREMAINLOOOP-------------------------")
        self.app.MainLoop()

    @staticmethod
    def _init_xthreads():
        if sys.platform == 'linux2' and os.environ.get("TRIBLER_INITTHREADS", "true").lower() == "true":
            try:
                import ctypes
                x11 = ctypes.cdll.LoadLibrary('libX11.so.6')
                x11.XInitThreads()
                os.environ["TRIBLER_INITTHREADS"] = "False"
            except OSError as e:
                logger.debug("Failed to call XInitThreads '%s'", repr(e))
            except:
                logger.exception('Failed to call xInitThreads %s', repr(e))


Deferred.debug = True
#
# wxgui_component.py ends here
